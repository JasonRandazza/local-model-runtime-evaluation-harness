from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
import threading
import unittest
from pathlib import Path

from local_model_runtime_evaluation.lifecycle import LifecycleStore
from local_model_runtime_evaluation.locking import RunLock
from local_model_runtime_evaluation.models import Operation
from local_model_runtime_evaluation.resources import MemoryPressure, ResourceSnapshot
from local_model_runtime_evaluation.runner import StageZeroRunner
from local_model_runtime_evaluation.stage_two import (
    HostValidation,
    ModelDescriptor,
    ProcessOwnership,
    StageTwoError,
)
from local_model_runtime_evaluation.stage_two_inference import StageTwoInferenceEngine
from local_model_runtime_evaluation.stage_two_profiles import RuntimeProfileRegistry
from local_model_runtime_evaluation.stage_two_smoke_suite import StageTwoSmokeSuite
from local_model_runtime_evaluation.transport import TransportResult


class FakeController:
    def __init__(self) -> None:
        self.identity = ProcessOwnership(4242, 4000, 4242, "started", "command")
        self.running = True

    def capture(self) -> ProcessOwnership:
        return self.identity

    def matches(self, identity: ProcessOwnership) -> bool:
        return self.running and identity == self.identity

    def assert_stopped(self, identity: ProcessOwnership) -> None:
        if self.running or identity != self.identity:
            raise StageTwoError("operator_shutdown_pending", "fake operator is still running")


class FakeTransport:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []
        self.posts: list[tuple[str, str]] = []
        self.in_flight = 0
        self.maximum_in_flight = 0

    def health(self, base_url: str) -> dict[str, object]:
        route = "direct" if ":8080" in base_url else "routed"
        self.calls.append(("GET", f"{route}_health"))
        return {"status": "ok" if route == "direct" else "healthy"}

    def list_models(self, base_url: str) -> tuple[ModelDescriptor, ...]:
        route = "direct" if ":8080" in base_url else "routed"
        self.calls.append(("GET", f"{route}_models"))
        if route == "direct":
            return (ModelDescriptor("mlx-community/VibeThinker-3B-OptiQ-4bit"),)
        return (ModelDescriptor("optiq/mlx-community/VibeThinker-3B-OptiQ-4bit"),)

    def chat(
        self,
        base_url: str,
        model_id: str,
        prompt: str,
        max_tokens: int,
        cancel: threading.Event,
    ) -> TransportResult:
        route = "direct" if ":8080" in base_url else "routed"
        self.in_flight += 1
        self.maximum_in_flight = max(self.maximum_in_flight, self.in_flight)
        self.posts.append((route, model_id))
        try:
            content = (
                '{"name":"status","arguments":{"run_id":"stage2b-test","include_details":false}}'
                if "Return exactly" in prompt
                else "Deterministic fake text response remains in memory only."
            )
            return TransportResult(
                content=content,
                content_sha256=hashlib.sha256(content.encode("utf-8")).hexdigest(),
                ttft_seconds=0.1,
                total_seconds=1.0,
                completion_tokens=10,
                finish_reason="stop",
                http_status=200,
                stream_valid=True,
                content_event_count=2,
                last_content_seconds=0.5,
                reasoning_tokens=2,
                visible_output_tokens=8,
                token_accounting_status="EXACT_VISIBLE",
            )
        finally:
            self.in_flight -= 1


