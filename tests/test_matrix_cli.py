from __future__ import annotations

import io
import json
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from local_model_runtime_evaluation.matrix_runner import main


class MatrixCliTest(unittest.TestCase):
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
        self.assertEqual(payload["cell_count"], 9)
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
        self.assertEqual(payload["cell_count"], 9)
        missing = payload["artifact_missing"]
        self.assertIsInstance(missing, list)
        for path in missing:
            self.assertFalse(Path(path).exists(), path)


if __name__ == "__main__":
    unittest.main()
