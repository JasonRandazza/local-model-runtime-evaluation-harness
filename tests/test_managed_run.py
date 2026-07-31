from __future__ import annotations

import json
import unittest
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch

from local_model_runtime_evaluation.credentials import Credential
from local_model_runtime_evaluation.evidence_bundle import EvidenceBundle
from local_model_runtime_evaluation.managed_run import (
    ManagedCollectorHooks,
    default_collector_hooks,
    execute_managed_run,
    resume_managed_run,
)
from local_model_runtime_evaluation.managed_run_types import (
    ManagedStep,
    StepState,
)
from local_model_runtime_evaluation.operator_policy import (
    AdoptedPolicy,
    OperatorPolicy,
    adopt_policy,
    canonical_hash,
)
from local_model_runtime_evaluation.overhead_config import (
    DEFAULT_PAIRS_ROOT,
    OverheadPair,
)
from local_model_runtime_evaluation.run_identity import build_plan


ROOT = Path(__file__).resolve().parents[1]
RECIPE = ROOT / "config" / "managed-runs" / "complete-native-quality-v1.json"
POLICY = (
    ROOT
    / "config"
    / "operator-policies"
    / "local-managed-v1.example.json"
)


def _required_routes(pair_ids: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(
        OverheadPair.load(DEFAULT_PAIRS_ROOT / f"{pair_id}.json").routed_model_id
        for pair_id in pair_ids
    )


class FakeRuntimeManager:
    def __init__(self, *, cleanup_error: Exception | None = None) -> None:
        self.cleanup_error = cleanup_error
        self.release_all_called = False
        self.build_server = object()

    def release_all(self) -> None:
        self.release_all_called = True
        if self.cleanup_error is not None:
            raise self.cleanup_error


class FakeHooks:
    def __init__(
        self,
        plan,
        *,
        fail_at: str | None = None,
        interrupt_at: str | None = None,
        routed_models: tuple[str, ...] | None = None,
    ) -> None:
        self.plan = plan
        self.fail_at = fail_at
        self.interrupt_at = interrupt_at
        self.models = (
            _required_routes(plan.pair_ids)
            if routed_models is None
            else routed_models
        )
        self.calls: list[str] = []
        self.overhead_called = False

    def _run(self, name: str, output_root: Path) -> Path:
        self.calls.append(name)
        if self.interrupt_at == name:
            raise KeyboardInterrupt
        if self.fail_at == name:
            raise RuntimeError(f"{name} failed")
        run_dir = output_root / f"{name}-result"
        run_dir.mkdir(parents=True)
        (run_dir / "raw.json").write_text("{}\n", encoding="utf-8")
        return run_dir

    def hooks(self) -> ManagedCollectorHooks:
        def preflight(plan) -> dict[str, object]:
            self.calls.append("preflight")
            if self.interrupt_at == "preflight":
                raise KeyboardInterrupt
            if self.fail_at == "preflight":
                raise RuntimeError("preflight failed")
            return {"artifact_count": len(plan.cell_ids)}

        def matrix(plan, output_root, build_server) -> Path:
            del plan, build_server
            return self._run("matrix", output_root)

        def preference(plan, output_root, build_server) -> Path:
            del plan, build_server
            return self._run("preference", output_root)

        def rag_oracle(plan, output_root, build_server) -> Path:
            del plan, build_server
            return self._run("rag-oracle", output_root)

        def rag_keyword(plan, output_root, build_server) -> Path:
            del plan, build_server
            return self._run("rag-keyword", output_root)

        def routed_models(plan) -> tuple[str, ...]:
            del plan
            self.calls.append("route-check")
            return self.models

        def overhead(plan, output_root, build_server) -> Path:
            del plan, build_server
            self.overhead_called = True
            return self._run("overhead", output_root)

        return ManagedCollectorHooks(
            preflight=preflight,
            matrix=matrix,
            preference=preference,
            rag_oracle=rag_oracle,
            rag_keyword=rag_keyword,
            routed_models=routed_models,
            overhead=overhead,
        )


class ManagedRunTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.results_root = self.root / "results"
        self.adopted = adopt_policy(
            POLICY,
            self.root / ".lmre",
            now=datetime(2026, 7, 30, 18, 0, tzinfo=timezone.utc),
        )
        self.plan = build_plan(
            RECIPE,
            family_id="gemma-4-12b-qat",
            run_name="managed fixture",
            comparison_id=None,
            parent_run_id=None,
            results_root=self.results_root,
            now=datetime(2026, 7, 30, 18, 0, tzinfo=timezone.utc),
            entropy="a1b2c3",
        )
        self.bundle = EvidenceBundle.create(
            self.results_root,
            self.plan,
            self.adopted,
            {"platform": "test"},
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _step_state(self, step: ManagedStep) -> StepState:
        return next(
            record.state
            for record in self.bundle.state.steps
            if record.step is step
        )

    def test_normal_run_calls_collectors_in_immutable_order(self) -> None:
        fake = FakeHooks(self.plan)
        manager = FakeRuntimeManager()
        summary = execute_managed_run(
            self.plan,
            self.adopted,
            self.bundle,
            manager,
            fake.hooks(),
        )
        self.assertEqual(
            fake.calls,
            [
                "preflight",
                "matrix",
                "preference",
                "rag-oracle",
                "rag-keyword",
                "route-check",
                "overhead",
            ],
        )
        self.assertEqual(summary["status"], "PASS")
        self.assertTrue(manager.release_all_called)
        self.assertTrue(self.bundle.state.sealed)
        self.bundle.verify()

    def test_collector_failure_stops_dependent_steps_and_seals(self) -> None:
        fake = FakeHooks(self.plan, fail_at="preference")
        manager = FakeRuntimeManager()
        summary = execute_managed_run(
            self.plan,
            self.adopted,
            self.bundle,
            manager,
            fake.hooks(),
        )
        self.assertEqual(summary["status"], "FAIL")
        self.assertEqual(
            self._step_state(ManagedStep.PREFERENCE),
            StepState.FAIL,
        )
        self.assertEqual(
            self._step_state(ManagedStep.RAG_ORACLE),
            StepState.STOPPED,
        )
        self.assertTrue(manager.release_all_called)
        self.bundle.verify()

    def test_keyboard_interrupt_records_stopped_and_seals(self) -> None:
        fake = FakeHooks(self.plan, interrupt_at="rag-oracle")
        manager = FakeRuntimeManager()
        summary = execute_managed_run(
            self.plan,
            self.adopted,
            self.bundle,
            manager,
            fake.hooks(),
        )
        self.assertEqual(summary["status"], "STOPPED")
        self.assertEqual(
            self._step_state(ManagedStep.RAG_ORACLE),
            StepState.STOPPED,
        )
        self.bundle.verify()

    def test_policy_denial_occurs_before_preflight(self) -> None:
        restrictive_body = self.adopted.policy.to_dict()
        restrictive_body["max_requests_per_run"] = 50
        restrictive_policy = OperatorPolicy.from_dict(restrictive_body)
        restrictive = AdoptedPolicy(
            restrictive_policy,
            canonical_hash(restrictive_policy.to_dict()),
            self.adopted.adopted_at,
        )
        fake = FakeHooks(self.plan)
        manager = FakeRuntimeManager()
        summary = execute_managed_run(
            self.plan,
            restrictive,
            self.bundle,
            manager,
            fake.hooks(),
        )
        self.assertEqual(summary["status"], "FAIL")
        self.assertEqual(fake.calls, [])
        self.assertTrue(manager.release_all_called)
        self.bundle.verify()

    def test_initial_run_rejects_changed_policy_snapshot_before_preflight(
        self,
    ) -> None:
        changed_body = self.adopted.policy.to_dict()
        changed_body["max_run_minutes"] = 91
        changed_policy = OperatorPolicy.from_dict(changed_body)
        changed = AdoptedPolicy(
            changed_policy,
            canonical_hash(changed_policy.to_dict()),
            self.adopted.adopted_at,
        )
        fake = FakeHooks(self.plan)

        summary = execute_managed_run(
            self.plan,
            changed,
            self.bundle,
            FakeRuntimeManager(),
            fake.hooks(),
        )

        self.assertEqual(summary["status"], "FAIL")
        self.assertEqual(fake.calls, [])
        persisted = json.loads(
            (self.bundle.run_dir / "summary.json").read_text(encoding="utf-8")
        )
        self.assertIn(
            "does not match the run policy snapshot",
            persisted["error"]["error_message"],
        )

    def test_initial_run_rejects_readoption_after_planning(self) -> None:
        readopted = AdoptedPolicy(
            self.adopted.policy,
            self.adopted.policy_hash,
            "2026-07-30T19:00:00+00:00",
        )
        fake = FakeHooks(self.plan)

        summary = execute_managed_run(
            self.plan,
            readopted,
            self.bundle,
            FakeRuntimeManager(),
            fake.hooks(),
        )

        self.assertEqual(summary["status"], "FAIL")
        self.assertEqual(fake.calls, [])

    def test_preflight_failure_starts_no_collector(self) -> None:
        fake = FakeHooks(self.plan, fail_at="preflight")
        summary = execute_managed_run(
            self.plan,
            self.adopted,
            self.bundle,
            FakeRuntimeManager(),
            fake.hooks(),
        )
        self.assertEqual(summary["status"], "FAIL")
        self.assertEqual(fake.calls, ["preflight"])
        self.assertEqual(
            self._step_state(ManagedStep.MATRIX),
            StepState.STOPPED,
        )

    def test_collector_outputs_remain_inside_step_attempt_directory(self) -> None:
        fake = FakeHooks(self.plan)
        execute_managed_run(
            self.plan,
            self.adopted,
            self.bundle,
            FakeRuntimeManager(),
            fake.hooks(),
        )
        preference = next(
            record
            for record in self.bundle.state.steps
            if record.step is ManagedStep.PREFERENCE
        )
        self.assertEqual(
            preference.output_path,
            "steps/preference/attempt-001/preference-result",
        )

    def test_cleanup_failure_prevents_pass_and_seal(self) -> None:
        fake = FakeHooks(self.plan)
        manager = FakeRuntimeManager(
            cleanup_error=RuntimeError("cleanup failed")
        )
        summary = execute_managed_run(
            self.plan,
            self.adopted,
            self.bundle,
            manager,
            fake.hooks(),
        )
        self.assertEqual(summary["status"], "FAIL")
        self.assertFalse(self.bundle.state.sealed)
        self.assertFalse(
            (self.bundle.run_dir / "checksums.sha256").exists()
        )

    def test_persisted_error_message_is_sanitized(self) -> None:
        fake = FakeHooks(self.plan)

        def unsafe_preflight(plan) -> dict[str, object]:
            del plan
            raise RuntimeError("api_key=do-not-persist")

        hooks = fake.hooks()
        hooks = ManagedCollectorHooks(
            preflight=unsafe_preflight,
            matrix=hooks.matrix,
            preference=hooks.preference,
            rag_oracle=hooks.rag_oracle,
            rag_keyword=hooks.rag_keyword,
            routed_models=hooks.routed_models,
            overhead=hooks.overhead,
        )
        execute_managed_run(
            self.plan,
            self.adopted,
            self.bundle,
            FakeRuntimeManager(),
            hooks,
        )
        summary = json.loads(
            (self.bundle.run_dir / "summary.json").read_text(encoding="utf-8")
        )
        self.assertNotIn("do-not-persist", json.dumps(summary))
        self.assertIn("<redacted>", json.dumps(summary))

    def test_missing_route_preserves_native_steps_and_blocks_overhead(
        self,
    ) -> None:
        fake = FakeHooks(self.plan, routed_models=())
        summary = execute_managed_run(
            self.plan,
            self.adopted,
            self.bundle,
            FakeRuntimeManager(),
            fake.hooks(),
        )
        self.assertEqual(summary["status"], "PARTIAL_BLOCKED")
        self.assertEqual(
            self._step_state(ManagedStep.RAG_KEYWORD),
            StepState.PASS,
        )
        self.assertEqual(
            self._step_state(ManagedStep.OVERHEAD),
            StepState.BLOCKED_PROVIDER_RECONNECT,
        )
        self.assertFalse(fake.overhead_called)
        self.bundle.verify()

    def test_default_route_check_starts_managed_osaurus_first(self) -> None:
        handle = MagicMock()
        manager = MagicMock()
        manager.build_server.return_value = handle
        required = _required_routes(self.plan.pair_ids)
        with patch(
            "local_model_runtime_evaluation.managed_run."
            "KeychainCredentialProvider.get",
            return_value=Credential("local-test-key"),
        ), patch(
            "local_model_runtime_evaluation.managed_run."
            "LoopbackTransport.list_models",
            return_value=required,
        ):
            hooks = default_collector_hooks(
                self.plan,
                manager,
                self.bundle,
            )
            models = hooks.routed_models(self.plan)

        self.assertEqual(models, required)
        managed_cell = manager.build_server.call_args.args[0]
        self.assertEqual(managed_cell.server, "osaurus")
        handle.start.assert_called_once_with()
        handle.wait_ready.assert_called_once_with(
            managed_cell.model_id,
            180.0,
        )

    def test_resume_runs_only_overhead_and_preserves_attempt_one(self) -> None:
        execute_managed_run(
            self.plan,
            self.adopted,
            self.bundle,
            FakeRuntimeManager(),
            FakeHooks(self.plan, routed_models=()).hooks(),
        )
        native_raw = (
            self.bundle.run_dir
            / "steps"
            / "rag-keyword"
            / "attempt-001"
            / "rag-keyword-result"
            / "raw.json"
        )
        before = native_raw.read_bytes()
        fake = FakeHooks(self.plan)
        summary = resume_managed_run(
            self.bundle.run_dir,
            self.adopted,
            FakeRuntimeManager(),
            fake.hooks(),
        )
        self.assertEqual(fake.calls, ["route-check", "overhead"])
        self.assertEqual(summary["status"], "PASS")
        self.assertEqual(native_raw.read_bytes(), before)
        self.assertTrue(
            (
                self.bundle.run_dir
                / "steps"
                / "overhead"
                / "attempt-002"
            ).is_dir()
        )
        EvidenceBundle.load(self.bundle.run_dir).verify()

    def test_resume_unseals_before_route_check_writes_evidence(self) -> None:
        execute_managed_run(
            self.plan,
            self.adopted,
            self.bundle,
            FakeRuntimeManager(),
            FakeHooks(self.plan, routed_models=()).hooks(),
        )
        fake = FakeHooks(self.plan)
        hooks = fake.hooks()

        def routed_models(plan) -> tuple[str, ...]:
            del plan
            self.bundle.append_event("route_probe", {})
            fake.calls.append("route-check")
            return fake.models

        writing_hooks = ManagedCollectorHooks(
            preflight=hooks.preflight,
            matrix=hooks.matrix,
            preference=hooks.preference,
            rag_oracle=hooks.rag_oracle,
            rag_keyword=hooks.rag_keyword,
            routed_models=routed_models,
            overhead=hooks.overhead,
        )

        summary = resume_managed_run(
            self.bundle.run_dir,
            self.adopted,
            FakeRuntimeManager(),
            writing_hooks,
        )

        self.assertEqual(summary["status"], "PASS")
        EvidenceBundle.load(self.bundle.run_dir).verify()

    def test_resume_retries_sealed_overhead_failure(self) -> None:
        failed = execute_managed_run(
            self.plan,
            self.adopted,
            self.bundle,
            FakeRuntimeManager(),
            FakeHooks(self.plan, fail_at="overhead").hooks(),
        )
        self.assertEqual(failed["status"], "FAIL")

        summary = resume_managed_run(
            self.bundle.run_dir,
            self.adopted,
            FakeRuntimeManager(),
            FakeHooks(self.plan).hooks(),
        )

        self.assertEqual(summary["status"], "PASS")
        self.assertEqual(summary["attempt"], 2)
        EvidenceBundle.load(self.bundle.run_dir).verify()

    def test_resume_rejects_missing_route_without_unsealing(self) -> None:
        execute_managed_run(
            self.plan,
            self.adopted,
            self.bundle,
            FakeRuntimeManager(),
            FakeHooks(self.plan, routed_models=()).hooks(),
        )
        with self.assertRaises(RuntimeError):
            resume_managed_run(
                self.bundle.run_dir,
                self.adopted,
                FakeRuntimeManager(),
                FakeHooks(self.plan, routed_models=()).hooks(),
            )
        self.assertTrue(EvidenceBundle.load(self.bundle.run_dir).state.sealed)

    def test_resume_rejects_second_active_writer(self) -> None:
        execute_managed_run(
            self.plan,
            self.adopted,
            self.bundle,
            FakeRuntimeManager(),
            FakeHooks(self.plan, routed_models=()).hooks(),
        )
        lock = self.bundle.run_dir / ".resume.lock"
        lock.write_text("", encoding="utf-8")
        try:
            with self.assertRaises(RuntimeError):
                resume_managed_run(
                    self.bundle.run_dir,
                    self.adopted,
                    FakeRuntimeManager(),
                    FakeHooks(self.plan).hooks(),
                )
        finally:
            lock.unlink()

    def test_resume_rejects_changed_policy_hash(self) -> None:
        execute_managed_run(
            self.plan,
            self.adopted,
            self.bundle,
            FakeRuntimeManager(),
            FakeHooks(self.plan, routed_models=()).hooks(),
        )
        changed_body = self.adopted.policy.to_dict()
        changed_body["max_run_minutes"] = 91
        changed_policy = OperatorPolicy.from_dict(changed_body)
        changed = AdoptedPolicy(
            changed_policy,
            canonical_hash(changed_policy.to_dict()),
            self.adopted.adopted_at,
        )
        with self.assertRaises(RuntimeError):
            resume_managed_run(
                self.bundle.run_dir,
                changed,
                FakeRuntimeManager(),
                FakeHooks(self.plan).hooks(),
            )


if __name__ == "__main__":
    unittest.main()