class StageTwoGateAE2ETest(unittest.TestCase):
    run_id = "stage2-20260715-901"

    def test_fake_stage_2b1_lifecycle_seals_a_redacted_eight_post_bundle_before_lock_release(self) -> None:
        source_root = Path(__file__).parents[1]
        with tempfile.TemporaryDirectory() as repository_temp, tempfile.TemporaryDirectory() as output_temp:
            repository = Path(repository_temp)
            output = Path(output_temp)
            (repository / "manifests").mkdir()
            (repository / "config").mkdir()
            (repository / "suites").mkdir()
            shutil.copytree(
                source_root / "config" / "runtime-profiles",
                repository / "config" / "runtime-profiles",
            )
            shutil.copy(
                source_root / "suites" / "optiq-route-smoke-v1.json",
                repository / "suites" / "optiq-route-smoke-v1.json",
            )
            manifest_path = repository / "manifests" / "stage2-inference.json"
            manifest = json.loads(
                (source_root / "tests" / "fixtures" / "valid-stage-2-inference.json").read_text(
                    encoding="utf-8"
                )
            )
            manifest["expires_at"] = "2099-01-01T00:00:00Z"
            manifest_path.write_text(json.dumps(manifest) + "\n", encoding="utf-8")

            controller = FakeController()
            transport = FakeTransport()
            resource_samples: list[ResourceSnapshot] = []
            validation_order: list[tuple[str | None, bool]] = []

            def resource_probe(_health: object) -> ResourceSnapshot:
                snapshot = ResourceSnapshot(MemoryPressure.NORMAL, (), None)
                resource_samples.append(snapshot)
                return snapshot

            def engine_factory(parsed_manifest, output_root: Path) -> StageTwoInferenceEngine:
                profile = RuntimeProfileRegistry(
                    repository / "config" / "runtime-profiles"
                ).get(parsed_manifest.runtime_profile_id, parsed_manifest.runtime_profile_revision)
                suite = StageTwoSmokeSuite.load(repository / "suites" / "optiq-route-smoke-v1.json")
                host_validation = HostValidation(
                    runtime_identity={
                        "version": profile.runtime_version,
                        "packages": dict(profile.package_versions),
                    },
                    artifact_identity={
                        "revision": profile.model_revision,
                        "hashes": dict(profile.artifact_hashes),
                    },
                    provider_identity={
                        "provider_id": "Optiq",
                        "enabled": True,
                        "custom_header_count": 0,
                        "secret_header_key_count": 0,
                    },
                )
                engine = StageTwoInferenceEngine(
                    parsed_manifest,
                    profile,
                    suite,
                    output_root,
                    resource_probe,
                    lambda: host_validation,
                    controller,
                    transport,
                    RunLock(output_root).owner,
                )
                original_validate = engine.bundle.validate

                def validate_while_lock_is_held():
                    result = original_validate()
                    validation_order.append((RunLock(output_root).owner(), result.valid))
                    return result

                engine.bundle.validate = validate_while_lock_is_held
                return engine

            runner = StageZeroRunner(
                repository,
                output_root_override=output,
                stage_two_engine_factory=engine_factory,
            )

            preflight = runner.dispatch(Operation.PREFLIGHT, self.run_id)
            self.assertEqual(preflight["state"], "ready")
            self.assertEqual((output / ".active-run.lock").read_text(encoding="utf-8").strip(), self.run_id)

            worker = runner.execute_stage_two_worker(self.run_id)
            self.assertEqual(worker["state"], "awaiting_review")
            self.assertEqual(worker["inference_request_attempts"], 8)
            self.assertEqual(worker["http_post_attempts"], 8)
            self.assertEqual(worker["inference_path_acceptance"], "PASS")
            self.assertEqual(worker["behavioral_contract_acceptance"], "PASS")

            controller.running = False
            cleanup = runner.dispatch(Operation.CLEANUP, self.run_id)
            bundle = runner.validate_bundle(self.run_id)
            run_dir = output / self.run_id
            observations = [
                json.loads(line)
                for line in (run_dir / "raw-runs.jsonl").read_text(encoding="utf-8").splitlines()
            ]
            request_evidence = [
                json.loads(line)
                for line in (run_dir / "request-evidence.jsonl").read_text(encoding="utf-8").splitlines()
            ]
            summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))

            self.assertEqual(
                LifecycleStore(output).history(self.run_id),
                [
                    "queued", "preflight", "resource_gate", "endpoint_identity", "ready",
                    "running", "warmup", "measured", "artifact_validation", "awaiting_review",
                    "cleaned",
                ],
            )
            self.assertEqual(len(transport.posts), 8)
            self.assertEqual(transport.maximum_in_flight, 1)
            self.assertEqual(
                transport.posts,
                [
                    ("direct", "mlx-community/VibeThinker-3B-OptiQ-4bit"),
                    ("routed", "optiq/mlx-community/VibeThinker-3B-OptiQ-4bit"),
                    ("direct", "mlx-community/VibeThinker-3B-OptiQ-4bit"),
                    ("routed", "optiq/mlx-community/VibeThinker-3B-OptiQ-4bit"),
                    ("routed", "optiq/mlx-community/VibeThinker-3B-OptiQ-4bit"),
                    ("direct", "mlx-community/VibeThinker-3B-OptiQ-4bit"),
                    ("routed", "optiq/mlx-community/VibeThinker-3B-OptiQ-4bit"),
                    ("direct", "mlx-community/VibeThinker-3B-OptiQ-4bit"),
                ],
            )
            self.assertEqual(len(observations), 8)
            self.assertEqual(sum(not item["measured"] for item in observations), 4)
            self.assertEqual(sum(item["measured"] for item in observations), 4)
            self.assertTrue(all(len(item["output_sha256"]) == 64 for item in observations))
            self.assertEqual(sum(item["method"] == "POST" for item in request_evidence), 8)
            self.assertEqual(summary["inference_path_acceptance"], "PASS")
            self.assertEqual(summary["behavioral_contract_acceptance"], "PASS")
            self.assertEqual(cleanup["checksum_validation"], "PASS")
            self.assertTrue(bundle["valid"])
            self.assertEqual(validation_order, [(self.run_id, True)])
            self.assertFalse((output / ".active-run.lock").exists())
            self.assertGreaterEqual(len(resource_samples), 17)

            artifact_bytes = b"".join(
                path.read_bytes() for path in run_dir.iterdir() if path.is_file()
            )
            for forbidden in (
                b"Deterministic fake text response remains in memory only.",
                b"stage2b-test",
                b"In two sentences, explain why reproducible measurements matter.",
                b"Return exactly this JSON object with no markdown or extra text:",
                b"Authorization",
                b"Bearer",
            ):
                self.assertNotIn(forbidden, artifact_bytes)


if __name__ == "__main__":
    unittest.main()
