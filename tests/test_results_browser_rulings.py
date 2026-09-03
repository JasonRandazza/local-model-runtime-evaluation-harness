"""Rendering tests for the rulings slice of the results browser.

These tests exercise build_rulings_index / render_rulings_index /
render_ruling / write_browser against ruling JSON files written through
the real `ruling_store.save_ruling` API (and one inline hostile-content
ruling for the escaping test). No mocks; everything runs in a
TemporaryDirectory.
"""

from __future__ import annotations

import json
import unittest
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from local_model_runtime_evaluation.ruling import (
    CELL_NAMED,
    NO_CELL_QUALIFIES,
    UNAVAILABLE,
)
from local_model_runtime_evaluation.ruling_store import save_ruling
from local_model_runtime_evaluation.results_browser import build_rulings_index
from local_model_runtime_evaluation.results_browser_html import (
    render_ruling,
    render_rulings_index,
    write_browser,
)
from tests.results_browser_fixtures import make_sealed_pass

HOSTILE = "<script>alert(1)</script>"


def _write_ruling(rulings_root: Path, ruling: dict) -> Path:
    return save_ruling(rulings_root, ruling)


def _cell_named_ruling(*, ruling_id: str, run_id: str, created_at: str) -> dict:
    return {
        "schema_version": "ruling-1.0.0",
        "ruling_id": ruling_id,
        "created_at": created_at,
        "run_id": run_id,
        "plan_hash": "planhash123",
        "comparison_id": "compare-fixture",
        "family_id": "gemma-4-12b-qat",
        "rubric": {
            "rubric_id": "rubric-fixture",
            "revision": "1",
            "hash": "rubrichash456",
        },
        "cells": [
            {
                "cell_id": "cell-a",
                "family_id": "gemma-4-12b-qat",
                "floors": [
                    {
                        "metric": "matrix.median_total_seconds",
                        "comparator": "<=",
                        "value": 2.0,
                        "measured": 1.5,
                        "passed": True,
                    }
                ],
                "order_by": {
                    "metric": "matrix.median_total_seconds",
                    "measured": 1.5,
                },
                "qualified": True,
            },
            {
                "cell_id": "cell-b",
                "family_id": "gemma-4-12b-qat",
                "floors": [
                    {
                        "metric": "matrix.median_total_seconds",
                        "comparator": "<=",
                        "value": 2.0,
                        "measured": 2.5,
                        "passed": False,
                    }
                ],
                "order_by": {
                    "metric": "matrix.median_total_seconds",
                    "measured": 2.5,
                },
                "qualified": False,
            },
        ],
        "outcome": {
            "state": CELL_NAMED,
            "cell_id": "cell-a",
            "reason": (
                "cleared every floor and ordered first on "
                "matrix.median_total_seconds (asc)"
            ),
        },
    }


def _unavailable_ruling(*, ruling_id: str, run_id: str, created_at: str) -> dict:
    return {
        "schema_version": "ruling-1.0.0",
        "ruling_id": ruling_id,
        "created_at": created_at,
        "run_id": run_id,
        "outcome": {
            "state": UNAVAILABLE,
            "cell_id": None,
            "reason": "bundle is not sealed and verified (UNSEALED)",
        },
        "code": "bundle_not_trusted",
        "cells": [],
    }


def _no_cell_qualifies_ruling(
    *, ruling_id: str, run_id: str, created_at: str
) -> dict:
    return {
        "schema_version": "ruling-1.0.0",
        "ruling_id": ruling_id,
        "created_at": created_at,
        "run_id": run_id,
        "plan_hash": "planhash789",
        "comparison_id": "compare-fixture",
        "family_id": "gemma-4-12b-qat",
        "rubric": {
            "rubric_id": "rubric-strict",
            "revision": "1",
            "hash": "rubrichashabc",
        },
        "cells": [
            {
                "cell_id": "cell-a",
                "family_id": "gemma-4-12b-qat",
                "floors": [
                    {
                        "metric": "matrix.median_total_seconds",
                        "comparator": "<=",
                        "value": 0.5,
                        "measured": 1.5,
                        "passed": False,
                    }
                ],
                "order_by": {
                    "metric": "matrix.median_total_seconds",
                    "measured": 1.5,
                },
                "qualified": False,
            }
        ],
        "outcome": {
            "state": NO_CELL_QUALIFIES,
            "cell_id": None,
            "reason": "no cell cleared every floor",
        },
    }


class BuildRulingsIndexTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.results_root = self.root / "results"

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_missing_root(self) -> None:
        index = build_rulings_index(self.root / "does-not-exist")
        self.assertTrue(index["missing_root"])
        self.assertEqual(index["rulings"], [])

    def test_no_rulings_directory_renders_empty(self) -> None:
        self.results_root.mkdir(parents=True)
        index = build_rulings_index(self.results_root)
        self.assertFalse(index["missing_root"])
        self.assertEqual(index["rulings"], [])

    def test_empty_rulings_directory_renders_empty(self) -> None:
        self.results_root.mkdir(parents=True)
        (self.results_root / "rulings").mkdir()
        index = build_rulings_index(self.results_root)
        self.assertFalse(index["missing_root"])
        self.assertEqual(index["rulings"], [])

    def test_single_ruling_listed(self) -> None:
        self.results_root.mkdir(parents=True)
        rulings_root = self.results_root / "rulings"
        rulings_root.mkdir()
        ruling = _cell_named_ruling(
            ruling_id="rule-1",
            run_id="run-20260731-050000-a1a1a1",
            created_at="2026-07-31T05:00:00Z",
        )
        _write_ruling(rulings_root, ruling)
        index = build_rulings_index(self.results_root)
        self.assertFalse(index["missing_root"])
        self.assertEqual(len(index["rulings"]), 1)
        self.assertEqual(index["rulings"][0]["ruling_id"], "rule-1")
        self.assertIsNone(index["rulings"][0]["superseded_by"])

    def test_supersession_derived_at_read_time(self) -> None:
        self.results_root.mkdir(parents=True)
        rulings_root = self.results_root / "rulings"
        rulings_root.mkdir()
        earlier = _cell_named_ruling(
            ruling_id="rule-earlier",
            run_id="run-20260731-050000-a1a1a1",
            created_at="2026-07-31T05:00:00Z",
        )
        later = _cell_named_ruling(
            ruling_id="rule-later",
            run_id="run-20260731-050000-a1a1a1",
            created_at="2026-07-31T06:00:00Z",
        )
        _write_ruling(rulings_root, earlier)
        _write_ruling(rulings_root, later)
        index = build_rulings_index(self.results_root)
        by_id = {e["ruling_id"]: e for e in index["rulings"]}
        self.assertIsNone(by_id["rule-later"]["superseded_by"])
        self.assertEqual(by_id["rule-earlier"]["superseded_by"], "rule-later")
        # Newest first.
        self.assertEqual(index["rulings"][0]["ruling_id"], "rule-later")

    def test_junk_files_skipped_silently(self) -> None:
        self.results_root.mkdir(parents=True)
        rulings_root = self.results_root / "rulings"
        rulings_root.mkdir()
        valid = _cell_named_ruling(
            ruling_id="rule-valid",
            run_id="run-20260731-050000-a1a1a1",
            created_at="2026-07-31T05:00:00Z",
        )
        _write_ruling(rulings_root, valid)
        (rulings_root / "junk.json").write_text(
            "not valid json {{{", encoding="utf-8"
        )
        (rulings_root / "missing-keys.json").write_text(
            json.dumps({"ruling_id": "only-id"}), encoding="utf-8"
        )
        index = build_rulings_index(self.results_root)
        self.assertEqual(len(index["rulings"]), 1)
        self.assertEqual(index["rulings"][0]["ruling_id"], "rule-valid")


class RenderRulingsIndexTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.results_root = self.root / "results"

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_missing_root_renders_distinct_message(self) -> None:
        index = build_rulings_index(self.root / "does-not-exist")
        html_text = render_rulings_index(index)
        self.assertIn(str(self.root / "does-not-exist"), html_text)
        self.assertIn("does not exist", html_text.lower())
        self.assertNotIn("<script", html_text)

    def test_empty_root_renders_explicit_empty_state(self) -> None:
        self.results_root.mkdir(parents=True)
        (self.results_root / "rulings").mkdir()
        index = build_rulings_index(self.results_root)
        html_text = render_rulings_index(index)
        self.assertIn("no rulings were found", html_text.lower())

    def test_rulings_index_links_to_ruling_pages(self) -> None:
        self.results_root.mkdir(parents=True)
        rulings_root = self.results_root / "rulings"
        rulings_root.mkdir()
        ruling = _cell_named_ruling(
            ruling_id="rule-1",
            run_id="run-20260731-050000-a1a1a1",
            created_at="2026-07-31T05:00:00Z",
        )
        _write_ruling(rulings_root, ruling)
        index = build_rulings_index(self.results_root)
        html_text = render_rulings_index(index)
        self.assertIn('href="rule-1.html"', html_text)
        self.assertIn("Cell named", html_text)
        self.assertIn("cell-a", html_text)
        self.assertIn("current", html_text)

    def test_superseded_ruling_marked_visibly(self) -> None:
        self.results_root.mkdir(parents=True)
        rulings_root = self.results_root / "rulings"
        rulings_root.mkdir()
        earlier = _cell_named_ruling(
            ruling_id="rule-earlier",
            run_id="run-20260731-050000-a1a1a1",
            created_at="2026-07-31T05:00:00Z",
        )
        later = _cell_named_ruling(
            ruling_id="rule-later",
            run_id="run-20260731-050000-a1a1a1",
            created_at="2026-07-31T06:00:00Z",
        )
        _write_ruling(rulings_root, earlier)
        _write_ruling(rulings_root, later)
        index = build_rulings_index(self.results_root)
        html_text = render_rulings_index(index)
        self.assertIn("superseded", html_text)
        self.assertNotIn("superseded", html_text.split("rule-later.html")[0].split("<tr>")[-1])


class RenderRulingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.results_root = self.root / "results"

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_cell_named_ruling_renders_cell_and_floors(self) -> None:
        self.results_root.mkdir(parents=True)
        rulings_root = self.results_root / "rulings"
        rulings_root.mkdir()
        ruling = _cell_named_ruling(
            ruling_id="rule-1",
            run_id="run-20260731-050000-a1a1a1",
            created_at="2026-07-31T05:00:00Z",
        )
        _write_ruling(rulings_root, ruling)
        index = build_rulings_index(self.results_root)
        entry = index["rulings"][0]
        html_text = render_ruling(entry)
        self.assertIn("rule-1", html_text)
        self.assertIn("cell-a", html_text)
        self.assertIn("CELL_NAMED", html_text)
        self.assertIn("rubric-fixture", html_text)
        self.assertIn("rubrichash456", html_text)
        self.assertIn("matrix.median_total_seconds", html_text)
        self.assertIn("1.5", html_text)
        self.assertIn("current", html_text.lower())
        self.assertNotIn("SUPERSEDED", html_text)

    def test_unavailable_ruling_shows_code_and_reason(self) -> None:
        self.results_root.mkdir(parents=True)
        rulings_root = self.results_root / "rulings"
        rulings_root.mkdir()
        ruling = _unavailable_ruling(
            ruling_id="rule-unavail",
            run_id="run-20260731-050000-a1a1a1",
            created_at="2026-07-31T05:00:00Z",
        )
        _write_ruling(rulings_root, ruling)
        index = build_rulings_index(self.results_root)
        entry = index["rulings"][0]
        html_text = render_ruling(entry)
        self.assertIn("UNAVAILABLE", html_text)
        self.assertIn("bundle_not_trusted", html_text)
        self.assertIn("bundle is not sealed and verified (UNSEALED)", html_text)
        self.assertIn("did not support a conclusion", html_text)

    def test_no_cell_qualifies_shows_reason(self) -> None:
        self.results_root.mkdir(parents=True)
        rulings_root = self.results_root / "rulings"
        rulings_root.mkdir()
        ruling = _no_cell_qualifies_ruling(
            ruling_id="rule-none",
            run_id="run-20260731-050000-a1a1a1",
            created_at="2026-07-31T05:00:00Z",
        )
        _write_ruling(rulings_root, ruling)
        index = build_rulings_index(self.results_root)
        entry = index["rulings"][0]
        html_text = render_ruling(entry)
        self.assertIn("NO_CELL_QUALIFIES", html_text)
        self.assertIn("no cell cleared every floor", html_text)

    def test_superseded_ruling_page_shows_superseded_banner(self) -> None:
        self.results_root.mkdir(parents=True)
        rulings_root = self.results_root / "rulings"
        rulings_root.mkdir()
        earlier = _cell_named_ruling(
            ruling_id="rule-earlier",
            run_id="run-20260731-050000-a1a1a1",
            created_at="2026-07-31T05:00:00Z",
        )
        later = _cell_named_ruling(
            ruling_id="rule-later",
            run_id="run-20260731-050000-a1a1a1",
            created_at="2026-07-31T06:00:00Z",
        )
        _write_ruling(rulings_root, earlier)
        _write_ruling(rulings_root, later)
        index = build_rulings_index(self.results_root)
        entries = {e["ruling_id"]: e for e in index["rulings"]}
        html_text = render_ruling(entries["rule-earlier"])
        self.assertIn("SUPERSEDED", html_text)
        self.assertIn("rule-later", html_text)
        # The later ruling must NOT show as superseded.
        later_html = render_ruling(entries["rule-later"])
        self.assertNotIn("SUPERSEDED", later_html)


class RulingsEscapingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.results_root = self.root / "results"

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_hostile_ruling_id_is_escaped(self) -> None:
        self.results_root.mkdir(parents=True)
        rulings_root = self.results_root / "rulings"
        rulings_root.mkdir()
        ruling = _cell_named_ruling(
            ruling_id="rule-hostile",
            run_id="run-20260731-050000-a1a1a1",
            created_at="2026-07-31T05:00:00Z",
        )
        ruling["ruling_id"] = "rule-hostile"
        ruling["outcome"]["cell_id"] = HOSTILE
        ruling["outcome"]["reason"] = HOSTILE
        ruling["cells"][0]["cell_id"] = HOSTILE
        ruling["cells"][0]["floors"][0]["metric"] = HOSTILE
        _write_ruling(rulings_root, ruling)
        index = build_rulings_index(self.results_root)
        entry = index["rulings"][0]
        html_text = render_ruling(entry)
        self.assertNotIn(HOSTILE, html_text)
        self.assertNotIn("<script", html_text)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", html_text)

    def test_floor_metric_is_escaped_exactly_once(self) -> None:
        # The floors cell escapes each piece, so escaping the joined string
        # again would render a legitimate "&" as "&amp;amp;". Safe but wrong.
        self.results_root.mkdir(parents=True)
        rulings_root = self.results_root / "rulings"
        rulings_root.mkdir()
        ruling = _cell_named_ruling(
            ruling_id="rule-amp",
            run_id="run-20260731-050000-b2b2b2",
            created_at="2026-07-31T05:00:00Z",
        )
        ruling["cells"][0]["floors"][0]["metric"] = "rag&keyword"
        _write_ruling(rulings_root, ruling)
        index = build_rulings_index(self.results_root)
        html_text = render_ruling(index["rulings"][0])
        self.assertIn("rag&amp;keyword", html_text)
        self.assertNotIn("rag&amp;amp;keyword", html_text)

    def test_hostile_ruling_index_is_escaped(self) -> None:
        self.results_root.mkdir(parents=True)
        rulings_root = self.results_root / "rulings"
        rulings_root.mkdir()
        ruling = _cell_named_ruling(
            ruling_id="rule-hostile-idx",
            run_id="run-20260731-050000-a1a1a1",
            created_at="2026-07-31T05:00:00Z",
        )
        ruling["outcome"]["cell_id"] = HOSTILE
        _write_ruling(rulings_root, ruling)
        index = build_rulings_index(self.results_root)
        html_text = render_rulings_index(index)
        self.assertNotIn(HOSTILE, html_text)
        self.assertNotIn("<script", html_text)
        self.assertIn("&amp;lt;script&amp;gt;alert(1)&amp;lt;/script&amp;gt;", html_text)


class WriteBrowserRulingsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.results_root = self.root / "results"
        self.output_root = self.root / "browser-out"

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_write_browser_creates_rulings_pages(self) -> None:
        self.results_root.mkdir(parents=True)
        make_sealed_pass(self.root)
        rulings_root = self.results_root / "rulings"
        rulings_root.mkdir()
        ruling = _cell_named_ruling(
            ruling_id="rule-1",
            run_id="run-20260731-050000-a1a1a1",
            created_at="2026-07-31T05:00:00Z",
        )
        _write_ruling(rulings_root, ruling)
        result = write_browser(self.results_root, self.output_root)
        self.assertEqual(result["rulings"], 1)
        rulings_index_path = Path(result["rulings_index"])
        self.assertTrue(rulings_index_path.is_file())
        self.assertEqual(
            rulings_index_path, self.output_root / "rulings" / "index.html"
        )
        ruling_page = self.output_root / "rulings" / "rule-1.html"
        self.assertTrue(ruling_page.is_file())
        # Main index links to rulings.
        index_text = (self.output_root / "index.html").read_text(
            encoding="utf-8"
        )
        self.assertIn('href="rulings/index.html"', index_text)

    def test_write_browser_no_rulings_directory(self) -> None:
        self.results_root.mkdir(parents=True)
        make_sealed_pass(self.root)
        result = write_browser(self.results_root, self.output_root)
        self.assertEqual(result["rulings"], 0)
        rulings_index_path = self.output_root / "rulings" / "index.html"
        self.assertTrue(rulings_index_path.is_file())
        index_text = rulings_index_path.read_text(encoding="utf-8")
        self.assertIn("no rulings were found", index_text.lower())

    def test_rulings_pages_have_no_script_tags(self) -> None:
        self.results_root.mkdir(parents=True)
        make_sealed_pass(self.root)
        rulings_root = self.results_root / "rulings"
        rulings_root.mkdir()
        ruling = _cell_named_ruling(
            ruling_id="rule-1",
            run_id="run-20260731-050000-a1a1a1",
            created_at="2026-07-31T05:00:00Z",
        )
        _write_ruling(rulings_root, ruling)
        write_browser(self.results_root, self.output_root)
        for page in (self.output_root / "rulings").iterdir():
            text = page.read_text(encoding="utf-8")
            self.assertNotIn("<script", text)


if __name__ == "__main__":
    unittest.main()
