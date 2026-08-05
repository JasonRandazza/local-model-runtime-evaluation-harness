"""Tests for Approach 3 free-form recipes (Gate A / fake-only)."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from local_model_runtime_evaluation.approach3 import (
    Approach3Error,
    FreeFormRecipe,
    dry_config,
    resolve_recipe_path,
)
from local_model_runtime_evaluation.approach3_cli import main as _approach3_main
from local_model_runtime_evaluation.matrix_config import REPOSITORY_ROOT
from tests.artifact_profile_fixtures import synthetic_artifact_roots

ROOT = REPOSITORY_ROOT
NATIVE = ROOT / "config/approach3/gemma-freeform-native-triple-v1.json"
ROOTS = synthetic_artifact_roots()


def approach3_main(argv: list[str]) -> int:
    return _approach3_main(argv, artifact_roots=ROOTS)


class Approach3RecipeTests(unittest.TestCase):
    def test_load_native_triple_recipe(self) -> None:
        recipe = FreeFormRecipe.load(NATIVE)
        self.assertEqual(recipe.recipe_id, "gemma-freeform-native-triple-v1")
        self.assertFalse(recipe.require_native_server)
        self.assertEqual(len(recipe.cell_ids), 3)

    def test_dry_config_ok(self) -> None:
        report = dry_config(NATIVE, artifact_roots=ROOTS)
        self.assertTrue(report["ok"])
        self.assertEqual(report["status"], "DRY_CONFIG_OK")
        self.assertEqual(report["live_collect"], "UNTESTED")
        self.assertEqual(report["servers"], ["osaurus", "omlx", "optiq"])

    def test_duplicate_cell_ids_fail(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.json"
            path.write_text(
                json.dumps(
                    {
                        "schema_version": "1.0.0",
                        "recipe_id": "bad",
                        "revision": "1",
                        "family_id": "gemma-4-12b-qat",
                        "require_native_server": False,
                        "cell_ids": ["jang_4m__osaurus", "jang_4m__osaurus"],
                        "suites": ["preference"],
                        "notes": "x",
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaises(Approach3Error) as ctx:
                FreeFormRecipe.load(path)
            self.assertEqual(ctx.exception.code, "duplicate_cells")

    def test_resolve_by_stem(self) -> None:
        path = resolve_recipe_path("gemma-freeform-native-triple-v1")
        self.assertEqual(path, NATIVE.resolve())


class Approach3CliTests(unittest.TestCase):
    def test_cli_dry_config(self) -> None:
        code = approach3_main(["dry-config", "gemma-freeform-native-triple-v1"])
        self.assertEqual(code, 0)

    def test_cli_collect_preference_refuses_without_flag(self) -> None:
        code = approach3_main(
            ["collect-preference", "gemma-freeform-native-triple-v1"]
        )
        self.assertEqual(code, 1)

    def test_cli_collect_preference_passes_recipe_native_policy(self) -> None:
        from unittest.mock import patch
        from pathlib import Path

        with patch(
            "local_model_runtime_evaluation.approach3_cli.run_collect",
            return_value=Path("/tmp/fake-preference-run"),
        ) as mock_collect:
            code = approach3_main(
                [
                    "collect-preference",
                    "gemma-freeform-native-triple-v1",
                    "--i-understand-live",
                ]
            )
        self.assertEqual(code, 0)
        self.assertFalse(mock_collect.call_args.kwargs["require_native_server"])

    def test_cli_collect_rag_refuses_without_flag(self) -> None:
        code = approach3_main(
            ["collect-rag", "gemma-freeform-native-triple-v1", "--mode", "oracle"]
        )
        self.assertEqual(code, 1)

    def test_cli_collect_overhead_refuses_without_flag(self) -> None:
        code = approach3_main(
            ["collect-overhead", "gemma-freeform-native-triple-v1"]
        )
        self.assertEqual(code, 1)

    def test_cli_collect_overhead_passes_pair_ids(self) -> None:
        from unittest.mock import patch
        from pathlib import Path

        with patch(
            "local_model_runtime_evaluation.approach3_cli.run_overhead",
            return_value=Path("/tmp/fake-overhead-run"),
        ) as mock_run:
            code = approach3_main(
                [
                    "collect-overhead",
                    "gemma-freeform-native-triple-v1",
                    "--i-understand-live",
                ]
            )
        self.assertEqual(code, 0)
        pair_ids = mock_run.call_args.args[0]
        self.assertIn("oq4_fp16", pair_ids)
        self.assertIn("optiq_4bit", pair_ids)

    def test_cli_collect_rag_passes_mode_and_require_native(self) -> None:
        from unittest.mock import patch
        from pathlib import Path

        with patch(
            "local_model_runtime_evaluation.approach3_cli.run_rag_collect",
            return_value=Path("/tmp/fake-rag-run"),
        ) as mock_collect:
            code = approach3_main(
                [
                    "collect-rag",
                    "gemma-freeform-native-triple-v1",
                    "--mode",
                    "keyword",
                    "--i-understand-live",
                ]
            )
        self.assertEqual(code, 0)
        self.assertEqual(mock_collect.call_args.kwargs["mode"], "keyword")
        self.assertFalse(mock_collect.call_args.kwargs["require_native_server"])


if __name__ == "__main__":
    unittest.main()
