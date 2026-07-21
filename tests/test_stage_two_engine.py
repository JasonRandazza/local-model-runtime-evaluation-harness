from __future__ import annotations

import json
import tempfile
import threading
import unittest
from datetime import datetime, timezone
from pathlib import Path

from local_model_runtime_evaluation.artifacts import ArtifactError
from local_model_runtime_evaluation.manifest import load_manifest
from local_model_runtime_evaluation.resources import MemoryPressure, ResourceSnapshot
from local_model_runtime_evaluation.stage_two import (
    HostValidation,
    ModelDescriptor,
    ProcessOwnership,
    StageTwoEngine,
    StageTwoError,
    discover_route_identity,
)
from local_model_runtime_evaluation.stage_two_profiles import RuntimeProfileRegistry


class FakeOperatorController:
    def __init__(self, *, matches: bool = True, running: bool = True) -> None:
        self.identity_matches = matches
        self.running = running
        self.calls: list[str] = []
        self.identity = ProcessOwnership(
            4242, 4000, 4242, "2026-07-15T12:00:00Z", "command-hash"
        )

    def capture(self) -> ProcessOwnership:
        self.calls.append("capture")
        return self.identity

    def matches(self, identity: ProcessOwnership) -> bool:
        self.calls.append("matches")
        return self.running and self.identity_matches and identity == self.identity

    def assert_stopped(self, identity: ProcessOwnership) -> None:
        self.calls.append("assert_stopped")
        if self.running or identity != self.identity:
            raise StageTwoError("operator_shutdown_pending", "operator service is still running")


class FakeTransport:
    def __init__(self, routed_models: tuple[ModelDescriptor, ...] | None = None) -> None:
        self.calls: list[tuple[str, str]] = []
        self.routed_models = routed_models

    def health(self, base_url: str) -> dict[str, object]:
        self.calls.append(("GET", "direct_health" if ":8080" in base_url else "routed_health"))
        if ":8080" in base_url:
            return {"status": "ok"}
        return {"status": "healthy"}

    def list_models(self, base_url: str) -> tuple[ModelDescriptor, ...]:
        self.calls.append(("GET", "direct_models" if ":8080" in base_url else "routed_models"))
        if ":8080" in base_url:
            return (
                ModelDescriptor("mlx-community/VibeThinker-3B-OptiQ-4bit", "optiq", "base"),
            )
        return self.routed_models or (
            ModelDescriptor(
                "optiq/mlx-community/VibeThinker-3B-OptiQ-4bit", "Optiq", "upstream"
            ),
            ModelDescriptor("vibethinker-3b-optiq-4bit", "osaurus", "local"),
        )


