from __future__ import annotations

from dataclasses import asdict, fields
import hashlib
import json
from pathlib import Path
import threading
import time
from types import MappingProxyType
from typing import Callable, Mapping, Protocol

from .artifacts import ArtifactBundle, ArtifactError
from .lifecycle import LifecycleStore
from .models import BenchmarkManifest, Operation, RunStatus
from .post_attempt_journal import PostAttemptJournal, PostAttemptPhase
from .resources import MemoryPressure, ResourcePolicy, ResourceSnapshot
from .stage_two import (
    HostValidation,
    ModelDescriptor,
    ProcessOwnership,
    StageTwoController,
    StageTwoError,
    direct_health_is_safe,
    discover_route_identity,
    routed_health_is_ready,
)
from .stage_two_profiles import RuntimeProfile
from .stage_two_smoke_measurement import SmokeObservation, summarize_smoke
from .stage_two_smoke_suite import StageTwoSmokeSuite
from .transport import TransportResult


_STAGE_2B_1_OPERATIONS = (
    Operation.INVENTORY,
    Operation.PREFLIGHT,
    Operation.RUN_SCENARIO,
    Operation.STATUS,
    Operation.CANCEL,
    Operation.CLEANUP,
)
_STAGE_2B_1_ROUTES = {
    "direct": "http://127.0.0.1:8080/v1",
    "routed": "http://127.0.0.1:1337/v1",
}
_STAGE_2B_1_LIMITS = {
    "request_timeout_seconds": 120,
    "memory_stop_level": "warning",
    "maximum_in_flight_requests": 1,
    "total_request_limit": 8,
}
_STAGE_2B_1_WORKLOADS = (
    (
        "short-chat",
        "In two sentences, explain why reproducible measurements matter.",
        128,
        "text",
    ),
    (
        "structured-tool-json",
        "Return exactly this JSON object with no markdown or extra text: "
        '{"name":"status","arguments":{"run_id":"stage2b-test","include_details":false}}',
        512,
        "stage2b-status-tool-json",
    ),
)
_STAGE_2B_1_SCHEDULE = (
    ("short-chat", "direct", False, 1, 0),
    ("short-chat", "routed", False, 2, 0),
    ("short-chat", "direct", True, 3, 1),
    ("short-chat", "routed", True, 4, 1),
    ("structured-tool-json", "routed", False, 5, 0),
    ("structured-tool-json", "direct", False, 6, 0),
    ("structured-tool-json", "routed", True, 7, 1),
    ("structured-tool-json", "direct", True, 8, 1),
)
_STAGE_2B_1_PROFILE = RuntimeProfile(
    profile_id="gemma-4-12b-optiq-4bit",
    revision="2",
    runtime_executable=Path("/Users/jrazz/Dev/tools/mlx-optiq/.venv/bin/optiq"),
    runtime_version="0.3.3",
    coordinator_model_id="gemma-4-12b-it-qat-jang_4m",
    package_versions=MappingProxyType({
        "mlx-optiq": "0.3.3",
        "mlx": "0.32.0",
        "mlx-lm": "0.31.3",
        "transformers": "5.12.1",
    }),
    model_repository="mlx-community/gemma-4-12B-it-qat-OptiQ-4bit",
    model_revision="083d338ef60c7ce2b47b27e1447ed92e729c4150",
    model_snapshot=Path(
        "/Users/jrazz/.cache/huggingface/hub/mlx-community/gemma-4-12B-it-qat-OptiQ-4bit"
    ),
    artifact_hashes=MappingProxyType({
        "config.json": "10c3765fec68c1cd13e6b67dd968468fa71c0e66f33b4c8003d9e7565f68b209",
        "optiq_metadata.json": "e64e0271ef661b18c1d6b54c395266681be08771aa3e11804c7a206ada32dddf",
        "model.safetensors.index.json": "62d43537384d711cd4af06295524cb92e1f6d3f3df7fdfbcbcb2628ea5d0f08d",
        "model-00001-of-00002.safetensors": (
            "515896784d9237ed8545ee2668eb886f665b075abe8ae50dc70f10cf173763c1"
        ),
        "model-00002-of-00002.safetensors": (
            "0bea2433d5812dbb20fddc75b4adaa2d33a964420209eabefef94579048b0457"
        ),
    }),
    serve_arguments=(
        "serve", "--model",
        "/Users/jrazz/.cache/huggingface/hub/mlx-community/gemma-4-12B-it-qat-OptiQ-4bit",
        "--host", "127.0.0.1", "--port", "8080", "--no-anthropic", "--no-responses",
        "--no-auth", "--single-model", "--max-concurrent", "1", "--idle-timeout", "0",
        "--max-context", "8192", "--context-scale", "1.0", "--no-stream-experts",
        "--decode-concurrency", "1", "--prompt-concurrency", "1",
    ),
    direct_base_url="http://127.0.0.1:8080/v1",
    routed_base_url="http://127.0.0.1:1337/v1",
    direct_model_identities=(
        "/Users/jrazz/.cache/huggingface/hub/mlx-community/gemma-4-12B-it-qat-OptiQ-4bit:no-think",
        "/Users/jrazz/.cache/huggingface/hub/mlx-community/gemma-4-12B-it-qat-OptiQ-4bit",
        "mlx-community/gemma-4-12B-it-qat-OptiQ-4bit",
    ),
    osaurus_provider_id="Optiq",
    routed_model_id=(
        "optiq//Users/jrazz/.cache/huggingface/hub/"
        "mlx-community/gemma-4-12B-it-qat-OptiQ-4bit:no-think"
    ),
    rejected_local_model_ids=(
        "gemma-4-12b-optiq-4bit",
        "mlx-community/gemma-4-12B-it-qat-OptiQ-4bit",
        "optiq/mlx-community/gemma-4-12B-it-qat-OptiQ-4bit",
        "optiq//Users/jrazz/.cache/huggingface/hub/mlx-community/gemma-4-12B-it-qat-OptiQ-4bit",
    ),
    service_ownership="operator",
    provider_activation="operator_reconnect_required",
)


class StageTwoInferenceTransportProtocol(Protocol):
    def health(self, base_url: str) -> dict[str, object]: ...
    def list_models(self, base_url: str) -> tuple[ModelDescriptor, ...]: ...
    def chat(
        self, base_url: str, model_id: str, prompt: str, max_tokens: int,
        cancel: threading.Event,
    ) -> TransportResult: ...


