"""Focused tests for the sealed cross-run comparison slice.

All bundles are built through the real fixture builders (real
EvidenceBundle / build_plan / adopt_policy APIs) in temporary directories.
Nothing here contacts a runtime or touches real results/runs/ evidence.
"""

from __future__ import annotations

import json
import unittest
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from local_model_runtime_evaluation.results_browser import (
    VERDICT_COMPARABLE,
    VERDICT_INCOMPARABLE,
    VERDICT_NOT_APPLICABLE,
    build_comparisons,
)
from local_model_runtime_evaluation.results_browser_html import (
    render_comparison_group,
    render_comparisons_index,
    write_browser,
)
from tests.results_browser_fixtures import (
    make_corrupt,
    make_missing_plan,
    make_sealed_pass,
    make_unsealed_running,
    make_unsupported_schema,
)


COMPARISON_ID = "compare-fixture-group"


def _two_sealed(root: Path) -> tuple[Path, Path]:
    """Two sealed verified bundles sharing COMPARISON_ID.

    The later-created bundle is built first so deterministic ordering cannot
    accidentally come from filesystem creation order.
    """
    later = make_sealed_pass(
        root,
        run_name="fixture-sealed-later",
        entropy="a2a2a2",
        now=datetime(2026, 7, 31, 6, 0, tzinfo=timezone.utc),
        comparison_id=COMPARISON_ID,
    )
    earlier = make_sealed_pass(
        root,
        run_name="fixture-sealed-earlier",
        entropy="a1a1a1",
        now=datetime(2026, 7, 31, 5, 0, tzinfo=timezone.utc),
        comparison_id=COMPARISON_ID,
    )
    return earlier, later


class BuildComparisonsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.results_root = self.root / "results"

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_missing_root(self) -> None:
        comparisons = build_comparisons(self.root / "does-not-exist")
        self.assertTrue(comparisons["missing_root"])
        self.assertEqual(comparisons["groups"], [])

    def test_empty_root(self) -> None:
        self.results_root.mkdir(parents=True)
        comparisons = build_comparisons(self.results_root)
        self.assertFalse(comparisons["missing_root"])
        self.assertEqual(comparisons["groups"], [])

    def test_two_sealed_verified_group_comparable_and_ordered(self) -> None:
        earlier, later = _two_sealed(self.root)
        comparisons = build_comparisons(self.results_root)
        groups = [
            g
            for g in comparisons["groups"]
            if g["comparison_id"] == COMPARISON_ID
        ]
        self.assertEqual(len(groups), 1)
        group = groups[0]
        self.assertEqual(group["verdict"], VERDICT_COMPARABLE)
        self.assertEqual(group["verdict_reason"], "")
        self.assertEqual(group["accepted_count"], 2)
        self.assertEqual(group["excluded_count"], 0)
        self.assertIsNotNone(group["dimensions"])
        # created_at ascending, independent of build order.
        self.assertEqual(
            [m["run_dir_name"] for m in group["members"]],
            [earlier.name, later.name],
        )
        self.assertTrue(all(m["accepted"] for m in group["members"]))

    def test_family_mismatch_is_incomparable_with_stable_reason(self) -> None:
        make_sealed_pass(
            self.root,
            run_name="fixture-family-a",
            entropy="b1b1b1",
            now=datetime(2026, 7, 31, 5, 0, tzinfo=timezone.utc),
            comparison_id=COMPARISON_ID,
        )
        make_sealed_pass(
            self.root,
            run_name="fixture-family-b",
            entropy="b2b2b2",
            now=datetime(2026, 7, 31, 6, 0, tzinfo=timezone.utc),
            comparison_id=COMPARISON_ID,
            family_id="ornith-35b",
        )
        group = build_comparisons(self.results_root)["groups"][0]
        self.assertEqual(group["verdict"], VERDICT_INCOMPARABLE)
        self.assertTrue(
            group["verdict_reason"].startswith(
                "plan_dimension_mismatch: family_id"
            )
        )
        # No aggregation target exists: shared dimensions are withheld.
        self.assertIsNone(group["dimensions"])
        # Both individual runs stay visible as members.
        self.assertEqual(len(group["members"]), 2)

    def test_mixed_health_excludes_but_keeps_verified_usable(self) -> None:
        make_sealed_pass(self.root, comparison_id=COMPARISON_ID)
        make_unsealed_running(self.root, comparison_id=COMPARISON_ID)
        make_corrupt(self.root, comparison_id=COMPARISON_ID)
        # Unattributable bundles: no vetted identity, so no group membership.
        make_missing_plan(self.root)
        make_unsupported_schema(self.root)

        comparisons = build_comparisons(self.results_root)
        groups = {g["comparison_id"]: g for g in comparisons["groups"]}
        group = groups[COMPARISON_ID]
        self.assertEqual(group["accepted_count"], 1)
        self.assertEqual(group["excluded_count"], 2)
        # One accepted member only: nothing to compare, N/A verbatim.
        self.assertEqual(group["verdict"], VERDICT_NOT_APPLICABLE)
        self.assertEqual(
            group["verdict_reason"], "fewer than two accepted members"
        )
        excluded = {
            m["health"]: m["exclusion_reason"]
            for m in group["members"]
            if not m["accepted"]
        }
        self.assertEqual(
            excluded,
            {
                "UNSEALED": "excluded: bundle is not sealed",
                "SEALED_CORRUPT": (
                    "excluded: sealed but failed checksum verification"
                ),
            },
        )
        # The unreadable and unsupported bundles joined no group at all.
        all_members = [
            m["run_dir_name"] for g in comparisons["groups"] for m in g["members"]
        ]
        self.assertNotIn("run-20260731-000000-eeeeee", all_members)
        self.assertEqual(len(all_members), len(set(all_members)))

    def test_malformed_comparison_id_never_forms_a_group(self) -> None:
        run_dir = make_unsealed_running(self.root, comparison_id=COMPARISON_ID)
        plan_path = run_dir / "plan.json"
        raw = json.loads(plan_path.read_text(encoding="utf-8"))
        raw["identity"]["comparison_id"] = "../Evil Name"
        plan_path.write_text(json.dumps(raw), encoding="utf-8")

        comparisons = build_comparisons(self.results_root)
        for group in comparisons["groups"]:
            self.assertNotIn("..", group["comparison_id"])
            self.assertNotIn(
                run_dir.name, [m["run_dir_name"] for m in group["members"]]
            )


class ComparisonHtmlTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.results_root = self.root / "results"
        self.output_root = self.root / "browser-out"

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_write_browser_writes_comparison_pages_under_output_root(
        self,
    ) -> None:
        earlier, later = _two_sealed(self.root)
        sources_before = {
            path: path.read_bytes()
            for path in sorted(self.results_root.rglob("*"))
            if path.is_file()
        }
        result = write_browser(self.results_root, self.output_root)
        self.assertEqual(result["comparisons"], 1)
        comparison_index = Path(result["comparison_index"])
        self.assertEqual(
            comparison_index, self.output_root / "comparisons" / "index.html"
        )
        group_page = (
            self.output_root / "comparisons" / f"{COMPARISON_ID}.html"
        )
        self.assertTrue(group_page.is_file())
        # Members link to their existing run detail pages.
        page_text = group_page.read_text(encoding="utf-8")
        self.assertIn(f'href="../runs/{earlier.name}.html"', page_text)
        self.assertIn(f'href="../runs/{later.name}.html"', page_text)
        # Main index links to the comparison index.
        index_text = (self.output_root / "index.html").read_text(
            encoding="utf-8"
        )
        self.assertIn('href="comparisons/index.html"', index_text)
        # Source bundles are byte-for-byte untouched.
        for path, content in sources_before.items():
            self.assertEqual(path.read_bytes(), content)
        # Nothing was written outside the output root.
        for path in self.results_root.rglob("*"):
            self.assertFalse(path.name.endswith(".html"))

    def test_pages_have_no_script_or_network_references(self) -> None:
        _two_sealed(self.root)
        make_corrupt(self.root, comparison_id=COMPARISON_ID)
        write_browser(self.results_root, self.output_root)
        for page in (self.output_root / "comparisons").iterdir():
            text = page.read_text(encoding="utf-8")
            lowered = text.lower()
            self.assertNotIn("<script", lowered)
            self.assertNotIn("http://", lowered.replace("http://127", ""))
            self.assertNotIn("https://", lowered)
            self.assertNotIn("src=", lowered)
            # Withheld report content never leaks into comparison pages.
            self.assertNotIn("matrix screen report", lowered)

    def test_hostile_strings_are_escaped(self) -> None:
        group = {
            "comparison_id": "safe-id",
            "verdict": VERDICT_INCOMPARABLE,
            "verdict_reason": "plan_dimension_mismatch: family_id",
            "accepted_count": 2,
            "excluded_count": 0,
            "dimensions": None,
            "members": [
                {
                    "run_dir_name": "run-20260731-050000-a1a1a1",
                    "run_id": "run-20260731-050000-a1a1a1",
                    "run_name": "<script>alert(1)</script>",
                    "attempt": 1,
                    "created_at": "2026-07-31T05:00:00+00:00",
                    "run_status": "PASS",
                    "health": "SEALED_VERIFIED",
                    "health_detail": "",
                    "accepted": True,
                    "exclusion_reason": None,
                }
            ],
        }
        text = render_comparison_group(group)
        self.assertNotIn("<script>", text)
        self.assertIn("&lt;script&gt;", text)

    def test_missing_root_and_empty_index_pages_render(self) -> None:
        missing = render_comparisons_index(
            {"results_root": "/nope", "missing_root": True, "groups": []}
        )
        self.assertIn("does not exist", missing)
        empty = render_comparisons_index(
            {"results_root": "/empty", "missing_root": False, "groups": []}
        )
        self.assertIn("No comparison groups", empty)


if __name__ == "__main__":
    unittest.main()
