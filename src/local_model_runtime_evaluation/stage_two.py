from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
import threading
from typing import Callable, Mapping, Protocol

from .artifacts import ArtifactBundle
from .lifecycle import LifecycleStore
from .models import BenchmarkManifest, RunStatus
from .resources import ResourcePolicy, ResourceSnapshot
from .stage_two_profiles import RuntimeProfile


class StageTwoError(RuntimeError):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        reason: str | None = None,
        http_status: int | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.reason = reason
        self.http_status = http_status


@dataclass(frozen=True)
class HostValidation:
    runtime_identity: Mapping[str, object]
    artifact_identity: Mapping[str, object]
    provider_identity: Mapping[str, object]


@dataclass(frozen=True)
class ProcessOwnership:
    pid: int
    parent_pid: int
    process_group_id: int
    started_at: str
    command_sha256: str


@dataclass(frozen=True)
class ModelDescriptor:
    id: str
    owned_by: str | None = None
    root: str | None = None

    def evidence(self) -> dict[str, str]:
        result = {"id": self.id}
        if self.owned_by is not None:
            result["owned_by"] = self.owned_by
        if self.root is not None:
            result["root"] = self.root
        return result


class StageTwoController(Protocol):
    def capture(self) -> ProcessOwnership: ...
    def matches(self, identity: ProcessOwnership) -> bool: ...
    def assert_stopped(self, identity: ProcessOwnership) -> None: ...


class StageTwoTransport(Protocol):
    def health(self, base_url: str) -> dict[str, object]: ...
    def list_models(self, base_url: str) -> tuple[ModelDescriptor, ...]: ...


def direct_health_is_safe(
    health: Mapping[str, object], expected_models: tuple[str, ...],
) -> bool:
    """Accept minimal health while rejecting conflicting optional diagnostics."""
    if health.get("status") != "ok":
        return False
    expected = set(expected_models)
    if health.get("model_loaded") not in (None, True):
        return False
    for key in ("current_model", "model", "model_path"):
        value = health.get(key)
        if value not in (None, "") and value not in expected:
            return False
    for key in ("loaded", "loaded_models", "resident_models"):
        value = health.get(key)
        if value in (None, [], ()):
            continue
        if isinstance(value, bool):
            if value is not True:
                return False
            continue
        if not isinstance(value, (list, tuple)) or any(item not in expected for item in value):
            return False
    return health.get("active_requests") in (None, 0) and health.get("foreground_active") in (None, 0)


def routed_health_is_ready(health: Mapping[str, object]) -> bool:
    return health.get("status") in {"healthy", "ok"} or health.get("ok") is True


def discover_route_identity(
    profile: RuntimeProfile,
    direct_models: tuple[ModelDescriptor, ...],
    routed_models: tuple[ModelDescriptor, ...],
) -> str:
    approved_direct = {
        item.id for item in direct_models if item.id in profile.direct_model_identities
    }
    if not approved_direct:
        raise StageTwoError("route_identity_failed", "approved direct model identity is missing")
    routed_candidates = [
        item for item in routed_models if item.id == profile.routed_model_id
    ]
    if len(routed_candidates) != 1:
        raise StageTwoError("route_identity_failed", "OptiQ routed model identity is missing or ambiguous")
    return routed_candidates[0].id


