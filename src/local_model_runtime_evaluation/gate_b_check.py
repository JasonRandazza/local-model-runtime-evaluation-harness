from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .credentials import KeychainCredentialProvider
from .manifest import load_manifest
from .model_profiles import ModelProfileRegistry
from .operator_check import collect_operator_check
from .resources import HostResourceProbe
from .transport import LoopbackTransport


COORDINATOR_MODEL_ID = "gemma-4-12b-it-qat-jang_4m"
PLUGIN_VERSION = "0.2.0"


def build_gate_b_report(
    *, run_id: str, manifest_profile_revision: str, manifest_suite_revision: str,
    installed_version: str,
    packaged_sha256: str, installed_sha256: str, operator_result: dict[str, object],
) -> dict[str, object]:
    checks = {
        "manifest_profile_revision": manifest_profile_revision == "3",
        "operator_profile_revision": operator_result.get("profile_revision") == "3",
        "manifest_suite_revision": manifest_suite_revision == "2",
        "coordinator_model": operator_result.get("coordinator_model_id") == COORDINATOR_MODEL_ID,
        "plugin_version": installed_version == PLUGIN_VERSION,
        "plugin_checksum": packaged_sha256 == installed_sha256,
        "operator_readiness": operator_result.get("overall") == "READY_FOR_GATE_B_REVIEW",
        "zero_inference": operator_result.get("inference_requests_attempted") == 0,
    }
    ready = all(checks.values())
    return {
        "overall": "READY_FOR_LIVE_AUTHORIZATION" if ready else "STOPPED",
        "run_id": run_id,
        "profile_revision": manifest_profile_revision,
        "suite_revision": manifest_suite_revision,
        "coordinator_model_id": COORDINATOR_MODEL_ID,
        "plugin_version": installed_version,
        "checks": checks,
        "resource_gate": operator_result.get("resource_gate"),
        "osaurus_health": operator_result.get("osaurus_health"),
        "inference_requests_attempted": operator_result.get("inference_requests_attempted", 0),
        "model_load_attempts": operator_result.get("model_load_attempts", 0),
        "service_lifecycle_actions": operator_result.get("service_lifecycle_actions", 0),
        "manager_review_required": True,
    }


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    repository_root = Path(__file__).resolve().parents[2]
    try:
        manifest = load_manifest(repository_root / "manifests" / "stage-1-route-overhead-002.json")
        profile = ModelProfileRegistry(repository_root / "config" / "model-profiles").get(
            manifest.model_profile_id, manifest.model_profile_revision
        )
        transport = LoopbackTransport({profile.direct.base_url, profile.routed.base_url}, timeout_seconds=15)
        operator = collect_operator_check(
            profile, KeychainCredentialProvider(), transport, HostResourceProbe()
        )
        packaged = repository_root / "plugins" / "osaurus-evaluation-harness" / "libOsaurusEvaluationHarness.dylib"
        installed_root = (
            Path.home() / ".osaurus" / "Tools" / "local.jrazz.model-runtime-evaluation-harness" / PLUGIN_VERSION
        )
        receipt = json.loads((installed_root / "receipt.json").read_text(encoding="utf-8"))
        result = build_gate_b_report(
            run_id=manifest.run_id,
            manifest_profile_revision=manifest.model_profile_revision or "",
            manifest_suite_revision=manifest.suite_revision or "",
            installed_version=str(receipt.get("version", "")),
            packaged_sha256=_sha256(packaged),
            installed_sha256=_sha256(installed_root / "libOsaurusEvaluationHarness.dylib"),
            operator_result=operator,
        )
        exit_code = 0 if result["overall"] == "READY_FOR_LIVE_AUTHORIZATION" else 1
    except Exception as error:
        result = {
            "overall": "STOPPED",
            "error_kind": getattr(error, "code", error.__class__.__name__),
            "credential_value_exposed": False,
            "inference_requests_attempted": 0,
            "manager_review_required": True,
        }
        exit_code = 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return exit_code
