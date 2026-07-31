from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from local_model_runtime_evaluation.results_browser import (
    HEALTH_SEALED_CORRUPT,
    HEALTH_SEALED_VERIFIED,
    HEALTH_UNRECOGNIZED,
    HEALTH_UNREADABLE,
    HEALTH_UNSEALED,
    HEALTH_UNSUPPORTED_SCHEMA,
    build_index,
    build_run_view,
    classify_bundle,
)
from tests.results_browser_fixtures import (
    make_corrupt,
    make_missing_plan,
    make_partial_blocked_with_attempts,
    make_sealed_pass,
    make_unsealed_running,
    make_unsupported_schema,
)


class ClassifyBundleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = TemporaryDirectory()
        self.root = Path(self.temporary.name)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_sealed_pass_is_verified(self) -> None:
        run_dir = make_sealed_pass(self.root)
        health, detail = classify_bundle(run_dir)
        self.assertEqual(health, HEALTH_SEALED_VERIFIED)
        self.assertEqual(detail, "")

    def test_partial_blocked_with_attempts_is_verified(self) -> None:
        run_dir = make_partial_blocked_with_attempts(self.root)
        health, detail = classify_bundle(run_dir)
        self.assertEqual(health, HEALTH_SEALED_VERIFIED)
        self.assertEqual(detail, "")

    def test_unsealed_running_is_unsealed(self) -> None:
        run_dir = make_unsealed_running(self.root)
        health, detail = classify_bundle(run_dir)
        self.assertEqual(health, HEALTH_UNSEALED)
        self.assertEqual(detail, "")

    def test_corrupt_is_sealed_corrupt(self) -> None:
        run_dir = make_corrupt(self.root)
        health, detail = classify_bundle(run_dir)
        self.assertEqual(health, HEALTH_SEALED_CORRUPT)
        self.assertTrue(detail.startswith("evidence_checksum_mismatch:"))

    def test_missing_plan_is_unreadable(self) -> None:
        run_dir = make_missing_plan(self.root)
        health, detail = classify_bundle(run_dir)
        self.assertEqual(health, HEALTH_UNREADABLE)
        self.assertTrue(detail.startswith("evidence_file_missing:"))

    def test_unsupported_schema_is_unsupported_schema(self) -> None:
        run_dir = make_unsupported_schema(self.root)
        health, detail = classify_bundle(run_dir)
        self.assertEqual(health, HEALTH_UNSUPPORTED_SCHEMA)
        self.assertIn("9.9.9", detail)

    def test_unrecognized_name_does_not_open_files(self) -> None:
        run_dir = self.root / "results" / "not-a-run-dir"
        run_dir.mkdir(parents=True)
        # Deliberately do not write plan.json; classification must fail
        # closed purely on the name pattern without attempting to read it.
        health, detail = classify_bundle(run_dir)
        self.assertEqual(health, HEALTH_UNRECOGNIZED)
        self.assertNotEqual(detail, "")

    def test_non_directory_is_unrecognized(self) -> None:
        results_root = self.root / "results"
        results_root.mkdir(parents=True)
        stray_file = results_root / "run-20260731-000000-123456"
        stray_file.write_text("not a directory\n", encoding="utf-8")
        health, _ = classify_bundle(stray_file)
        self.assertEqual(health, HEALTH_UNRECOGNIZED)


class BuildIndexTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = TemporaryDirectory()
        self.root = Path(self.temporary.name)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_missing_root_is_reported_without_raising(self) -> None:
        index = build_index(self.root / "results")
        self.assertTrue(index["missing_root"])
        self.assertEqual(index["entries"], [])

    def test_empty_root_produces_empty_entries(self) -> None:
        results_root = self.root / "results"
        results_root.mkdir(parents=True)
        index = build_index(results_root)
        self.assertFalse(index["missing_root"])
        self.assertEqual(index["entries"], [])

    def test_index_sorts_created_at_descending_with_none_last_and_degraded_rows(
        self,
    ) -> None:
        make_sealed_pass(self.root)  # created_at 04:00
        make_partial_blocked_with_attempts(self.root)  # created_at 03:00
        make_unsealed_running(self.root)  # created_at 02:00
        missing_plan_dir = make_missing_plan(self.root)  # no plan -> no created_at

        results_root = self.root / "results"
        index = build_index(results_root)
        self.assertFalse(index["missing_root"])
        entries = index["entries"]
        self.assertEqual(len(entries), 4)

        # Never raises for malformed bundles; each becomes its own row.
        healths = {entry["run_dir_name"]: entry["health"] for entry in entries}
        self.assertEqual(healths[missing_plan_dir.name], HEALTH_UNREADABLE)

        created_ats = [entry["created_at"] for entry in entries]
        self.assertEqual(created_ats[-1], None)
        non_none = [value for value in created_ats if value is not None]
        self.assertEqual(non_none, sorted(non_none, reverse=True))

    def test_index_entry_never_raises_for_unrecognized_dir(self) -> None:
        results_root = self.root / "results"
        results_root.mkdir(parents=True)
        (results_root / "garbage").mkdir()
        index = build_index(results_root)
        self.assertEqual(len(index["entries"]), 1)
        entry = index["entries"][0]
        self.assertEqual(entry["health"], HEALTH_UNRECOGNIZED)
        self.assertIsNone(entry["run_id"])
        self.assertIsNone(entry["created_at"])


class BuildRunViewTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = TemporaryDirectory()
        self.root = Path(self.temporary.name)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_sealed_pass_identity_and_policy_allowlist(self) -> None:
        run_dir = make_sealed_pass(self.root)
        view = build_run_view(run_dir)
        self.assertEqual(view["health"], HEALTH_SEALED_VERIFIED)

        identity = view["identity"]
        self.assertIsNotNone(identity)
        self.assertEqual(identity["run_name"], "fixture-sealed-pass")
        self.assertEqual(identity["family_id"], "gemma-4-12b-qat")
        self.assertEqual(identity["schema_version"], "1.0.0")
        for key in (
            "run_id",
            "comparison_id",
            "parent_run_id",
            "attempt",
            "recipe_id",
            "matrix_mode",
            "plan_hash",
            "created_at",
            "request_count",
            "estimated_minutes",
            "runtimes",
            "endpoints",
            "cell_ids",
            "pair_ids",
        ):
            self.assertIn(key, identity)

        policy = view["policy"]
        self.assertIsNotNone(policy)
        self.assertEqual(
            set(policy),
            {
                "policy_id",
                "schema_version",
                "authorization_mode",
                "loopback_only",
                "allowed_runtimes",
                "allow_inference",
                "allow_start",
                "allow_exact_reclaim",
                "reclaim_grace_seconds",
                "allow_terminate_after_interrupt",
                "allow_force_kill",
                "allow_provider_edits",
                "max_parallel_models",
                "memory_floor_percent",
                "max_run_minutes",
                "max_requests_per_run",
                "expires_at",
                "policy_hash",
                "adopted_at",
            },
        )
        self.assertEqual(policy["policy_id"], "local-managed-v1")
        # No credential-shaped keys leak through the allowlist.
        self.assertNotIn("api_key", policy)

        self.assertEqual(view["summary"]["status"], "PASS")

    def test_sealed_pass_steps_report_files(self) -> None:
        run_dir = make_sealed_pass(self.root)
        view = build_run_view(run_dir)
        steps_by_name = {step["step"]: step for step in view["steps"]}

        matrix_step = steps_by_name["matrix"]
        self.assertEqual(matrix_step["state"], "PASS")
        self.assertTrue(matrix_step["has_output_dir"])
        self.assertEqual(matrix_step["report_files"], ["raw.json", "report.md"])

        preflight_step = steps_by_name["preflight"]
        self.assertFalse(preflight_step["has_output_dir"])
        self.assertEqual(preflight_step["report_files"], [])

    def test_sealed_pass_step_reports_populated_only_for_verified(self) -> None:
        run_dir = make_sealed_pass(self.root)
        view = build_run_view(run_dir)
        self.assertIn("overhead", view["step_reports"])
        self.assertIn("N/A (optiq pair skipped: port busy)", view["step_reports"]["overhead"])
        self.assertIn("est.", view["step_reports"]["overhead"])
        self.assertIn("—", view["step_reports"]["overhead"])  # em dash
        self.assertIn("matrix", view["step_reports"])

    def test_unsealed_view_withholds_step_reports(self) -> None:
        run_dir = make_unsealed_running(self.root)
        view = build_run_view(run_dir)
        self.assertEqual(view["health"], HEALTH_UNSEALED)
        self.assertIsNotNone(view["identity"])
        self.assertIsNotNone(view["steps"])
        self.assertEqual(view["step_reports"], {})

    def test_corrupt_view_withholds_step_reports_but_keeps_metadata(self) -> None:
        run_dir = make_corrupt(self.root)
        view = build_run_view(run_dir)
        self.assertEqual(view["health"], HEALTH_SEALED_CORRUPT)
        self.assertIsNotNone(view["identity"])
        self.assertEqual(view["step_reports"], {})

    def test_unrecognized_and_unreadable_views_are_fully_degraded(self) -> None:
        missing_plan_dir = make_missing_plan(self.root)
        view = build_run_view(missing_plan_dir)
        self.assertEqual(view["health"], HEALTH_UNREADABLE)
        self.assertIsNone(view["identity"])
        self.assertIsNone(view["policy"])
        self.assertIsNone(view["summary"])
        self.assertIsNone(view["steps"])
        self.assertEqual(view["attempts"], [])
        self.assertEqual(view["lifecycle"], {"leases": [], "unparsed_lines": 0})
        self.assertEqual(view["step_reports"], {})

    def test_unsupported_schema_view_is_fully_degraded(self) -> None:
        run_dir = make_unsupported_schema(self.root)
        view = build_run_view(run_dir)
        self.assertEqual(view["health"], HEALTH_UNSUPPORTED_SCHEMA)
        self.assertIsNone(view["identity"])
        self.assertEqual(view["attempts"], [])
        self.assertEqual(view["step_reports"], {})

    def test_partial_blocked_attempts_history_and_final_state(self) -> None:
        run_dir = make_partial_blocked_with_attempts(self.root)
        view = build_run_view(run_dir)
        self.assertEqual(view["health"], HEALTH_SEALED_VERIFIED)
        self.assertEqual(view["summary"]["status"], "PARTIAL_BLOCKED")

        steps_by_name = {step["step"]: step for step in view["steps"]}
        overhead_step = steps_by_name["overhead"]
        self.assertEqual(overhead_step["state"], "BLOCKED_PROVIDER_RECONNECT")
        self.assertGreaterEqual(overhead_step["attempt"], 2)

        attempts = view["attempts"]
        self.assertEqual(len(attempts), 1)
        preserved = attempts[0]
        self.assertEqual(preserved["attempt"], 1)
        self.assertEqual(preserved["status"], "PARTIAL_BLOCKED")
        self.assertTrue(preserved["has_checksums"])
        preserved_overhead = next(
            step for step in preserved["steps"] if step["step"] == "overhead"
        )
        self.assertEqual(
            preserved_overhead["state"], "BLOCKED_PROVIDER_RECONNECT"
        )

    def test_attempts_extraction_skips_unreadable_snapshot(self) -> None:
        run_dir = make_sealed_pass(self.root)
        attempts_dir = run_dir / "attempts"
        attempts_dir.mkdir(parents=True, exist_ok=True)
        (attempts_dir / "attempt-007.json").write_text(
            "{not valid json", encoding="utf-8"
        )
        # Read the view directly rather than through classify_bundle so the
        # (now-corrupted-by-us) evidence set doesn't need to verify; steps
        # extraction is exercised independent of the seal/verify path here.
        from local_model_runtime_evaluation.results_browser import _attempts_list

        attempts = _attempts_list(run_dir)
        entry = next(a for a in attempts if a["attempt"] == 7)
        self.assertEqual(entry, {"attempt": 7, "error": "attempt snapshot is invalid"})

    def test_lifecycle_summary_reports_unresolved_lease_and_unparsed_lines(
        self,
    ) -> None:
        run_dir = make_sealed_pass(self.root)
        # Append extra raw lines directly (bypassing the sealed-immutability
        # guard) to exercise an unresolved lease and an unparsable line,
        # independent of the seal/verify path.
        from local_model_runtime_evaluation.results_browser import (
            _lifecycle_summary,
        )

        lifecycle_path = run_dir / "lifecycle.jsonl"
        with lifecycle_path.open("a", encoding="utf-8") as stream:
            stream.write(
                '{"action":"lease_acquired","attempt":1,'
                '"payload":{"lease_id":"lease-unresolved","ownership":"owned"},'
                '"runtime":"optiq","timestamp":"2026-07-31T04:05:00+00:00"}\n'
            )
            stream.write("not json at all\n")
            # Valid journal entries without lease data are not parse failures.
            stream.write(
                '{"action":"initial_observation","attempt":1,"payload":{},'
                '"runtime":"optiq","timestamp":"2026-07-31T04:05:01+00:00"}\n'
            )

        summary = _lifecycle_summary(run_dir)
        self.assertEqual(summary["unparsed_lines"], 1)
        leases_by_id = {lease["lease_id"]: lease for lease in summary["leases"]}
        self.assertEqual(
            leases_by_id["lease-unresolved"]["terminal_action"], "unresolved"
        )
        self.assertEqual(leases_by_id["lease-owned"]["terminal_action"], "released")
        self.assertEqual(
            leases_by_id["lease-attached"]["terminal_action"], "untouched"
        )


