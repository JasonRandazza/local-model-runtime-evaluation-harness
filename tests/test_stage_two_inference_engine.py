from __future__ import annotations

import json
import tempfile
import threading
import unittest
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

from local_model_runtime_evaluation.manifest import load_manifest
from local_model_runtime_evaluation.models import RunState, RunStatus
from local_model_runtime_evaluation.resources import MemoryPressure, ResourceSnapshot
from local_model_runtime_evaluation.stage_two import (
    HostValidation,
    ModelDescriptor,
    ProcessOwnership,
    StageTwoError,
)
from local_model_runtime_evaluation.artifacts import ArtifactError
from local_model_runtime_evaluation.stage_two_inference import StageTwoInferenceEngine
from local_model_runtime_evaluation.stage_two_profiles import RuntimeProfileRegistry
from local_model_runtime_evaluation.stage_two_smoke_suite import StageTwoSmokeSuite
from local_model_runtime_evaluation.transport import TransportResult


class FakeController:
    def __init__(self) -> None:
        self.identity = ProcessOwnership(4242, 4000, 4242, "started", "command")
        self.matches_calls = 0
        self.running = True

    def capture(self) -> ProcessOwnership:
        return self.identity

    def matches(self, identity: ProcessOwnership) -> bool:
        self.matches_calls += 1
        return self.running and identity == self.identity

    def assert_stopped(self, identity: ProcessOwnership) -> None:
        if self.running:
            raise StageTwoError("operator_shutdown_pending", "still running")


class RestartingController(FakeController):
    """Reports stopped once, then reports the operator service as restarted."""

    def __init__(self) -> None:
        super().__init__()
        self.assert_stopped_calls = 0

    def assert_stopped(self, identity: ProcessOwnership) -> None:
        self.assert_stopped_calls += 1
        if self.assert_stopped_calls == 1:
            return
        raise StageTwoError("operator_shutdown_pending", "operator service restarted")


class MutableLockOwner:
    def __init__(self, run_id: str) -> None:
        self.value: str | None = run_id

    def __call__(self) -> str | None:
        return self.value


class FakeTransport:
    def __init__(
        self,
        *,
        invalid_structured: bool = False,
        empty_content: bool = False,
        fail_chat_at: int | None = None,
        cancel_during_chat_at: int | None = None,
        http_status_at: int | None = None,
        malformed_sse_at: int | None = None,
        drift_inventory_after_chat: int | None = None,
    ) -> None:
        self.calls: list[tuple[str, str]] = []
        self.chat_calls: list[tuple[str, str]] = []
        self.invalid_structured = invalid_structured
        self.empty_content = empty_content
        self.fail_chat_at = fail_chat_at
        self.cancel_during_chat_at = cancel_during_chat_at
        self.http_status_at = http_status_at
        self.malformed_sse_at = malformed_sse_at
        self.drift_inventory_after_chat = drift_inventory_after_chat
        self.in_flight = 0
        self.max_in_flight = 0

    def health(self, base_url: str) -> dict[str, object]:
        route = "direct" if ":8080" in base_url else "routed"
        self.calls.append(("GET", f"{route}_health"))
        return {"status": "ok" if route == "direct" else "healthy"}

    def list_models(self, base_url: str) -> tuple[ModelDescriptor, ...]:
        route = "direct" if ":8080" in base_url else "routed"
        self.calls.append(("GET", f"{route}_models"))
        if (
            self.drift_inventory_after_chat is not None
            and len(self.chat_calls) >= self.drift_inventory_after_chat
            and route == "routed"
        ):
            return (ModelDescriptor("optiq/unapproved-model"),)
        if route == "direct":
            return (ModelDescriptor("mlx-community/VibeThinker-3B-OptiQ-4bit"),)
        return (ModelDescriptor("optiq/mlx-community/VibeThinker-3B-OptiQ-4bit"),)

    def chat(
        self, base_url: str, model_id: str, prompt: str, max_tokens: int,
        cancel: threading.Event,
    ) -> TransportResult:
        route = "direct" if ":8080" in base_url else "routed"
        self.in_flight += 1
        self.max_in_flight = max(self.max_in_flight, self.in_flight)
        self.chat_calls.append((route, model_id))
        try:
            attempt = len(self.chat_calls)
            if self.cancel_during_chat_at == attempt:
                cancel.set()
                raise RuntimeError("prompt=private prompt Authorization=secret")
            if self.fail_chat_at == attempt:
                raise RuntimeError("response body includes private prompt and Authorization=secret")
            if "Return exactly" in prompt:
                content = (
                    "not-json" if self.invalid_structured else
                    '{"name":"status","arguments":{"run_id":"stage2b-test","include_details":false}}'
                )
            else:
                content = "" if self.empty_content else (
                    "Reproducible measurements make comparisons reliable. They expose drift."
                )
            return TransportResult(
                content, "a" * 64, 0.1, 1.0, 10, "stop",
                500 if self.http_status_at == attempt else 200,
                self.malformed_sse_at != attempt,
                2, 0.5, 2, 8, "EXACT_VISIBLE",
            )
        finally:
            self.in_flight -= 1


