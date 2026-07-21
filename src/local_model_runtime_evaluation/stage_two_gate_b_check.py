from __future__ import annotations

import argparse
from collections.abc import Mapping
import hashlib
import json
from pathlib import Path
import re
import subprocess
from typing import Callable

from .manifest import CANONICAL_OUTPUT_ROOT, load_manifest
from .resources import HostResourceProbe, ResourcePolicy, snapshot_from_health
from .stage_two_host import HostValidator, MacProcessBackend, StageTwoReadOnlyTransport
from .stage_two_host import OperatorOptiQController
from .stage_two import direct_health_is_safe, discover_route_identity, routed_health_is_ready
from .stage_two_profiles import RuntimeProfile, RuntimeProfileRegistry


_PASS_FIELDS = (
    "runtime_identity",
    "artifact_identity",
    "provider_identity",
    "operator_service_identity",
    "route_identity",
    "resource_gate",
)

_ZERO_FIELDS = (
    "custom_header_count",
    "secret_header_key_count",
    "model_load_attempts",
    "inference_request_attempts",
    "http_post_attempts",
    "service_lifecycle_actions",
)

_PLUGIN_ID = "local.jrazz.model-runtime-evaluation-harness"
_PROFILE_ID = "gemma-4-12b-optiq-4bit"
_PROFILE_REVISION = "1"
_ROUTED_MODEL_ID = "optiq/mlx-community/gemma-4-12B-it-qat-OptiQ-4bit"


class GateBReadinessError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def parse_active_plugin_version(output: str) -> str | None:
    pattern = re.compile(rf"^{re.escape(_PLUGIN_ID)}\s+version=([^\s]+)", re.MULTILINE)
    match = pattern.search(output)
    return match.group(1) if match else None


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _run_tools_list(command: list[str]) -> object:
    return subprocess.run(
        command, capture_output=True, text=True, check=False, timeout=30,
    )


def collect_plugin_state(
    *, packaged_path: Path, home: Path,
    command_runner: Callable[[list[str]], object] = _run_tools_list,
) -> dict[str, str | None]:
    packaged_sha256 = _sha256(packaged_path)
    result = command_runner(["osaurus", "tools", "list"])
    if getattr(result, "returncode", 1) != 0:
        raise RuntimeError("installed Osaurus tool inventory is unavailable")
    installed_version = parse_active_plugin_version(str(getattr(result, "stdout", "")))
    installed_path = (
        home / ".osaurus" / "Tools" / _PLUGIN_ID / str(installed_version)
        / "libOsaurusEvaluationHarness.dylib"
    )
    installed_sha256 = _sha256(installed_path) if installed_version and installed_path.is_file() else None
    return {
        "installed_version": installed_version,
        "packaged_sha256": packaged_sha256,
        "installed_sha256": installed_sha256,
    }


def load_authorized_manifest(
    repository_root: Path, run_id: str, output_root: Path | None = None,
) -> dict[str, object]:
    matches: list[tuple[Path, dict[str, object]]] = []
    for path in (repository_root / "manifests").glob("*.json"):
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(raw, dict) and raw.get("run_id") == run_id:
            matches.append((path, raw))
    if len(matches) != 1:
        raise ValueError("exactly one authorized Stage 2A manifest is required")
    path, raw = matches[0]
    raw_output_root = raw.get("output_root")
    replay_root = output_root
    if replay_root is None and raw_output_root == str(CANONICAL_OUTPUT_ROOT):
        replay_root = CANONICAL_OUTPUT_ROOT
    if replay_root is not None and (replay_root / run_id).exists():
        raise GateBReadinessError(
            "run_id_consumed",
            "the authorized Stage 2A run ID already has canonical output",
        )
    manifest = load_manifest(path)
    if manifest.stage != 2 or manifest.mode != "operator_route_probe":
        raise ValueError("authorized manifest is outside Stage 2A")
    return dict(manifest.raw)


def collect_static_result(
    *, profile: RuntimeProfile, validator: object, process_backend: object,
    transport: object, resource_probe: object,
) -> dict[str, object]:
    validation = validator.validate()
    if (
        validation.runtime_identity.get("version") != profile.runtime_version
        or validation.runtime_identity.get("packages") != profile.package_versions
    ):
        raise ValueError("runtime identity differs from the approved profile")
    if (
        validation.artifact_identity.get("revision") != profile.model_revision
        or validation.artifact_identity.get("hashes") != profile.artifact_hashes
    ):
        raise ValueError("artifact identity differs from the approved profile")
    provider = validation.provider_identity
    if (
        provider.get("provider_id") != profile.osaurus_provider_id
        or provider.get("enabled") is not True
        or provider.get("custom_header_count") != 0
        or provider.get("secret_header_key_count") != 0
    ):
        raise ValueError("provider identity differs from the approved profile")

    command = (str(profile.runtime_executable), *profile.serve_arguments)
    controller = OperatorOptiQController(
        command, process_backend, lambda: transport.health(profile.direct_base_url)
    )
    identity = controller.capture()
    direct_models = transport.list_models(profile.direct_base_url)
    routed_models = transport.list_models(profile.routed_base_url)
    after_inventory_health = transport.health(profile.direct_base_url)
    if not direct_health_is_safe(
        after_inventory_health,
        (str(profile.model_snapshot), profile.model_repository, *profile.direct_model_identities),
    ):
        raise ValueError("operator service health conflicted after inventory")
    if not controller.matches(identity):
        raise ValueError("operator service identity changed during inventory")
    discovered_route = discover_route_identity(profile, direct_models, routed_models)
    port_free = process_backend.port_is_free()
    processes = process_backend.optiq_processes()
    health = transport.health(profile.routed_base_url)
    if not routed_health_is_ready(health):
        raise ValueError("Osaurus routed health is unavailable")
    snapshot = snapshot_from_health(
        resource_probe.free_memory_percent(), health, active_run_id=None,
    )
    decision = ResourcePolicy(profile.coordinator_model_id).evaluate(snapshot)

    return {
        "runtime_profile_id": profile.profile_id,
        "runtime_profile_revision": profile.revision,
        "runtime_identity": "PASS",
        "artifact_identity": "PASS",
        "provider_identity": "PASS",
        "operator_service_identity": "PASS",
        "route_identity": "PASS" if discovered_route == profile.routed_model_id else "STOP",
        "operator_process_id": identity.pid,
        "resource_gate": "PASS" if decision.allowed else "STOP",
        "resource_warning": decision.warning,
        "coordinator_model_id": profile.coordinator_model_id,
        "port_8080_free": port_free,
        "optiq_process_count": len(processes),
        "custom_header_count": int(provider["custom_header_count"]),
        "secret_header_key_count": int(provider["secret_header_key_count"]),
        "model_load_attempts": 0,
        "inference_request_attempts": 0,
        "http_post_attempts": 0,
        "service_lifecycle_actions": 0,
    }


