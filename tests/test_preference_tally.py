from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from local_model_runtime_evaluation.preference_config import PreferenceError
from local_model_runtime_evaluation.preference_tally import (
    render_tally_report,
    run_tally,
    tally,
)


class TallyTests(unittest.TestCase):
    def test_tally_win_rates(self) -> None:
        pairs = [
            {"pair_id": "p1", "prompt_id": "x", "cell_a": "c1", "cell_b": "c2"},
            {"pair_id": "p2", "prompt_id": "x", "cell_a": "c1", "cell_b": "c2"},
        ]
        judgments = [
            {"pair_id": "p1", "winner": "A"},
            {"pair_id": "p2", "winner": "tie"},
        ]
        result = tally(pairs, judgments)
        self.assertEqual(result["c1"]["wins"], 1)
        self.assertEqual(result["c1"]["losses"], 0)
        self.assertEqual(result["c1"]["ties"], 1)
        self.assertAlmostEqual(result["c1"]["win_rate"], 1.0)
        self.assertEqual(result["c2"]["wins"], 0)
        self.assertEqual(result["c2"]["losses"], 1)
        self.assertEqual(result["c2"]["ties"], 1)
        self.assertAlmostEqual(result["c2"]["win_rate"], 0.0)

    def test_tally_win_rate_null_when_only_ties(self) -> None:
        pairs = [
            {"pair_id": "p1", "prompt_id": "x", "cell_a": "c1", "cell_b": "c2"},
        ]
        judgments = [{"pair_id": "p1", "winner": "tie"}]
        result = tally(pairs, judgments)
        self.assertIsNone(result["c1"]["win_rate"])
        self.assertIsNone(result["c2"]["win_rate"])

    def test_tally_initializes_all_cells(self) -> None:
        pairs = [
            {"pair_id": "p1", "prompt_id": "x", "cell_a": "c1", "cell_b": "c2"},
        ]
        judgments = [{"pair_id": "p1", "winner": "B"}]
        result = tally(pairs, judgments)
        self.assertEqual(set(result), {"c1", "c2"})
        for stats in result.values():
            self.assertEqual(
                set(stats),
                {"wins", "losses", "ties", "win_rate"},
            )

    def test_rejects_unknown_winner(self) -> None:
        pairs = [
            {"pair_id": "p1", "prompt_id": "x", "cell_a": "c1", "cell_b": "c2"},
        ]
        with self.assertRaises(PreferenceError):
            tally(pairs, [{"pair_id": "p1", "winner": "C"}])

    def test_rejects_null_winner(self) -> None:
        pairs = [
            {"pair_id": "p1", "prompt_id": "x", "cell_a": "c1", "cell_b": "c2"},
        ]
        with self.assertRaises(PreferenceError) as ctx:
            tally(pairs, [{"pair_id": "p1", "winner": None}])
        self.assertIn("p1", str(ctx.exception))

    def test_rejects_missing_judgment(self) -> None:
        pairs = [
            {"pair_id": "p1", "prompt_id": "x", "cell_a": "c1", "cell_b": "c2"},
            {"pair_id": "p2", "prompt_id": "x", "cell_a": "c1", "cell_b": "c2"},
        ]
        judgments = [{"pair_id": "p1", "winner": "A"}]
        with self.assertRaises(PreferenceError) as ctx:
            tally(pairs, judgments)
        message = str(ctx.exception)
        self.assertIn("p2", message)

    def test_b_winner_updates_both_cells(self) -> None:
        pairs = [
            {"pair_id": "p1", "prompt_id": "x", "cell_a": "c1", "cell_b": "c2"},
        ]
        judgments = [{"pair_id": "p1", "winner": "B"}]
        result = tally(pairs, judgments)
        self.assertEqual(result["c1"]["losses"], 1)
        self.assertEqual(result["c2"]["wins"], 1)
        self.assertAlmostEqual(result["c2"]["win_rate"], 1.0)


class RenderTallyReportTests(unittest.TestCase):
    def test_render_includes_cells_and_latency_note(self) -> None:
        stats = {
            "c1": {"wins": 2, "losses": 1, "ties": 0, "win_rate": 2 / 3},
            "c2": {"wins": 1, "losses": 2, "ties": 0, "win_rate": 1 / 3},
        }
        report = render_tally_report(
            stats,
            run_id="gemma-preference-test",
            suite_id="gemma-preference-v1",
        )
        self.assertIn("gemma-preference-test", report)
        self.assertIn("gemma-preference-v1", report)
        self.assertIn("c1", report)
        self.assertIn("c2", report)
        self.assertIn("latency was not used", report.lower())


class RunTallyTests(unittest.TestCase):
    def test_run_tally_writes_report(self) -> None:
        pairs = [
            {"pair_id": "p1", "prompt_id": "x", "cell_a": "c1", "cell_b": "c2"},
        ]
        judgments = [{"pair_id": "p1", "winner": "A"}]
        with TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "gemma-preference-test"
            run_dir.mkdir()
            (run_dir / "pairs.json").write_text(
                json.dumps({"pairs": pairs}, indent=2) + "\n",
                encoding="utf-8",
            )
            (run_dir / "judgments.json").write_text(
                json.dumps({"judgments": judgments}, indent=2) + "\n",
                encoding="utf-8",
            )
            (run_dir / "raw.json").write_text(
                json.dumps(
                    {
                        "suite_id": "gemma-preference-v1",
                        "suite_revision": "1",
                        "cell_ids": ["c1", "c2"],
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            result = run_tally(run_dir)
            self.assertEqual(result, run_dir)
            report = (run_dir / "report.md").read_text(encoding="utf-8")
            self.assertIn("c1", report)
            self.assertIn("gemma-preference-v1", report)
            tally_json = json.loads((run_dir / "tally.json").read_text(encoding="utf-8"))
            self.assertIn("cells", tally_json)
            self.assertIn("c1", tally_json["cells"])

    def test_run_tally_uses_run_dir_name_without_raw(self) -> None:
        pairs = [
            {"pair_id": "p1", "prompt_id": "x", "cell_a": "c1", "cell_b": "c2"},
        ]
        judgments = [{"pair_id": "p1", "winner": "tie"}]
        with TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "gemma-preference-fallback"
            run_dir.mkdir()
            (run_dir / "pairs.json").write_text(
                json.dumps({"pairs": pairs}, indent=2) + "\n",
                encoding="utf-8",
            )
            (run_dir / "judgments.json").write_text(
                json.dumps({"judgments": judgments}, indent=2) + "\n",
                encoding="utf-8",
            )
            run_tally(run_dir)
            report = (run_dir / "report.md").read_text(encoding="utf-8")
            self.assertIn("gemma-preference-fallback", report)


if __name__ == "__main__":
    unittest.main()
