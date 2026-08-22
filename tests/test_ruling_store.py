from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from local_model_runtime_evaluation.ruling_store import (
    RulingStoreError,
    list_rulings,
    save_ruling,
)


def _ruling(
    ruling_id: str = "r1",
    *,
    created_at: str = "2026-01-01T00:00:00Z",
    run_id: str = "run-1",
) -> dict:
    # A minimal saveable ruling carries exactly the three required keys; this one
    # also carries an extra key so round-tripping can be checked.
    return {
        "ruling_id": ruling_id,
        "created_at": created_at,
        "run_id": run_id,
        "extra": {"note": f"from {ruling_id}"},
    }


class RulingStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name) / "rulings"      # deliberately does not exist yet

    # -- save_ruling: success -------------------------------------------------

    def test_save_returns_the_target_path(self) -> None:
        target = save_ruling(self.root, _ruling())
        self.assertEqual(target, self.root / "r1.json")

    def test_creates_the_root_directory_when_absent(self) -> None:
        self.assertFalse(self.root.exists())
        save_ruling(self.root, _ruling())
        self.assertTrue(self.root.is_dir())

    def test_round_trips_extra_keys(self) -> None:
        ruling = _ruling()
        target = save_ruling(self.root, ruling)
        with open(target, encoding="utf-8") as handle:
            self.assertEqual(json.load(handle), ruling)

    def test_leaves_no_tmp_file_behind(self) -> None:
        save_ruling(self.root, _ruling())
        self.assertEqual(list(self.root.glob("*.tmp")), [])

    # -- save_ruling: refusals ------------------------------------------------

    def test_rejects_a_non_dict_ruling(self) -> None:
        with self.assertRaises(RulingStoreError):
            save_ruling(self.root, None)

    def test_rejects_an_unavailable_ruling_without_a_ruling_id(self) -> None:
        # An UNAVAILABLE ruling has no identity key and must not be persisted.
        with self.assertRaises(RulingStoreError):
            save_ruling(
                self.root, {"created_at": "2026-01-01T00:00:00Z", "run_id": "run-1"}
            )

    def test_rejects_a_missing_created_at(self) -> None:
        with self.assertRaises(RulingStoreError):
            save_ruling(self.root, {"ruling_id": "r1", "run_id": "run-1"})

    def test_rejects_a_missing_run_id(self) -> None:
        with self.assertRaises(RulingStoreError):
            save_ruling(
                self.root, {"ruling_id": "r1", "created_at": "2026-01-01T00:00:00Z"}
            )

    def test_rejects_an_empty_ruling_id(self) -> None:
        with self.assertRaises(RulingStoreError):
            save_ruling(
                self.root,
                {"ruling_id": "", "created_at": "2026-01-01T00:00:00Z", "run_id": "run-1"},
            )

    def test_rejects_a_ruling_id_that_escapes_the_directory(self) -> None:
        with self.assertRaises(RulingStoreError):
            save_ruling(self.root, _ruling(ruling_id="../evil"))
        # nothing must have been written outside the rulings directory
        self.assertFalse((self.root.parent / "evil.json").exists())

    def test_rejects_a_ruling_id_with_a_slash(self) -> None:
        with self.assertRaises(RulingStoreError):
            save_ruling(self.root, _ruling(ruling_id="a/b"))

    def test_never_overwrites_an_existing_ruling(self) -> None:
        first = _ruling(ruling_id="dup", created_at="2026-01-01T00:00:00Z")
        target = save_ruling(self.root, first)
        with self.assertRaises(RulingStoreError):
            save_ruling(
                self.root, _ruling(ruling_id="dup", created_at="2026-01-01T00:00:01Z")
            )
        # never-overwrite is the point of the rule -- assert the content on disk
        with open(target, encoding="utf-8") as handle:
            self.assertEqual(json.load(handle), first)

    # -- list_rulings: never raises -------------------------------------------

    def test_lists_nothing_when_the_root_is_absent(self) -> None:
        self.assertEqual(list_rulings(self.root), [])

    def test_lists_nothing_when_the_root_is_a_file(self) -> None:
        self.root.write_text("{}", encoding="utf-8")
        self.assertEqual(list_rulings(self.root), [])

    def test_lists_nothing_in_an_empty_directory(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        self.assertEqual(list_rulings(self.root), [])

    def test_skips_invalid_json_but_keeps_valid_rulings(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / "broken.json").write_text("{not json", encoding="utf-8")
        save_ruling(self.root, _ruling(ruling_id="good", run_id="run-1"))
        ids = [entry["ruling_id"] for entry in list_rulings(self.root)]
        self.assertEqual(ids, ["good"])

    def test_skips_valid_json_that_is_not_an_object(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / "array.json").write_text("[1, 2]", encoding="utf-8")
        save_ruling(self.root, _ruling(ruling_id="good", run_id="run-1"))
        ids = [entry["ruling_id"] for entry in list_rulings(self.root)]
        self.assertEqual(ids, ["good"])

    def test_skips_an_object_that_lacks_the_required_keys(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / "partial.json").write_text(json.dumps({"ruling_id": "x"}), encoding="utf-8")
        save_ruling(self.root, _ruling(ruling_id="good", run_id="run-1"))
        ids = [entry["ruling_id"] for entry in list_rulings(self.root)]
        self.assertEqual(ids, ["good"])

    # -- list_rulings: supersede and order ------------------------------------

    def test_supersedes_the_older_ruling_within_a_run(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        save_ruling(
            self.root, _ruling(ruling_id="old", created_at="2026-01-01T00:00:00Z", run_id="run-1")
        )
        save_ruling(
            self.root, _ruling(ruling_id="new", created_at="2026-01-01T00:00:05Z", run_id="run-1")
        )
        by_id = {entry["ruling_id"]: entry for entry in list_rulings(self.root)}
        self.assertIsNone(by_id["new"]["superseded_by"])
        self.assertEqual(by_id["old"]["superseded_by"], "new")

    def test_does_not_supersede_across_runs(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        save_ruling(
            self.root, _ruling(ruling_id="a", created_at="2026-01-01T00:00:05Z", run_id="run-a")
        )
        save_ruling(
            self.root, _ruling(ruling_id="b", created_at="2026-01-01T00:00:09Z", run_id="run-b")
        )
        by_id = {entry["ruling_id"]: entry for entry in list_rulings(self.root)}
        self.assertIsNone(by_id["a"]["superseded_by"])
        self.assertIsNone(by_id["b"]["superseded_by"])

    def test_a_single_ruling_is_never_superseded(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        save_ruling(self.root, _ruling())
        entries = list_rulings(self.root)
        self.assertEqual(len(entries), 1)
        self.assertIsNone(entries[0]["superseded_by"])

    def test_orders_newest_first(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        save_ruling(self.root, _ruling(ruling_id="a", created_at="2026-01-01T00:00:01Z"))
        save_ruling(self.root, _ruling(ruling_id="b", created_at="2026-01-01T00:00:03Z"))
        save_ruling(self.root, _ruling(ruling_id="c", created_at="2026-01-01T00:00:05Z"))
        self.assertEqual(
            [entry["ruling_id"] for entry in list_rulings(self.root)], ["c", "b", "a"]
        )

    def test_listing_does_not_delete_or_rewrite_earlier_rulings(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        save_ruling(
            self.root, _ruling(ruling_id="old", created_at="2026-01-01T00:00:00Z", run_id="run-1")
        )
        save_ruling(
            self.root, _ruling(ruling_id="new", created_at="2026-01-01T00:00:05Z", run_id="run-1")
        )
        list_rulings(self.root)
        self.assertTrue((self.root / "old.json").exists())
        self.assertTrue((self.root / "new.json").exists())

    def test_each_entry_carries_the_full_ruling_and_a_real_path(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        original = _ruling(ruling_id="r1", created_at="2026-01-01T00:00:00Z", run_id="run-1")
        save_ruling(self.root, original)
        entry = list_rulings(self.root)[0]
        self.assertEqual(entry["ruling_id"], "r1")
        self.assertEqual(entry["created_at"], "2026-01-01T00:00:00Z")
        self.assertEqual(entry["run_id"], "run-1")
        self.assertIn("path", entry)
        self.assertTrue(Path(entry["path"]).exists())
        self.assertEqual(entry["ruling"], original)


if __name__ == "__main__":
    unittest.main()
