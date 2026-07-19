from __future__ import annotations

from pathlib import Path

from .benchmark_suite import BenchmarkSuite
from .credentials import KeychainCredentialProvider
from .model_profiles import ModelProfileRegistry
from .resources import HostResourceProbe, snapshot_from_health
from .stage_one import StageOneEngine
from .transport import LoopbackTransport


def build_stage_one_engine(repository_root: Path, manifest, output_root: Path) -> StageOneEngine:
    registry = ModelProfileRegistry(repository_root / "config" / "model-profiles")
    profile = registry.get(manifest.model_profile_id, manifest.model_profile_revision)
    suite = BenchmarkSuite.load(repository_root / "suites" / f"{manifest.suite_id}.json")
    if suite.revision != manifest.suite_revision or profile.suite_id != suite.suite_id:
        raise ValueError("approved benchmark suite revision does not match")
    transport = LoopbackTransport(
        {profile.direct.base_url, profile.routed.base_url},
        timeout_seconds=int(manifest.limits["request_timeout_seconds"]),
    )
    def snapshot():
        health = transport.health(profile.routed.base_url)
        return snapshot_from_health(HostResourceProbe().free_memory_percent(), health, None)

    return StageOneEngine(
        manifest, profile, suite, output_root, KeychainCredentialProvider(), snapshot, transport,
    )
