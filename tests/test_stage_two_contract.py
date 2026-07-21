from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from local_model_runtime_evaluation.artifacts import (
    ArtifactBundle,
    STAGE_TWO_INFERENCE_REQUIRED_FILES,
    STAGE_TWO_REVISION_THREE_REQUIRED_FILES,
)
from local_model_runtime_evaluation.lifecycle import LifecycleStore
from local_model_runtime_evaluation.manifest import load_manifest
from local_model_runtime_evaluation.models import RunStatus
from local_model_runtime_evaluation.worker import WorkerLauncher


class StageTwoContractTest(unittest.TestCase):
    def test_stage_two_inference_bundle_requires_only_the_stage_2b_evidence_contract(self) -> None:
        manifest = load_manifest(
            Path(__file__).parent / "fixtures" / "valid-stage-2-inference-gemma.json",
            now=datetime(2026, 7, 20, tzinfo=timezone.utc),
        )
        with tempfile.TemporaryDirectory() as temp:
            bundle = ArtifactBundle.create(manifest, Path(temp))
            jsonl = {
                "lifecycle.jsonl", "service-events.jsonl", "memory-samples.jsonl",
                "request-evidence.jsonl", "raw-runs.jsonl", "post-attempts.jsonl",
            }
            for name in STAGE_TWO_INFERENCE_REQUIRED_FILES - {"manifest.json", "summary.json"} - jsonl:
                bundle.write_json(name, {"ok": True})
            for name in jsonl:
                bundle.append_jsonl(name, {"ok": True})
            bundle.finalize({"disposition": "PASS"})
            self.assertTrue(bundle.validate().valid)

    def test_lifecycle_records_operator_observation_sequence(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store = LifecycleStore(Path(temp))
            run_id = "stage2-20260714-001"
            store.create(run_id)
            for status in (
                RunStatus.PREFLIGHT, RunStatus.RESOURCE_GATE, RunStatus.READY,
                RunStatus.RUNNING, RunStatus.SERVICE_READY, RunStatus.ENDPOINT_IDENTITY,
                RunStatus.ARTIFACT_VALIDATION, RunStatus.AWAITING_REVIEW, RunStatus.CLEANED,
            ):
                store.transition(run_id, status, status.value)
            self.assertEqual(store.history(run_id)[-4:], [
                "endpoint_identity", "artifact_validation", "awaiting_review", "cleaned"
            ])

    def test_worker_command_is_fixed_for_stage_two(self) -> None:
        launcher = WorkerLauncher(Path("/fixed/bin/lmre-stage0"))
        self.assertEqual(launcher.command("stage2-20260714-001"), [
            "/fixed/bin/lmre-stage0", "_stage2-worker", "stage2-20260714-001"
        ])
        self.assertTrue(launcher.matches_process_command(
            "python3 /fixed/bin/lmre-stage0 _stage2-worker stage2-20260714-001",
            "stage2-20260714-001",
        ))

    def test_stage_two_bundle_requires_operator_observation_evidence(self) -> None:
        manifest = load_manifest(
            Path(__file__).parent / "fixtures" / "valid-stage-2.json",
            now=datetime(2026, 7, 14, tzinfo=timezone.utc),
        )
        with tempfile.TemporaryDirectory() as temp:
            bundle = ArtifactBundle.create(manifest, Path(temp))
            jsonl = {
                "lifecycle.jsonl", "service-events.jsonl", "memory-samples.jsonl",
                "request-evidence.jsonl",
            }
            for name in STAGE_TWO_REVISION_THREE_REQUIRED_FILES - {"manifest.json", "summary.json"} - jsonl:
                bundle.write_json(name, {"ok": True})
            for name in jsonl:
                bundle.append_jsonl(name, {"ok": True})
            bundle.finalize({
                "disposition": "PASS", "model_load_attempts": 0,
                "inference_request_attempts": 0, "http_post_attempts": 0,
            })
            self.assertTrue(bundle.validate().valid)


if __name__ == "__main__":
    unittest.main()
