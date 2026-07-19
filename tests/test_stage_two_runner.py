from __future__ import annotations

import shutil
import tempfile
import unittest
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from local_model_runtime_evaluation.lifecycle import LifecycleStore
from local_model_runtime_evaluation.manifest import load_manifest
from local_model_runtime_evaluation.models import Operation, RunStatus
from local_model_runtime_evaluation.locking import RunLock
from local_model_runtime_evaluation.resources import ResourcePolicy
from local_model_runtime_evaluation.runner import RunnerError, StageZeroRunner
from local_model_runtime_evaluation.stage_two import StageTwoEngine
from local_model_runtime_evaluation.stage_two_factory import build_stage_two_engine
from local_model_runtime_evaluation.stage_two_inference import StageTwoInferenceEngine


class StubStageTwoEngine:
    def __init__(self, manifest, output_root: Path) -> None:
        self.manifest = manifest
        self.lifecycle = LifecycleStore(output_root)

    def preflight(self):
        self.lifecycle.create(self.manifest.run_id)
        self.lifecycle.transition(self.manifest.run_id, RunStatus.PREFLIGHT, "validated")
        self.lifecycle.transition(self.manifest.run_id, RunStatus.RESOURCE_GATE, "resources")
        state = self.lifecycle.transition(self.manifest.run_id, RunStatus.READY, "ready")
        return {"run_id": self.manifest.run_id, "state": state.status.value}

    def cleanup(self):
        state = self.lifecycle.transition(self.manifest.run_id, RunStatus.CLEANED, "cleaned")
        return {"run_id": self.manifest.run_id, "state": state.status.value, "checksum_validation": "PASS"}


class FailingPreflightStageTwoEngine:
    def __init__(self, manifest, output_root: Path) -> None:
        self.manifest = manifest
        self.lifecycle = LifecycleStore(output_root)
        self.cleanup_calls = 0

    def preflight(self):
        self.lifecycle.create(self.manifest.run_id)
        self.lifecycle.transition(self.manifest.run_id, RunStatus.PREFLIGHT, "validated")
        raise RuntimeError("host validation failed")

    def cleanup(self):
        self.cleanup_calls += 1
        raise AssertionError("preflight recovery must not touch the operator cleanup path")


class RecoveringCleanupStageTwoEngine(StubStageTwoEngine):
    cleanup_attempts = 0

    def cleanup(self):
        type(self).cleanup_attempts += 1
        state = self.lifecycle.read(self.manifest.run_id)
        if state.status is not RunStatus.CLEANED:
            self.lifecycle.transition(self.manifest.run_id, RunStatus.CLEANED, "cleaned")
        if type(self).cleanup_attempts == 1:
            raise RuntimeError("injected post-transition seal failure")
        return {
            "run_id": self.manifest.run_id,
            "state": "cleaned",
            "disposition": "PASS",
            "checksum_validation": "PASS",
        }


class FakeLauncher:
    def launch(self, run_id, log_path):
        return 5252

    def cancel(self, pid, run_id):
        self.cancelled = (pid, run_id)


