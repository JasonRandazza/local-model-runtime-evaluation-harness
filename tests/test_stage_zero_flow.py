from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from local_model_runtime_evaluation.models import Operation
from local_model_runtime_evaluation.runner import StageZeroRunner


class StageZeroFlowTest(unittest.TestCase):
    def test_preflight_cancel_cleanup_flow(self) -> None:
        root = Path(__file__).parents[1]
        with tempfile.TemporaryDirectory() as temp:
            runner = StageZeroRunner(root, output_root_override=Path(temp))
            run_id = "stage0-20260713-002"
            preflight = runner.dispatch(Operation.PREFLIGHT, run_id)
            self.assertEqual(preflight["state"], "ready")
            self.assertEqual(preflight["manifest_validation"], "PASS")
            self.assertEqual(preflight["manifest"]["schema_version"], "1.0.0")
            self.assertEqual(preflight["manifest"]["mode"], "dry_run")
            self.assertEqual(len(preflight["manifest"]["operations"]), 6)
            self.assertEqual(runner.dispatch(Operation.RUN_SCENARIO, run_id)["state"], "running")
            self.assertEqual(runner.dispatch(Operation.CANCEL, run_id)["state"], "cancelled")
            result = runner.dispatch(Operation.CLEANUP, run_id)
            self.assertEqual(result["state"], "cleaned")
            self.assertEqual(result["disposition"], "STOPPED")
            self.assertEqual(
                result["state_sequence"],
                ["queued", "preflight", "ready", "running", "cancelled", "cleaned"],
            )
            self.assertEqual(result["artifact_validation"], "PASS")
            self.assertEqual(result["checksum_validation"], "PASS")
            self.assertTrue(result["required_artifacts_present"])
            self.assertEqual(
                set(result["artifacts"]),
                {
                    "manifest.json",
                    "preflight.json",
                    "inventory.json",
                    "lifecycle.jsonl",
                    "summary.json",
                    "checksums.txt",
                },
            )
            self.assertEqual(result["harness_model_load_attempts"], 0)
            self.assertEqual(result["harness_inference_request_attempts"], 0)
            self.assertEqual(result["network_calls_attempted"], 0)
            self.assertTrue(runner.validate_bundle(run_id)["valid"])


if __name__ == "__main__":
    unittest.main()