class ReviewRegressionTests(unittest.TestCase):
    """Fixes validated during the results-browser review wave."""

    def setUp(self) -> None:
        self.temporary = TemporaryDirectory()
        self.root = Path(self.temporary.name)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_symlinked_run_dir_is_unrecognized_and_never_followed(self) -> None:
        real_run = make_sealed_pass(self.root)
        outside = self.root / "outside"
        outside.mkdir()
        link = real_run.parent / "run-20260731-000000-abcdef"
        link.symlink_to(outside)

        health, detail = classify_bundle(link)
        self.assertEqual(health, HEALTH_UNRECOGNIZED)
        self.assertIn("symlink", detail)

        index = build_index(real_run.parent)
        by_name = {e["run_dir_name"]: e for e in index["entries"]}
        self.assertEqual(
            by_name["run-20260731-000000-abcdef"]["health"], HEALTH_UNRECOGNIZED
        )

    def test_index_entry_fails_closed_for_unsupported_schema(self) -> None:
        run_dir = make_unsupported_schema(self.root)
        index = build_index(run_dir.parent)
        entry = next(
            e for e in index["entries"] if e["run_dir_name"] == run_dir.name
        )
        self.assertEqual(entry["health"], HEALTH_UNSUPPORTED_SCHEMA)
        self.assertIsNone(entry["run_name"])
        self.assertIsNone(entry["run_id"])
        self.assertIsNone(entry["run_status"])
        self.assertIsNone(entry["created_at"])

    def test_bad_bytes_degrade_one_row_without_aborting_index(self) -> None:
        good = make_sealed_pass(self.root)
        bad = make_unsealed_running(self.root)
        (bad / "plan.json").write_bytes(b"\xff\xfe\x00 not utf8")
        lifecycle = good / "lifecycle.jsonl"
        # Appending bad bytes to the sealed bundle's journal corrupts it, but
        # the index must still render every row rather than raising.
        with lifecycle.open("ab") as stream:
            stream.write(b"\xff\xff\n")

        index = build_index(good.parent)
        by_name = {e["run_dir_name"]: e for e in index["entries"]}
        self.assertEqual(by_name[bad.name]["health"], HEALTH_UNREADABLE)
        self.assertIn(by_name[good.name]["health"], (HEALTH_SEALED_CORRUPT,))
        view = build_run_view(good)
        self.assertEqual(view["health"], HEALTH_SEALED_CORRUPT)


if __name__ == "__main__":
    unittest.main()
