from __future__ import annotations

import argparse
import json
import tempfile
import unittest
from pathlib import Path

from local_model_runtime_evaluation.ruling import UNAVAILABLE
from local_model_runtime_evaluation.ruling_cli import add_ruling_parser, command_ruling
from local_model_runtime_evaluation.rubric import RubricError
from tests.results_browser_fixtures import make_sealed_pass

# Every cell clears this floor, so the run always yields a named cell.
_PERMISSIVE = [{"metric": "preference.wins", "comparator": ">=", "value": 0}]
# No cell clears this one.
_IMPOSSIBLE = [{"metric": "preference.wins", "comparator": ">=", "value": 999}]
_ORDER = {"metric": "preference.win_rate", "direction": "desc"}


class RulingCliTests(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.rulings_root = self.root / "rulings"
        self.run_dir = make_sealed_pass(self.root / "runs")
        self.parser = argparse.ArgumentParser()
        add_ruling_parser(self.parser.add_subparsers(dest="command", required=True))

    def _rubric(self, floors: list[dict], name: str = "fixture-rubric") -> Path:
        path = self.root / f"{name}.json"
        path.write_text(
            json.dumps(
                {
                    "rubric_id": name,
                    "revision": "1",
                    "floors": floors,
                    "order_by": _ORDER,
                }
            ),
            encoding="utf-8",
        )
        return path

    def _make(self, rubric: Path, run: Path | None = None) -> dict:
        args = self.parser.parse_args(
            [
                "ruling", "make",
                "--run", str(run if run is not None else self.run_dir),
                "--rubric", str(rubric),
                "--rulings-root", str(self.rulings_root),
            ]
        )
        return command_ruling(args)

    def _list(self) -> dict:
        args = self.parser.parse_args(
            ["ruling", "list", "--rulings-root", str(self.rulings_root)]
        )
        return command_ruling(args)

    # --- make -------------------------------------------------------------

    def test_make_names_a_cell_and_saves_it(self) -> None:
        body = self._make(self._rubric(_PERMISSIVE))
        self.assertTrue(body["ok"])
        self.assertTrue(body["saved"])
        self.assertEqual(body["ruling"]["outcome"]["cell_id"], "optiq_4bit__optiq")
        self.assertTrue(Path(body["path"]).is_file())

    def test_the_saved_file_holds_the_ruling_that_was_returned(self) -> None:
        body = self._make(self._rubric(_PERMISSIVE))
        on_disk = json.loads(Path(body["path"]).read_text(encoding="utf-8"))
        self.assertEqual(on_disk, body["ruling"])

    def test_no_cell_qualifying_is_still_a_conclusion_and_is_saved(self) -> None:
        body = self._make(self._rubric(_IMPOSSIBLE))
        self.assertTrue(body["saved"])
        self.assertEqual(body["ruling"]["outcome"]["state"], "NO_CELL_QUALIFIES")
        self.assertIsNone(body["ruling"]["outcome"]["cell_id"])

    def test_an_unrulable_run_reports_ok_but_saves_nothing(self) -> None:
        body = self._make(self._rubric(_PERMISSIVE), run=self.root / "not-a-run")
        self.assertTrue(body["ok"])  # the command worked
        self.assertFalse(body["saved"])  # but there is nothing to record
        self.assertIsNone(body["path"])
        self.assertEqual(body["ruling"]["outcome"]["state"], UNAVAILABLE)
        self.assertFalse(self.rulings_root.exists())

    def test_a_bad_rubric_is_an_operator_error_and_raises(self) -> None:
        # Unlike an unrulable bundle, this is not a conclusion: the CLI turns
        # the raise into an error payload and a non-zero exit.
        with self.assertRaises(RubricError):
            self._make(self.root / "missing-rubric.json")

    # --- list -------------------------------------------------------------

    def test_list_is_empty_before_anything_is_ruled(self) -> None:
        self.assertEqual(self._list()["rulings"], [])

    def test_list_indexes_without_carrying_the_rulings_themselves(self) -> None:
        self._make(self._rubric(_PERMISSIVE))
        entries = self._list()["rulings"]
        self.assertEqual(len(entries), 1)
        self.assertNotIn("ruling", entries[0])
        self.assertEqual(
            sorted(entries[0]),
            ["created_at", "path", "ruling_id", "run_id", "superseded_by"],
        )

    def test_a_second_rubric_over_the_same_run_supersedes_the_first(self) -> None:
        first = self._make(self._rubric(_PERMISSIVE, name="rubric-a"))
        second = self._make(self._rubric(_IMPOSSIBLE, name="rubric-b"))
        by_id = {entry["ruling_id"]: entry for entry in self._list()["rulings"]}

        superseded = [
            rid for rid, entry in by_id.items() if entry["superseded_by"] is not None
        ]
        current = [
            rid for rid, entry in by_id.items() if entry["superseded_by"] is None
        ]
        self.assertEqual(len(current), 1, "exactly one conclusion is current per run")
        self.assertEqual(len(superseded), 1)

        # Superseding never removes the earlier ruling: both files survive.
        self.assertTrue(Path(first["path"]).is_file())
        self.assertTrue(Path(second["path"]).is_file())


if __name__ == "__main__":
    unittest.main()
