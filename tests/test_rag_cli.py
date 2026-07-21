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

    def test_collect_dry_config_includes_family_id(self) -> None:
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = main(["collect", "--dry-config"])
        self.assertEqual(code, 0)
        payload = json.loads(buffer.getvalue())
        self.assertEqual(payload["family_id"], "gemma-4-12b-qat")
        self.assertEqual(len(payload["cells"]), 4)
        self.assertIn("optiq_4bit__omlx", payload["cells"])

    def test_collect_dry_config_family_ornith(self) -> None:
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = main(["collect", "--dry-config", "--family", "ornith-35b"])
        self.assertEqual(code, 0)
        payload = json.loads(buffer.getvalue())
        self.assertEqual(payload["family_id"], "ornith-35b")
        self.assertEqual(len(payload["cells"]), 4)
        self.assertTrue(all(c.startswith("ornith_") for c in payload["cells"]))

    def test_collect_dry_config_family_qwen(self) -> None:
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = main(["collect", "--dry-config", "--family", "qwen36-35b-a3b"])
        self.assertEqual(code, 0)
        payload = json.loads(buffer.getvalue())
        self.assertEqual(payload["family_id"], "qwen36-35b-a3b")
        self.assertEqual(
            payload["cells"],
            [
                "qwen_mxfp4__osaurus",
                "qwen_oq4__omlx",
                "qwen_optiq_4bit__omlx",
                "qwen_optiq_4bit__optiq",
            ],
        )

    def test_collect_rejects_ornith_cell_under_gemma_family(self) -> None:
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = main([
                "collect", "--dry-config",
                "--family", "gemma-4-12b-qat",
                "--cells", "ornith_jang_4m__omlx",
            ])
        self.assertNotEqual(code, 0)

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
