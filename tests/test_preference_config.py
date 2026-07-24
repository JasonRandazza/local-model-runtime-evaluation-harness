from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from local_model_runtime_evaluation.preference_config import (
    PreferenceDefaults,
    PreferenceError,
    PreferenceSuite,
    default_preference_cells,
    load_family_cell_recipes,
    load_preference_defaults,
    resolve_preference_selection,
)

ROOT = Path(__file__).resolve().parents[1]


class PreferenceConfigTests(unittest.TestCase):
    def test_suite_loads_six_prompts(self) -> None:
        suite = PreferenceSuite.load(ROOT / "suites/multi-family-preference-v1.json")
        self.assertEqual(suite.suite_id, "multi-family-preference-v1")
        self.assertEqual(suite.revision, "1")
        self.assertEqual(len(suite.prompts), 6)
        self.assertTrue(all(p.max_tokens == 2048 for p in suite.prompts))

    def test_historical_gemma_preference_suite_still_loads(self) -> None:
        suite = PreferenceSuite.load(ROOT / "suites/gemma-preference-v1.json")
        self.assertEqual(suite.suite_id, "gemma-preference-v1")
        self.assertEqual(len({p.prompt_id for p in suite.prompts}), 6)
        cells = default_preference_cells()
        self.assertEqual(len(cells), 3)
        self.assertEqual(
            cells,
            ("jang_4m__osaurus", "oq4_fp16__omlx", "optiq_4bit__optiq"),
        )

    def test_defaults_load_gemma_family(self) -> None:
        defaults = load_preference_defaults()
        self.assertEqual(defaults.family_id, "gemma-4-12b-qat")
        self.assertEqual(len(defaults.cells), 3)
        self.assertEqual(
            defaults.cells,
            ("jang_4m__osaurus", "oq4_fp16__omlx", "optiq_4bit__optiq"),
        )

    def test_resolve_family_override_ornith(self) -> None:
        selection = resolve_preference_selection(family_id="ornith-35b", cells=None)
        self.assertEqual(selection.family_id, "ornith-35b")
        self.assertEqual(
            selection.cells,
            (
                "ornith_jang_4m__osaurus",
                "ornith_oq4__omlx",
                "ornith_optiq_4bit__optiq",
            ),
        )

    def test_resolve_family_override_qwen(self) -> None:
        selection = resolve_preference_selection(family_id="qwen36-35b-a3b", cells=None)
        self.assertEqual(selection.family_id, "qwen36-35b-a3b")
        self.assertEqual(
            selection.cells,
            (
                "qwen_mxfp4__osaurus",
                "qwen_oq4__omlx",
                "qwen_optiq_4bit__optiq",
            ),
        )

    def test_resolve_missing_family_fails(self) -> None:
        empty = PreferenceDefaults(family_id="", cells=())
        with self.assertRaises(PreferenceError):
            resolve_preference_selection(family_id=None, cells=None, defaults=empty)

    def test_gemma_defaults_match_recipe(self) -> None:
        defaults = load_preference_defaults()
        recipes = load_family_cell_recipes()
        self.assertEqual(defaults.cells, recipes["gemma-4-12b-qat"])

    def test_rejects_wrong_prompt_count(self) -> None:
        bad = {
            "schema_version": "1.0.0",
            "suite_id": "gemma-preference-v1",
            "revision": "1",
            "temperature": 0,
            "streaming": True,
            "prompts": [
                {
                    "prompt_id": f"prompt-{index}",
                    "prompt": "test prompt",
                    "max_tokens": 256,
                }
                for index in range(5)
            ],
        }
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as handle:
            json.dump(bad, handle)
            path = Path(handle.name)
        try:
            with self.assertRaises(PreferenceError):
                PreferenceSuite.load(path)
        finally:
            path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
