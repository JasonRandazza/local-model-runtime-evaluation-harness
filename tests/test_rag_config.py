from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from local_model_runtime_evaluation.rag_config import (
    DEFAULT_RAG_CELLS,
    RagCorpus,
    RagError,
    RagSuite,
)

ROOT = Path(__file__).resolve().parents[1]


class RagConfigTests(unittest.TestCase):
    def test_corpus_loads_six_chunks(self) -> None:
        corpus = RagCorpus.load(ROOT / "corpora/rag-oracle-v1")
        self.assertEqual(corpus.corpus_id, "rag-oracle-v1")
        self.assertEqual(len(corpus.chunks), 6)
        self.assertIn("OSAURUS_PORT=1337", corpus.get("syn-ports").text)

    def test_suite_loads_six_questions(self) -> None:
        suite = RagSuite.load(ROOT / "suites/gemma-rag-oracle-v1.json")
        self.assertEqual(suite.suite_id, "gemma-rag-oracle-v1")
        self.assertEqual(suite.revision, "1")
        self.assertEqual(suite.corpus_id, "rag-oracle-v1")
        self.assertEqual(len(suite.questions), 6)
        self.assertEqual(
            DEFAULT_RAG_CELLS,
            ("jang_4m__osaurus", "oq4_fp16__omlx", "optiq_4bit__optiq"),
        )

    def test_suite_rejects_wrong_question_count(self) -> None:
        bad = {
            "schema_version": "1.0.0",
            "suite_id": "gemma-rag-oracle-v1",
            "revision": "1",
            "temperature": 0,
            "streaming": True,
            "corpus_id": "rag-oracle-v1",
            "questions": [
                {
                    "prompt_id": f"question-{index}",
                    "question": "test question",
                    "gold_chunk_ids": ["syn-ports"],
                    "required_facts": ["OSAURUS_PORT=1337"],
                    "max_tokens": 256,
                }
                for index in range(5)
            ],
        }
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as handle:
            json.dump(bad, handle)
            path = Path(handle.name)
        try:
            with self.assertRaises(RagError):
                RagSuite.load(path)
        finally:
            path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
