from __future__ import annotations

from pathlib import Path

from .resources import HostResourceProbe, snapshot_from_health
from .stage_two import StageTwoEngine
from .stage_two_inference import (
    _STAGE_2B_1_LIMITS,
    _STAGE_2B_1_OPERATIONS,
    _STAGE_2B_1_ROUTES,
    StageTwoInferenceEngine,
)
from .stage_two_inference_transport import StageTwoInferenceTransport
from .stage_two_host import (
    HostValidator, MacProcessBackend, OperatorOptiQController, StageTwoReadOnlyTransport,
)
from .stage_two_profiles import RuntimeProfileRegistry
from .stage_two_smoke_suite import StageTwoSmokeSuite
from .locking import RunLock


PROVIDER_CONFIG = Path("/Users/jrazz/.osaurus/providers/remote.json")


def _validate_stage_two_inference_manifest(manifest) -> None:
    fixed_contract = (
        manifest.stage == 2
        and manifest.schema_version == "3.2.0"
        and manifest.mode == "operator_inference_probe"
        and manifest.comparison_class == "optiq-operator-route-smoke"
        and manifest.runtime_profile_id == "vibethinker-3b-optiq-4bit"
        and manifest.runtime_profile_revision == "3"
        and manifest.suite_id == "optiq-route-smoke-v1"
        and manifest.suite_revision == "1"
        and manifest.repetitions == 1
        and manifest.route_order == "counterbalanced"
        and tuple(manifest.operations) == _STAGE_2B_1_OPERATIONS
        and dict(manifest.routes or {}) == _STAGE_2B_1_ROUTES
        and dict(manifest.limits or {}) == _STAGE_2B_1_LIMITS
    )
    if not fixed_contract:
        raise ValueError("unsupported Stage 2 mode")


def build_stage_two_engine(repository_root: Path, manifest, output_root: Path) -> StageTwoEngine | StageTwoInferenceEngine:
    contract = (manifest.schema_version, manifest.mode)
    if contract == ("3.2.0", "operator_inference_probe"):
        _validate_stage_two_inference_manifest(manifest)
    elif contract != ("3.1.0", "operator_route_probe"):
        raise ValueError("unsupported Stage 2 mode")
    profile = RuntimeProfileRegistry(repository_root / "config" / "runtime-profiles").get(
        manifest.runtime_profile_id, manifest.runtime_profile_revision
    )
    if contract == ("3.2.0", "operator_inference_probe"):
        suite = StageTwoSmokeSuite.load(repository_root / "suites" / "optiq-route-smoke-v1.json")
        transport = StageTwoInferenceTransport(set(manifest.routes.values()), timeout_seconds=120)
        controller = OperatorOptiQController(
            (str(profile.runtime_executable), *profile.serve_arguments),
            MacProcessBackend(),
            lambda: transport.health(profile.direct_base_url),
        )
        lock = RunLock(output_root)

        def resources(health: dict[str, object]):
            return snapshot_from_health(HostResourceProbe().free_memory_percent(), health, None)

        return StageTwoInferenceEngine(
            manifest, profile, suite, output_root, resources,
            lambda: HostValidator(profile, PROVIDER_CONFIG).validate(),
            controller, transport, lock.owner,
        )

    transport = StageTwoReadOnlyTransport(
        {profile.direct_base_url, profile.routed_base_url},
        timeout_seconds=int(manifest.limits["request_timeout_seconds"]),
    )
    command = (str(profile.runtime_executable), *profile.serve_arguments)
    controller = OperatorOptiQController(
        command, MacProcessBackend(), lambda: transport.health(profile.direct_base_url)
    )

    def resources():
        health = transport.health(profile.routed_base_url)
        return snapshot_from_health(HostResourceProbe().free_memory_percent(), health, None)

    return StageTwoEngine(
        manifest, profile, output_root, resources,
        lambda: HostValidator(profile, PROVIDER_CONFIG).validate(),
        controller, transport,
    )