class StageTwoInferenceEngineTest(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(__file__).parents[1]
        self.manifest = load_manifest(
            Path(__file__).parent / "fixtures" / "valid-stage-2-inference.json",
            now=datetime(2026, 7, 15, 12, tzinfo=timezone.utc),
        )
        self.profile = RuntimeProfileRegistry(self.root / "config" / "runtime-profiles").get(
            self.manifest.runtime_profile_id, self.manifest.runtime_profile_revision,
        )
        self.suite = StageTwoSmokeSuite.load(self.root / "suites" / "optiq-route-smoke-v1.json")
        self.validation = HostValidation(
            runtime_identity={"version": "0.3.3", "packages": dict(self.profile.package_versions)},
            artifact_identity={
                "revision": self.profile.model_revision,
                "hashes": dict(self.profile.artifact_hashes),
            },
            provider_identity={
                "provider_id": "Optiq", "enabled": True,
                "custom_header_count": 0, "secret_header_key_count": 0,
            },
        )

    def _engine(
        self, output: Path, transport: FakeTransport, controller: FakeController,
        resource_probe=None, lock_owner=None, profile=None, host_validation=None,
    ) -> StageTwoInferenceEngine:
        probe = resource_probe or (
            lambda _health: ResourceSnapshot(MemoryPressure.NORMAL, (), None)
        )
        return StageTwoInferenceEngine(
            self.manifest, profile or self.profile, self.suite, output, probe,
            host_validation or (lambda: self.validation), controller, transport,
            lock_owner or (lambda: self.manifest.run_id),
        )

    def _assert_sanitized(self, context: unittest.case._AssertRaisesContext) -> None:
        error = context.exception
        details = " ".join(
            str(item) for item in (error, error.__cause__, error.__context__) if item is not None
        )
        self.assertNotIn("private prompt", details)
        self.assertNotIn("Authorization", details)
        self.assertIsNone(error.__cause__)
        self.assertIsNone(error.__context__)

    def _post_evidence(self, output: Path) -> list[dict[str, object]]:
        path = output / self.manifest.run_id / "request-evidence.jsonl"
        return [
            json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
            if json.loads(line)["method"] == "POST"
        ]

    def _complete_and_shutdown(
        self, output: Path, transport: FakeTransport | None = None,
    ) -> tuple[StageTwoInferenceEngine, FakeController, FakeTransport]:
        controller = FakeController()
        actual_transport = transport or FakeTransport()
        engine = self._engine(output, actual_transport, controller)
        engine.preflight()
        engine.run(threading.Event())
        controller.running = False
        return engine, controller, actual_transport

    @staticmethod
    def _mutate_json(path: Path, mutate) -> None:
        payload = json.loads(path.read_text(encoding="utf-8"))
        mutate(payload)
        path.write_text(json.dumps(payload) + "\n", encoding="utf-8")

    @staticmethod
    def _mutate_jsonl(path: Path, index: int, mutate) -> None:
        payloads = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
        mutate(payloads[index])
        path.write_text(
            "\n".join(json.dumps(payload) for payload in payloads) + "\n",
            encoding="utf-8",
        )

    def test_preflight_proves_routes_without_post_authority(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp)
            transport = FakeTransport()
            engine = self._engine(output, transport, FakeController())
            result = engine.preflight()
            self.assertEqual(result["state"], "ready")
            self.assertEqual(result["http_post_attempts"], 0)
            self.assertEqual(result["inference_request_attempts"], 0)
            self.assertEqual([item[0] for item in transport.calls], ["GET"] * 4)
            run_dir = output / self.manifest.run_id
            for name in (
                "runtime-identity.json", "artifact-identity.json",
                "operator-service-identity.json", "endpoint-inventory.json",
                "inference-suite.json", "preflight.json", "memory-samples.jsonl",
                "request-evidence.jsonl", "service-events.jsonl", "lifecycle.jsonl",
            ):
                self.assertTrue((run_dir / name).is_file(), name)
            suite = json.loads((run_dir / "inference-suite.json").read_text())
            self.assertNotIn("prompt", json.dumps(suite))

    def test_exact_eight_request_schedule_is_serial_and_sanitized(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp)
            transport = FakeTransport()
            engine = self._engine(output, transport, FakeController())
            engine.preflight()
            result = engine.run(threading.Event())
            self.assertEqual(result["state"], "awaiting_review")
            self.assertEqual(result["inference_request_attempts"], 8)
            self.assertEqual(result["http_post_attempts"], 8)
            self.assertEqual(transport.max_in_flight, 1)
            self.assertEqual([route for route, _ in transport.chat_calls], [
                "direct", "routed", "direct", "routed",
                "routed", "direct", "routed", "direct",
            ])
            raw = (output / self.manifest.run_id / "raw-runs.jsonl").read_text()
            self.assertNotIn("Reproducible", raw)
            self.assertNotIn("stage2b-test", raw)
            self.assertEqual(len(raw.splitlines()), 8)

    def test_behavioral_failure_finishes_safe_cohort(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            transport = FakeTransport(invalid_structured=True)
            engine = self._engine(Path(temp), transport, FakeController())
            engine.preflight()
            result = engine.run(threading.Event())
            self.assertEqual(len(transport.chat_calls), 8)
            self.assertEqual(result["inference_path_acceptance"], "PASS")
            self.assertEqual(result["behavioral_contract_acceptance"], "FAIL")

    def test_cleanup_requires_manual_shutdown_before_checksums(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp)
            controller = FakeController()
            engine = self._engine(output, FakeTransport(), controller)
            engine.preflight()
            engine.run(threading.Event())
            with self.assertRaises(StageTwoError) as context:
                engine.cleanup()
            self._assert_sanitized(context)
            self.assertEqual(context.exception.code, "cleanup_failed")
            self.assertFalse((output / self.manifest.run_id / "checksums.txt").exists())

    def test_cleanup_fails_if_lock_disappears_before_seal(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp)
            controller = FakeController()
            lock_owner = MutableLockOwner(self.manifest.run_id)
            engine = self._engine(output, FakeTransport(), controller, lock_owner=lock_owner)
            engine.preflight()
            engine.run(threading.Event())
            controller.running = False

            original_reconcile_memory = engine._reconcile_memory

            def drop_lock_then_reconcile() -> None:
                original_reconcile_memory()
                lock_owner.value = None

            engine._reconcile_memory = drop_lock_then_reconcile
            with self.assertRaises(StageTwoError) as context:
                engine.cleanup()
            self.assertEqual(context.exception.code, "lock_identity_failed")
            self.assertFalse((output / self.manifest.run_id / "checksums.txt").exists())

    def test_cleanup_fails_if_lock_owner_is_replaced_before_seal(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp)
            controller = FakeController()
            lock_owner = MutableLockOwner(self.manifest.run_id)
            engine = self._engine(output, FakeTransport(), controller, lock_owner=lock_owner)
            engine.preflight()
            engine.run(threading.Event())
            controller.running = False

            original_reconcile_memory = engine._reconcile_memory

            def replace_lock_then_reconcile() -> None:
                original_reconcile_memory()
                lock_owner.value = "stage2-other"

            engine._reconcile_memory = replace_lock_then_reconcile
            with self.assertRaises(StageTwoError) as context:
                engine.cleanup()
            self.assertEqual(context.exception.code, "lock_identity_failed")
            self.assertFalse((output / self.manifest.run_id / "checksums.txt").exists())

    def test_cleanup_rechecks_shutdown_immediately_before_final_seal(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp)
            controller = RestartingController()
            engine = self._engine(output, FakeTransport(), controller)
            engine.preflight()
            engine.run(threading.Event())
            with self.assertRaises(StageTwoError) as context:
                engine.cleanup()
            self.assertEqual(context.exception.code, "cleanup_failed")
            self.assertEqual(controller.assert_stopped_calls, 2)
            self.assertFalse((output / self.manifest.run_id / "checksums.txt").exists())

    def test_cleanup_seals_complete_redacted_pass_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp)
            engine, _, _ = self._complete_and_shutdown(output)
            result = engine.cleanup()
            self.assertEqual(result["disposition"], "PASS")
            self.assertEqual(result["inference_path_acceptance"], "PASS")
            self.assertEqual(result["behavioral_contract_acceptance"], "PASS")
            self.assertEqual(result["checksum_validation"], "PASS")
            run_dir = output / self.manifest.run_id
            artifact_bytes = b"".join(
                path.read_bytes() for path in run_dir.iterdir() if path.is_file()
            )
            for forbidden in (
                b"In two sentences, explain why reproducible measurements matter.",
                b"Return exactly this JSON object with no markdown or extra text:",
                b"Reproducible measurements make comparisons reliable.",
                b"Authorization", b"Bearer", b"fake-secret",
            ):
                self.assertNotIn(forbidden, artifact_bytes)
            self.assertFalse((run_dir / "draft-report.md").exists())
            self.assertFalse((run_dir / "route-comparison.json").exists())
            self.assertNotIn(b"stable_median", artifact_bytes)

    def test_cleanup_keeps_infrastructure_and_behavioral_acceptance_independent(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp)
            engine, _, _ = self._complete_and_shutdown(
                output, FakeTransport(invalid_structured=True),
            )
            result = engine.cleanup()
            self.assertEqual(result["disposition"], "PASS")
            self.assertEqual(result["inference_path_acceptance"], "PASS")
            self.assertEqual(result["behavioral_contract_acceptance"], "FAIL")

    def test_cleanup_finalizes_failed_and_cancelled_runs_as_stopped(self) -> None:
        scenarios = (
            ("failed", "FAIL", FakeTransport(fail_chat_at=1)),
            ("cancelled", "STOPPED", FakeTransport(cancel_during_chat_at=1)),
        )
        for expected_state, expected_acceptance, transport in scenarios:
            with self.subTest(expected_state=expected_state), tempfile.TemporaryDirectory() as temp:
                output = Path(temp)
                controller = FakeController()
                engine = self._engine(output, transport, controller)
                engine.preflight()
                with self.assertRaises(StageTwoError):
                    engine.run(threading.Event())
                self.assertEqual(engine.lifecycle.read(self.manifest.run_id).status.value, expected_state)
                controller.running = False
                result = engine.cleanup()
                self.assertEqual(result["disposition"], "STOPPED")
                self.assertEqual(result["inference_path_acceptance"], expected_acceptance)
                self.assertEqual(result["inference_request_attempts"], 1)
                self.assertEqual(result["http_post_attempts"], 1)
                self.assertEqual(result["checksum_validation"], "PASS")
                repeated = self._engine(output, transport, controller).cleanup()
                self.assertEqual(repeated["disposition"], "STOPPED")
                self.assertEqual(repeated["checksum_validation"], "PASS")

    def test_cleanup_rejects_tampered_complete_evidence_before_sealing(self) -> None:
        mutations = (
            ("route", lambda run_dir: self._mutate_json(
                run_dir / "endpoint-inventory.json",
                lambda payload: payload["route_identity"].update(
                    {"discovered_routed_model_id": "optiq/wrong-model"}
                ),
            )),
            ("observation_count", lambda run_dir: (run_dir / "raw-runs.jsonl").write_text(
                "\n".join((run_dir / "raw-runs.jsonl").read_text().splitlines()[:-1]) + "\n"
            )),
            ("sequence", lambda run_dir: self._mutate_jsonl(
                run_dir / "raw-runs.jsonl", 0, lambda payload: payload.update({"sequence": 9})
            )),
            ("method", lambda run_dir: self._mutate_jsonl(
                run_dir / "request-evidence.jsonl", 8, lambda payload: payload.update({"method": "GET"})
            )),
            ("output_hash", lambda run_dir: self._mutate_jsonl(
                run_dir / "raw-runs.jsonl", 2, lambda payload: payload.update({"output_sha256": "0" * 64})
            )),
            ("summary", lambda run_dir: (run_dir / "smoke-summary.json").write_text("{}\n")),
            ("suite", lambda run_dir: self._mutate_json(
                run_dir / "inference-suite.json",
                lambda payload: payload.update({"request_count": 9}),
            )),
        )
        for name, mutate in mutations:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temp:
                output = Path(temp)
                engine, _, _ = self._complete_and_shutdown(output)
                mutate(output / self.manifest.run_id)
                with self.assertRaises(StageTwoError):
                    engine.cleanup()
                self.assertFalse((output / self.manifest.run_id / "checksums.txt").exists())

    def test_complete_cleanup_requires_the_exact_get_and_post_evidence_trace(self) -> None:
        mutations = (
            ("removed_get", lambda path: path.write_text(
                "\n".join(path.read_text(encoding="utf-8").splitlines()[1:]) + "\n",
                encoding="utf-8",
            )),
            ("extra_get", lambda path: path.write_text(
                path.read_text(encoding="utf-8")
                + json.dumps({
                    "method": "GET", "endpoint": "direct_health", "status": 200,
                    "payload_sha256": "0" * 64,
                }) + "\n",
                encoding="utf-8",
            )),
            ("changed_get_sequence", lambda path: self._mutate_jsonl(
                path, 4, lambda record: record.update({"sequence": 99})
            )),
            ("changed_get_status", lambda path: self._mutate_jsonl(
                path, 4, lambda record: record.update({"status": 201})
            )),
            ("changed_post_endpoint", lambda path: self._mutate_jsonl(
                path, 8, lambda record: record.update({"endpoint": "routed_chat_completions"})
            )),
            ("changed_post_hash", lambda path: self._mutate_jsonl(
                path, 8, lambda record: record.update({"fixed_request_sha256": "0" * 64})
            )),
        )
        for name, mutate in mutations:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temp:
                output = Path(temp)
                engine, _, _ = self._complete_and_shutdown(output)
                mutate(output / self.manifest.run_id / "request-evidence.jsonl")
                with self.assertRaises(StageTwoError):
                    engine.cleanup()
                self.assertFalse((output / self.manifest.run_id / "checksums.txt").exists())

    def test_failed_preflight_captures_operator_identity_for_stopped_partial_cleanup(self) -> None:
        def fail_validation():
            raise StageTwoError("external_validation", "Bearer fake-secret external host failure")

        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp)
            controller = FakeController()
            engine = self._engine(
                output, FakeTransport(), controller, host_validation=fail_validation,
            )
            with self.assertRaises(StageTwoError) as context:
                engine.preflight()
            self._assert_sanitized(context)
            self.assertTrue((output / self.manifest.run_id / "operator-service-identity.json").is_file())
            controller.running = False
            result = engine.cleanup()
            self.assertEqual(result["disposition"], "STOPPED")
            self.assertEqual(result["http_post_attempts"], 0)
            self.assertEqual(result["completed_requests"], 0)

    def test_cleanup_sanitizes_typed_controller_shutdown_failure(self) -> None:
        class SensitiveController(FakeController):
            def assert_stopped(self, identity: ProcessOwnership) -> None:
                raise StageTwoError("external_shutdown", "Authorization: Bearer fake-secret")

        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp)
            controller = SensitiveController()
            engine = self._engine(output, FakeTransport(), controller)
            engine.preflight()
            engine.run(threading.Event())
            controller.running = False
            with self.assertRaises(StageTwoError) as context:
                engine.cleanup()
            self._assert_sanitized(context)
            self.assertEqual(context.exception.code, "cleanup_failed")

    def test_partial_cleanup_rejects_non_prefix_post_and_observation_evidence(self) -> None:
        mutations = (
            ("duplicate_post", lambda path: path.write_text(
                path.read_text(encoding="utf-8") + path.read_text(encoding="utf-8").splitlines()[0] + "\n",
                encoding="utf-8",
            )),
            ("observation_gap", lambda path: self._mutate_jsonl(
                path, 0, lambda record: record.update({"sequence": 2})
            )),
            ("duplicate_observation", lambda path: path.write_text(
                path.read_text(encoding="utf-8") + path.read_text(encoding="utf-8"),
                encoding="utf-8",
            )),
        )
        for name, mutate in mutations:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temp:
                output = Path(temp)
                controller = FakeController()
                engine = self._engine(output, FakeTransport(fail_chat_at=2), controller)
                engine.preflight()
                with self.assertRaises(StageTwoError):
                    engine.run(threading.Event())
                target = (
                    output / self.manifest.run_id / "request-evidence.jsonl"
                    if name == "duplicate_post" else output / self.manifest.run_id / "raw-runs.jsonl"
                )
                mutate(target)
                controller.running = False
                with self.assertRaises(StageTwoError):
                    engine.cleanup()
                self.assertFalse((output / self.manifest.run_id / "checksums.txt").exists())

    def test_cleaned_stopped_bundle_semantically_revalidates_present_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp)
            controller = FakeController()
            engine = self._engine(output, FakeTransport(fail_chat_at=2), controller)
            engine.preflight()
            with self.assertRaises(StageTwoError):
                engine.run(threading.Event())
            controller.running = False
            engine.cleanup()
            raw = output / self.manifest.run_id / "raw-runs.jsonl"
            raw.write_text(raw.read_text(encoding="utf-8") * 2, encoding="utf-8")
            engine.bundle._write_checksums()
            with self.assertRaises(StageTwoError):
                self._engine(output, FakeTransport(fail_chat_at=2), controller).cleanup()

    def test_partial_cleanup_rejects_unredacted_artifact_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp)
            controller = FakeController()
            engine = self._engine(output, FakeTransport(fail_chat_at=1), controller)
            engine.preflight()
            with self.assertRaises(StageTwoError):
                engine.run(threading.Event())
            path = output / self.manifest.run_id / "request-evidence.jsonl"
            path.write_text(path.read_text(encoding="utf-8") + '{"note":"fake-secret"}\n')
            controller.running = False
            with self.assertRaisesRegex(StageTwoError, "redaction"):
                engine.cleanup()
            self.assertFalse((output / self.manifest.run_id / "checksums.txt").exists())

    def test_cleanup_recovers_once_after_reseal_failure_and_revalidates_cleaned_bundles(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp)
            engine, controller, transport = self._complete_and_shutdown(output)
            original_reseal = engine.bundle.reseal_after_state_transition

            def fail_once() -> None:
                engine.bundle.reseal_after_state_transition = original_reseal
                raise ArtifactError("injected reseal failure fake-secret")

            engine.bundle.reseal_after_state_transition = fail_once
            with self.assertRaises(StageTwoError) as context:
                engine.cleanup()
            self._assert_sanitized(context)
            self.assertEqual(engine.lifecycle.read(self.manifest.run_id).status, RunStatus.CLEANED)
            recovered = self._engine(output, transport, controller).cleanup()
            self.assertEqual(recovered["disposition"], "PASS")
            self.assertEqual(recovered["checksum_validation"], "PASS")
            repeated = self._engine(output, transport, controller).cleanup()
            self.assertEqual(repeated["disposition"], "PASS")
            self.assertEqual(repeated["checksum_validation"], "PASS")

    def test_recovery_cleanup_fails_if_lock_disappears_before_reseal(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp)
            engine, controller, transport = self._complete_and_shutdown(output)
            original_reseal = engine.bundle.reseal_after_state_transition

            def fail_once() -> None:
                engine.bundle.reseal_after_state_transition = original_reseal
                raise ArtifactError("injected reseal failure fake-secret")

            engine.bundle.reseal_after_state_transition = fail_once
            with self.assertRaises(StageTwoError):
                engine.cleanup()
            self.assertEqual(engine.lifecycle.read(self.manifest.run_id).status, RunStatus.CLEANED)

            lock_owner = MutableLockOwner(self.manifest.run_id)
            recovery_engine = self._engine(output, transport, controller, lock_owner=lock_owner)
            original_reconcile_memory = recovery_engine._reconcile_memory

            def drop_lock_then_reconcile() -> None:
                original_reconcile_memory()
                lock_owner.value = None

            recovery_engine._reconcile_memory = drop_lock_then_reconcile
            with self.assertRaises(StageTwoError) as context:
                recovery_engine.cleanup()
            self.assertEqual(context.exception.code, "lock_identity_failed")

    def test_recovery_cleanup_rechecks_shutdown_immediately_before_final_reseal(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp)
            engine, controller, transport = self._complete_and_shutdown(output)
            original_reseal = engine.bundle.reseal_after_state_transition

            def fail_once() -> None:
                engine.bundle.reseal_after_state_transition = original_reseal
                raise ArtifactError("injected reseal failure fake-secret")

            engine.bundle.reseal_after_state_transition = fail_once
            with self.assertRaises(StageTwoError):
                engine.cleanup()
            self.assertEqual(engine.lifecycle.read(self.manifest.run_id).status, RunStatus.CLEANED)

            restarting_controller = RestartingController()
            restarting_controller.running = False
            recovery_engine = self._engine(output, transport, restarting_controller)
            with self.assertRaises(StageTwoError) as context:
                recovery_engine.cleanup()
            self.assertEqual(context.exception.code, "cleanup_failed")
            self.assertEqual(restarting_controller.assert_stopped_calls, 2)

    def test_empty_content_is_behavioral_and_finishes_safe_cohort(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            transport = FakeTransport(empty_content=True)
            engine = self._engine(Path(temp), transport, FakeController())
            engine.preflight()
            result = engine.run(threading.Event())
            self.assertEqual(len(transport.chat_calls), 8)
            self.assertEqual(result["inference_path_acceptance"], "PASS")
            self.assertEqual(result["behavioral_contract_acceptance"], "FAIL")

    def test_warning_memory_before_first_post_stops_with_zero_attempts(self) -> None:
        calls = 0

        def probe(_health):
            nonlocal calls
            calls += 1
            pressure = MemoryPressure.NORMAL if calls == 1 else MemoryPressure.WARNING
            return ResourceSnapshot(pressure, (), None)

        with tempfile.TemporaryDirectory() as temp:
            transport = FakeTransport()
            engine = self._engine(Path(temp), transport, FakeController(), probe)
            engine.preflight()
            with self.assertRaisesRegex(StageTwoError, "normal memory"):
                engine.run(threading.Event())
            self.assertEqual(engine.inference_request_attempts, 0)
            self.assertEqual(transport.chat_calls, [])
            self.assertEqual(engine.lifecycle.read(self.manifest.run_id).status.value, "failed")

    def test_cancel_and_lock_drift_prevent_next_post(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            engine = self._engine(Path(temp), FakeTransport(), FakeController())
            engine.preflight()
            cancel = threading.Event()
            cancel.set()
            with self.assertRaisesRegex(StageTwoError, "cancelled"):
                engine.run(cancel)
            self.assertEqual(engine.inference_request_attempts, 0)
            self.assertEqual(engine.lifecycle.read(self.manifest.run_id).status.value, "cancelled")

        owners = iter([self.manifest.run_id, "stage2-other"])
        with tempfile.TemporaryDirectory() as temp:
            transport = FakeTransport()
            engine = self._engine(
                Path(temp), transport, FakeController(), lock_owner=lambda: next(owners),
            )
            engine.preflight()
            with self.assertRaisesRegex(StageTwoError, "active lock"):
                engine.run(threading.Event())
            self.assertEqual(transport.chat_calls, [])

    def test_rejects_wrong_manifest_mode(self) -> None:
        raw = dict(self.manifest.raw)
        raw["mode"] = "operator_route_probe"
        altered = self.manifest.__class__(
            **{**self.manifest.__dict__, "mode": "operator_route_probe", "raw": raw}
        )
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(ValueError, "Stage 2B-1"):
                StageTwoInferenceEngine(
                    altered, self.profile, self.suite, Path(temp),
                    lambda _health: ResourceSnapshot(MemoryPressure.NORMAL, (), None),
                    lambda: self.validation, FakeController(), FakeTransport(),
                    lambda: altered.run_id,
                )

    def test_rejects_every_altered_fixed_manifest_field_before_post_authority(self) -> None:
        altered_manifests = (
            replace(self.manifest, repetitions=2),
            replace(self.manifest, route_order="direct_first"),
            replace(self.manifest, limits={**self.manifest.limits, "total_request_limit": 9}),
            replace(self.manifest, operations=tuple(reversed(self.manifest.operations))),
        )
        for manifest in altered_manifests:
            with self.subTest(manifest=manifest):
                with tempfile.TemporaryDirectory() as temp:
                    with self.assertRaisesRegex(ValueError, "Stage 2B-1"):
                        StageTwoInferenceEngine(
                            manifest, self.profile, self.suite, Path(temp),
                            lambda _health: ResourceSnapshot(MemoryPressure.NORMAL, (), None),
                            lambda: self.validation, FakeController(), FakeTransport(),
                            lambda: manifest.run_id,
                        )

    def test_rejects_same_identity_nine_request_suite_before_post_authority(self) -> None:
        class NineRequestSuite(StageTwoSmokeSuite):
            def schedule(self):
                return super().schedule() + (super().schedule()[0],)

        suite = NineRequestSuite(
            self.suite.suite_id, self.suite.revision, self.suite.temperature,
            self.suite.streaming, self.suite.workloads,
        )
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(ValueError, "Stage 2B-1"):
                StageTwoInferenceEngine(
                    self.manifest, self.profile, suite, Path(temp),
                    lambda _health: ResourceSnapshot(MemoryPressure.NORMAL, (), None),
                    lambda: self.validation, FakeController(), FakeTransport(),
                    lambda: self.manifest.run_id,
                )

    def test_rejects_every_runtime_profile_contract_mutation_before_transport_use(self) -> None:
        altered_profiles = (
            replace(self.profile, runtime_executable=Path("/tmp/unapproved-optiq")),
            replace(self.profile, runtime_version="0.3.4"),
            replace(self.profile, coordinator_model_id="unapproved-coordinator"),
            replace(self.profile, package_versions={"mlx-optiq": "unapproved"}),
            replace(self.profile, model_repository="unapproved/model"),
            replace(self.profile, model_revision="unapproved-revision"),
            replace(self.profile, model_snapshot=Path("/tmp/unapproved-model")),
            replace(self.profile, artifact_hashes={"config.json": "0" * 64}),
            replace(self.profile, serve_arguments=("serve", "--port", "9999")),
            replace(self.profile, direct_base_url="http://127.0.0.1:9999/v1"),
            replace(self.profile, routed_base_url="http://127.0.0.1:9998/v1"),
            replace(self.profile, direct_model_identities=("unapproved-direct-model",)),
            replace(self.profile, osaurus_provider_id="unapproved-provider"),
            replace(self.profile, routed_model_id="unapproved-routed-model"),
            replace(self.profile, rejected_local_model_ids=("unapproved-rejected-model",)),
            replace(self.profile, service_ownership="harness"),
            replace(self.profile, provider_activation="automatic"),
        )
        for profile in altered_profiles:
            with self.subTest(profile=profile):
                with tempfile.TemporaryDirectory() as temp:
                    transport = FakeTransport()
                    with self.assertRaisesRegex(ValueError, "Stage 2B-1"):
                        self._engine(Path(temp), transport, FakeController(), profile=profile)
                    self.assertEqual(transport.calls, [])
                    self.assertEqual(transport.chat_calls, [])

    def test_runtime_profile_is_immutable_after_engine_construction(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            transport = FakeTransport()
            profile = replace(
                self.profile,
                package_versions=dict(self.profile.package_versions),
                artifact_hashes=dict(self.profile.artifact_hashes),
            )
            engine = self._engine(Path(temp), transport, FakeController(), profile=profile)

            profile.package_versions["mlx-optiq"] = "mutated-after-construction"
            profile.artifact_hashes["config.json"] = "0" * 64

            self.assertEqual(engine.profile.runtime_version, "0.3.3")
            self.assertEqual(engine.profile.package_versions["mlx-optiq"], "0.3.3")
            self.assertNotEqual(engine.profile.artifact_hashes["config.json"], "0" * 64)
            with self.assertRaises(TypeError):
                engine.profile.package_versions["mlx-optiq"] = "mutated-through-engine"
            with self.assertRaises(TypeError):
                engine.profile.artifact_hashes["config.json"] = "0" * 64

            engine.preflight()
            self.assertEqual(transport.chat_calls, [])

    def test_run_rejects_every_lifecycle_state_except_ready_or_running_before_post(self) -> None:
        for status in set(RunStatus) - {RunStatus.READY, RunStatus.RUNNING}:
            with self.subTest(status=status.value), tempfile.TemporaryDirectory() as temp:
                transport = FakeTransport()
                engine = self._engine(Path(temp), transport, FakeController())
                engine.lifecycle._write(RunState(
                    self.manifest.run_id, status, 0, "2026-07-15T12:00:00+00:00", "test state",
                ))
                with self.assertRaises(StageTwoError) as context:
                    engine.run(threading.Event())
                self._assert_sanitized(context)
                self.assertEqual(context.exception.code, "invalid_lifecycle_state")
                self.assertEqual(transport.chat_calls, [])
                self.assertEqual(engine.lifecycle.read(self.manifest.run_id).status, status)

    def test_preflight_failure_after_lifecycle_creation_transitions_to_failed(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            engine = self._engine(
                Path(temp), FakeTransport(), FakeController(),
                resource_probe=lambda _health: (_ for _ in ()).throw(
                    RuntimeError("response private prompt Authorization=secret")
                ),
            )
            with self.assertRaises(StageTwoError) as context:
                engine.preflight()
            self._assert_sanitized(context)
            self.assertEqual(engine.lifecycle.read(self.manifest.run_id).status.value, "failed")

    def test_mid_sse_cancellation_stops_after_attempt_and_sanitizes_transport_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp)
            transport = FakeTransport(cancel_during_chat_at=1)
            engine = self._engine(output, transport, FakeController())
            engine.preflight()
            with self.assertRaises(StageTwoError) as context:
                engine.run(threading.Event())
            self._assert_sanitized(context)
            self.assertEqual(context.exception.code, "cancelled")
            self.assertEqual(len(transport.chat_calls), 1)
            self.assertEqual(engine.http_post_attempts, 1)
            evidence = self._post_evidence(output)
            self.assertEqual(len(evidence), 1)
            self.assertNotIn("status", evidence[0])
            self.assertNotIn("prompt", json.dumps(evidence[0]))
            self.assertEqual(engine.lifecycle.read(self.manifest.run_id).status.value, "cancelled")

    def test_process_drift_after_post_prevents_next_post(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            controller = FakeController()
            transport = FakeTransport()
            engine = self._engine(Path(temp), transport, controller)
            engine.preflight()
            original_chat = transport.chat

            def chat_and_drift(*args, **kwargs):
                result = original_chat(*args, **kwargs)
                controller.running = False
                return result

            transport.chat = chat_and_drift
            with self.assertRaises(StageTwoError) as context:
                engine.run(threading.Event())
            self._assert_sanitized(context)
            self.assertEqual(context.exception.code, "operator_identity_changed")
            self.assertEqual(len(transport.chat_calls), 1)

    def test_route_inventory_drift_prevents_next_post(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            transport = FakeTransport(drift_inventory_after_chat=1)
            engine = self._engine(Path(temp), transport, FakeController())
            engine.preflight()
            with self.assertRaises(StageTwoError) as context:
                engine.run(threading.Event())
            self._assert_sanitized(context)
            self.assertEqual(len(transport.chat_calls), 1)

    def test_warning_memory_after_post_prevents_next_post(self) -> None:
        calls = 0

        def probe(_health):
            nonlocal calls
            calls += 1
            pressure = MemoryPressure.WARNING if calls == 3 else MemoryPressure.NORMAL
            return ResourceSnapshot(pressure, (), None)

        with tempfile.TemporaryDirectory() as temp:
            transport = FakeTransport()
            engine = self._engine(Path(temp), transport, FakeController(), probe)
            engine.preflight()
            with self.assertRaises(StageTwoError) as context:
                engine.run(threading.Event())
            self._assert_sanitized(context)
            self.assertEqual(len(transport.chat_calls), 1)

    def test_timeout_records_unknown_post_attempt_and_prevents_next_post(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp)
            transport = FakeTransport(fail_chat_at=1)
            engine = self._engine(output, transport, FakeController())
            engine.preflight()
            with self.assertRaises(StageTwoError) as context:
                engine.run(threading.Event())
            self._assert_sanitized(context)
            self.assertEqual(context.exception.code, "transport_failed")
            self.assertEqual(len(transport.chat_calls), 1)
            self.assertEqual(engine.inference_request_attempts, 1)
            evidence = self._post_evidence(output)
            self.assertEqual(len(evidence), 1)
            self.assertNotIn("status", evidence[0])

    def test_malformed_sse_prevents_next_post(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            transport = FakeTransport(malformed_sse_at=1)
            engine = self._engine(Path(temp), transport, FakeController())
            engine.preflight()
            with self.assertRaises(StageTwoError) as context:
                engine.run(threading.Event())
            self._assert_sanitized(context)
            self.assertEqual(len(transport.chat_calls), 1)

    def test_http_failure_records_status_and_prevents_next_post(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp)
            transport = FakeTransport(http_status_at=1)
            engine = self._engine(output, transport, FakeController())
            engine.preflight()
            with self.assertRaises(StageTwoError) as context:
                engine.run(threading.Event())
            self._assert_sanitized(context)
            self.assertEqual(context.exception.code, "http_post_failed")
            self.assertEqual(len(transport.chat_calls), 1)
            evidence = self._post_evidence(output)
            self.assertEqual(evidence[0]["status"], 500)

    def test_artifact_append_failure_prevents_next_post_and_is_sanitized(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            transport = FakeTransport()
            engine = self._engine(Path(temp), transport, FakeController())
            engine.preflight()
            append = engine.bundle.append_jsonl

            def fail_raw_runs(name, payload):
                if name == "raw-runs.jsonl":
                    raise RuntimeError("response private prompt Authorization=secret")
                append(name, payload)

            engine.bundle.append_jsonl = fail_raw_runs
            with self.assertRaises(StageTwoError) as context:
                engine.run(threading.Event())
            self._assert_sanitized(context)
            self.assertEqual(len(transport.chat_calls), 1)
            self.assertEqual(engine.lifecycle.read(self.manifest.run_id).status.value, "failed")


if __name__ == "__main__":
    unittest.main()
