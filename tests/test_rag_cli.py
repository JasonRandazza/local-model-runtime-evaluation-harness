from __future__ import annotations

import io
import json
import unittest
from contextlib import redirect_stdout

from local_model_runtime_evaluation.rag_cli import main
from local_model_runtime_evaluation.rag_config import DEFAULT_RAG_CELLS


class RagCliTests(unittest.TestCase):
    def test_collect_dry_config_ok(self) -> None:
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = main(["collect", "--dry-config"])
        self.assertEqual(code, 0)
        payload = json.loads(buffer.getvalue())
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["cells"], list(DEFAULT_RAG_CELLS))
        self.assertEqual(payload["questions"], 6)
        self.assertEqual(payload["corpus_id"], "rag-oracle-v1")
        self.assertEqual(payload["mode"], "oracle")
        self.assertEqual(payload["top_k"], 2)

    def test_cli_keyword_dry_config(self) -> None:
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = main(["collect", "--mode", "keyword", "--dry-config"])
        self.assertEqual(code, 0)
        payload = json.loads(buffer.getvalue())
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["mode"], "keyword")
        self.assertEqual(payload["top_k"], 2)

    def test_score_missing_run_fails(self) -> None:
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = main(["score", "--run", "/nonexistent/rag-run"])
        self.assertNotEqual(code, 0)
        payload = json.loads(buffer.getvalue())
        self.assertFalse(payload["ok"])


if __name__ == "__main__":
    unittest.main()