class StageTwoInferenceEngine:
    def __init__(
        self,
        manifest: BenchmarkManifest,
        profile: RuntimeProfile,
        suite: StageTwoSmokeSuite,
        output_root: Path,
        resource_probe: Callable[[Mapping[str, object]], ResourceSnapshot],
        host_validation: Callable[[], HostValidation],
        controller: StageTwoController,
        transport: StageTwoInferenceTransportProtocol,
        lock_owner: Callable[[], str | None],
    ) -> None:
        self._validate_contract(manifest, profile, suite)
        self._harness = self._is_harness_contract(manifest)
        self.manifest = manifest
        self.profile = profile if self._harness else _STAGE_2B_1_PROFILE
        self.suite = suite
        self.output_root = output_root
        self.resource_probe = resource_probe
        self.host_validation = host_validation
        self.controller = controller
        self.transport = transport
        self.lock_owner = lock_owner
        self.lifecycle = LifecycleStore(output_root)
        self.bundle = ArtifactBundle.create(manifest, output_root)
        self.post_attempt_journal = PostAttemptJournal(self.bundle)
        self.inference_request_attempts = 0
        self.http_post_attempts = 0
        self.observations: list[SmokeObservation] = []

    @staticmethod
    def _is_harness_contract(manifest: BenchmarkManifest) -> bool:
        return (
            manifest.schema_version == "3.5.0"
            and manifest.mode == "harness_inference_probe"
        )

    @staticmethod
    def _validate_contract(
        manifest: BenchmarkManifest,
        profile: RuntimeProfile,
        suite: StageTwoSmokeSuite,
    ) -> None:
        if StageTwoInferenceEngine._is_harness_contract(manifest):
            valid_manifest = (
                manifest.stage == 2
                and manifest.schema_version == "3.5.0"
                and manifest.mode == "harness_inference_probe"
                and manifest.comparison_class == "gemma-optiq-042-harness-route-smoke"
                and manifest.runtime_profile_id == "gemma-4-12b-optiq-4bit"
                and manifest.runtime_profile_revision == "4"
                and manifest.suite_id == "gemma-optiq-042-harness-route-smoke-v1"
                and manifest.suite_revision == "1"
                and manifest.repetitions == 1
                and manifest.route_order == "counterbalanced"
                and tuple(manifest.operations) == _STAGE_2B_1_OPERATIONS
                and dict(manifest.routes or {}) == _STAGE_2B_1_ROUTES
                and dict(manifest.limits or {}) == _STAGE_2B_1_LIMITS
            )
            if not valid_manifest:
                raise ValueError("StageTwoInferenceEngine requires the fixed Stage 2 harness contract")
            valid_profile = (
                profile.profile_id == "gemma-4-12b-optiq-4bit"
                and profile.revision == "4"
                and profile.service_ownership == "harness"
                and profile.runtime_version == "0.4.2"
            )
            valid_suite = (
                suite.suite_id == "gemma-optiq-042-harness-route-smoke-v1"
                and suite.revision == "1"
                and suite.temperature == 0
                and suite.streaming is True
                and tuple(
                    (item.workload_id, item.prompt, item.max_tokens, item.response_contract)
                    for item in suite.workloads
                ) == _STAGE_2B_1_WORKLOADS
                and tuple(
                    (item.workload_id, item.route, item.measured, item.sequence, item.repetition)
                    for item in suite.schedule()
                ) == _STAGE_2B_1_SCHEDULE
            )
            if not valid_profile or not valid_suite:
                raise ValueError("StageTwoInferenceEngine requires the fixed Stage 2 harness contract")
            return
        valid_manifest = (
            manifest.stage == 2
            and manifest.schema_version == "3.3.0"
            and manifest.mode == "operator_inference_probe"
            and manifest.comparison_class == "gemma-optiq-operator-route-smoke"
            and manifest.runtime_profile_id == "gemma-4-12b-optiq-4bit"
            and manifest.runtime_profile_revision == "2"
            and manifest.suite_id == "gemma-optiq-route-smoke-v1"
            and manifest.suite_revision == "1"
            and manifest.repetitions == 1
            and manifest.route_order == "counterbalanced"
            and tuple(manifest.operations) == _STAGE_2B_1_OPERATIONS
            and dict(manifest.routes or {}) == _STAGE_2B_1_ROUTES
            and dict(manifest.limits or {}) == _STAGE_2B_1_LIMITS
        )
        if not valid_manifest:
            raise ValueError("StageTwoInferenceEngine requires the fixed Stage 2B-1 contract")
        valid_profile = profile == _STAGE_2B_1_PROFILE
        valid_suite = (
            suite.suite_id == "gemma-optiq-route-smoke-v1"
            and suite.revision == "1"
            and suite.temperature == 0
            and suite.streaming is True
            and tuple(
                (item.workload_id, item.prompt, item.max_tokens, item.response_contract)
                for item in suite.workloads
            ) == _STAGE_2B_1_WORKLOADS
            and tuple(
                (item.workload_id, item.route, item.measured, item.sequence, item.repetition)
                for item in suite.schedule()
            ) == _STAGE_2B_1_SCHEDULE
        )
        if not valid_profile or not valid_suite:
            raise ValueError("StageTwoInferenceEngine requires the fixed Stage 2B-1 contract")

    def _service_lifecycle_actions(self) -> int:
        if not self._harness:
            return 0
        actions = getattr(self.controller, "lifecycle_actions", None)
        if not isinstance(actions, int):
            raise StageTwoError(
                "harness_lifecycle_actions_unavailable",
                "harness controller missing lifecycle_actions",
            )
        return actions

    @staticmethod
    def _external_call(callback: Callable[[], object]) -> tuple[bool, object | None]:
        try:
            return True, callback()
        except Exception:
            return False, None

    def _event(self, event: str, **details: object) -> None:
        self.bundle.append_jsonl("service-events.jsonl", {"event": event, **details})

    def _validate_provider_activation(self) -> None:
        activation = self.profile.provider_activation
        if activation == "verify_routed_id_only":
            if not self._harness:
                raise StageTwoError(
                    "provider_activation_failed",
                    "verify_routed_id_only requires the harness-unattended contract",
                )
            return
        if activation != "operator_reconnect_required":
            raise StageTwoError(
                "provider_activation_failed",
                "unsupported provider activation policy",
            )

    def _validate_host(self, validation: HostValidation) -> None:
        if validation.runtime_identity.get("version") != self.profile.runtime_version:
            raise StageTwoError("runtime_identity_failed", "mlx-optiq runtime version differs from profile")
        if validation.runtime_identity.get("packages") != self.profile.package_versions:
            raise StageTwoError("runtime_identity_failed", "mlx-optiq package versions differ from profile")
        if validation.artifact_identity.get("revision") != self.profile.model_revision:
            raise StageTwoError("artifact_identity_failed", "OptiQ model revision differs from profile")
        if validation.artifact_identity.get("hashes") != self.profile.artifact_hashes:
            raise StageTwoError("artifact_identity_failed", "OptiQ artifact hashes differ from profile")
        self._validate_provider_activation()
        provider = validation.provider_identity
        if provider.get("provider_id") != self.profile.osaurus_provider_id or provider.get("enabled") is not True:
            raise StageTwoError("provider_identity_failed", "approved Osaurus provider is unavailable")
        if provider.get("custom_header_count") != 0 or provider.get("secret_header_key_count") != 0:
            raise StageTwoError("provider_headers_forbidden", "Osaurus OptiQ headers must be empty")

    def _load_operator_identity(self) -> ProcessOwnership:
        identity: ProcessOwnership | None = None
        try:
            payload = json.loads(
                (self.bundle.path / "operator-service-identity.json").read_text(encoding="utf-8")
            )
            identity = ProcessOwnership(
                pid=int(payload["pid"]),
                parent_pid=int(payload["parent_pid"]),
                process_group_id=int(payload["process_group_id"]),
                started_at=str(payload["started_at"]),
                command_sha256=str(payload["command_sha256"]),
            )
        except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError):
            pass
        if identity is None:
            raise StageTwoError(
                "operator_identity_failed", "operator service identity evidence is unavailable"
            )
        return identity

    def _direct_health_is_safe(self, health: Mapping[str, object]) -> bool:
        return direct_health_is_safe(health, (
            str(self.profile.model_snapshot),
            self.profile.model_repository,
            *self.profile.direct_model_identities,
        ))

    def _request_evidence(
        self, method: str, endpoint: str, payload: object, sequence: int | None = None,
        workload_id: str | None = None, route: str | None = None,
    ) -> None:
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        record: dict[str, object] = {
            "method": method,
            "endpoint": endpoint,
            "status": 200,
            "payload_sha256": hashlib.sha256(encoded).hexdigest(),
        }
        if sequence is not None:
            record["sequence"] = sequence
        if workload_id is not None:
            record["workload_id"] = workload_id
        if route is not None:
            record["route"] = route
        self.bundle.append_jsonl("request-evidence.jsonl", record)

    def _post_attempt_evidence(
        self,
        sequence: int,
        workload_id: str,
        route: str,
        model_id: str,
        max_tokens: int,
        status: int | None,
    ) -> None:
        record: dict[str, object] = {
            "method": "POST",
            "endpoint": f"{route}_chat_completions",
            "sequence": sequence,
            "workload_id": workload_id,
            "route": route,
            "fixed_request_sha256": self._fixed_request_sha256(
                model_id, workload_id, max_tokens,
            ),
        }
        if status is not None:
            record["status"] = status
        self.bundle.append_jsonl("request-evidence.jsonl", record)

    @staticmethod
    def _fixed_request_sha256(model_id: str, workload_id: str, max_tokens: int) -> str:
        fixed_request = {
            "model": model_id,
            "workload_id": workload_id,
            "max_tokens": max_tokens,
            "temperature": 0,
            "stream": True,
            "stream_options": {"include_usage": True},
        }
        return hashlib.sha256(
            json.dumps(fixed_request, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()

    def _health(
        self, base_url: str, endpoint: str, sequence: int | None = None,
    ) -> dict[str, object]:
        succeeded, payload = self._external_call(lambda: self.transport.health(base_url))
        if not succeeded or not isinstance(payload, dict):
            raise StageTwoError("transport_failed", "Stage 2B-1 health transport failed")
        self._request_evidence("GET", endpoint, payload, sequence)
        return payload

    def _models(
        self, base_url: str, endpoint: str, sequence: int | None = None,
    ) -> tuple[ModelDescriptor, ...]:
        succeeded, result = self._external_call(lambda: self.transport.list_models(base_url))
        if not succeeded or not isinstance(result, tuple):
            raise StageTwoError("transport_failed", "Stage 2B-1 inventory transport failed")
        models = result
        self._request_evidence(
            "GET", endpoint, [item.evidence() for item in models], sequence,
        )
        return models

    def _memory_sample(self, phase: str, snapshot: ResourceSnapshot) -> None:
        self.bundle.append_jsonl("memory-samples.jsonl", {
            "phase": phase,
            "memory_pressure": snapshot.memory_pressure.value,
            "osaurus_native_model_loaded": snapshot.osaurus_native_model_loaded,
            "osaurus_native_models": list(snapshot.osaurus_native_models),
        })

    def _assert_current_lock(self) -> None:
        succeeded, owner = self._external_call(self.lock_owner)
        if not succeeded or owner != self.manifest.run_id:
            raise StageTwoError("lock_identity_failed", "current run does not own the active lock")

    def _assert_normal_resources(self, snapshot: ResourceSnapshot, phase: str) -> None:
        try:
            ResourcePolicy(self.profile.coordinator_model_id).evaluate(snapshot)
        except Exception:
            raise StageTwoError("resource_gate_failed", "Stage 2B-1 resource policy failed")
        self._memory_sample(phase, snapshot)
        if snapshot.memory_pressure is not MemoryPressure.NORMAL:
            raise StageTwoError("resource_gate_failed", "Stage 2B-1 requires normal memory pressure")

    def _observe_routes(
        self, sequence: int | None = None,
    ) -> tuple[dict[str, object], tuple[ModelDescriptor, ...], tuple[ModelDescriptor, ...]]:
        direct_health = self._health(self.profile.direct_base_url, "direct_health", sequence)
        routed_health = self._health(self.profile.routed_base_url, "routed_health", sequence)
        if not self._direct_health_is_safe(direct_health):
            raise StageTwoError("operator_health_failed", "direct health is unavailable or conflicting")
        if not routed_health_is_ready(routed_health):
            raise StageTwoError("route_health_failed", "routed health is unavailable")
        direct_models = self._models(self.profile.direct_base_url, "direct_models", sequence)
        routed_models = self._models(self.profile.routed_base_url, "routed_models", sequence)
        discover_route_identity(self.profile, direct_models, routed_models)
        return routed_health, direct_models, routed_models

    def _observe_routes_for_preflight(
        self,
    ) -> tuple[dict[str, object], tuple[ModelDescriptor, ...], tuple[ModelDescriptor, ...]]:
        """Harness lane: allow one operator reconnect tap while OptiQ stays up."""
        if not self._harness:
            return self._observe_routes()
        deadline = time.monotonic() + 300.0
        last_error: StageTwoError | None = None
        while time.monotonic() < deadline:
            try:
                result = self._observe_routes()
                if last_error is not None:
                    self._event("provider_reconnect_tap_observed", required_routed_model_id=self.profile.routed_model_id)
                return result
            except StageTwoError as error:
                if error.code != "route_identity_failed":
                    raise
                last_error = error
                self._event(
                    "provider_reconnect_tap_waiting",
                    required_routed_model_id=self.profile.routed_model_id,
                    seconds_remaining=max(0, int(deadline - time.monotonic())),
                )
                time.sleep(2.0)
        assert last_error is not None
        raise last_error

    def _resource_snapshot(self, routed_health: Mapping[str, object]) -> ResourceSnapshot:
        succeeded, snapshot = self._external_call(lambda: self.resource_probe(routed_health))
        if not succeeded or not isinstance(snapshot, ResourceSnapshot):
            raise StageTwoError("resource_gate_failed", "Stage 2B-1 resource probe failed")
        return snapshot

    def _fail(self, run_id: str, target: RunStatus) -> None:
        try:
            current = self.lifecycle.read(run_id)
            if current.status not in {RunStatus.CANCELLED, RunStatus.FAILED}:
                self.lifecycle.transition(run_id, target, "Stage 2B-1 stopped before acceptance")
        except Exception:
            pass

    def _raise_recovered_failure(self, run_id: str, failure: Exception) -> None:
        target = (
            RunStatus.CANCELLED
            if isinstance(failure, StageTwoError) and failure.code == "cancelled"
            else RunStatus.FAILED
        )
        self._fail(run_id, target)
        if isinstance(failure, StageTwoError):
            raise failure
        raise StageTwoError("infrastructure_failed", "Stage 2B-1 stopped before acceptance")

    def preflight(self) -> dict[str, object]:
        run_id = self.manifest.run_id
        self.lifecycle.create(run_id)
        failure: Exception | None = None
        try:
            self.lifecycle.transition(run_id, RunStatus.PREFLIGHT, "Stage 2B-1 manifest and policy validated")
            succeeded, identity = self._external_call(self.controller.capture)
            if not succeeded or not isinstance(identity, ProcessOwnership):
                raise StageTwoError("operator_identity_failed", "operator service identity is unavailable")
            self.bundle.write_json("operator-service-identity.json", asdict(identity))
            self._event("operator_service_observed", pid=identity.pid, command_sha256=identity.command_sha256)
            self._assert_current_lock()
            succeeded, validation = self._external_call(self.host_validation)
            if not succeeded or not isinstance(validation, HostValidation):
                raise StageTwoError("host_validation_failed", "Stage 2B-1 host validation failed")
            self._validate_host(validation)
            routed_health, direct_models, routed_models = self._observe_routes_for_preflight()
            self._assert_normal_resources(self._resource_snapshot(routed_health), "preflight")
            self.lifecycle.transition(run_id, RunStatus.RESOURCE_GATE, "normal serial resource gate passed")
            self.bundle.write_json("runtime-identity.json", dict(validation.runtime_identity))
            self.bundle.write_json("artifact-identity.json", dict(validation.artifact_identity))
            self.bundle.write_json("endpoint-inventory.json", {
            "direct": {
                "base_url": self.profile.direct_base_url,
                "models": [item.evidence() for item in direct_models],
            },
            "routed": {
                "base_url": self.profile.routed_base_url,
                "models": [item.evidence() for item in routed_models],
            },
            "expected_routed_model_id": self.profile.routed_model_id,
            "route_identity": {
                "status": "PASS",
                "discovered_routed_model_id": self.profile.routed_model_id,
            },
            })
            self.bundle.write_json("inference-suite.json", {
            "suite_id": self.suite.suite_id,
            "revision": self.suite.revision,
            "temperature": self.suite.temperature,
            "streaming": self.suite.streaming,
            "workloads": [
                {
                    "workload_id": item.workload_id,
                    "max_tokens": item.max_tokens,
                    "response_contract": item.response_contract,
                }
                for item in self.suite.workloads
            ],
            "request_count": len(self.suite.schedule()),
            })
            preflight_record: dict[str, object] = {
            "ok": True,
            "stage": 2,
            "mode": self.manifest.mode,
            "provider_identity": dict(validation.provider_identity),
            "route_identity": "PASS",
            "resource_gate": "PASS",
            "model_load_attempts": 0,
            "inference_request_attempts": 0,
            "http_post_attempts": 0,
            "service_lifecycle_actions": self._service_lifecycle_actions(),
            }
            if self.profile.provider_activation is not None:
                preflight_record["provider_activation"] = self.profile.provider_activation
            self.bundle.write_json("preflight.json", preflight_record)
            self.lifecycle.transition(run_id, RunStatus.ENDPOINT_IDENTITY, "Stage 2B-1 route identity proven")
            state = self.lifecycle.transition(run_id, RunStatus.READY, "Stage 2B-1 inference probe ready")
        except Exception as error:
            failure = error
        if failure is not None:
            self._raise_recovered_failure(run_id, failure)
        return {
            "run_id": run_id,
            "state": state.status.value,
            "manifest_validation": "PASS",
            "runtime_identity": "PASS",
            "artifact_identity": "PASS",
            "provider_identity": "PASS",
            "route_identity": "PASS",
            "resource_gate": "PASS",
            "manifest": {
                "schema_version": self.manifest.schema_version,
                "run_id": run_id,
                "stage": 2,
                "mode": self.manifest.mode,
                "comparison_class": self.manifest.comparison_class,
                "runtime_profile_id": self.manifest.runtime_profile_id,
                "runtime_profile_revision": self.manifest.runtime_profile_revision,
                "suite_id": self.manifest.suite_id,
                "suite_revision": self.manifest.suite_revision,
                "repetitions": self.manifest.repetitions,
                "route_order": self.manifest.route_order,
                "routes": dict(self.manifest.routes or {}),
                "limits": dict(self.manifest.limits or {}),
            },
            "model_load_attempts": 0,
            "inference_request_attempts": 0,
            "http_post_attempts": 0,
            "service_lifecycle_actions": self._service_lifecycle_actions(),
        }

    def _gate_before_post(self, cancel: threading.Event, sequence: int) -> dict[str, object]:
        if cancel.is_set():
            raise StageTwoError("cancelled", "Stage 2B-1 cancelled before next request")
        self._assert_current_lock()
        identity = self._load_operator_identity()
        succeeded, matches = self._external_call(lambda: self.controller.matches(identity))
        if not succeeded or matches is not True:
            raise StageTwoError("operator_identity_changed", "operator service identity changed")
        routed_health, _, _ = self._observe_routes(sequence)
        self._assert_normal_resources(
            self._resource_snapshot(routed_health), f"before_request_{sequence}",
        )
        return routed_health

    def _gate_after_post(self, sequence: int) -> None:
        identity = self._load_operator_identity()
        succeeded, matches = self._external_call(lambda: self.controller.matches(identity))
        if not succeeded or matches is not True:
            raise StageTwoError("operator_identity_changed", "operator service identity changed")
        routed_health = self._health(
            self.profile.routed_base_url, "routed_health_after_post", sequence,
        )
        if not routed_health_is_ready(routed_health):
            raise StageTwoError("route_health_failed", "routed health is unavailable after inference")
        self._assert_normal_resources(
            self._resource_snapshot(routed_health), f"after_request_{sequence}",
        )

    def _chat(
        self,
        base_url: str,
        model_id: str,
        prompt: str,
        max_tokens: int,
        cancel: threading.Event,
        sequence: int,
        workload_id: str,
        route: str,
    ) -> TransportResult:
        self.post_attempt_journal.record(
            sequence=sequence, phase=PostAttemptPhase.PREPARED,
            workload_id=workload_id, route=route,
        )
        self.post_attempt_journal.record(
            sequence=sequence, phase=PostAttemptPhase.DISPATCHED,
            workload_id=workload_id, route=route,
        )
        failure: StageTwoError | None = None
        result: TransportResult | None = None
        try:
            result = self.transport.chat(base_url, model_id, prompt, max_tokens, cancel)
        except StageTwoError as error:
            detail = (
                "cancelled" if cancel.is_set() or error.reason == "cancelled"
                else (error.reason or "transport_failed")
            )
            self.post_attempt_journal.record(
                sequence=sequence, phase=PostAttemptPhase.FAILED,
                workload_id=workload_id, route=route,
                detail=detail,
                http_status=error.http_status,
            )
            self._post_attempt_evidence(
                sequence, workload_id, route, model_id, max_tokens, error.http_status,
            )
            if cancel.is_set() or error.reason == "cancelled" or error.code == "cancelled":
                failure = StageTwoError("cancelled", "Stage 2B-1 cancelled during request")
            else:
                failure = StageTwoError(
                    error.code,
                    "Stage 2B-1 chat transport failed",
                    reason=error.reason or "transport_failed",
                    http_status=error.http_status,
                )
        except Exception:
            detail = "cancelled" if cancel.is_set() else "transport_failed"
            self.post_attempt_journal.record(
                sequence=sequence, phase=PostAttemptPhase.FAILED,
                workload_id=workload_id, route=route,
                detail=detail,
            )
            self._post_attempt_evidence(
                sequence, workload_id, route, model_id, max_tokens, None,
            )
            if cancel.is_set():
                failure = StageTwoError("cancelled", "Stage 2B-1 cancelled during request")
            else:
                failure = StageTwoError("transport_failed", "Stage 2B-1 chat transport failed")
        if failure is not None:
            raise failure
        if not isinstance(result, TransportResult):
            self.post_attempt_journal.record(
                sequence=sequence, phase=PostAttemptPhase.FAILED,
                workload_id=workload_id, route=route,
                detail="transport_failed",
            )
            self._post_attempt_evidence(
                sequence, workload_id, route, model_id, max_tokens, None,
            )
            raise StageTwoError("transport_failed", "Stage 2B-1 chat transport failed")
        self.post_attempt_journal.record(
            sequence=sequence, phase=PostAttemptPhase.COMPLETED,
            workload_id=workload_id, route=route,
        )
        status = result.http_status if type(result.http_status) is int else None
        self._post_attempt_evidence(
            sequence, workload_id, route, model_id, max_tokens, status,
        )
        if status != 200:
            raise StageTwoError("http_post_failed", "Stage 2B-1 chat returned a non-200 status")
        if result.stream_valid is not True:
            raise StageTwoError("sse_invalid", "Stage 2B-1 chat stream was invalid")
        return result

    def run(self, cancel: threading.Event) -> dict[str, object]:
        run_id = self.manifest.run_id
        try:
            state = self.lifecycle.read(run_id)
        except Exception:
            raise StageTwoError(
                "invalid_lifecycle_state", "Stage 2B-1 run requires ready or running lifecycle state"
            ) from None
        if state.status not in {RunStatus.READY, RunStatus.RUNNING}:
            raise StageTwoError(
                "invalid_lifecycle_state", "Stage 2B-1 run requires ready or running lifecycle state"
            )
        failure: Exception | None = None
        try:
            if state.status is RunStatus.READY:
                self.lifecycle.transition(run_id, RunStatus.RUNNING, "fixed Stage 2B-1 worker started")
            self.lifecycle.transition(run_id, RunStatus.WARMUP, "fixed smoke cohort started")
            workloads = {item.workload_id: item for item in self.suite.workloads}
            for request in self.suite.schedule():
                if self.http_post_attempts >= 8:
                    raise StageTwoError(
                        "request_limit_exceeded", "Stage 2B-1 permits at most eight POST attempts"
                    )
                self._gate_before_post(cancel, request.sequence)
                workload = workloads[request.workload_id]
                if request.route == "direct":
                    base_url = self.profile.direct_base_url
                    model_id = self.profile.direct_model_identities[0]
                else:
                    base_url = self.profile.routed_base_url
                    model_id = self.profile.routed_model_id
                self.inference_request_attempts += 1
                self.http_post_attempts += 1
                result = self._chat(
                    base_url, model_id, workload.prompt, workload.max_tokens, cancel,
                    request.sequence, workload.workload_id, request.route,
                )
                contract_result = self.suite.validate_response(
                    workload.response_contract, result.content,
                )
                observation = SmokeObservation.from_result(
                    request, workload, result, contract_result,
                )
                self.bundle.append_jsonl("raw-runs.jsonl", observation.as_json())
                self.observations.append(observation)
                del result
                self._gate_after_post(request.sequence)
            self.lifecycle.transition(run_id, RunStatus.MEASURED, "fixed smoke cohort complete")
            summary = summarize_smoke(tuple(self.observations))
            self.bundle.write_json("direct-observations.json", {
                "route": "direct", "observations": summary["direct_observations"],
            })
            self.bundle.write_json("routed-observations.json", {
                "route": "routed", "observations": summary["routed_observations"],
            })
            self.bundle.write_json("smoke-summary.json", summary)
            self.lifecycle.transition(run_id, RunStatus.ARTIFACT_VALIDATION, "Stage 2B-1 evidence reconciled")
            final = self.lifecycle.transition(
                run_id, RunStatus.AWAITING_REVIEW,
                "harness shutdown required" if self._harness else "operator shutdown required",
            )
            return {
                "run_id": run_id,
                "state": final.status.value,
                "inference_path_acceptance": summary["inference_path_acceptance"],
                "behavioral_contract_acceptance": summary["behavioral_contract_acceptance"],
                "inference_request_attempts": self.inference_request_attempts,
                "http_post_attempts": self.http_post_attempts,
                "model_load_attempts": 0,
                "service_lifecycle_actions": self._service_lifecycle_actions(),
                "manager_review_required": True,
            }
        except Exception as error:
            failure = error
        if failure is not None:
            self._raise_recovered_failure(run_id, failure)
        raise AssertionError("unreachable")

    def _read_json(self, name: str) -> object:
        try:
            return json.loads((self.bundle.path / name).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            raise StageTwoError("evidence_incomplete", "Stage 2B-1 evidence is unavailable") from None

    def _read_jsonl(self, name: str, *, optional: bool = False) -> list[object]:
        try:
            return [
                json.loads(line)
                for line in (self.bundle.path / name).read_text(encoding="utf-8").splitlines()
            ]
        except FileNotFoundError:
            if optional:
                return []
            raise StageTwoError("evidence_incomplete", "Stage 2B-1 evidence is unavailable") from None
        except (OSError, json.JSONDecodeError):
            raise StageTwoError("evidence_incomplete", "Stage 2B-1 evidence is unavailable") from None

    @staticmethod
    def _expect_mapping(payload: object) -> Mapping[str, object]:
        if not isinstance(payload, dict):
            raise StageTwoError("evidence_incomplete", "Stage 2B-1 evidence is invalid")
        return payload

    def _reconcile_endpoint_identity(self) -> None:
        inventory = self._expect_mapping(self._read_json("endpoint-inventory.json"))
        direct = self._expect_mapping(inventory.get("direct"))
        routed = self._expect_mapping(inventory.get("routed"))
        if (
            direct.get("base_url") != self.profile.direct_base_url
            or routed.get("base_url") != self.profile.routed_base_url
            or inventory.get("expected_routed_model_id") != self.profile.routed_model_id
        ):
            raise StageTwoError("evidence_incomplete", "Stage 2B-1 route evidence is invalid")
        try:
            direct_models = tuple(ModelDescriptor(**item) for item in direct["models"])
            routed_models = tuple(ModelDescriptor(**item) for item in routed["models"])
            discovered = inventory["route_identity"]["discovered_routed_model_id"]
        except (KeyError, TypeError):
            raise StageTwoError("evidence_incomplete", "Stage 2B-1 route evidence is invalid") from None
        if (
            inventory.get("route_identity", {}).get("status") != "PASS"
            or discover_route_identity(self.profile, direct_models, routed_models)
            != self.profile.routed_model_id
            or discovered != self.profile.routed_model_id
        ):
            raise StageTwoError("evidence_incomplete", "Stage 2B-1 route evidence is invalid")

    def _reconcile_inference_suite(self) -> None:
        expected = {
            "suite_id": self.suite.suite_id,
            "revision": self.suite.revision,
            "temperature": self.suite.temperature,
            "streaming": self.suite.streaming,
            "workloads": [
                {
                    "workload_id": item.workload_id,
                    "max_tokens": item.max_tokens,
                    "response_contract": item.response_contract,
                }
                for item in self.suite.workloads
            ],
            "request_count": len(self.suite.schedule()),
        }
        if self._read_json("inference-suite.json") != expected:
            raise StageTwoError("evidence_incomplete", "Stage 2B-1 inference suite evidence is invalid")

    @staticmethod
    def _is_sha256(value: object) -> bool:
        return (
            isinstance(value, str)
            and len(value) == 64
            and all(character in "0123456789abcdef" for character in value)
        )

    def _request_trace(self) -> tuple[tuple[str, str, int | None, object | None], ...]:
        trace: list[tuple[str, str, int | None, object | None]] = [
            ("GET", endpoint, None, None)
            for endpoint in ("direct_health", "routed_health", "direct_models", "routed_models")
        ]
        workloads = {item.workload_id: item for item in self.suite.workloads}
        for request in self.suite.schedule():
            trace.extend((
                ("GET", "direct_health", request.sequence, None),
                ("GET", "routed_health", request.sequence, None),
                ("GET", "direct_models", request.sequence, None),
                ("GET", "routed_models", request.sequence, None),
                ("POST", f"{request.route}_chat_completions", request.sequence, request),
                ("GET", "routed_health_after_post", request.sequence, None),
            ))
        return tuple(trace)

    def _validate_request_record(
        self,
        record: Mapping[str, object],
        expected: tuple[str, str, int | None, object | None],
        *,
        complete: bool,
    ) -> None:
        method, endpoint, sequence, request = expected
        if method == "GET":
            expected_keys = {"method", "endpoint", "status", "payload_sha256"}
            if sequence is not None:
                expected_keys.add("sequence")
            if (
                set(record) != expected_keys
                or record.get("method") != "GET"
                or record.get("endpoint") != endpoint
                or record.get("status") != 200
                or not self._is_sha256(record.get("payload_sha256"))
                or (sequence is not None and record.get("sequence") != sequence)
            ):
                raise StageTwoError("evidence_incomplete", "Stage 2B-1 request evidence is invalid")
            return

        if not isinstance(request, object):
            raise StageTwoError("evidence_incomplete", "Stage 2B-1 request evidence is invalid")
        workload_id = getattr(request, "workload_id", None)
        route = getattr(request, "route", None)
        workload = next(
            (item for item in self.suite.workloads if item.workload_id == workload_id), None,
        )
        model_id = (
            self.profile.direct_model_identities[0]
            if route == "direct" else self.profile.routed_model_id
        )
        expected_keys = {
            "method", "endpoint", "sequence", "workload_id", "route", "fixed_request_sha256",
        }
        if "status" in record:
            expected_keys.add("status")
        if (
            workload is None
            or set(record) != expected_keys
            or record.get("method") != "POST"
            or record.get("endpoint") != endpoint
            or record.get("sequence") != sequence
            or record.get("workload_id") != workload_id
            or record.get("route") != route
            or record.get("fixed_request_sha256") != self._fixed_request_sha256(
                model_id, workload.workload_id, workload.max_tokens,
            )
            or ("status" in record and (
                type(record["status"]) is not int or record["status"] < 100 or record["status"] > 599
            ))
            or (complete and record.get("status") != 200)
        ):
            raise StageTwoError("evidence_incomplete", "Stage 2B-1 request evidence is invalid")

    def _reconcile_request_evidence(self, *, complete: bool) -> list[Mapping[str, object]]:
        records = [
            self._expect_mapping(payload)
            for payload in self._read_jsonl("request-evidence.jsonl", optional=not complete)
        ]
        trace = self._request_trace()
        if (complete and len(records) != len(trace)) or (not complete and len(records) > len(trace)):
            raise StageTwoError("evidence_incomplete", "Stage 2B-1 request evidence is invalid")
        for record, expected in zip(records, trace):
            self._validate_request_record(record, expected, complete=complete)
        posts = [record for record in records if record.get("method") == "POST"]
        if complete and len(posts) != len(self.suite.schedule()):
            raise StageTwoError("evidence_incomplete", "Stage 2B-1 request evidence is invalid")
        return posts

    def _load_observations(self, *, optional: bool) -> list[SmokeObservation]:
        expected_keys = {field.name for field in fields(SmokeObservation)}
        observations: list[SmokeObservation] = []
        for payload in self._read_jsonl("raw-runs.jsonl", optional=optional):
            record = self._expect_mapping(payload)
            if set(record) != expected_keys:
                raise StageTwoError("evidence_incomplete", "Stage 2B-1 observation evidence is invalid")
            try:
                observations.append(SmokeObservation(**record))
            except (TypeError, ValueError):
                raise StageTwoError("evidence_incomplete", "Stage 2B-1 observation evidence is invalid") from None
        return observations

    def _conservative_post_attempts(self, posts: list[Mapping[str, object]]) -> int:
        """Never claim fewer POSTs than the durable journal recorded as dispatched.

        `request-evidence.jsonl` and the journal are independently appended;
        when they disagree, the journal is the crash-consistent authority and
        the higher (more conservative) count wins.
        """
        return max(len(posts), self.post_attempt_journal.conservative_post_count())

    def _reconcile_partial_observations(
        self, posts: list[Mapping[str, object]],
    ) -> list[SmokeObservation]:
        observations = self._load_observations(optional=True)
        schedule = tuple(self.suite.schedule())
        observed_schedule = tuple(
            (item.workload_id, item.route, item.measured, item.sequence, item.repetition)
            for item in observations
        )
        expected_schedule = tuple(
            (item.workload_id, item.route, item.measured, item.sequence, item.repetition)
            for item in schedule[:len(observations)]
        )
        if observed_schedule != expected_schedule:
            raise StageTwoError("evidence_incomplete", "Stage 2B-1 observation schedule is invalid")
        successful_sequences = {
            record["sequence"] for record in posts if record.get("status") == 200
        }
        if any(item.sequence not in successful_sequences for item in observations):
            raise StageTwoError("evidence_incomplete", "Stage 2B-1 observation evidence is invalid")
        return observations

    def _reconcile_observations(self) -> dict[str, object]:
        observations = self._load_observations(optional=False)
        schedule = tuple(self.suite.schedule())
        observed_schedule = tuple(
            (item.workload_id, item.route, item.measured, item.sequence, item.repetition)
            for item in observations
        )
        expected_schedule = tuple(
            (item.workload_id, item.route, item.measured, item.sequence, item.repetition)
            for item in schedule
        )
        if observed_schedule != expected_schedule:
            raise StageTwoError("evidence_incomplete", "Stage 2B-1 observation schedule is invalid")
        summary = summarize_smoke(tuple(observations))
        stored_summary = self._expect_mapping(self._read_json("smoke-summary.json"))
        direct = self._expect_mapping(self._read_json("direct-observations.json"))
        routed = self._expect_mapping(self._read_json("routed-observations.json"))
        if (
            stored_summary != summary
            or direct != {"route": "direct", "observations": summary["direct_observations"]}
            or routed != {"route": "routed", "observations": summary["routed_observations"]}
        ):
            raise StageTwoError("evidence_incomplete", "Stage 2B-1 smoke evidence is invalid")
        return summary

    def _reconcile_memory(self) -> None:
        samples = [self._expect_mapping(payload) for payload in self._read_jsonl("memory-samples.jsonl")]
        expected_phases = {"preflight"} | {
            f"{position}_request_{sequence}"
            for sequence in range(1, 9) for position in ("before", "after")
        }
        phases = [sample.get("phase") for sample in samples]
        if (
            set(phases) != expected_phases
            or len(phases) != len(expected_phases)
            or any(sample.get("memory_pressure") != MemoryPressure.NORMAL.value for sample in samples)
        ):
            raise StageTwoError("evidence_incomplete", "Stage 2B-1 memory evidence is invalid")

    def _assert_redacted_artifacts(self) -> None:
        prohibited = (
            *[item[1] for item in _STAGE_2B_1_WORKLOADS],
            "Reproducible measurements make comparisons reliable.",
            "Authorization", "Bearer", "fake-secret",
        )
        for path in self.bundle.path.iterdir():
            if path.is_file() and path.name != "state.json":
                try:
                    contents = path.read_text(encoding="utf-8")
                except OSError:
                    raise StageTwoError("evidence_incomplete", "Stage 2B-1 artifacts are unavailable") from None
                if any(fragment in contents for fragment in prohibited):
                    raise StageTwoError("evidence_incomplete", "Stage 2B-1 artifact redaction failed")

    def _complete_summary(self, smoke: Mapping[str, object]) -> dict[str, object]:
        return {
            "run_id": self.manifest.run_id,
            "stage": 2,
            "mode": self.manifest.mode,
            "comparison_class": self.manifest.comparison_class,
            "runtime_profile_id": self.profile.profile_id,
            "runtime_profile_revision": self.profile.revision,
            "suite_id": self.suite.suite_id,
            "suite_revision": self.suite.revision,
            "state": "cleaned",
            "disposition": "PASS",
            "inference_path_acceptance": "PASS",
            "behavioral_contract_acceptance": smoke["behavioral_contract_acceptance"],
            "measured_requests": 4,
            "excluded_warmups": 4,
            "inference_request_attempts": 8,
            "http_post_attempts": 8,
            "model_load_attempts": 0,
            "service_lifecycle_actions": self._service_lifecycle_actions(),
            "operator_shutdown_verified": "PASS",
            "manager_review_required": True,
        }

    def _partial_summary(
        self, state: RunStatus, *, post_attempts: int, observations: int,
    ) -> dict[str, object]:
        acceptance = "STOPPED" if state is RunStatus.CANCELLED else "FAIL"
        return {
            "run_id": self.manifest.run_id,
            "stage": 2,
            "mode": self.manifest.mode,
            "comparison_class": self.manifest.comparison_class,
            "runtime_profile_id": self.profile.profile_id,
            "runtime_profile_revision": self.profile.revision,
            "suite_id": self.suite.suite_id,
            "suite_revision": self.suite.revision,
            "state": "cleaned",
            "disposition": "STOPPED",
            "inference_path_acceptance": acceptance,
            "behavioral_contract_acceptance": "STOPPED",
            "completed_requests": observations,
            "inference_request_attempts": post_attempts,
            "http_post_attempts": post_attempts,
            "model_load_attempts": 0,
            "service_lifecycle_actions": self._service_lifecycle_actions(),
            "operator_shutdown_verified": "PASS",
            "manager_review_required": True,
        }

    def _finalize_and_validate(self, summary: dict[str, object], *, partial: bool) -> dict[str, object]:
        self._assert_current_lock()
        identity = self._load_operator_identity()
        shutdown_recheck_failed = False
        try:
            self.controller.assert_stopped(identity)
        except Exception:
            shutdown_recheck_failed = True
        if shutdown_recheck_failed:
            raise StageTwoError(
                "cleanup_failed", "Stage 2B-1 cleanup could not be completed",
            )
        prior_lifecycle_lines = self.lifecycle.verified_history(self.manifest.run_id)
        if partial:
            self.bundle.finalize_partial(summary)
        else:
            self.bundle.finalize(summary)
        self.lifecycle.transition(
            self.manifest.run_id, RunStatus.CLEANED, "Stage 2B-1 evidence cleaned",
        )
        self.bundle.reseal_after_state_transition(
            expected_lifecycle_lines=self.lifecycle.verified_history(self.manifest.run_id),
            prior_lifecycle_lines=prior_lifecycle_lines,
        )
        validation = self.bundle.validate_partial() if partial else self.bundle.validate()
        return {
            **summary,
            "artifact_directory": str(self.bundle.path),
            "artifact_validation": "PASS" if validation.valid else "FAIL",
            "checksum_validation": "PASS" if validation.valid else "FAIL",
        }

    def _recover_cleaned(self) -> dict[str, object]:
        summary = self._expect_mapping(self._read_json("summary.json"))
        disposition = summary.get("disposition")
        if disposition == "PASS":
            self._reconcile_endpoint_identity()
            self._reconcile_inference_suite()
            smoke = self._reconcile_observations()
            self._reconcile_request_evidence(complete=True)
            self._reconcile_memory()
            if summary != self._complete_summary(smoke):
                raise StageTwoError("evidence_incomplete", "cleaned Stage 2B-1 summary is invalid")
            partial = False
        elif disposition == "STOPPED":
            terminal = (
                RunStatus.CANCELLED
                if summary.get("inference_path_acceptance") == "STOPPED"
                else RunStatus.FAILED
            )
            posts = self._reconcile_request_evidence(complete=False)
            observations = self._reconcile_partial_observations(posts)
            post_attempts = self._conservative_post_attempts(posts)
            if summary != self._partial_summary(
                terminal, post_attempts=post_attempts, observations=len(observations),
            ):
                raise StageTwoError("evidence_incomplete", "cleaned Stage 2B-1 summary is invalid")
            partial = True
        else:
            raise StageTwoError("evidence_incomplete", "cleaned Stage 2B-1 disposition is invalid")
        self._assert_redacted_artifacts()
        self._assert_current_lock()
        identity = self._load_operator_identity()
        shutdown_recheck_failed = False
        try:
            self.controller.assert_stopped(identity)
        except Exception:
            shutdown_recheck_failed = True
        if shutdown_recheck_failed:
            raise StageTwoError(
                "cleanup_failed", "Stage 2B-1 cleanup could not be completed",
            )
        self.bundle.reseal_after_state_transition(
            expected_lifecycle_lines=self.lifecycle.verified_history(self.manifest.run_id),
        )
        validation = self.bundle.validate_partial() if partial else self.bundle.validate()
        return {
            **summary,
            "artifact_directory": str(self.bundle.path),
            "artifact_validation": "PASS" if validation.valid else "FAIL",
            "checksum_validation": "PASS" if validation.valid else "FAIL",
        }

    def cleanup(self) -> dict[str, object]:
        failure: StageTwoError | None = None
        try:
            run_id = self.manifest.run_id
            state = self.lifecycle.read(run_id)
            if state.status not in {
                RunStatus.AWAITING_REVIEW, RunStatus.CANCELLED, RunStatus.FAILED,
                RunStatus.CLEANED,
            }:
                raise StageTwoError(
                    "evidence_incomplete", "review-ready or stopped Stage 2B-1 evidence is required",
                )
            self._assert_current_lock()
            identity = self._load_operator_identity()
            shutdown_verification_failed = False
            try:
                self.controller.assert_stopped(identity)
            except Exception:
                shutdown_verification_failed = True
            if shutdown_verification_failed:
                raise StageTwoError(
                    "cleanup_failed", "Stage 2B-1 cleanup could not be completed",
                )
            if state.status is RunStatus.CLEANED:
                return self._recover_cleaned()
            self._event("operator_shutdown_verified", pid=identity.pid, port_free_observations=2)
            if state.status in {RunStatus.CANCELLED, RunStatus.FAILED}:
                self._assert_redacted_artifacts()
                posts = self._reconcile_request_evidence(complete=False)
                observations = self._reconcile_partial_observations(posts)
                post_attempts = self._conservative_post_attempts(posts)
                return self._finalize_and_validate(
                    self._partial_summary(
                        state.status, post_attempts=post_attempts, observations=len(observations),
                    ), partial=True,
                )
            self._reconcile_endpoint_identity()
            self._reconcile_inference_suite()
            smoke = self._reconcile_observations()
            self._reconcile_request_evidence(complete=True)
            self._reconcile_memory()
            self._assert_redacted_artifacts()
            return self._finalize_and_validate(self._complete_summary(smoke), partial=False)
        except StageTwoError as error:
            failure = error
        except ArtifactError as error:
            failure = StageTwoError(
                "evidence_incomplete",
                f"Stage 2B-1 cleanup evidence could not be sealed: {error}",
            )
        except Exception:
            failure = StageTwoError(
                "evidence_incomplete", "Stage 2B-1 cleanup evidence could not be sealed",
            )
        if failure is not None:
            raise failure
        raise AssertionError("unreachable")
