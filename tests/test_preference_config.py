from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from local_model_runtime_evaluation.preference_config import (
    DEFAULT_PREFERENCE_CELLS,
    PreferenceError,
    PreferenceSuite,
)

ROOT = Path(__file__).resolve().parents[1]


class PreferenceConfigTests(unittest.TestCase):
    def test_suite_loads_six_prompts(self) -> None:
        suite = PreferenceSuite.load(ROOT / "suites/gemma-preference-v1.json")
        self.assertEqual(suite.suite_id, "gemma-preference-v1")
        self.assertEqual(suite.revision, "1")
        self.assertEqual(len(suite.prompts), 6)
        self.assertEqual(len({p.prompt_id for p in suite.prompts}), 6)
        self.assertEqual(
            DEFAULT_PREFERENCE_CELLS,
            ("jang_4m__osaurus", "oq4_fp16__omlx", "optiq_4bit__optiq"),
        )

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
