from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from local_model_runtime_evaluation.rag_config import RagSuite
from local_model_runtime_evaluation.rag_score import (
    score_answer,
    score_retrieval,
    score_run,
)

ROOT = Path(__file__).resolve().parents[1]


class RagScoreTests(unittest.TestCase):
    def test_score_full_partial_zero_and_case(self) -> None:
        full = score_answer(
            "... OSAURUS_PORT=1337 ... OMLX_PORT=8100 ... OPTIQ_PORT=8080",
            ("OSAURUS_PORT=1337", "OMLX_PORT=8100", "OPTIQ_PORT=8080"),
            success=True,
        )
        self.assertEqual(full["hits"], 3)
        self.assertEqual(full["total"], 3)
        self.assertEqual(full["hit_rate"], 1.0)
        self.assertEqual(full["missing_facts"], [])

        partial = score_answer(
            "OSAURUS_PORT=1337",
            ("OSAURUS_PORT=1337", "OMLX_PORT=8100"),
            success=True,
        )
        self.assertEqual(partial["hits"], 1)
        self.assertAlmostEqual(partial["hit_rate"], 0.5)
        self.assertEqual(partial["missing_facts"], ["OMLX_PORT=8100"])

        self.assertEqual(
            score_answer("osaurus_port=1337", ("OSAURUS_PORT=1337",), success=True)["hit_rate"],
            0.0,
        )
        failed = score_answer(None, ("X",), success=False)
        self.assertEqual(failed["hit_rate"], 0.0)
        self.assertEqual(failed["missing_facts"], ["X"])

    def test_score_retrieval_metrics(self) -> None:
        result = score_retrieval(("syn-ports", "syn-auth"), ("syn-ports",))
        self.assertAlmostEqual(result["recall"], 1.0)
        self.assertAlmostEqual(result["precision"], 0.5)
        self.assertEqual(result["hits"], 1)
        self.assertEqual(result["gold_total"], 1)
        self.assertEqual(result["retrieved_total"], 2)

    def test_score_run_keyword_includes_retrieval(self) -> None:
        suite = RagSuite.load(ROOT / "suites/gemma-rag-oracle-v1.json")
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            answers_dir = run_dir / "answers"
            answers_dir.mkdir()
            (run_dir / "raw.json").write_text(
                json.dumps({"mode": "keyword", "top_k": 2}, indent=2) + "\n",
                encoding="utf-8",
            )
            payload = {
                "cell_id": "jang_4m__osaurus",
                "model_id": "gemma-test",
                "answers": [
                    {
                        "prompt_id": question.prompt_id,
                        "cell_id": "jang_4m__osaurus",
                        "model_id": "gemma-test",
                        "content": " ".join(question.required_facts),
                        "success": True,
                        "error": None,
                        "total_seconds": 1.0,
                        "ttft_seconds": 0.1,
                        "retrieved_chunk_ids": [
                            question.gold_chunk_ids[0],
                            "syn-auth",
                        ],
                    }
                    for question in suite.questions
                ],
            }
            (answers_dir / "jang_4m__osaurus.json").write_text(
                json.dumps(payload, indent=2) + "\n",
                encoding="utf-8",
            )

            score_run(run_dir, suite)
            scores = json.loads((run_dir / "scores.json").read_text(encoding="utf-8"))
            self.assertEqual(scores["mode"], "keyword")
            self.assertEqual(scores["top_k"], 2)
            cell = scores["cells"]["jang_4m__osaurus"]
            self.assertAlmostEqual(cell["mean_recall"], 1.0)
            self.assertAlmostEqual(cell["mean_precision"], 0.5)
            prompt = cell["prompts"]["ports-lookup"]
            self.assertAlmostEqual(prompt["retrieval"]["recall"], 1.0)
            self.assertAlmostEqual(prompt["retrieval"]["precision"], 0.5)

            report = (run_dir / "report.md").read_text(encoding="utf-8")
            self.assertIn("keyword", report.lower())
            self.assertIn("mean recall", report.lower())

    def test_score_run_oracle_without_mode_in_raw(self) -> None:
        suite = RagSuite.load(ROOT / "suites/gemma-rag-oracle-v1.json")
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            answers_dir = run_dir / "answers"
            answers_dir.mkdir()
            payload = {
                "cell_id": "jang_4m__osaurus",
                "model_id": "gemma-test",
                "answers": [
                    {
                        "prompt_id": question.prompt_id,
                        "cell_id": "jang_4m__osaurus",
                        "model_id": "gemma-test",
                        "content": " ".join(question.required_facts),
                        "success": True,
                        "error": None,
                        "total_seconds": 1.0,
                        "ttft_seconds": 0.1,
                    }
                    for question in suite.questions
                ],
            }
            (answers_dir / "jang_4m__osaurus.json").write_text(
                json.dumps(payload, indent=2) + "\n",
                encoding="utf-8",
            )

            score_run(run_dir, suite)
            scores = json.loads((run_dir / "scores.json").read_text(encoding="utf-8"))
            self.assertEqual(scores["mode"], "oracle")
            cell = scores["cells"]["jang_4m__osaurus"]
            self.assertNotIn("mean_recall", cell)
            self.assertNotIn("retrieval", cell["prompts"]["ports-lookup"])

    def test_score_run_writes_report(self) -> None:
        suite = RagSuite.load(ROOT / "suites/gemma-rag-oracle-v1.json")
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            answers_dir = run_dir / "answers"
            answers_dir.mkdir()
            payload = {
                "cell_id": "jang_4m__osaurus",
                "model_id": "gemma-test",
                "answers": [
                    {
                        "prompt_id": question.prompt_id,
                        "cell_id": "jang_4m__osaurus",
                        "model_id": "gemma-test",
                        "content": " ".join(question.required_facts),
                        "success": True,
                        "error": None,
                        "total_seconds": 1.0,
                        "ttft_seconds": 0.1,
                    }
                    for question in suite.questions
                ],
            }
            (answers_dir / "jang_4m__osaurus.json").write_text(
                json.dumps(payload, indent=2) + "\n",
                encoding="utf-8",
            )

            result = score_run(run_dir, suite)
            self.assertEqual(result, run_dir)
            self.assertTrue((run_dir / "scores.json").is_file())
            self.assertTrue((run_dir / "report.md").is_file())

            scores = json.loads((run_dir / "scores.json").read_text(encoding="utf-8"))
            self.assertEqual(scores["cells"]["jang_4m__osaurus"]["mean_hit_rate"], 1.0)

            report = (run_dir / "report.md").read_text(encoding="utf-8")
            self.assertIn("jang_4m__osaurus", report)
            self.assertIn("1.000", report)


if __name__ == "__main__":
    unittest.main()
