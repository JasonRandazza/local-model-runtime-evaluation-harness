from __future__ import annotations

import time
from pathlib import Path

from .harness_lifecycle import ServerPin, default_lab_closed
from .matrix_lifecycle import ManagedProcess, port_is_free
from .resources import HostResourceProbe, snapshot_from_health
from .stage_two import StageTwoEngine
from .stage_two_benchmark import (
    _STAGE_2B_2_LIMITS,
    _STAGE_2B_2_OPERATIONS,
    _STAGE_2B_2_ROUTES,
    StageTwoBenchmarkEngine,
)
from .stage_two_benchmark_suite import StageTwoBenchmarkSuite
from .stage_two_inference import (
    _STAGE_2B_1_LIMITS,
    _STAGE_2B_1_OPERATIONS,
    _STAGE_2B_1_ROUTES,
    StageTwoInferenceEngine,
)
from .stage_two_inference_transport import StageTwoInferenceTransport
from .stage_two_harness_lifecycle import HarnessOptiQController
from .stage_two_host import (
    HostValidator, MacProcessBackend, OperatorOptiQController, StageTwoReadOnlyTransport,
)
from .stage_two_profiles import RuntimeProfileRegistry
from .stage_two_smoke_suite import StageTwoSmokeSuite
from .locking import RunLock

_HARNESS_OPTIQ_READY_TIMEOUT_SECONDS = 600.0


PROVIDER_CONFIG = Path("/Users/jrazz/.osaurus/providers/remote.json")


def _validate_stage_two_inference_manifest(manifest) -> None:
    common = (
        manifest.stage == 2
        and manifest.schema_version == "3.3.0"
        and manifest.mode == "operator_inference_probe"
        and manifest.runtime_profile_id == "gemma-4-12b-optiq-4bit"
        and manifest.suite_revision == "1"
        and manifest.repetitions == 1
        and manifest.route_order == "counterbalanced"
        and tuple(manifest.operations) == _STAGE_2B_1_OPERATIONS
        and dict(manifest.routes or {}) == _STAGE_2B_1_ROUTES
        and dict(manifest.limits or {}) == _STAGE_2B_1_LIMITS
    )
    historical = (
        manifest.comparison_class == "gemma-optiq-operator-route-smoke"
        and manifest.runtime_profile_revision == "2"
        and manifest.suite_id == "gemma-optiq-route-smoke-v1"
    )
    operator_042 = (
        manifest.comparison_class == "gemma-optiq-042-operator-route-smoke"
        and manifest.runtime_profile_revision == "3"
        and manifest.suite_id == "gemma-optiq-042-operator-route-smoke-v1"
    )
    if not (common and (historical or operator_042)):
        raise ValueError("unsupported Stage 2 mode")


