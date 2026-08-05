from __future__ import annotations

import io
import json
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from local_model_runtime_evaluation.artifact_profile import load_artifact_roots
from local_model_runtime_evaluation.matrix_runner import main as _main
from tests.artifact_profile_fixtures import synthetic_artifact_roots, temporary_machine_profile

ROOTS = synthetic_artifact_roots()


def main(argv: list[str], *, artifact_roots=None) -> int:
    return _main(argv, artifact_roots=artifact_roots or ROOTS)


class MatrixCliTest(unittest.TestCase):
    def test_dry_config_uses_injected_roots_for_exact_artifact_checks(self) -> None:
        with temporary_machine_profile() as (profile, paths):
            existing = (
                paths["local_models"] / "gemma-4-12B-it-qat-JANG_4M"
            )
            existing.mkdir()
            roots = load_artifact_roots(profile)
            buffer = io.StringIO()
            with redirect_stdout(buffer):
                code = main(
                    [
                        "--dry-config",
                        "--campaign",
                        "config/matrix/gemma-4-12b-qat-campaign.json",
                    ],
                    artifact_roots=roots,
                )

        self.assertEqual(code, 0)
        payload = json.loads(buffer.getvalue())
        self.assertNotIn(str(existing.resolve()), payload["artifact_missing"])
        self.assertEqual(len(payload["artifact_missing"]), 2)
        self.assertTrue(
            all("{LMRE_ROOT:" not in path for path in payload["artifact_missing"])
        )

    def test_dry_config_prints_ok(self) -> None:
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = main(["--dry-config", "--campaign", "config/matrix/gemma-4-12b-qat-campaign.json"])
        self.assertEqual(code, 0)
        payload = json.loads(buffer.getvalue())
        self.assertTrue(payload["ok"])

    def test_dry_config_includes_family_id(self) -> None:
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = main(["--dry-config", "--campaign", "config/matrix/gemma-4-12b-qat-campaign.json"])
        self.assertEqual(code, 0)
        payload = json.loads(buffer.getvalue())
        self.assertEqual(payload["family_id"], "gemma-4-12b-qat")
        self.assertIn("artifact_missing", payload)
        self.assertIsInstance(payload["artifact_missing"], list)

    def test_ornith_dry_config_reports_missing_artifacts(self) -> None:
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = main(["--dry-config", "--campaign", "config/matrix/ornith-35b-campaign.json"])
        self.assertEqual(code, 0)
        payload = json.loads(buffer.getvalue())
        self.assertEqual(payload["family_id"], "ornith-35b")
        self.assertEqual(payload["cell_count"], 3)
        missing = payload["artifact_missing"]
        self.assertIsInstance(missing, list)
        for path in missing:
            self.assertFalse(Path(path).exists(), path)

    def test_qwen_dry_config_reports_family_and_missing(self) -> None:
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = main(
                ["--dry-config", "--campaign", "config/matrix/qwen36-35b-a3b-campaign.json"]
            )
        self.assertEqual(code, 0)
        payload = json.loads(buffer.getvalue())
        self.assertEqual(payload["family_id"], "qwen36-35b-a3b")
        self.assertEqual(payload["cell_count"], 3)
        missing = payload["artifact_missing"]
        self.assertIsInstance(missing, list)
        for path in missing:
            self.assertFalse(Path(path).exists(), path)


if __name__ == "__main__":
    unittest.main()
