"""Rendering tests for results_browser_html.

These tests exercise render_index / render_run / write_browser against real
view models built by results_browser.py from bundles constructed through the
real EvidenceBundle API (via tests/results_browser_fixtures.py, plus one
inline hostile-content bundle built the same way for the escaping test).
No mocks; everything runs in a TemporaryDirectory.
"""

from __future__ import annotations

import re
import unittest
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from local_model_runtime_evaluation.evidence_bundle import EvidenceBundle
from local_model_runtime_evaluation.managed_run_types import ManagedStep, StepState
from local_model_runtime_evaluation.operator_policy import adopt_policy
from local_model_runtime_evaluation.run_identity import build_plan
from local_model_runtime_evaluation.results_browser import (
    build_index,
    build_run_view,
)
from local_model_runtime_evaluation.results_browser_html import (
    render_index,
    render_run,
    write_browser,
)
from tests.results_browser_fixtures import (
    make_corrupt,
    make_missing_plan,
    make_partial_blocked_with_attempts,
    make_sealed_pass,
    make_unsealed_running,
    make_unsupported_schema,
)


ROOT = Path(__file__).resolve().parents[1]
RECIPE = ROOT / "config" / "managed-runs" / "complete-native-quality-v1.json"
POLICY = ROOT / "config" / "operator-policies" / "local-managed-v1.example.json"
FAMILY_ID = "gemma-4-12b-qat"
HOSTILE = "<script>alert(1)</script>"


def _build_hostile_bundle(root: Path) -> Path:
    """Build a sealed, verified bundle whose run_name and a step report both
    carry a raw <script> tag, through the same real EvidenceBundle flow the
    fixtures module uses (not a fixtures.py edit -- this stays local to this
    test file since it needs non-standard content the shared builders don't
    take a parameter for)."""
    results_root = root / "results"
    state_root = root / ".lmre"
    now = datetime(2026, 7, 31, 6, 0, tzinfo=timezone.utc)
    adopted = adopt_policy(POLICY, state_root, now=now)
    plan = build_plan(
        RECIPE,
        family_id=FAMILY_ID,
        run_name=HOSTILE,
        comparison_id=None,
        parent_run_id=None,
        results_root=results_root,
        now=now,
        entropy="999999",
    )
    bundle = EvidenceBundle.create(
        results_root, plan, adopted, {"platform": "macOS", "python": "3.11"}
    )
    for step in bundle.plan.steps:
        bundle.transition_step(step, StepState.RUNNING)
        output_path = None
        if step is ManagedStep.MATRIX:
            output_dir = bundle.step_attempt_dir(step, 1)
            output_dir.mkdir(parents=True, exist_ok=True)
            (output_dir / "report.md").write_text(
                f"# report\n\n{HOSTILE}\n", encoding="utf-8"
            )
            output_path = output_dir.relative_to(bundle.run_dir).as_posix()
        bundle.transition_step(step, StepState.PASS, output_path=output_path)
    bundle.mark_cleanup_complete()
    bundle.write_summary(
        {
            "attempt": 1,
            "comparison_id": plan.identity.comparison_id,
            "run_id": plan.identity.run_id,
            "run_name": plan.identity.run_name,
            "status": "PASS",
        }
    )
    bundle.seal()
    return bundle.run_dir


class RenderIndexTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = TemporaryDirectory()
        self.root = Path(self.temporary.name)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_missing_root_renders_distinct_message(self) -> None:
        index = build_index(self.root / "results")
        html_text = render_index(index)
        self.assertIn(str(self.root / "results"), html_text)
        self.assertIn("does not exist", html_text.lower())
        self.assertNotIn("<script", html_text)

    def test_empty_root_renders_explicit_empty_state(self) -> None:
        results_root = self.root / "results"
        results_root.mkdir(parents=True)
        index = build_index(results_root)
        html_text = render_index(index)
        self.assertIn("no evidence bundles", html_text.lower())

    def test_entries_escaped_linked_and_none_is_em_dash(self) -> None:
        make_sealed_pass(self.root)
        make_missing_plan(self.root)  # no plan.json -> most fields None
        results_root = self.root / "results"
        index = build_index(results_root)
        html_text = render_index(index)

        # Real run got a link to its run page.
        sealed_entry = next(
            e for e in index["entries"] if e["health"] == "SEALED_VERIFIED"
        )
        self.assertIn(f'runs/{sealed_entry["run_dir_name"]}.html', html_text)
        self.assertIn(sealed_entry["run_id"], html_text)

        # Degraded entry has None fields rendered as an em dash somewhere.
        self.assertIn("—", html_text)
        self.assertNotIn("<script", html_text)
        self.assertNotIn("http://", html_text)
        self.assertNotIn("https://", html_text)


class RenderRunFailClosedTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = TemporaryDirectory()
        self.root = Path(self.temporary.name)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_corrupt_page_fails_closed_and_withholds_reports(self) -> None:
        run_dir = make_corrupt(self.root)
        view = build_run_view(run_dir)
        html_text = render_run(view)
        self.assertIn("FAILED VERIFICATION", html_text)
        self.assertIn("evidence_checksum_mismatch", html_text)
        self.assertNotIn("Matrix screen report", html_text)
        self.assertNotIn("N/A (optiq pair skipped: port busy)", html_text)

    def test_unsealed_page_shows_not_accepted_and_withholds_reports(self) -> None:
        run_dir = make_unsealed_running(self.root)
        view = build_run_view(run_dir)
        html_text = render_run(view)
        self.assertIn("not accepted evidence", html_text.lower())
        self.assertNotIn("Matrix screen report", html_text)

    def test_unsupported_schema_page_shows_reason(self) -> None:
        run_dir = make_unsupported_schema(self.root)
        view = build_run_view(run_dir)
        html_text = render_run(view)
        self.assertIn("9.9.9", html_text)
        self.assertIn("unsupported", html_text.lower())

    def test_unreadable_page_shows_reason(self) -> None:
        run_dir = make_missing_plan(self.root)
        view = build_run_view(run_dir)
        html_text = render_run(view)
        self.assertIn("evidence_file_missing", html_text)
        self.assertIn("unreadable", html_text.lower())
        self.assertNotIn("http://", html_text)
        self.assertNotIn("<script", html_text)


class RenderRunVerifiedTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = TemporaryDirectory()
        self.root = Path(self.temporary.name)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_verified_page_contains_overhead_report_verbatim(self) -> None:
        run_dir = make_sealed_pass(self.root)
        view = build_run_view(run_dir)
        html_text = render_run(view)
        self.assertIn("N/A (optiq pair skipped: port busy)", html_text)
        self.assertIn("est.", html_text)
        self.assertIn("—", html_text)  # em dash
        self.assertIn("trusted", html_text.lower())

    def test_pipe_table_becomes_html_table_cell_for_cell(self) -> None:
        run_dir = make_sealed_pass(self.root)
        view = build_run_view(run_dir)
        html_text = render_run(view)
        table_match = re.search(
            r"<table>.*?fake-cell-a.*?</table>", html_text, re.DOTALL
        )
        self.assertIsNotNone(table_match)
        table_html = table_match.group(0)
        self.assertIn("<th scope=\"col\">Cell</th>", table_html)
        self.assertIn("<td>fake-cell-a</td>", table_html)
        self.assertIn("<td>PASS</td>", table_html)
        self.assertIn("<td>1.23s</td>", table_html)
        # Markdown separator row must not leak through as a data row.
        self.assertNotIn("---", table_html)

    def test_attempt_history_rendered_for_partial_blocked(self) -> None:
        run_dir = make_partial_blocked_with_attempts(self.root)
        view = build_run_view(run_dir)
        html_text = render_run(view)
        self.assertIn("PARTIAL_BLOCKED", html_text)
        self.assertIn("BLOCKED_PROVIDER_RECONNECT", html_text)

    def test_no_preserved_attempts_message(self) -> None:
        run_dir = make_sealed_pass(self.root)
        view = build_run_view(run_dir)
        html_text = render_run(view)
        self.assertIn("no preserved earlier attempts", html_text.lower())

    def test_absent_summary_renders_not_written(self) -> None:
        run_dir = make_missing_plan(self.root)
        view = build_run_view(run_dir)
        html_text = render_run(view)
        self.assertIn("summary not written", html_text.lower())


class HostileStringEscapingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = TemporaryDirectory()
        self.root = Path(self.temporary.name)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_hostile_run_name_and_report_text_are_escaped(self) -> None:
        run_dir = _build_hostile_bundle(self.root)
        view = build_run_view(run_dir)
        html_text = render_run(view)
        self.assertNotIn(HOSTILE, html_text)
        self.assertNotIn("<script", html_text)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", html_text)


class WriteBrowserTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = TemporaryDirectory()
        self.root = Path(self.temporary.name)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_write_browser_creates_index_and_one_page_per_bundle(self) -> None:
        make_sealed_pass(self.root)
        make_partial_blocked_with_attempts(self.root)
        make_unsealed_running(self.root)
        make_corrupt(self.root)
        make_missing_plan(self.root)
        make_unsupported_schema(self.root)

        results_root = self.root / "results"
        output_root = self.root / "browser-out"
        result = write_browser(results_root, output_root)

        self.assertEqual(result["runs"], 6)
        self.assertEqual(len(result["pages"]), 6)
        index_path = Path(result["index"])
        self.assertTrue(index_path.is_file())
        self.assertEqual(index_path, output_root / "index.html")
        for page in result["pages"]:
            page_path = Path(page)
            self.assertTrue(page_path.is_file())
            self.assertTrue(str(page_path).startswith(str(output_root)))

    def test_no_url_or_script_substrings_leak_into_page_chrome(self) -> None:
        # Scoped check: legitimate plan data (loopback endpoints) does
        # contain "http://" by design (run_identity.py hardcodes
        # http://127.0.0.1:PORT/v1 endpoints, and the spec requires
        # rendering them verbatim in the identity table). So this checks
        # the page chrome/CSS and the degraded pages that carry no plan
        # data, plus <script> absence everywhere (the real injection risk).
        make_missing_plan(self.root)
        results_root = self.root / "results"
        output_root = self.root / "browser-out"
        result = write_browser(results_root, output_root)

        index_html = (output_root / "index.html").read_text(encoding="utf-8")
        self.assertNotIn("<script", index_html)
        self.assertNotIn("http://", index_html)
        self.assertNotIn("https://", index_html)

        for page in result["pages"]:
            page_html = Path(page).read_text(encoding="utf-8")
            self.assertNotIn("<script", page_html)


if __name__ == "__main__":
    unittest.main()