class StageTwoEngineTest(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(__file__).parents[1]
        self.manifest = load_manifest(
            Path(__file__).parent / "fixtures" / "valid-stage-2.json",
            now=datetime(2026, 7, 14, tzinfo=timezone.utc),
        )
        self.profile = RuntimeProfileRegistry(self.root / "config" / "runtime-profiles").get(
            self.manifest.runtime_profile_id, self.manifest.runtime_profile_revision
        )
        self.validation = HostValidation(
            runtime_identity={"version": "0.3.3", "packages": dict(self.profile.package_versions)},
            artifact_identity={"revision": self.profile.model_revision, "hashes": dict(self.profile.artifact_hashes)},
            provider_identity={
                "provider_id": "Optiq", "enabled": True,
                "custom_header_count": 0, "secret_header_key_count": 0,
            },
        )

    def _engine(self, root: Path, controller: FakeOperatorController, transport: FakeTransport) -> StageTwoEngine:
        return StageTwoEngine(
            self.manifest, self.profile, root,
            ResourceSnapshot(MemoryPressure.NORMAL, (), None),
            lambda: self.validation, controller, transport,
        )

    def test_operator_route_probe_is_get_only_and_requires_manual_shutdown(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            controller = FakeOperatorController()
            transport = FakeTransport()
            engine = self._engine(root, controller, transport)

            preflight = engine.preflight()
            self.assertEqual(preflight["state"], "ready")
            self.assertEqual(preflight["manifest"]["schema_version"], "3.1.0")
            self.assertEqual(preflight["manifest"]["runtime_profile_revision"], "3")
            self.assertEqual(preflight["service_lifecycle_actions"], 0)

            result = engine.run(threading.Event())
            self.assertEqual(result["state"], "awaiting_review")
            self.assertEqual(result["discovered_routed_model_id"], self.profile.routed_model_id)
            self.assertEqual(
                transport.calls,
                [
                    ("GET", "direct_health"), ("GET", "direct_models"),
                    ("GET", "routed_health"), ("GET", "routed_models"),
                    ("GET", "direct_health"),
                ],
            )
            self.assertNotIn("start", controller.calls)
            self.assertNotIn("stop", controller.calls)
            with self.assertRaisesRegex(StageTwoError, "still running"):
                engine.cleanup()

            controller.running = False
            cleanup = self._engine(root, controller, transport).cleanup()
            self.assertEqual(cleanup["disposition"], "PASS")
            self.assertEqual(cleanup["service_lifecycle_actions"], 0)
            self.assertEqual(cleanup["operator_shutdown_verified"], "PASS")
            self.assertEqual(cleanup["checksum_validation"], "PASS")

            run_dir = root / self.manifest.run_id
            self.assertTrue((run_dir / "operator-service-identity.json").is_file())
            self.assertTrue((run_dir / "request-evidence.jsonl").is_file())
            self.assertFalse((run_dir / "process-ownership.json").exists())
            self.assertFalse((run_dir / "redacted-log.md").exists())
            requests = [json.loads(line) for line in (run_dir / "request-evidence.jsonl").read_text().splitlines()]
            self.assertEqual(len(requests), 5)
            self.assertTrue(all(set(item) == {"method", "endpoint", "status", "payload_sha256"} for item in requests))
            self.assertTrue(all(item["method"] == "GET" and item["status"] == 200 for item in requests))

    def test_preflight_rejects_provider_headers_without_exposing_values(self) -> None:
        validation = HostValidation(
            runtime_identity=self.validation.runtime_identity,
            artifact_identity=self.validation.artifact_identity,
            provider_identity={
                "provider_id": "Optiq", "enabled": True,
                "custom_header_count": 1, "secret_header_key_count": 0,
            },
        )
        with tempfile.TemporaryDirectory() as temp:
            engine = StageTwoEngine(
                self.manifest, self.profile, Path(temp),
                ResourceSnapshot(MemoryPressure.NORMAL, (), None),
                lambda: validation, FakeOperatorController(), FakeTransport(),
            )
            with self.assertRaisesRegex(StageTwoError, "custom headers") as raised:
                engine.preflight()
            self.assertNotIn("Authorization", str(raised.exception))

    def test_exact_provider_prefixed_id_proves_route(self) -> None:
        direct = tuple(ModelDescriptor(value) for value in self.profile.direct_model_identities)
        self.assertEqual(
            discover_route_identity(
                self.profile, direct,
                (
                    ModelDescriptor("vibethinker-3b-optiq-4bit"),
                    ModelDescriptor(self.profile.routed_model_id, "Optiq", "upstream"),
                ),
            ),
            self.profile.routed_model_id,
        )

    def test_route_identity_rejects_raw_local_and_duplicate_matches(self) -> None:
        direct = tuple(ModelDescriptor(value) for value in self.profile.direct_model_identities)
        invalid_routed = (
            (ModelDescriptor("vibethinker-3b-optiq-4bit"),),
            (ModelDescriptor("mlx-community/VibeThinker-3B-OptiQ-4bit"),),
            (ModelDescriptor("optiq/VibeThinker-3B-OptiQ-4bit"),),
            (ModelDescriptor(self.profile.routed_model_id), ModelDescriptor(self.profile.routed_model_id)),
        )
        for routed in invalid_routed:
            with self.subTest(routed=routed), self.assertRaisesRegex(StageTwoError, "missing or ambiguous"):
                discover_route_identity(self.profile, direct, routed)

    def test_failed_route_preserves_pending_evidence_and_requires_shutdown_cleanup(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            controller = FakeOperatorController()
            engine = self._engine(
                root, controller,
                FakeTransport((ModelDescriptor("mlx-community/VibeThinker-3B-OptiQ-4bit"),)),
            )
            engine.preflight()
            with self.assertRaisesRegex(StageTwoError, "missing or ambiguous"):
                engine.run(threading.Event())
            self.assertEqual(engine.lifecycle.read(self.manifest.run_id).status.value, "failed")
            inventory = json.loads((root / self.manifest.run_id / "endpoint-inventory.json").read_text())
            self.assertEqual(inventory["route_identity"], {"status": "PENDING"})
            with self.assertRaisesRegex(StageTwoError, "still running"):
                engine.cleanup()
            controller.running = False
            cleanup = self._engine(root, controller, FakeTransport()).cleanup()
            self.assertEqual(cleanup["disposition"], "STOPPED")
            self.assertEqual(cleanup["checksum_validation"], "PASS")

    def test_cleanup_rejects_tampered_routed_identity_before_sealing(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            controller = FakeOperatorController()
            engine = self._engine(root, controller, FakeTransport())
            engine.preflight()
            engine.run(threading.Event())
            controller.running = False
            inventory_path = root / self.manifest.run_id / "endpoint-inventory.json"
            inventory = json.loads(inventory_path.read_text())
            inventory["route_identity"]["discovered_routed_model_id"] = "optiq/wrong-model"
            inventory_path.write_text(json.dumps(inventory) + "\n")

            with self.assertRaisesRegex(StageTwoError, "routed model identity is invalid"):
                engine.cleanup()

            self.assertEqual(engine.lifecycle.read(self.manifest.run_id).status.value, "awaiting_review")
            self.assertFalse((root / self.manifest.run_id / "checksums.txt").exists())

    def test_cleaned_state_recovers_from_one_reseal_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            controller = FakeOperatorController()
            engine = self._engine(root, controller, FakeTransport())
            engine.preflight()
            engine.run(threading.Event())
            controller.running = False
            original_reseal = engine.bundle.reseal_after_state_transition

            def fail_once(**kwargs) -> None:
                engine.bundle.reseal_after_state_transition = original_reseal
                raise ArtifactError("injected reseal failure")

            engine.bundle.reseal_after_state_transition = fail_once
            with self.assertRaisesRegex(ArtifactError, "injected reseal failure"):
                engine.cleanup()
            self.assertEqual(engine.lifecycle.read(self.manifest.run_id).status.value, "cleaned")

            recovered = self._engine(root, controller, FakeTransport()).cleanup()
            self.assertEqual(recovered["disposition"], "PASS")
            self.assertEqual(recovered["checksum_validation"], "PASS")

    def test_partial_cleaned_state_recovers_from_one_reseal_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            controller = FakeOperatorController()
            engine = self._engine(
                root, controller,
                FakeTransport((ModelDescriptor("mlx-community/VibeThinker-3B-OptiQ-4bit"),)),
            )
            engine.preflight()
            with self.assertRaises(StageTwoError):
                engine.run(threading.Event())
            controller.running = False
            original_reseal = engine.bundle.reseal_after_state_transition

            def fail_once(**kwargs) -> None:
                engine.bundle.reseal_after_state_transition = original_reseal
                raise ArtifactError("injected partial reseal failure")

            engine.bundle.reseal_after_state_transition = fail_once
            with self.assertRaisesRegex(ArtifactError, "injected partial reseal failure"):
                engine.cleanup()
            self.assertEqual(engine.lifecycle.read(self.manifest.run_id).status.value, "cleaned")

            recovered = self._engine(root, controller, FakeTransport()).cleanup()
            self.assertEqual(recovered["disposition"], "STOPPED")
            self.assertEqual(recovered["checksum_validation"], "PASS")

    def test_identity_mismatch_fails_without_lifecycle_action(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            controller = FakeOperatorController(matches=False)
            engine = self._engine(Path(temp), controller, FakeTransport())
            engine.preflight()
            with self.assertRaisesRegex(StageTwoError, "identity changed"):
                engine.run(threading.Event())
            self.assertNotIn("stop", controller.calls)

    def test_pre_run_cancellation_records_cancelled_without_requests(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            controller = FakeOperatorController()
            transport = FakeTransport()
            engine = self._engine(Path(temp), controller, transport)
            engine.preflight()
            cancel = threading.Event()
            cancel.set()
            with self.assertRaisesRegex(StageTwoError, "cancelled"):
                engine.run(cancel)
            self.assertEqual(engine.lifecycle.read(self.manifest.run_id).status.value, "cancelled")
            self.assertEqual(transport.calls, [])


if __name__ == "__main__":
    unittest.main()
