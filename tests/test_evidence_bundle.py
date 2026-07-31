from __future__ import annotations

import json
import unittest
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from local_model_runtime_evaluation.evidence_bundle import (
    EvidenceBundle,
    EvidenceError,
)
from local_model_runtime_evaluation.managed_run_types import (
    ManagedStep,
    RunSummaryState,
    StepState,
)
from local_model_runtime_evaluation.operator_policy import adopt_policy
from local_model_runtime_evaluation.run_identity import build_plan


ROOT = Path(__file__).resolve().parents[1]
RECIPE = ROOT / "config" / "managed-runs" / "complete-native-quality-v1.json"
POLICY = (
    ROOT
    / "config"
    / "operator-policies"
    / "local-managed-v1.example.json"
)


class EvidenceBundleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.results_root = self.root / "results"
        state_root = self.root / ".lmre"
        adopted = adopt_policy(
            POLICY,
            state_root,
            now=datetime(2026, 7, 30, 18, 0, tzinfo=timezone.utc),
        )
        plan = build_plan(
            RECIPE,
            family_id="gemma-4-12b-qat",
            run_name="evidence fixture",
            comparison_id=None,
            parent_run_id=None,
            results_root=self.results_root,
            now=datetime(2026, 7, 30, 18, 0, tzinfo=timezone.utc),
            entropy="a1b2c3",
        )
        self.bundle = EvidenceBundle.create(
            self.results_root,
            plan,
            adopted,
            {
                "platform": "macOS",
                "python": "3.11",
            },
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _seal_pass(self) -> None:
        self.bundle.mark_cleanup_complete()
        self.bundle.write_summary({"status": "PASS"})
        self.bundle.seal()

    def test_create_writes_immutable_inputs_and_pending_state(self) -> None:
        self.assertTrue((self.bundle.run_dir / "plan.json").is_file())
        self.assertTrue(
            (self.bundle.run_dir / "policy-snapshot.json").is_file()
        )
        self.assertTrue((self.bundle.run_dir / "environment.json").is_file())
        state = json.loads(
            (self.bundle.run_dir / "state.json").read_text(encoding="utf-8")
        )
        self.assertEqual(state["attempt"], 1)
        self.assertEqual(state["summary_state"], "PENDING")
        self.assertFalse(state["cleanup_complete"])
        self.assertFalse(state["sealed"])
        self.assertEqual(
            [record["step"] for record in state["steps"]],
            [step.value for step in self.bundle.plan.steps],
        )

    def test_journals_append_without_rewriting_prior_lines(self) -> None:
        self.bundle.append_event("plan_loaded", {"count": 1})
        first = (self.bundle.run_dir / "events.jsonl").read_text(
            encoding="utf-8"
        )
        self.bundle.append_event("policy_authorized", {"count": 2})
        second = (self.bundle.run_dir / "events.jsonl").read_text(
            encoding="utf-8"
        )
        self.assertTrue(second.startswith(first))
        lines = [json.loads(line) for line in second.splitlines()]
        self.assertEqual(
            [line["event_type"] for line in lines],
            ["plan_loaded", "policy_authorized"],
        )

    def test_secret_shaped_payload_key_is_rejected(self) -> None:
        with self.assertRaises(EvidenceError) as context:
            self.bundle.append_event(
                "unsafe",
                {"nested": {"api_key": "must-not-persist"}},
            )
        self.assertEqual(context.exception.code, "evidence_secret_rejected")
        self.assertFalse((self.bundle.run_dir / "events.jsonl").exists())

    def test_step_transition_table_fails_closed(self) -> None:
        self.bundle.transition_step(
            ManagedStep.PREFLIGHT,
            StepState.RUNNING,
        )
        self.bundle.transition_step(
            ManagedStep.PREFLIGHT,
            StepState.PASS,
            detail={"checked": True},
        )
        with self.assertRaises(EvidenceError) as context:
            self.bundle.transition_step(
                ManagedStep.PREFLIGHT,
                StepState.RUNNING,
            )
        self.assertEqual(
            context.exception.code,
            "evidence_transition_invalid",
        )

    def test_seal_then_verify_detects_tampering(self) -> None:
        self._seal_pass()
        self.bundle.verify()
        (self.bundle.run_dir / "summary.json").write_text(
            '{"status":"FAIL"}\n',
            encoding="utf-8",
        )
        with self.assertRaises(EvidenceError) as context:
            self.bundle.verify()
        self.assertEqual(
            context.exception.code,
            "evidence_checksum_mismatch",
        )

    def test_seal_requires_cleanup_complete(self) -> None:
        self.bundle.write_summary({"status": "PASS"})
        with self.assertRaises(EvidenceError) as context:
            self.bundle.seal()
        self.assertEqual(
            context.exception.code,
            "evidence_cleanup_incomplete",
        )

    def test_seal_requires_owned_release_and_attached_untouched(self) -> None:
        self.bundle.append_lifecycle(
            "omlx",
            "lease_acquired",
            {"lease_id": "lease-owned", "ownership": "owned"},
        )
        self.bundle.append_lifecycle(
            "osaurus",
            "lease_acquired",
            {"lease_id": "lease-attached", "ownership": "attached"},
        )
        self.bundle.mark_cleanup_complete()
        self.bundle.write_summary({"status": "PASS"})
        with self.assertRaises(EvidenceError):
            self.bundle.seal()
        self.bundle.append_lifecycle(
            "omlx",
            "released",
            {"lease_id": "lease-owned"},
        )
        self.bundle.append_lifecycle(
            "osaurus",
            "untouched",
            {"lease_id": "lease-attached"},
        )
        self.bundle.seal()
        self.bundle.verify()

    def test_resume_attempt_uses_new_directory_without_overwrite(self) -> None:
        self.bundle.transition_step(
            ManagedStep.OVERHEAD,
            StepState.RUNNING,
        )
        self.bundle.transition_step(
            ManagedStep.OVERHEAD,
            StepState.BLOCKED_PROVIDER_RECONNECT,
            detail={"missing_routed_model_ids": ["omlx/model-a"]},
        )
        first = self.bundle.step_attempt_dir(ManagedStep.OVERHEAD, 1)
        first.mkdir(parents=True)
        (first / "raw.json").write_text("{}\n", encoding="utf-8")
        self.bundle.mark_cleanup_complete()
        self.bundle.write_summary({"status": "PARTIAL_BLOCKED"})
        self.bundle.seal()
        self.bundle.verify()

        self.assertEqual(self.bundle.begin_attempt(), 2)
        second = self.bundle.step_attempt_dir(ManagedStep.OVERHEAD, 2)
        self.assertNotEqual(first, second)
        self.assertTrue((first / "raw.json").is_file())
        self.assertFalse(second.exists())
        state = self.bundle.state
        self.assertEqual(state.attempt, 2)
        overhead = next(
            record
            for record in state.steps
            if record.step is ManagedStep.OVERHEAD
        )
        self.assertEqual(overhead.state, StepState.PENDING)
        self.assertEqual(
            state.summary_state,
            RunSummaryState.PARTIAL_BLOCKED,
        )
        self.assertTrue(
            (self.bundle.run_dir / "attempts" / "attempt-001.json").is_file()
        )

    def test_begin_attempt_rejects_non_blocked_run(self) -> None:
        with self.assertRaises(EvidenceError) as context:
            self.bundle.begin_attempt()
        self.assertEqual(
            context.exception.code,
            "evidence_resume_not_allowed",
        )

    def test_begin_attempt_allows_sealed_overhead_failure_retry(self) -> None:
        for record in self.bundle.state.steps:
            self.bundle.transition_step(record.step, StepState.RUNNING)
            self.bundle.transition_step(
                record.step,
                (
                    StepState.FAIL
                    if record.step is ManagedStep.OVERHEAD
                    else StepState.PASS
                ),
            )
        self.bundle.mark_cleanup_complete()
        self.bundle.write_summary({"status": "FAIL"})
        self.bundle.seal()
        self.bundle.verify()

        self.assertEqual(self.bundle.begin_attempt(), 2)
        overhead = next(
            record
            for record in self.bundle.state.steps
            if record.step is ManagedStep.OVERHEAD
        )
        self.assertEqual(overhead.state, StepState.PENDING)
        self.assertEqual(overhead.attempt, 2)

    def test_verify_rejects_manifest_path_traversal(self) -> None:
        self._seal_pass()
        manifest = self.bundle.run_dir / "checksums.sha256"
        manifest.write_text(
            manifest.read_text(encoding="utf-8")
            + ("0" * 64)
            + "  ../outside\n",
            encoding="utf-8",
        )
        with self.assertRaises(EvidenceError) as context:
            self.bundle.verify()
        self.assertEqual(
            context.exception.code,
            "evidence_manifest_invalid",
        )

    def test_load_round_trip_uses_persisted_plan(self) -> None:
        loaded = EvidenceBundle.load(self.bundle.run_dir)
        self.assertEqual(loaded.plan.plan_hash, self.bundle.plan.plan_hash)
        self.assertEqual(loaded.state.run_id, self.bundle.plan.identity.run_id)


if __name__ == "__main__":
    unittest.main()
