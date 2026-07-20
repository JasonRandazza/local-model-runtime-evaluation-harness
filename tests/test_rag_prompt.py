from __future__ import annotations

import unittest
from pathlib import Path

from local_model_runtime_evaluation.rag_config import RagCorpus, RagError, RagSuite
from local_model_runtime_evaluation.rag_prompt import build_oracle_prompt

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

    def test_oracle_prompt_fails_on_missing_chunk(self) -> None:
        from local_model_runtime_evaluation.rag_config import RagQuestion

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
