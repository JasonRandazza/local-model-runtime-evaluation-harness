from __future__ import annotations

import io
import json
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from local_model_runtime_evaluation.preference_config import DEFAULT_PREFERENCE_CELLS
from local_model_runtime_evaluation.preference_cli import main
from local_model_runtime_evaluation.preference_judge import DEFAULT_JUDGE_CELL

ROOT = Path(__file__).resolve().parents[1]


class PreferenceCliTests(unittest.TestCase):
    def test_collect_dry_config_ok(self) -> None:
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = main(["collect", "--dry-config"])
        self.assertEqual(code, 0)
        payload = json.loads(buffer.getvalue())
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["cells"], list(DEFAULT_PREFERENCE_CELLS))
        self.assertEqual(payload["prompts"], 6)
        self.assertEqual(payload["suite_id"], "multi-family-preference-v1")

    def test_collect_dry_config_includes_family_id(self) -> None:
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = main(["collect", "--dry-config"])
        self.assertEqual(code, 0)
        payload = json.loads(buffer.getvalue())
        self.assertEqual(payload["family_id"], "gemma-4-12b-qat")
        self.assertEqual(len(payload["cells"]), 3)
        self.assertEqual(
            payload["cells"],
            ["jang_4m__osaurus", "oq4_fp16__omlx", "optiq_4bit__optiq"],
        )

    def test_collect_dry_config_family_ornith(self) -> None:
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = main(["collect", "--dry-config", "--family", "ornith-35b"])
        self.assertEqual(code, 0)
        payload = json.loads(buffer.getvalue())
        self.assertEqual(payload["family_id"], "ornith-35b")
        self.assertEqual(
            payload["cells"],
            [
                "ornith_jang_4m__osaurus",
                "ornith_oq4__omlx",
                "ornith_optiq_4bit__optiq",
            ],
        )

    def test_collect_dry_config_family_qwen(self) -> None:
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = main(["collect", "--dry-config", "--family", "qwen36-35b-a3b"])
        self.assertEqual(code, 0)
        payload = json.loads(buffer.getvalue())
        self.assertEqual(payload["family_id"], "qwen36-35b-a3b")
        self.assertEqual(len(payload["cells"]), 3)
        self.assertEqual(
            payload["cells"],
            [
                "qwen_mxfp4__osaurus",
                "qwen_oq4__omlx",
                "qwen_optiq_4bit__optiq",
            ],
        )

    def test_collect_rejects_ornith_cell_under_gemma_family(self) -> None:
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = main([
                "collect", "--dry-config",
                "--family", "gemma-4-12b-qat",
                "--cells", "ornith_jang_4m__osaurus",
            ])
        self.assertNotEqual(code, 0)

    def test_review_missing_run_dir_nonzero(self) -> None:
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = main(["review", "--run", "/nonexistent/preference-run"])
        self.assertNotEqual(code, 0)
        payload = json.loads(buffer.getvalue())
        self.assertFalse(payload["ok"])

    def test_tally_missing_run_dir_nonzero(self) -> None:
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = main(["tally", "--run", "/nonexistent/preference-run"])
        self.assertNotEqual(code, 0)
        payload = json.loads(buffer.getvalue())
        self.assertFalse(payload["ok"])

    def test_review_and_tally_roundtrip_fakes(self) -> None:
        from local_model_runtime_evaluation.preference_config import PreferenceSuite

        suite = PreferenceSuite.load(ROOT / "suites/multi-family-preference-v1.json")
        with TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "gemma-4-12b-qat-preference-test"
            answers_dir = run_dir / "answers"
            answers_dir.mkdir(parents=True)
            for index, cell_id in enumerate(DEFAULT_PREFERENCE_CELLS):
                payload = {
                    "cell_id": cell_id,
                    "model_id": f"model-{index}",
                    "answers": [
                        {
                            "prompt_id": prompt.prompt_id,
                            "cell_id": cell_id,
                            "model_id": f"model-{index}",
                            "content": f"Answer {prompt.prompt_id} v{index}.",
                            "success": True,
                            "error": None,
                            "total_seconds": 1.0,
                            "ttft_seconds": 0.1,
                        }
                        for prompt in suite.prompts
                    ],
                }
                (answers_dir / f"{cell_id}.json").write_text(
                    json.dumps(payload, indent=2) + "\n",
                    encoding="utf-8",
                )
            (run_dir / "raw.json").write_text(
                json.dumps(
                    {
                        "suite_id": suite.suite_id,
                        "cell_ids": list(DEFAULT_PREFERENCE_CELLS),
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )

            buffer = io.StringIO()
            with redirect_stdout(buffer):
                review_code = main(["review", "--run", str(run_dir), "--seed", "0"])
            self.assertEqual(review_code, 0)
            self.assertTrue((run_dir / "review.md").is_file())
            self.assertTrue((run_dir / "judgments.json").is_file())

            judgments_path = run_dir / "judgments.json"
            judgments_payload = json.loads(judgments_path.read_text(encoding="utf-8"))
            for item in judgments_payload["judgments"]:
                item["winner"] = "A"

            judgments_path.write_text(
                json.dumps(judgments_payload, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )

            buffer = io.StringIO()
            with redirect_stdout(buffer):
                tally_code = main(["tally", "--run", str(run_dir)])
            self.assertEqual(tally_code, 0)
            self.assertTrue((run_dir / "report.md").is_file())
            tally_payload = json.loads(buffer.getvalue())
            self.assertTrue(tally_payload["ok"])
            self.assertEqual(tally_payload["run_dir"], str(run_dir))

    def test_judge_dry_config_ok(self) -> None:
        with TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "preference-judge-dry"
            run_dir.mkdir()
            (run_dir / "answers").mkdir()
            (run_dir / "pairs.json").write_text(
                json.dumps(
                    {
                        "pairs": [
                            {
                                "pair_id": "p1",
                                "prompt_id": "x",
                                "cell_a": "c1",
                                "cell_b": "c2",
                            },
                            {
                                "pair_id": "p2",
                                "prompt_id": "x",
                                "cell_a": "c1",
                                "cell_b": "c2",
                            },
                        ],
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            buffer = io.StringIO()
            with redirect_stdout(buffer):
                code = main(["judge", "--run", str(run_dir), "--dry-config"])
            self.assertEqual(code, 0)
            payload = json.loads(buffer.getvalue())
            self.assertTrue(payload["ok"])
            self.assertEqual(payload["judge_cell"], DEFAULT_JUDGE_CELL)
            self.assertEqual(payload["run_dir"], str(run_dir))
            self.assertEqual(payload["pairs"], 2)

    def test_judge_dry_config_judge_cell_override(self) -> None:
        with TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "preference-judge-dry"
            run_dir.mkdir()
            (run_dir / "answers").mkdir()
            (run_dir / "pairs.json").write_text(
                json.dumps(
                    {
                        "pairs": [
                            {
                                "pair_id": "p1",
                                "prompt_id": "x",
                                "cell_a": "c1",
                                "cell_b": "c2",
                            },
                        ],
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            buffer = io.StringIO()
            with redirect_stdout(buffer):
                code = main(
                    ["judge", "--run", str(run_dir), "--dry-config", "--judge-cell", "oq4_fp16__omlx"],
                )
            self.assertEqual(code, 0)
            payload = json.loads(buffer.getvalue())
            self.assertTrue(payload["ok"])
            self.assertEqual(payload["judge_cell"], "oq4_fp16__omlx")

    def test_judge_dry_config_rejects_empty_pairs(self) -> None:
        with TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "preference-judge-dry"
            run_dir.mkdir()
            (run_dir / "answers").mkdir()
            (run_dir / "pairs.json").write_text(
                json.dumps({"pairs": []}, indent=2) + "\n",
                encoding="utf-8",
            )
            buffer = io.StringIO()
            with redirect_stdout(buffer):
                code = main(["judge", "--run", str(run_dir), "--dry-config"])
            self.assertEqual(code, 1)
            payload = json.loads(buffer.getvalue())
            self.assertFalse(payload["ok"])

    def test_judge_dry_config_rejects_invalid_pair(self) -> None:
        with TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "preference-judge-dry"
            run_dir.mkdir()
            (run_dir / "answers").mkdir()
            (run_dir / "pairs.json").write_text(
                json.dumps({"pairs": [{"pair_id": "p1"}]}, indent=2) + "\n",
                encoding="utf-8",
            )
            buffer = io.StringIO()
            with redirect_stdout(buffer):
                code = main(["judge", "--run", str(run_dir), "--dry-config"])
            self.assertEqual(code, 1)
            payload = json.loads(buffer.getvalue())
            self.assertFalse(payload["ok"])

    def test_judge_missing_run_fails(self) -> None:
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = main(["judge", "--run", "/tmp/lmre-preference-missing-run-xyz"])
        self.assertEqual(code, 1)
        payload = json.loads(buffer.getvalue())
        self.assertFalse(payload["ok"])

    def test_judge_live_delegates_to_run_judge(self) -> None:
        with TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "preference-judge-live"
            run_dir.mkdir()
            (run_dir / "answers").mkdir()
            (run_dir / "pairs.json").write_text(
                json.dumps(
                    {
                        "pairs": [
                            {
                                "pair_id": "p1",
                                "prompt_id": "x",
                                "cell_a": "c1",
                                "cell_b": "c2",
                            },
                        ],
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            with patch(
                "local_model_runtime_evaluation.preference_cli.run_judge",
                return_value=run_dir,
            ) as mock_judge:
                buffer = io.StringIO()
                with redirect_stdout(buffer):
                    code = main(["judge", "--run", str(run_dir)])
                self.assertEqual(code, 0)
                mock_judge.assert_called_once()
                payload = json.loads(buffer.getvalue())
                self.assertTrue(payload["ok"])
                self.assertEqual(payload["run_dir"], str(run_dir))

    def test_collect_live_delegates_to_run_collect(self) -> None:
        fake_run_dir = ROOT / "results" / "preference" / "fake-run"
        with patch(
            "local_model_runtime_evaluation.preference_cli.run_collect",
            return_value=fake_run_dir,
        ) as mock_collect:
            buffer = io.StringIO()
            with redirect_stdout(buffer):
                code = main(["collect"])
            self.assertEqual(code, 0)
            mock_collect.assert_called_once()
            payload = json.loads(buffer.getvalue())
            self.assertTrue(payload["ok"])
            self.assertEqual(payload["run_dir"], str(fake_run_dir))


if __name__ == "__main__":
    unittest.main()
