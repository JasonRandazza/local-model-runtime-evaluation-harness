from __future__ import annotations

import json
from pathlib import Path

from .credentials import CredentialProvider, CredentialState, KeychainCredentialProvider
from .identity import prove_route_identity
from .model_profiles import ModelProfile, ModelProfileRegistry
from .resources import HostResourceProbe, ResourcePolicy, snapshot_from_health
from .transport import LoopbackTransport


def collect_operator_check(profile: ModelProfile, credentials: CredentialProvider, transport, resource_probe) -> dict[str, object]:
    status = credentials.status()
    if status is not CredentialState.PRESENT:
        return {
            "overall": "STOPPED", "credential_status": status.value,
            "inference_requests_attempted": 0, "reason": "credential_not_present",
        }
    credential = credentials.get()
    direct_models = transport.list_models(profile.direct.base_url, credential)
    routed_models = transport.list_models(profile.routed.base_url, None)
    proof = prove_route_identity(profile, direct_models, routed_models)
    health = transport.health(profile.routed.base_url)
    free_percent = resource_probe.free_memory_percent()
    snapshot = snapshot_from_health(free_percent, health, None)
    decision = ResourcePolicy(profile.coordinator_model_id).evaluate(snapshot)
    return {
        "overall": "READY_FOR_GATE_B_REVIEW",
        "credential_status": CredentialState.PRESENT.value,
        "profile_id": profile.profile_id,
        "profile_revision": profile.revision,
        "runtime_owner": proof.runtime_owner,
        "coordinator_model_id": profile.coordinator_model_id,
        "direct": {
            "base_url": profile.direct.base_url, "model_id": proof.direct_model_id,
            "model_present_exactly_once": True, "authentication": "DEDICATED_KEYCHAIN_ITEM",
        },
        "routed": {
            "base_url": profile.routed.base_url, "model_id": proof.routed_model_id,
            "model_present_exactly_once": True, "direct_omlx_credential_forwarded": False,
        },
        "osaurus_health": {
            "status": health.get("status"), "loaded": health.get("loaded"),
            "current_model": health.get("current_model"),
            "resident_models": health.get("resident_models"),
            "http_inflight": health.get("http_inflight"),
        },
        "resource_gate": {
            "free_memory_percent": free_percent,
            "memory_pressure": snapshot.memory_pressure.value,
            "warning": decision.warning,
            "osaurus_native_model_loaded": snapshot.osaurus_native_model_loaded,
            "osaurus_native_models": list(snapshot.osaurus_native_models),
        },
        "model_load_attempts": 0,
        "inference_requests_attempted": 0,
        "service_lifecycle_actions": 0,
        "manager_review_required": True,
    }


def main() -> int:
    repository_root = Path(__file__).resolve().parents[2]
    try:
        profile = ModelProfileRegistry(repository_root / "config" / "model-profiles").get(
            "vibethinker-3b-mlx-oq4", "2"
        )
        transport = LoopbackTransport({profile.direct.base_url, profile.routed.base_url}, timeout_seconds=15)
        result = collect_operator_check(
            profile, KeychainCredentialProvider(), transport, HostResourceProbe()
        )
        exit_code = 0 if result["overall"] == "READY_FOR_GATE_B_REVIEW" else 1
    except Exception as error:
        result = {
            "overall": "STOPPED", "error_kind": getattr(error, "code", error.__class__.__name__),
            "credential_value_exposed": False, "inference_requests_attempted": 0,
            "manager_review_required": True,
        }
        exit_code = 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return exit_code
