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
from unittest import mock

from local_model_runtime_evaluation.evidence_bundle import (
    EvidenceBundle,
    EvidenceError,
)
from local_model_runtime_evaluation.managed_run_types import ManagedRunPlan
from local_model_runtime_evaluation.results_browser import (
    HEALTH_SEALED_VERIFIED,
    METRICS_AVAILABLE,
    METRICS_UNAVAILABLE,
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
from local_model_runtime_evaluation.run_identity import _canonical_plan_hash
from tests.results_browser_fixtures import (
    make_corrupt,
    make_missing_plan,
    make_sealed_pass,
    make_unsealed_running,
    make_unsupported_schema,
)


def _retamper_comparison_id(run_dir: Path, new_comparison_id: str) -> None:
    """Rewrite identity.comparison_id and recompute plan_hash so the bundle
    stays loadable -- only the SAFE_COMPARISON_ID check is meant to fail.
    """
    plan_path = run_dir / "plan.json"
    raw = json.loads(plan_path.read_text(encoding="utf-8"))
    raw["identity"]["comparison_id"] = new_comparison_id
    plan = ManagedRunPlan.from_dict(raw)
    raw["plan_hash"] = _canonical_plan_hash(plan)
    plan_path.write_text(json.dumps(raw), encoding="utf-8")


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
        self.assertEqual(
            group["metrics"]["availability"],
            [
                {
                    "run_id": earlier.name,
                    "matrix": METRICS_AVAILABLE,
                    "overhead": METRICS_AVAILABLE,
                },
                {
                    "run_id": later.name,
                    "matrix": METRICS_AVAILABLE,
                    "overhead": METRICS_AVAILABLE,
                },
            ],
        )
        self.assertEqual(
            len(group["metrics"]["matrix"]),
            2 * len(group["dimensions"]["cell_ids"]),
        )
        self.assertEqual(
            len(group["metrics"]["overhead"]),
            2 * len(group["dimensions"]["pair_ids"]),
        )
        first_matrix = group["metrics"]["matrix"][0]
        self.assertEqual(first_matrix["run_id"], earlier.name)
        self.assertEqual(
            first_matrix["cell_id"], group["dimensions"]["cell_ids"][0]
        )
        self.assertEqual(first_matrix["median_total_seconds"], 1.25)
        self.assertEqual(first_matrix["success_count"], 9)

    def test_comparable_group_marks_missing_structured_metrics_unavailable(
        self,
    ) -> None:
        available = make_sealed_pass(
            self.root,
            run_name="fixture-metrics-available",
            entropy="a3a3a3",
            now=datetime(2026, 7, 31, 5, 0, tzinfo=timezone.utc),
            comparison_id=COMPARISON_ID,
        )
        unavailable = make_sealed_pass(
            self.root,
            run_name="fixture-metrics-unavailable",
            entropy="a4a4a4",
            now=datetime(2026, 7, 31, 6, 0, tzinfo=timezone.utc),
            comparison_id=COMPARISON_ID,
            structured_metrics=False,
        )
        group = build_comparisons(self.results_root)["groups"][0]
        self.assertEqual(group["verdict"], VERDICT_COMPARABLE)
        self.assertEqual(
            group["metrics"]["availability"],
            [
                {
                    "run_id": available.name,
                    "matrix": METRICS_AVAILABLE,
                    "overhead": METRICS_AVAILABLE,
                },
                {
                    "run_id": unavailable.name,
                    "matrix": METRICS_UNAVAILABLE,
                    "overhead": METRICS_UNAVAILABLE,
                },
            ],
        )
        metric_run_ids = {
            row["run_id"]
            for section in ("matrix", "overhead")
            for row in group["metrics"][section]
        }
        self.assertEqual(metric_run_ids, {available.name})

    def test_state_read_race_reports_metrics_unavailable(self) -> None:
        # classify_bundle can verify a bundle whose state file changes before
        # the metrics read. The member must stay visible with UNAVAILABLE
        # metrics instead of crashing the comparisons build.
        _two_sealed(self.root)
        with mock.patch(
            "local_model_runtime_evaluation.results_browser.classify_bundle",
            return_value=(HEALTH_SEALED_VERIFIED, ""),
        ), mock.patch.object(
            EvidenceBundle,
            "state",
            new_callable=mock.PropertyMock,
            side_effect=EvidenceError("state changed after classification"),
        ):
            group = build_comparisons(self.results_root)["groups"][0]
        self.assertEqual(group["verdict"], VERDICT_COMPARABLE)
        for entry in group["metrics"]["availability"]:
            self.assertEqual(entry["matrix"], METRICS_UNAVAILABLE)
            self.assertEqual(entry["overhead"], METRICS_UNAVAILABLE)
        self.assertEqual(group["metrics"]["matrix"], [])
        self.assertEqual(group["metrics"]["overhead"], [])

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
        self.assertIsNone(group["metrics"])
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
        _retamper_comparison_id(run_dir, "../Evil Name")

        comparisons = build_comparisons(self.results_root)
        for group in comparisons["groups"]:
            self.assertNotIn("..", group["comparison_id"])
            self.assertNotIn(
                run_dir.name, [m["run_dir_name"] for m in group["members"]]
            )
        # Malformed comparison_id is now visible as an unattributed record.
        self.assertEqual(
            comparisons["unattributed_exclusions"],
            [
                {
                    "run_dir_name": run_dir.name,
                    "health": "UNSEALED",
                    "reason": "malformed_comparison_id",
                }
            ],
        )

    def test_healthy_solo_run_default_comparison_id_is_not_unattributed(
        self,
    ) -> None:
        # build_plan defaults a None comparison_id to the sanitized run
        # name, so a solo run forms its own one-member N/A group -- it is
        # not an exclusion, and never appears in unattributed_exclusions.
        make_sealed_pass(self.root, comparison_id=None)
        comparisons = build_comparisons(self.results_root)
        self.assertEqual(comparisons["unattributed_exclusions"], [])
        self.assertEqual(len(comparisons["groups"]), 1)
        self.assertEqual(comparisons["groups"][0]["verdict"], VERDICT_NOT_APPLICABLE)

    def test_degraded_bundles_are_unattributed_never_grouped(self) -> None:
        make_sealed_pass(self.root, comparison_id=COMPARISON_ID)
        make_unsealed_running(self.root, comparison_id=COMPARISON_ID)
        make_corrupt(self.root, comparison_id=COMPARISON_ID)
        missing_plan_dir = make_missing_plan(self.root)
        unsupported_dir = make_unsupported_schema(self.root)

        comparisons = build_comparisons(self.results_root)
        unattributed = {
            record["run_dir_name"]: record
            for record in comparisons["unattributed_exclusions"]
        }
        self.assertEqual(
            unattributed[missing_plan_dir.name],
            {
                "run_dir_name": missing_plan_dir.name,
                "health": "UNREADABLE",
                "reason": "unreadable_bundle",
            },
        )
        self.assertEqual(
            unattributed[unsupported_dir.name],
            {
                "run_dir_name": unsupported_dir.name,
                "health": "UNSUPPORTED_SCHEMA",
                "reason": "unsupported_schema",
            },
        )
        # Degraded bundles never join any group, accepted or excluded.
        all_members = [
            m["run_dir_name"] for g in comparisons["groups"] for m in g["members"]
        ]
        self.assertNotIn(missing_plan_dir.name, all_members)
        self.assertNotIn(unsupported_dir.name, all_members)
        # Existing group semantics for vetted-identity members are unchanged.
        group = comparisons["groups"][0]
        self.assertEqual(group["accepted_count"], 1)
        self.assertEqual(group["excluded_count"], 2)

    def test_symlinked_entry_is_unattributed_and_target_never_read(self) -> None:
        self.results_root.mkdir(parents=True)
        sentinel = "SENTINEL-SECRET-OUTSIDE-ROOT"
        target = self.root / "outside-target.txt"
        target.write_text(sentinel, encoding="utf-8")
        link = self.results_root / "run-20260731-070000-abcdef"
        link.symlink_to(target)

        comparisons = build_comparisons(self.results_root)
        self.assertEqual(
            comparisons["unattributed_exclusions"],
            [
                {
                    "run_dir_name": link.name,
                    "health": "UNRECOGNIZED",
                    "reason": "unrecognized_entry",
                }
            ],
        )
        rendered = render_comparisons_index(comparisons)
        self.assertNotIn(sentinel, rendered)

    def test_hostile_directory_name_is_unrecognized_and_never_leaks(self) -> None:
        self.results_root.mkdir(parents=True)
        hostile_name = '<script>alert(1)>-"quoted\''
        hostile_dir = self.results_root / hostile_name
        hostile_dir.mkdir()

        comparisons = build_comparisons(self.results_root)
        self.assertEqual(
            comparisons["unattributed_exclusions"],
            [
                {
                    "run_dir_name": "(unrecognized entry)",
                    "health": "UNRECOGNIZED",
                    "reason": "unrecognized_entry",
                }
            ],
        )
        rendered = render_comparisons_index(comparisons)
        self.assertNotIn(hostile_name, rendered)
        self.assertNotIn("<script", rendered.lower())

    def test_record_fields_are_exact_and_no_extra_content_leaks(self) -> None:
        run_dir = make_unsupported_schema(self.root)
        comparisons = build_comparisons(self.results_root)
        records = comparisons["unattributed_exclusions"]
        self.assertEqual(len(records), 1)
        self.assertEqual(
            set(records[0]), {"run_dir_name", "health", "reason"}
        )
        rendered = render_comparisons_index(comparisons)
        # health_detail text from classify_bundle must never leak in.
        self.assertNotIn("plan_schema_unsupported", rendered)
        # The bundle's real run_dir_name IS the expected safe display value
        # here (it matches SAFE_RUN_ID), so it legitimately appears.
        self.assertIn(run_dir.name, rendered)

    def test_unattributed_ordering_stable_regardless_of_creation_order(
        self,
    ) -> None:
        # Reverse-alphabetical creation order; assert sorted output anyway.
        unsupported_dir = make_unsupported_schema(self.root)
        missing_plan_dir = make_missing_plan(self.root)

        comparisons = build_comparisons(self.results_root)
        names = [r["run_dir_name"] for r in comparisons["unattributed_exclusions"]]
        expected = sorted(
            [missing_plan_dir.name, unsupported_dir.name],
            key=lambda name: (
                "UNREADABLE" if name == missing_plan_dir.name else "UNSUPPORTED_SCHEMA",
                name,
            ),
        )
        self.assertEqual(names, expected)


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
        self.assertIn("Comparable recorded metrics", page_text)
        self.assertIn("Median total seconds", page_text)
        self.assertIn("Direct versus Osaurus overhead", page_text)
        self.assertIn("does not calculate a winner", page_text)
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

    def test_write_browser_unattributed_exclusions_count_and_no_scope_leak(
        self,
    ) -> None:
        _two_sealed(self.root)
        missing_plan_dir = make_missing_plan(self.root)
        result = write_browser(self.results_root, self.output_root)
        self.assertEqual(result["unattributed_exclusions"], 1)
        index_page = (self.output_root / "comparisons" / "index.html").read_text(
            encoding="utf-8"
        )
        self.assertIn(missing_plan_dir.name, index_page)
        self.assertIn("Unattributed exclusions", index_page)
        for path in self.output_root.rglob("*"):
            self.assertTrue(str(path).startswith(str(self.output_root)))

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

    def test_hostile_recorded_metric_is_escaped(self) -> None:
        _two_sealed(self.root)
        group = build_comparisons(self.results_root)["groups"][0]
        group["metrics"]["matrix"][0]["status"] = "<script>metric()</script>"
        text = render_comparison_group(group)
        self.assertNotIn("<script>metric()", text)
        self.assertIn("&lt;script&gt;metric()&lt;/script&gt;", text)

    def test_missing_root_and_empty_index_pages_render(self) -> None:
        missing = render_comparisons_index(
            {
                "results_root": "/nope",
                "missing_root": True,
                "groups": [],
                "unattributed_exclusions": [],
            }
        )
        self.assertIn("does not exist", missing)
        self.assertIn("No unattributed exclusions", missing)
        empty = render_comparisons_index(
            {
                "results_root": "/empty",
                "missing_root": False,
                "groups": [],
                "unattributed_exclusions": [],
            }
        )
        self.assertIn("No comparison groups", empty)
        self.assertIn("No unattributed exclusions", empty)


if __name__ == "__main__":
    unittest.main()
