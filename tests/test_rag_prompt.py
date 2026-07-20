from __future__ import annotations

import unittest
from pathlib import Path

from local_model_runtime_evaluation.rag_config import RagCorpus, RagError, RagSuite
from local_model_runtime_evaluation.rag_config import RagQuestion
from local_model_runtime_evaluation.rag_prompt import (
    build_context_prompt,
    build_keyword_prompt,
    build_oracle_prompt,
)

ROOT = Path(__file__).resolve().parents[1]


class RagPromptTests(unittest.TestCase):
    def setUp(self) -> None:
        self.corpus = RagCorpus.load(ROOT / "corpora/rag-oracle-v1")
        self.suite = RagSuite.load(ROOT / "suites/gemma-rag-oracle-v1.json")

    def test_oracle_prompt_includes_gold_excludes_other(self) -> None:
        question = next(q for q in self.suite.questions if q.prompt_id == "ports-lookup")
        prompt = build_oracle_prompt(question, self.corpus)
        self.assertIn("Use only the provided context", prompt)
        self.assertIn("syn-ports", prompt)
        self.assertIn("OSAURUS_PORT=1337", prompt)
        self.assertNotIn("KEYCHAIN_SERVICE", prompt)

    def test_oracle_prompt_appends_question(self) -> None:
        question = self.suite.questions[0]
        prompt = build_oracle_prompt(question, self.corpus)
        self.assertIn(question.question, prompt)

    def test_keyword_prompt_uses_retrieved_not_necessarily_gold(self) -> None:
        question = RagQuestion(
            "ports-test",
            "What TCP ports do Osaurus oMLX OptiQ use OSAURUS_PORT OMLX_PORT OPTIQ_PORT",
            ("syn-auth",),
            ("X",),
            256,
        )
        prompt, retrieved = build_keyword_prompt(question, self.corpus, k=1)
        self.assertEqual(retrieved, ("syn-ports",))
        self.assertIn("OSAURUS_PORT=1337", prompt)
        self.assertNotIn("KEYCHAIN_SERVICE", prompt)

    def test_oracle_prompt_delegates_to_context_prompt(self) -> None:
        question = self.suite.questions[0]
        expected = build_context_prompt(question.gold_chunk_ids, question, self.corpus)
        self.assertEqual(build_oracle_prompt(question, self.corpus), expected)

    def test_oracle_prompt_fails_on_missing_chunk(self) -> None:
        bad = RagQuestion(
            "bad",
            "What?",
            ("missing-chunk",),
            ("X",),
            256,
        )
        with self.assertRaises(RagError):
            build_oracle_prompt(bad, self.corpus)


if __name__ == "__main__":
    unittest.main()