def build_gate_b_report(
    *,
    static_result: Mapping[str, object],
    installed_version: str | None,
    packaged_sha256: str | None,
    installed_sha256: str | None,
    manifest: Mapping[str, object] | None,
) -> dict[str, object]:
    static_ok = (
        all(static_result.get(field) == "PASS" for field in _PASS_FIELDS)
        and static_result.get("port_8080_free") is False
        and static_result.get("optiq_process_count") == 1
        and all(static_result.get(field) == 0 for field in _ZERO_FIELDS)
    )
    plugin_version_ok = installed_version == "0.3.0"
    plugin_checksum_ok = (
        plugin_version_ok
        and packaged_sha256 is not None
        and packaged_sha256 == installed_sha256
    )

    checks = {
        "static_identity_and_safety": static_ok,
        "plugin_version": plugin_version_ok,
        "plugin_checksum": plugin_checksum_ok,
        "manifest_authorized": manifest is not None,
    }
    if not static_ok:
        overall = "STOPPED"
    elif not plugin_version_ok or not plugin_checksum_ok:
        overall = "READY_FOR_PLUGIN_INSTALL"
    elif manifest is None:
        overall = "READY_FOR_MANIFEST_AUTHORIZATION"
    else:
        overall = "READY_FOR_RUN_AUTHORIZATION"

    return {
        "stage": "2A",
        "mode": "operator_route_observation",
        "runtime_profile_id": static_result.get("runtime_profile_id"),
        "runtime_profile_revision": static_result.get("runtime_profile_revision"),
        "overall": overall,
        "checks": checks,
        "installed_plugin_version": installed_version,
        "manager_review_required": True,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="lmre-stage2-gate-b-check")
    parser.add_argument("run_id", nargs="?")
    arguments = parser.parse_args(argv)
    repository_root = Path(__file__).resolve().parents[2]
    try:
        profile = RuntimeProfileRegistry(repository_root / "config" / "runtime-profiles").get(
            _PROFILE_ID, _PROFILE_REVISION,
        )
        if profile.routed_model_id != _ROUTED_MODEL_ID:
            raise ValueError("approved profile routed model id differs from Gate B pin")
        manifest = (
            load_authorized_manifest(repository_root, arguments.run_id)
            if arguments.run_id else None
        )
        static_result = collect_static_result(
            profile=profile,
            validator=HostValidator(
                profile, Path.home() / ".osaurus" / "providers" / "remote.json",
            ),
            process_backend=MacProcessBackend(),
            transport=StageTwoReadOnlyTransport(
                {profile.direct_base_url, profile.routed_base_url}, timeout_seconds=10,
            ),
            resource_probe=HostResourceProbe(),
        )
        plugin = collect_plugin_state(
            packaged_path=(
                repository_root / "plugins" / "osaurus-evaluation-harness"
                / ".build" / "release" / "libOsaurusEvaluationHarness.dylib"
            ),
            home=Path.home(),
        )
        result = build_gate_b_report(
            static_result=static_result,
            installed_version=plugin["installed_version"],
            packaged_sha256=plugin["packaged_sha256"],
            installed_sha256=plugin["installed_sha256"],
            manifest=manifest,
        )
        if arguments.run_id:
            result["run_id"] = arguments.run_id
        result["static_evidence"] = static_result
        exit_code = 0 if result["overall"] != "STOPPED" else 1
    except Exception as error:
        result = {
            "stage": "2A",
            "runtime_profile_id": _PROFILE_ID,
            "runtime_profile_revision": _PROFILE_REVISION,
            "overall": "STOPPED",
            "error_kind": getattr(error, "code", error.__class__.__name__),
            "model_load_attempts": 0,
            "inference_request_attempts": 0,
            "http_post_attempts": 0,
            "service_lifecycle_actions": 0,
            "credential_value_exposed": False,
            "manager_review_required": True,
        }
        if arguments.run_id:
            result["run_id"] = arguments.run_id
        exit_code = 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
