from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from local_model_runtime_evaluation.lifecycle import LifecycleStore
from local_model_runtime_evaluation.models import Operation, RunStatus
from local_model_runtime_evaluation.runner import RunnerError, StageZeroRunner
from local_model_runtime_evaluation.worker import WorkerLauncher


class InferenceEngineStub:
    def __init__(self, manifest, output_root: Path) -> None:
        self.manifest = manifest
        self.lifecycle = LifecycleStore(output_root)
        self.output_root = output_root
        self.preflight_calls = 0
        self.cleanup_calls = 0
        self.lock_owned_during_cleanup = False

    def preflight(self) -> dict[str, object]:
        self.preflight_calls += 1
        self.lifecycle.create(self.manifest.run_id)
        self.lifecycle.transition(self.manifest.run_id, RunStatus.PREFLIGHT, "validated")
        self.lifecycle.transition(self.manifest.run_id, RunStatus.RESOURCE_GATE, "resources")
        state = self.lifecycle.transition(self.manifest.run_id, RunStatus.READY, "ready")
        return {"run_id": self.manifest.run_id, "state": state.status.value}

    def cleanup(self) -> dict[str, object]:
        self.cleanup_calls += 1
        self.lock_owned_during_cleanup = (
            (self.output_root / ".active-run.lock").read_text(encoding="utf-8").strip()
            == self.manifest.run_id
        )
        state = self.lifecycle.read(self.manifest.run_id)
        if state.status is not RunStatus.CLEANED:
            self.lifecycle.transition(self.manifest.run_id, RunStatus.CLEANED, "sealed")
        return {
            "run_id": self.manifest.run_id,
            "state": "cleaned",
            "checksum_validation": "PASS",
            "manual_shutdown_validation": "PASS",
        }


class FailingInferencePreflight(InferenceEngineStub):
    def preflight(self) -> dict[str, object]:
        self.preflight_calls += 1
        self.lifecycle.create(self.manifest.run_id)
        self.lifecycle.transition(self.manifest.run_id, RunStatus.PREFLIGHT, "validated")
        raise RuntimeError("inference host validation failed")


class RetryableInferenceCleanup(FailingInferencePreflight):
    cleanup_attempts = 0

    def cleanup(self) -> dict[str, object]:
        result = super().cleanup()
        type(self).cleanup_attempts += 1
        if type(self).cleanup_attempts == 1:
            raise RuntimeError("inference cleanup sealing failed")
        return result


class RecordingLauncher:
    def __init__(self) -> None:
        self.launched: list[tuple[str, Path]] = []
        self.cancelled: list[tuple[int, str]] = []

    def launch(self, run_id: str, log_path: Path) -> int:
        self.launched.append((run_id, log_path))
        return 6262

    def cancel(self, pid: int, run_id: str) -> None:
        self.cancelled.append((pid, run_id))


