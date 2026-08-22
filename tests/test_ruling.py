from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from local_model_runtime_evaluation.ruling import (
    CELL_NAMED,
    NO_CELL_QUALIFIES,
    UNAVAILABLE,
    build_ruling,
    pick_winner,
    rubric_hash,
)
from local_model_runtime_evaluation.rubric import Rubric
from tests.results_browser_fixtures import (
    make_corrupt,
    make_sealed_pass,
    make_unsealed_running,
)

NOW = datetime(2026, 8, 22, 12, 0, tzinfo=timezone.utc)


def _rubric(root: Path, floors: list[dict], order_by: dict) -> Rubric:
    path = root / "fixture-rubric.json"
    path.write_text(
        json.dumps(
            {
                "rubric_id": "fixture-rubric",
                "revision": "1",
                "floors": floors,
                "order_by": order_by,
            }
        ),
        encoding="utf-8",
    )
    return Rubric.load(path)


class RulingTests(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.run_dir = make_sealed_pass(self.root / "ok")

    # --- a conclusion is reached -----------------------------------------

    def test_names_the_cell_that_orders_first_among_survivors(self) -> None:
        # Every cell clears a floor of 0 wins; win_rate rises with cell index,
        # so the last cell in plan order wins on a desc ordering.
        rubric = _rubric(
            self.root,
            [{"metric": "preference.wins", "comparator": ">=", "value": 0}],
            {"metric": "preference.win_rate", "direction": "desc"},
        )
        ruling = build_ruling(self.run_dir, rubric, now=NOW)
        self.assertEqual(ruling["outcome"]["state"], CELL_NAMED)
        self.assertEqual(ruling["outcome"]["cell_id"], "optiq_4bit__optiq")

    def test_direction_asc_names_the_other_end(self) -> None:
        rubric = _rubric(
            self.root,
            [{"metric": "preference.wins", "comparator": ">=", "value": 0}],
            {"metric": "preference.win_rate", "direction": "asc"},
        )
        ruling = build_ruling(self.run_dir, rubric, now=NOW)
        self.assertEqual(ruling["outcome"]["cell_id"], "jang_4m__osaurus")

    def test_a_tie_is_broken_deterministically(self) -> None:
        # ties is 0 for every cell, so ordering on it is a three-way tie that
        # must resolve the same way on every run.
        rubric = _rubric(
            self.root,
            [{"metric": "preference.wins", "comparator": ">=", "value": 0}],
            {"metric": "preference.ties", "direction": "desc"},
        )
        first = build_ruling(self.run_dir, rubric, now=NOW)["outcome"]["cell_id"]
        second = build_ruling(self.run_dir, rubric, now=NOW)["outcome"]["cell_id"]
        self.assertEqual(first, second)
        self.assertEqual(first, "jang_4m__osaurus")

    def test_a_floor_excludes_a_cell_and_reports_its_failing_value(self) -> None:
        # wins are 1, 2, 3 by cell index; a floor of 3 leaves exactly one.
        rubric = _rubric(
            self.root,
            [{"metric": "preference.wins", "comparator": ">=", "value": 3}],
            {"metric": "preference.win_rate", "direction": "desc"},
        )
        ruling = build_ruling(self.run_dir, rubric, now=NOW)
        self.assertEqual(ruling["outcome"]["cell_id"], "optiq_4bit__optiq")
        excluded = next(
            cell for cell in ruling["cells"] if cell["cell_id"] == "jang_4m__osaurus"
        )
        self.assertFalse(excluded["qualified"])
        self.assertEqual(excluded["floors"][0]["measured"], 1)
        self.assertFalse(excluded["floors"][0]["passed"])

    def test_no_cell_qualifies_rather_than_the_least_bad(self) -> None:
        rubric = _rubric(
            self.root,
            [{"metric": "preference.wins", "comparator": ">=", "value": 999}],
            {"metric": "preference.win_rate", "direction": "desc"},
        )
        ruling = build_ruling(self.run_dir, rubric, now=NOW)
        self.assertEqual(ruling["outcome"]["state"], NO_CELL_QUALIFIES)
        self.assertIsNone(ruling["outcome"]["cell_id"])
        self.assertTrue(all(not cell["qualified"] for cell in ruling["cells"]))

    def test_every_cell_is_reported_even_when_excluded(self) -> None:
        rubric = _rubric(
            self.root,
            [{"metric": "preference.wins", "comparator": ">=", "value": 999}],
            {"metric": "preference.win_rate", "direction": "desc"},
        )
        ruling = build_ruling(self.run_dir, rubric, now=NOW)
        self.assertEqual([cell["cell_id"] for cell in ruling["cells"]],
                         ["jang_4m__osaurus", "oq4_fp16__omlx", "optiq_4bit__optiq"])

    # --- metrics from the other steps ------------------------------------

    def test_rules_on_matrix_and_rag_metrics_too(self) -> None:
        rubric = _rubric(
            self.root,
            [
                {"metric": "matrix.success_count", "comparator": ">=", "value": 0},
                {"metric": "rag_keyword.retrieval_recall", "comparator": ">=", "value": 0.0},
            ],
            {"metric": "rag_oracle.fact_hit_rate", "direction": "desc"},
        )
        ruling = build_ruling(self.run_dir, rubric, now=NOW)
        self.assertEqual(ruling["outcome"]["state"], CELL_NAMED)

    def test_each_cell_carries_its_family(self) -> None:
        rubric = _rubric(
            self.root,
            [{"metric": "preference.wins", "comparator": ">=", "value": 0}],
            {"metric": "preference.win_rate", "direction": "desc"},
        )
        ruling = build_ruling(self.run_dir, rubric, now=NOW)
        self.assertTrue(all(cell["family_id"] for cell in ruling["cells"]))

    # --- fail closed ------------------------------------------------------

    def test_refuses_an_unsealed_bundle(self) -> None:
        run_dir = make_unsealed_running(self.root / "unsealed")
        rubric = _rubric(
            self.root,
            [{"metric": "preference.wins", "comparator": ">=", "value": 0}],
            {"metric": "preference.win_rate", "direction": "desc"},
        )
        ruling = build_ruling(run_dir, rubric, now=NOW)
        self.assertEqual(ruling["outcome"]["state"], UNAVAILABLE)
        self.assertEqual(ruling["code"], "bundle_not_trusted")
        self.assertEqual(ruling["cells"], [])

    def test_refuses_a_corrupt_bundle(self) -> None:
        run_dir = make_corrupt(self.root / "corrupt")
        rubric = _rubric(
            self.root,
            [{"metric": "preference.wins", "comparator": ">=", "value": 0}],
            {"metric": "preference.win_rate", "direction": "desc"},
        )
        ruling = build_ruling(run_dir, rubric, now=NOW)
        self.assertEqual(ruling["outcome"]["state"], UNAVAILABLE)
        self.assertEqual(ruling["code"], "bundle_not_trusted")

    def test_refuses_when_a_named_metric_is_malformed(self) -> None:
        run_dir = make_sealed_pass(self.root / "stub", structured_metrics=False)
        rubric = _rubric(
            self.root,
            [{"metric": "preference.wins", "comparator": ">=", "value": 0}],
            {"metric": "preference.win_rate", "direction": "desc"},
        )
        ruling = build_ruling(run_dir, rubric, now=NOW)
        self.assertEqual(ruling["outcome"]["state"], UNAVAILABLE)
        self.assertEqual(ruling["code"], "metrics_unavailable")

    def test_refuses_a_missing_run_directory(self) -> None:
        rubric = _rubric(
            self.root,
            [{"metric": "preference.wins", "comparator": ">=", "value": 0}],
            {"metric": "preference.win_rate", "direction": "desc"},
        )
        ruling = build_ruling(self.root / "nope", rubric, now=NOW)
        self.assertEqual(ruling["outcome"]["state"], UNAVAILABLE)

    # --- the rubric is bound in -------------------------------------------

    def test_records_the_rubric_by_hash(self) -> None:
        rubric = _rubric(
            self.root,
            [{"metric": "preference.wins", "comparator": ">=", "value": 0}],
            {"metric": "preference.win_rate", "direction": "desc"},
        )
        ruling = build_ruling(self.run_dir, rubric, now=NOW)
        self.assertEqual(ruling["rubric"]["hash"], rubric_hash(rubric))
        self.assertEqual(ruling["rubric"]["rubric_id"], "fixture-rubric")
        self.assertEqual(ruling["rubric"]["revision"], "1")

    def test_a_changed_floor_changes_the_rubric_hash(self) -> None:
        a = _rubric(
            self.root,
            [{"metric": "preference.wins", "comparator": ">=", "value": 0}],
            {"metric": "preference.win_rate", "direction": "desc"},
        )
        b = _rubric(
            self.root,
            [{"metric": "preference.wins", "comparator": ">=", "value": 1}],
            {"metric": "preference.win_rate", "direction": "desc"},
        )
        self.assertNotEqual(rubric_hash(a), rubric_hash(b))

    def test_cites_the_run_it_drew_on(self) -> None:
        rubric = _rubric(
            self.root,
            [{"metric": "preference.wins", "comparator": ">=", "value": 0}],
            {"metric": "preference.win_rate", "direction": "desc"},
        )
        ruling = build_ruling(self.run_dir, rubric, now=NOW)
        self.assertTrue(ruling["run_id"])
        self.assertTrue(ruling["plan_hash"])
        self.assertEqual(ruling["created_at"], "2026-08-22T12:00:00Z")
        self.assertTrue(ruling["ruling_id"].endswith("--fixture-rubric--20260822T120000Z"))
        self.assertNotIn(":", ruling["ruling_id"])  # must be a safe file name

    def test_tie_break_does_not_depend_on_arrival_order(self) -> None:
        # Same measured value for every survivor: only the cell_id tie-break
        # can decide, and it must decide the same way whichever order the
        # cells arrive in. Sort stability alone would not give this.
        def cell(cell_id: str) -> dict:
            return {"cell_id": cell_id, "order_by": {"measured": 0.5}}

        forward = [cell("aaa"), cell("bbb"), cell("ccc")]
        self.assertEqual(pick_winner(forward, "desc")["cell_id"], "aaa")
        self.assertEqual(pick_winner(list(reversed(forward)), "desc")["cell_id"], "aaa")
        self.assertEqual(pick_winner(forward, "asc")["cell_id"], "aaa")
        self.assertEqual(pick_winner(list(reversed(forward)), "asc")["cell_id"], "aaa")


if __name__ == "__main__":
    unittest.main()