def _validate_stage_two_harness_manifest(manifest) -> None:
    fixed_contract = (
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
    if not fixed_contract:
        raise ValueError("unsupported Stage 2 mode")


def _validate_stage_two_benchmark_manifest(manifest) -> None:
    common = (
        manifest.stage == 2
        and manifest.schema_version == "3.4.0"
        and manifest.mode == "operator_route_benchmark"
        and manifest.runtime_profile_id == "gemma-4-12b-optiq-4bit"
        and manifest.suite_revision == "1"
        and manifest.repetitions == 1
        and manifest.route_order == "counterbalanced"
        and tuple(manifest.operations) == _STAGE_2B_2_OPERATIONS
        and dict(manifest.routes or {}) == _STAGE_2B_2_ROUTES
        and dict(manifest.limits or {}) == _STAGE_2B_2_LIMITS
    )
    historical = (
        manifest.comparison_class == "gemma-optiq-operator-route-benchmark"
        and manifest.runtime_profile_revision == "2"
        and manifest.suite_id == "gemma-optiq-route-benchmark-v1"
    )
    operator_042 = (
        manifest.comparison_class == "gemma-optiq-042-operator-route-benchmark"
        and manifest.runtime_profile_revision == "3"
        and manifest.suite_id == "gemma-optiq-042-operator-route-benchmark-v1"
    )
    if not (common and (historical or operator_042)):
        raise ValueError("unsupported Stage 2 mode")


def build_stage_two_engine(
    repository_root: Path, manifest, output_root: Path,
) -> StageTwoEngine | StageTwoInferenceEngine | StageTwoBenchmarkEngine:
    contract = (manifest.schema_version, manifest.mode)
    if contract == ("3.3.0", "operator_inference_probe"):
        _validate_stage_two_inference_manifest(manifest)
    elif contract == ("3.4.0", "operator_route_benchmark"):
        _validate_stage_two_benchmark_manifest(manifest)
    elif contract == ("3.5.0", "harness_inference_probe"):
        _validate_stage_two_harness_manifest(manifest)
    elif contract != ("3.1.0", "operator_route_probe"):
        raise ValueError("unsupported Stage 2 mode")
    profile = RuntimeProfileRegistry(repository_root / "config" / "runtime-profiles").get(
        manifest.runtime_profile_id, manifest.runtime_profile_revision
    )
    if contract == ("3.4.0", "operator_route_benchmark"):
        benchmark_suite_name = (
            "gemma-optiq-042-operator-route-benchmark-v1.json"
            if manifest.comparison_class == "gemma-optiq-042-operator-route-benchmark"
            else "gemma-optiq-route-benchmark-v1.json"
        )
        suite = StageTwoBenchmarkSuite.load(
            repository_root / "suites" / benchmark_suite_name
        )
        transport = StageTwoInferenceTransport(set(manifest.routes.values()), timeout_seconds=120)
        controller = OperatorOptiQController(
            (str(profile.runtime_executable), *profile.serve_arguments),
            MacProcessBackend(),
            lambda: transport.health(profile.direct_base_url),
        )
        lock = RunLock(output_root)

        def resources(health: dict[str, object]):
            return snapshot_from_health(HostResourceProbe().free_memory_percent(), health, None)

        return StageTwoBenchmarkEngine(
            manifest, profile, suite, output_root, resources,
            lambda: HostValidator(profile, PROVIDER_CONFIG).validate(),
            controller, transport, lock.owner,
        )
    if contract == ("3.5.0", "harness_inference_probe"):
        suite = StageTwoSmokeSuite.load(
            repository_root / "suites" / "gemma-optiq-042-harness-route-smoke-v1.json"
        )
        transport = StageTwoInferenceTransport(set(manifest.routes.values()), timeout_seconds=120)

        def wait_ready(pin: ServerPin, process: ManagedProcess | None) -> None:
            del pin, process
            deadline = time.monotonic() + _HARNESS_OPTIQ_READY_TIMEOUT_SECONDS
            last_error: Exception | None = None
            while time.monotonic() < deadline:
                try:
                    health = transport.health(profile.direct_base_url)
                    if health.get("status") == "ok":
                        return
                except Exception as error:  # noqa: BLE001 — poll until ready or timeout
                    last_error = error
                time.sleep(0.5)
            message = "harness OptiQ did not become ready"
            if last_error is not None:
                message = f"{message}: {last_error}"
            raise TimeoutError(message)

        controller = HarnessOptiQController(
            free_memory=lambda: HostResourceProbe().free_memory_percent(),
            port_free=port_is_free,
            lab_closed=default_lab_closed,
            profile=profile,
            wait_ready=wait_ready,
        )
        lock = RunLock(output_root)

        def resources(health: dict[str, object]):
            return snapshot_from_health(HostResourceProbe().free_memory_percent(), health, None)

        return StageTwoInferenceEngine(
            manifest, profile, suite, output_root, resources,
            lambda: HostValidator(profile, PROVIDER_CONFIG).validate(),
            controller, transport, lock.owner,
        )
    if contract == ("3.3.0", "operator_inference_probe"):
        smoke_suite_name = (
            "gemma-optiq-042-operator-route-smoke-v1.json"
            if manifest.comparison_class == "gemma-optiq-042-operator-route-smoke"
            else "gemma-optiq-route-smoke-v1.json"
        )
        suite = StageTwoSmokeSuite.load(
            repository_root / "suites" / smoke_suite_name
        )
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