class StageTwoInferenceRunnerTest(unittest.TestCase):
    run_id = "stage2-20260720-901"

    def _runner(self, engine_type=InferenceEngineStub):
        if engine_type is RetryableInferenceCleanup:
            RetryableInferenceCleanup.cleanup_attempts = 0
        repo_temp = tempfile.TemporaryDirectory()
        output_temp = tempfile.TemporaryDirectory()
        self.addCleanup(repo_temp.cleanup)
        self.addCleanup(output_temp.cleanup)
        repo = Path(repo_temp.name)
        (repo / "manifests").mkdir()
        shutil.copy(
            Path(__file__).parent / "fixtures" / "valid-stage-2-inference-gemma.json",
            repo / "manifests" / "stage2-inference.json",
        )
        manifest_path = repo / "manifests" / "stage2-inference.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["expires_at"] = "2099-01-01T00:00:00Z"
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        output = Path(output_temp.name)
        engines: list[InferenceEngineStub] = []

        def factory(manifest, root):
            engine = engine_type(manifest, root)
            engines.append(engine)
            return engine

        launcher = RecordingLauncher()
        return StageZeroRunner(
            repo, output_root_override=output, stage_two_engine_factory=factory,
            worker_launcher=launcher,
        ), output, engines, launcher

    def test_preflight_acquires_the_inference_run_lock_and_invokes_the_engine(self) -> None:
        runner, output, engines, _ = self._runner()

        result = runner.dispatch(Operation.PREFLIGHT, self.run_id)

        self.assertEqual(result["state"], "ready")
        self.assertEqual(len(engines), 1)
        self.assertEqual(engines[0].preflight_calls, 1)
        self.assertEqual((output / ".active-run.lock").read_text(encoding="utf-8").strip(), self.run_id)

    def test_run_scenario_uses_only_the_fixed_stage_two_worker(self) -> None:
        runner, output, _, launcher = self._runner()
        runner.dispatch(Operation.PREFLIGHT, self.run_id)

        result = runner.dispatch(Operation.RUN_SCENARIO, self.run_id)

        self.assertEqual(result, {"run_id": self.run_id, "state": "running", "worker_pid": 6262})
        self.assertEqual(launcher.launched, [(self.run_id, output / self.run_id / "worker.log")])
        self.assertEqual(
            WorkerLauncher(Path("/fixed/lmre-stage0")).command(self.run_id),
            ["/fixed/lmre-stage0", "_stage2-worker", self.run_id],
        )

    def test_status_is_a_single_lifecycle_read_without_constructing_an_engine(self) -> None:
        runner, output, engines, _ = self._runner()
        lifecycle = LifecycleStore(output)
        lifecycle.create(self.run_id)

        result = runner.dispatch(Operation.STATUS, self.run_id)

        self.assertEqual(result, {"run_id": self.run_id, "state": "queued", "sequence": 0})
        self.assertEqual(engines, [])

    def test_cancel_signals_only_the_harness_owned_worker(self) -> None:
        runner, output, _, launcher = self._runner()
        runner.dispatch(Operation.PREFLIGHT, self.run_id)
        (output / self.run_id / "worker.json").write_text(json.dumps({"pid": 6262}), encoding="utf-8")

        result = runner.dispatch(Operation.CANCEL, self.run_id)

        self.assertTrue(result["cancellation_requested"])
        self.assertEqual(launcher.cancelled, [(6262, self.run_id)])

    def test_cleanup_runs_manual_shutdown_and_evidence_validation_before_lock_release(self) -> None:
        runner, output, engines, _ = self._runner()
        runner.dispatch(Operation.PREFLIGHT, self.run_id)
        LifecycleStore(output).transition(self.run_id, RunStatus.CANCELLED, "cancelled")

        result = runner.dispatch(Operation.CLEANUP, self.run_id)

        self.assertEqual(result["manual_shutdown_validation"], "PASS")
        self.assertEqual(result["checksum_validation"], "PASS")
        self.assertTrue(engines[-1].lock_owned_during_cleanup)
        self.assertFalse((output / ".active-run.lock").exists())

    def test_failed_preflight_cleanup_requires_engine_shutdown_validation_before_lock_release(self) -> None:
        runner, output, engines, _ = self._runner(FailingInferencePreflight)

        with self.assertRaises(RunnerError) as raised:
            runner.dispatch(Operation.PREFLIGHT, self.run_id)

        self.assertEqual(raised.exception.code, "stage_two_preflight_failed")
        self.assertEqual(engines[0].preflight_calls, 1)
        recovery = json.loads((output / self.run_id / "preflight-recovery.json").read_text(encoding="utf-8"))
        self.assertEqual(recovery["mode"], "operator_inference_probe")
        self.assertEqual(recovery["comparison_class"], "gemma-optiq-operator-route-smoke")
        self.assertEqual(recovery["http_post_attempts"], 0)
        self.assertTrue((output / ".active-run.lock").exists())

        result = runner.dispatch(Operation.CLEANUP, self.run_id)

        self.assertEqual(result["manual_shutdown_validation"], "PASS")
        self.assertEqual(result["checksum_validation"], "PASS")
        self.assertEqual(engines[-1].cleanup_calls, 1)
        self.assertTrue(engines[-1].lock_owned_during_cleanup)
        self.assertFalse((output / ".active-run.lock").exists())

    def test_cleanup_sealing_failure_retains_the_inference_lock_for_retry(self) -> None:
        runner, output, engines, _ = self._runner(RetryableInferenceCleanup)
        with self.assertRaises(RunnerError):
            runner.dispatch(Operation.PREFLIGHT, self.run_id)

        with self.assertRaisesRegex(RuntimeError, "inference cleanup sealing failed"):
            runner.dispatch(Operation.CLEANUP, self.run_id)

        self.assertTrue((output / ".active-run.lock").exists())
        self.assertTrue(engines[-1].lock_owned_during_cleanup)

        result = runner.dispatch(Operation.CLEANUP, self.run_id)
        self.assertEqual(result["checksum_validation"], "PASS")
        self.assertFalse((output / ".active-run.lock").exists())


if __name__ == "__main__":
    unittest.main()
