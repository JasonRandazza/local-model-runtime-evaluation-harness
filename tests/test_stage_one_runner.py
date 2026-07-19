from __future__ import annotations

import shutil
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from local_model_runtime_evaluation.benchmark_suite import BenchmarkSuite
from local_model_runtime_evaluation.credentials import Credential, FakeCredentialProvider
from local_model_runtime_evaluation.model_profiles import ModelProfileRegistry
from local_model_runtime_evaluation.models import Operation
from local_model_runtime_evaluation.resources import MemoryPressure, ResourceSnapshot
from local_model_runtime_evaluation.runner import StageZeroRunner
from local_model_runtime_evaluation.stage_one import StageOneEngine
from local_model_runtime_evaluation.transport import TransportResult


class FakeTransport:
    def list_models(self, base_url, credential):
        model_id = "omlx/VibeThinker-3B-MLX-oQ4" if ":1337" in base_url else "VibeThinker-3B-MLX-oQ4"
        return (model_id,)

    def chat(self, *args, **kwargs):
        return TransportResult("ok", "hash", 0.1, 1.0, 10, "stop", 200, True, 2, 0.6, 2, 8, "EXACT_VISIBLE")


class FakeLauncher:
    def launch(self, run_id, log_path):
        return 4242

    def cancel(self, pid, run_id):
        self.cancelled = (pid, run_id)


class StageOneRunnerTest(unittest.TestCase):
    def test_typed_runner_starts_fixed_worker_and_supports_status_cancel(self) -> None:
        project = Path(__file__).parents[1]
        with tempfile.TemporaryDirectory() as repo_temp, tempfile.TemporaryDirectory() as output_temp:
            repo = Path(repo_temp)
            (repo / "manifests").mkdir()
            shutil.copy(Path(__file__).parent / "fixtures" / "valid-stage-1.json", repo / "manifests" / "stage1.json")
            profile = ModelProfileRegistry(project / "config" / "model-profiles").get("vibethinker-3b-mlx-oq4", "3")
            suite = BenchmarkSuite.load(project / "suites" / "route-overhead-v1.json")
            output = Path(output_temp)

            def factory(manifest, output_root):
                return StageOneEngine(
                    manifest, profile, suite, output_root,
                    FakeCredentialProvider(Credential("test-key")),
                    ResourceSnapshot(MemoryPressure.NORMAL, (), None), FakeTransport(),
                )

            launcher = FakeLauncher()
            runner = StageZeroRunner(repo, output_root_override=output, stage_one_engine_factory=factory, worker_launcher=launcher)
            run_id = "stage1-20260713-001"
            self.assertEqual(runner.dispatch(Operation.PREFLIGHT, run_id)["state"], "ready")
            started = runner.dispatch(Operation.RUN_SCENARIO, run_id)
            self.assertEqual(started["state"], "running")
            self.assertEqual(started["worker_pid"], 4242)
            self.assertEqual(runner.dispatch(Operation.STATUS, run_id)["state"], "running")
            cancelled = runner.dispatch(Operation.CANCEL, run_id)
            self.assertEqual(cancelled["state"], "cancelled")
            self.assertEqual(launcher.cancelled, (4242, run_id))


if __name__ == "__main__":
    unittest.main()