class StageTwoEngine:
    def __init__(
        self, manifest: BenchmarkManifest, profile: RuntimeProfile, output_root: Path,
        resources: ResourceSnapshot | Callable[[], ResourceSnapshot],
        host_validation: Callable[[], HostValidation], controller: StageTwoController,
        transport: StageTwoTransport,
    ) -> None:
        if manifest.stage != 2 or manifest.mode != "operator_route_probe":
            raise ValueError("StageTwoEngine requires a Stage 2A operator route manifest")
        if (
            manifest.runtime_profile_id != profile.profile_id
            or manifest.runtime_profile_revision != profile.revision
        ):
            raise ValueError("manifest runtime profile reference does not match")
        self.manifest = manifest
        self.profile = profile
        self.output_root = output_root
        self.resources = resources
        self.host_validation = host_validation
        self.controller = controller
        self.transport = transport
        self.lifecycle = LifecycleStore(output_root)
        self.bundle = ArtifactBundle.create(manifest, output_root)
        self.discovered_routed_model_id: str | None = None

    def _resources(self) -> ResourceSnapshot:
        return self.resources() if callable(self.resources) else self.resources

    def _memory_sample(self, phase: str, snapshot: ResourceSnapshot) -> None:
        self.bundle.append_jsonl("memory-samples.jsonl", {
            "phase": phase,
            "memory_pressure": snapshot.memory_pressure.value,
            "osaurus_native_model_loaded": snapshot.osaurus_native_model_loaded,
            "osaurus_native_models": list(snapshot.osaurus_native_models),
        })

    def _validate_host(self, validation: HostValidation) -> None:
        if validation.runtime_identity.get("version") != self.profile.runtime_version:
            raise StageTwoError("runtime_identity_failed", "mlx-optiq runtime version differs from profile")
        if validation.runtime_identity.get("packages") != self.profile.package_versions:
            raise StageTwoError("runtime_identity_failed", "mlx-optiq package versions differ from profile")
        if validation.artifact_identity.get("revision") != self.profile.model_revision:
            raise StageTwoError("artifact_identity_failed", "OptiQ model revision differs from profile")
        if validation.artifact_identity.get("hashes") != self.profile.artifact_hashes:
            raise StageTwoError("artifact_identity_failed", "OptiQ artifact hashes differ from profile")
        if validation.provider_identity.get("provider_id") != self.profile.osaurus_provider_id:
            raise StageTwoError("provider_identity_failed", "approved Osaurus provider is unavailable")
        if validation.provider_identity.get("enabled") is not True:
            raise StageTwoError("provider_identity_failed", "approved Osaurus provider is disabled")
        if validation.provider_identity.get("custom_header_count") != 0:
            raise StageTwoError("provider_headers_forbidden", "Osaurus OptiQ custom headers must be empty")
        if validation.provider_identity.get("secret_header_key_count") != 0:
            raise StageTwoError("provider_headers_forbidden", "Osaurus OptiQ secret header metadata must be empty")

    def _load_operator_identity(self) -> ProcessOwnership:
        try:
            payload = json.loads(
                (self.bundle.path / "operator-service-identity.json").read_text(encoding="utf-8")
            )
            return ProcessOwnership(
                pid=int(payload["pid"]), parent_pid=int(payload["parent_pid"]),
                process_group_id=int(payload["process_group_id"]),
                started_at=str(payload["started_at"]),
                command_sha256=str(payload["command_sha256"]),
            )
        except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as error:
            raise StageTwoError(
                "operator_identity_failed", "operator service identity evidence is unavailable"
            ) from error

    def _direct_health_is_safe(self, health: Mapping[str, object]) -> bool:
        return direct_health_is_safe(health, (
            str(self.profile.model_snapshot),
            self.profile.model_repository,
            *self.profile.direct_model_identities,
        ))

    def _request_evidence(self, endpoint: str, payload: object) -> None:
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        self.bundle.append_jsonl("request-evidence.jsonl", {
            "method": "GET",
            "endpoint": endpoint,
            "status": 200,
            "payload_sha256": hashlib.sha256(encoded).hexdigest(),
        })

    def _health(self, base_url: str, endpoint: str) -> dict[str, object]:
        payload = self.transport.health(base_url)
        self._request_evidence(endpoint, payload)
        return payload

    def _models(self, base_url: str, endpoint: str) -> tuple[ModelDescriptor, ...]:
        models = self.transport.list_models(base_url)
        self._request_evidence(endpoint, [item.evidence() for item in models])
        return models

    def preflight(self) -> dict[str, object]:
        run_id = self.manifest.run_id
        self.lifecycle.create(run_id)
        self.lifecycle.transition(run_id, RunStatus.PREFLIGHT, "Stage 2A manifest and policy validated")
        validation = self.host_validation()
        self._validate_host(validation)
        identity = self.controller.capture()
        snapshot = self._resources()
        ResourcePolicy(self.profile.coordinator_model_id).evaluate(snapshot)
        self.lifecycle.transition(run_id, RunStatus.RESOURCE_GATE, "serial no-resident-model gate passed")
        self.bundle.write_json("runtime-identity.json", dict(validation.runtime_identity))
        self.bundle.write_json("artifact-identity.json", dict(validation.artifact_identity))
        self.bundle.write_json("operator-service-identity.json", asdict(identity))
        self._event("operator_service_observed", pid=identity.pid, command_sha256=identity.command_sha256)
        self.bundle.write_json("preflight.json", {
            "ok": True,
            "stage": 2,
            "mode": "operator_route_probe",
            "provider_identity": dict(validation.provider_identity),
            "model_load_attempts": 0,
            "inference_request_attempts": 0,
            "http_post_attempts": 0,
        })
        self._memory_sample("preflight", snapshot)
        state = self.lifecycle.transition(run_id, RunStatus.READY, "Stage 2A operator route probe ready")
        return {
            "run_id": run_id,
            "state": state.status.value,
            "manifest": {
                "schema_version": self.manifest.schema_version,
                "run_id": self.manifest.run_id,
                "stage": self.manifest.stage,
                "mode": self.manifest.mode,
                "operations": [operation.value for operation in self.manifest.operations],
                "output_root": str(self.manifest.output_root),
                "approved_by": self.manifest.approved_by,
                "approved_at": self.manifest.approved_at.isoformat(),
                "expires_at": self.manifest.expires_at.isoformat(),
                "comparison_class": self.manifest.comparison_class,
                "runtime_profile_id": self.manifest.runtime_profile_id,
                "runtime_profile_revision": self.manifest.runtime_profile_revision,
                "routes": dict(self.manifest.routes or {}),
                "limits": dict(self.manifest.limits or {}),
            },
            "manifest_validation": "PASS",
            "resource_gate": "PASS",
            "runtime_identity": "PASS",
            "artifact_identity": "PASS",
            "provider_identity": "PASS",
            "model_load_attempts": 0,
            "inference_request_attempts": 0,
            "http_post_attempts": 0,
            "service_lifecycle_actions": 0,
        }

    def _event(self, event: str, **details: object) -> None:
        self.bundle.append_jsonl("service-events.jsonl", {"event": event, **details})

    def run(self, cancel: threading.Event) -> dict[str, object]:
        run_id = self.manifest.run_id
        if self.lifecycle.read(run_id).status is RunStatus.READY:
            self.lifecycle.transition(run_id, RunStatus.RUNNING, "fixed Stage 2A worker started")
        try:
            if cancel.is_set():
                raise StageTwoError("cancelled", "Stage 2A was cancelled before route observation")
            identity = self._load_operator_identity()
            if not self.controller.matches(identity):
                raise StageTwoError("operator_identity_changed", "operator service identity changed")
            before_health = self._health(self.profile.direct_base_url, "direct_health")
            if not self._direct_health_is_safe(before_health):
                raise StageTwoError("operator_health_failed", "operator service health is unavailable or conflicting")
            self.lifecycle.transition(run_id, RunStatus.SERVICE_READY, "operator OptiQ service observed ready")
            direct_models = self._models(self.profile.direct_base_url, "direct_models")
            if cancel.is_set():
                raise StageTwoError("cancelled", "Stage 2A was cancelled during route discovery")
            routed_health = self._health(self.profile.routed_base_url, "routed_health")
            if not routed_health_is_ready(routed_health):
                raise StageTwoError("route_health_failed", "Osaurus routed health is unavailable")
            routed_models = self._models(self.profile.routed_base_url, "routed_models")
            inventory: dict[str, object] = {
                "direct": {
                    "base_url": self.profile.direct_base_url,
                    "models": [item.evidence() for item in direct_models],
                },
                "routed": {
                    "base_url": self.profile.routed_base_url,
                    "models": [item.evidence() for item in routed_models],
                },
                "expected_routed_model_id": self.profile.routed_model_id,
                "rejected_local_model_ids": list(self.profile.rejected_local_model_ids),
                "route_identity": {"status": "PENDING"},
                "request_methods": ["GET"],
            }
            self.bundle.write_json("endpoint-inventory.json", inventory)
            self.discovered_routed_model_id = discover_route_identity(
                self.profile, direct_models, routed_models
            )
            inventory["route_identity"] = {
                "status": "PASS",
                "discovered_routed_model_id": self.discovered_routed_model_id,
            }
            self.bundle.write_json("endpoint-inventory.json", inventory)
            self.lifecycle.transition(run_id, RunStatus.ENDPOINT_IDENTITY, "OptiQ route identity discovered")
            after_health = self._health(self.profile.direct_base_url, "direct_health")
            if not self._direct_health_is_safe(after_health):
                raise StageTwoError("operator_health_failed", "operator service health conflicted after inventory")
            if not self.controller.matches(identity):
                raise StageTwoError("operator_identity_changed", "operator service identity changed")
            self._validate_host(self.host_validation())
            after = self._resources()
            ResourcePolicy(self.profile.coordinator_model_id).evaluate(after)
            self._memory_sample("after_route_inventory", after)
            self.lifecycle.transition(run_id, RunStatus.ARTIFACT_VALIDATION, "Stage 2A evidence reconciled")
            state = self.lifecycle.transition(run_id, RunStatus.AWAITING_REVIEW, "operator shutdown required")
            return {
                "run_id": run_id,
                "state": state.status.value,
                "discovered_routed_model_id": self.discovered_routed_model_id,
                "model_load_attempts": 0,
                "inference_request_attempts": 0,
                "http_post_attempts": 0,
                "service_lifecycle_actions": 0,
                "manager_review_required": True,
            }
        except Exception as failure:
            target = (
                RunStatus.CANCELLED
                if isinstance(failure, StageTwoError) and failure.code == "cancelled"
                else RunStatus.FAILED
            )
            self.lifecycle.transition(run_id, target, "Stage 2A stopped before acceptance")
            raise failure

    def cleanup(self) -> dict[str, object]:
        run_id = self.manifest.run_id
        state = self.lifecycle.read(run_id)
        if state.status not in {
            RunStatus.AWAITING_REVIEW, RunStatus.CANCELLED, RunStatus.FAILED,
            RunStatus.CLEANED,
        }:
            raise StageTwoError("evidence_incomplete", "review-ready or stopped Stage 2A evidence is required")
        identity = self._load_operator_identity()
        self.controller.assert_stopped(identity)
        if state.status is RunStatus.CLEANED:
            return self._recover_cleaned()
        self._event("operator_shutdown_verified", pid=identity.pid, port_free_observations=2)
        if state.status is not RunStatus.AWAITING_REVIEW:
            summary = {
                "run_id": run_id, "stage": 2, "mode": "operator_route_probe",
                "comparison_class": self.manifest.comparison_class,
                "runtime_profile_id": self.profile.profile_id,
                "runtime_profile_revision": self.profile.revision,
                "state": "cleaned", "disposition": "STOPPED",
                "operator_shutdown_verified": "PASS", "service_lifecycle_actions": 0,
                "model_load_attempts": 0, "inference_request_attempts": 0,
                "http_post_attempts": 0, "manager_review_required": True,
            }
            prior_lifecycle_lines = self.lifecycle.verified_history(run_id)
            self.bundle.finalize_partial(summary)
            self.lifecycle.transition(run_id, RunStatus.CLEANED, "stopped Stage 2A evidence cleaned")
            self.bundle.reseal_after_state_transition(
                expected_lifecycle_lines=self.lifecycle.verified_history(run_id),
                prior_lifecycle_lines=prior_lifecycle_lines,
            )
            validation = self.bundle.validate_partial()
            return {
                **summary, "artifact_directory": str(self.bundle.path),
                "artifact_validation": "PASS" if validation.valid else "FAIL",
                "checksum_validation": "PASS" if validation.valid else "FAIL",
            }
        try:
            inventory = json.loads((self.bundle.path / "endpoint-inventory.json").read_text(encoding="utf-8"))
            route_identity = inventory["route_identity"]
            if route_identity["status"] != "PASS":
                raise KeyError("route identity did not pass")
            discovered_routed_model_id = route_identity["discovered_routed_model_id"]
        except (OSError, json.JSONDecodeError, KeyError, TypeError) as error:
            raise StageTwoError("evidence_incomplete", "Stage 2A route discovery evidence is unavailable") from error
        if discovered_routed_model_id != self.profile.routed_model_id:
            raise StageTwoError("evidence_incomplete", "Stage 2A routed model identity is invalid")
        summary = {
            "run_id": run_id,
            "stage": 2,
            "mode": "operator_route_probe",
            "comparison_class": self.manifest.comparison_class,
            "runtime_profile_id": self.profile.profile_id,
            "runtime_profile_revision": self.profile.revision,
            "state": "cleaned",
            "disposition": "PASS",
            "discovered_routed_model_id": discovered_routed_model_id,
            "model_load_attempts": 0,
            "inference_request_attempts": 0,
            "http_post_attempts": 0,
            "route_identity": "PASS",
            "resource_gate": "PASS",
            "runtime_identity": "PASS",
            "artifact_identity": "PASS",
            "provider_identity": "PASS",
            "service_ownership": "operator",
            "provider_activation": "operator_reconnect_required",
            "provider_route_observed": "PASS",
            "operator_service_identity": "PASS",
            "operator_shutdown_verified": "PASS",
            "service_lifecycle_actions": 0,
            "manager_review_required": True,
        }
        prior_lifecycle_lines = self.lifecycle.verified_history(run_id)
        self.bundle.finalize(summary)
        self.lifecycle.transition(run_id, RunStatus.CLEANED, "Stage 2A operator evidence cleaned")
        self.bundle.reseal_after_state_transition(
            expected_lifecycle_lines=self.lifecycle.verified_history(run_id),
            prior_lifecycle_lines=prior_lifecycle_lines,
        )
        validation = self.bundle.validate()
        return {
            **summary,
            "artifact_directory": str(self.bundle.path),
            "artifact_validation": "PASS" if validation.valid else "FAIL",
            "checksum_validation": "PASS" if validation.valid else "FAIL",
        }

    def _recover_cleaned(self) -> dict[str, object]:
        try:
            summary = json.loads((self.bundle.path / "summary.json").read_text(encoding="utf-8"))
            disposition = summary["disposition"]
        except (OSError, json.JSONDecodeError, KeyError, TypeError) as error:
            raise StageTwoError("evidence_incomplete", "cleaned Stage 2A summary is unavailable") from error
        if disposition == "PASS":
            try:
                inventory = json.loads(
                    (self.bundle.path / "endpoint-inventory.json").read_text(encoding="utf-8")
                )
                discovered = inventory["route_identity"]["discovered_routed_model_id"]
            except (OSError, json.JSONDecodeError, KeyError, TypeError) as error:
                raise StageTwoError("evidence_incomplete", "cleaned route evidence is unavailable") from error
            if (
                discovered != self.profile.routed_model_id
                or summary.get("discovered_routed_model_id") != self.profile.routed_model_id
            ):
                raise StageTwoError("evidence_incomplete", "cleaned routed model identity is invalid")
            validate = self.bundle.validate
        elif disposition == "STOPPED":
            validate = self.bundle.validate_partial
        else:
            raise StageTwoError("evidence_incomplete", "cleaned Stage 2A disposition is invalid")
        self.bundle.reseal_after_state_transition(
            expected_lifecycle_lines=self.lifecycle.verified_history(self.manifest.run_id),
        )
        validation = validate()
        return {
            **summary,
            "artifact_directory": str(self.bundle.path),
            "artifact_validation": "PASS" if validation.valid else "FAIL",
            "checksum_validation": "PASS" if validation.valid else "FAIL",
        }