class StageTwoRunnerTest(unittest.TestCase):
    def test_factory_selects_the_exact_engine_for_each_active_schema_and_mode(self) -> None:
        root = Path(__file__).parents[1]
        route_manifest = load_manifest(
            Path(__file__).parent / "fixtures" / "valid-stage-2.json",
        )
        inference_manifest = load_manifest(
            Path(__file__).parent / "fixtures" / "valid-stage-2-inference.json",
            now=datetime(2026, 7, 15, tzinfo=timezone.utc),
        )

        route_engine = build_stage_two_engine(root, route_manifest, Path(tempfile.mkdtemp()))
        with tempfile.TemporaryDirectory() as output_temp, patch(
            "local_model_runtime_evaluation.stage_two_factory.HostResourceProbe.free_memory_percent",
            return_value=80,
        ):
            output_root = Path(output_temp)
            inference_engine = build_stage_two_engine(root, inference_manifest, output_root)
            lock = RunLock(output_root)
            lock.acquire(inference_manifest.run_id)
            try:
                snapshot = inference_engine.resource_probe({"loaded": [], "resident_models": []})
                decision = ResourcePolicy(inference_engine.profile.coordinator_model_id).evaluate(snapshot)
            finally:
                lock.release(inference_manifest.run_id)

        self.assertIsInstance(route_engine, StageTwoEngine)
        self.assertIsInstance(inference_engine, StageTwoInferenceEngine)
        self.assertIsNone(snapshot.active_run_id)
        self.assertTrue(decision.allowed)
        self.assertEqual(
            inference_engine.transport._read.allowed_base_urls,
            frozenset(inference_manifest.routes.values()),
        )
        self.assertEqual(inference_engine.transport._read.timeout_seconds, 120)

    def test_factory_rejects_mixed_schema_and_mode_before_constructing_transport(self) -> None:
        root = Path(__file__).parents[1]
        route_manifest = load_manifest(
            Path(__file__).parent / "fixtures" / "valid-stage-2.json",
        )
        inference_manifest = load_manifest(
            Path(__file__).parent / "fixtures" / "valid-stage-2-inference.json",
            now=datetime(2026, 7, 15, tzinfo=timezone.utc),
        )
        mixed_manifests = (
            replace(route_manifest, mode="operator_inference_probe"),
            replace(inference_manifest, schema_version="3.1.0"),
            replace(inference_manifest, mode="operator_route_probe"),
            replace(inference_manifest, comparison_class="unapproved"),
            replace(inference_manifest, runtime_profile_id="unapproved-profile"),
            replace(inference_manifest, runtime_profile_revision="4"),
            replace(inference_manifest, suite_id="unapproved-suite"),
            replace(inference_manifest, suite_revision="2"),
            replace(inference_manifest, repetitions=2),
            replace(inference_manifest, route_order="sequential"),
            replace(inference_manifest, routes={"direct": "http://127.0.0.1:8080/v1"}),
            replace(inference_manifest, limits={"request_timeout_seconds": 121}),
            replace(inference_manifest, operations=tuple(reversed(inference_manifest.operations))),
        )

        with patch("local_model_runtime_evaluation.stage_two_factory.RuntimeProfileRegistry") as registry, patch(
            "local_model_runtime_evaluation.stage_two_factory.StageTwoSmokeSuite.load"
        ) as suite, patch(
            "local_model_runtime_evaluation.stage_two_factory.StageTwoReadOnlyTransport"
        ) as read_transport, patch(
            "local_model_runtime_evaluation.stage_two_factory.StageTwoInferenceTransport"
        ) as inference_transport, patch(
            "local_model_runtime_evaluation.stage_two_factory.OperatorOptiQController"
        ) as controller:
            for manifest in mixed_manifests:
                with self.assertRaisesRegex(ValueError, "unsupported Stage 2 mode"):
                    build_stage_two_engine(root, manifest, Path(tempfile.mkdtemp()))

        registry.assert_not_called()
        suite.assert_not_called()
        read_transport.assert_not_called()
        inference_transport.assert_not_called()
        controller.assert_not_called()

    def test_runner_starts_fixed_worker_and_requests_cooperative_cancel(self) -> None:
        with tempfile.TemporaryDirectory() as repo_temp, tempfile.TemporaryDirectory() as output_temp:
            repo = Path(repo_temp)
            (repo / "manifests").mkdir()
            shutil.copy(
                Path(__file__).parent / "fixtures" / "valid-stage-2.json",
                repo / "manifests" / "stage2.json",
            )
            launcher = FakeLauncher()
            runner = StageZeroRunner(
                repo, output_root_override=Path(output_temp),
                stage_two_engine_factory=lambda manifest, output: StubStageTwoEngine(manifest, output),
                worker_launcher=launcher,
            )
            run_id = "stage2-20260714-001"
            self.assertEqual(runner.dispatch(Operation.PREFLIGHT, run_id)["state"], "ready")
            started = runner.dispatch(Operation.RUN_SCENARIO, run_id)
            self.assertEqual(started["state"], "running")
            self.assertEqual(started["worker_pid"], 5252)
            cancelled = runner.dispatch(Operation.CANCEL, run_id)
            self.assertEqual(cancelled["state"], "running")
            self.assertTrue(cancelled["cancellation_requested"])
            self.assertEqual(launcher.cancelled, (5252, run_id))

    def test_terminal_cleanup_delegates_shutdown_verification_to_engine(self) -> None:
        with tempfile.TemporaryDirectory() as repo_temp, tempfile.TemporaryDirectory() as output_temp:
            repo = Path(repo_temp)
            (repo / "manifests").mkdir()
            shutil.copy(
                Path(__file__).parent / "fixtures" / "valid-stage-2.json",
                repo / "manifests" / "stage2.json",
            )
            output = Path(output_temp)
            runner = StageZeroRunner(
                repo, output_root_override=output,
                stage_two_engine_factory=lambda manifest, root: StubStageTwoEngine(manifest, root),
                worker_launcher=FakeLauncher(),
            )
            run_id = "stage2-20260714-001"
            runner.dispatch(Operation.PREFLIGHT, run_id)
            LifecycleStore(output).transition(run_id, RunStatus.CANCELLED, "cancelled")
            result = runner.dispatch(Operation.CLEANUP, run_id)
            self.assertEqual(result["state"], "cleaned")
            self.assertEqual(result["checksum_validation"], "PASS")

    def test_failed_preflight_preserves_evidence_for_manager_cleanup_without_operator_cleanup(self) -> None:
        with tempfile.TemporaryDirectory() as repo_temp, tempfile.TemporaryDirectory() as output_temp:
            repo = Path(repo_temp)
            (repo / "manifests").mkdir()
            shutil.copy(
                Path(__file__).parent / "fixtures" / "valid-stage-2.json",
                repo / "manifests" / "stage2.json",
            )
            output = Path(output_temp)
            engine: FailingPreflightStageTwoEngine | None = None

            def factory(manifest, root):
                nonlocal engine
                engine = FailingPreflightStageTwoEngine(manifest, root)
                return engine

            runner = StageZeroRunner(
                repo,
                output_root_override=output,
                stage_two_engine_factory=factory,
                worker_launcher=FakeLauncher(),
            )
            run_id = "stage2-20260714-001"

            with self.assertRaises(RunnerError) as raised:
                runner.dispatch(Operation.PREFLIGHT, run_id)

            self.assertEqual(raised.exception.code, "stage_two_preflight_failed")
            self.assertEqual(LifecycleStore(output).read(run_id).status, RunStatus.FAILED)
            self.assertTrue((output / run_id / "preflight-recovery.json").is_file())
            self.assertTrue((output / ".active-run.lock").is_file())

            result = runner.dispatch(Operation.CLEANUP, run_id)

            self.assertEqual(result["state"], "cleaned")
            self.assertEqual(result["disposition"], "STOPPED")
            self.assertEqual(result["checksum_validation"], "PASS")
            self.assertTrue(result["manager_review_required"])
            self.assertEqual(result["service_lifecycle_actions"], 0)
            self.assertIsNotNone(engine)
            self.assertEqual(engine.cleanup_calls, 0)
            self.assertFalse((output / ".active-run.lock").exists())

    def test_cleaned_state_retries_engine_validation_before_releasing_lock(self) -> None:
        with tempfile.TemporaryDirectory() as repo_temp, tempfile.TemporaryDirectory() as output_temp:
            repo = Path(repo_temp)
            (repo / "manifests").mkdir()
            shutil.copy(
                Path(__file__).parent / "fixtures" / "valid-stage-2.json",
                repo / "manifests" / "stage2.json",
            )
            output = Path(output_temp)
            RecoveringCleanupStageTwoEngine.cleanup_attempts = 0
            runner = StageZeroRunner(
                repo, output_root_override=output,
                stage_two_engine_factory=lambda manifest, root: RecoveringCleanupStageTwoEngine(manifest, root),
                worker_launcher=FakeLauncher(),
            )
            run_id = "stage2-20260714-001"
            runner.dispatch(Operation.PREFLIGHT, run_id)
            LifecycleStore(output).transition(run_id, RunStatus.CANCELLED, "cancelled")

            with self.assertRaisesRegex(RuntimeError, "injected post-transition"):
                runner.dispatch(Operation.CLEANUP, run_id)
            self.assertTrue((output / ".active-run.lock").exists())
            self.assertEqual(LifecycleStore(output).read(run_id).status, RunStatus.CLEANED)

            result = runner.dispatch(Operation.CLEANUP, run_id)
            self.assertEqual(result["checksum_validation"], "PASS")
            self.assertEqual(RecoveringCleanupStageTwoEngine.cleanup_attempts, 2)
            self.assertFalse((output / ".active-run.lock").exists())


if __name__ == "__main__":
    unittest.main()
