from __future__ import annotations

import io
import json
import sys
import unittest
from contextlib import redirect_stdout

from local_model_runtime_evaluation.overhead_cli import main
from local_model_runtime_evaluation.overhead_config import DEFAULT_PAIR_IDS

ROOT = __import__("pathlib").Path(__file__).resolve().parents[1]


class OverheadCliTests(unittest.TestCase):
    def test_dry_config_ok(self) -> None:
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = main(["run", "--dry-config"])
        self.assertEqual(code, 0)
        payload = json.loads(buffer.getvalue())
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["mode"], "screen")
        self.assertEqual(payload["suite_id"], "gemma-matrix-v1")
        pair_ids = {pair["pair_id"] for pair in payload["pairs"]}
        self.assertEqual(pair_ids, set(DEFAULT_PAIR_IDS))
        for pair in payload["pairs"]:
            self.assertIn("direct_cell_id", pair)
            self.assertIn("routed_cell_id", pair)
            self.assertIn("routed_model_id", pair)
            self.assertIn("routed_base_url", pair)
            self.assertEqual(pair["routed_base_url"], "http://127.0.0.1:1337/v1")
            self.assertTrue(pair["routed_cell_id"].endswith("__osaurus"))

    def test_dry_config_top_level(self) -> None:
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = main(["--dry-config"])
        self.assertEqual(code, 0)
        payload = json.loads(buffer.getvalue())
        self.assertTrue(payload["ok"])

    def test_report_missing_run_fails(self) -> None:
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = main(["report", "--run", "/nonexistent"])
        self.assertNotEqual(code, 0)
        payload = json.loads(buffer.getvalue())
        self.assertFalse(payload["ok"])


if __name__ == "__main__":
    raise SystemExit(unittest.main())
