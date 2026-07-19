from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import re
import subprocess


class MemoryPressure(str, Enum):
    NORMAL = "normal"
    WARNING = "warning"
    CRITICAL = "critical"


class ResourceGateError(RuntimeError):
    code = "resource_gate_failed"


@dataclass(frozen=True)
class ResourceSnapshot:
    memory_pressure: MemoryPressure
    osaurus_native_models: tuple[str, ...]
    active_run_id: str | None

    @property
    def osaurus_native_model_loaded(self) -> bool:
        return bool(self.osaurus_native_models)


@dataclass(frozen=True)
class ResourceDecision:
    allowed: bool
    warning: bool


class ResourcePolicy:
    """Provisional M2 Max 64GB policy; collectors are approved separately."""

    def __init__(self, coordinator_model_id: str | None = None) -> None:
        self.coordinator_model_id = coordinator_model_id

    def evaluate(self, snapshot: ResourceSnapshot) -> ResourceDecision:
        if snapshot.memory_pressure is MemoryPressure.CRITICAL:
            raise ResourceGateError("memory pressure is at the stop level")
        allowed = () if self.coordinator_model_id is None else (self.coordinator_model_id,)
        if snapshot.osaurus_native_models not in ((), allowed):
            raise ResourceGateError("an unapproved Osaurus-native model is resident")
        if snapshot.active_run_id:
            raise ResourceGateError("another harness run is active")
        return ResourceDecision(True, snapshot.memory_pressure is MemoryPressure.WARNING)


def snapshot_from_health(
    free_memory_percent: int, health: dict[str, object], active_run_id: str | None
) -> ResourceSnapshot:
    if free_memory_percent < 10:
        pressure = MemoryPressure.CRITICAL
    elif free_memory_percent < 20:
        pressure = MemoryPressure.WARNING
    else:
        pressure = MemoryPressure.NORMAL
    loaded = health.get("loaded") or []
    resident = health.get("resident_models") or []
    current = health.get("current_model")
    if not isinstance(loaded, list) or not isinstance(resident, list):
        raise ResourceGateError("Osaurus health residency fields are invalid")
    resident_names: list[object] = []
    for value in resident:
        resident_names.append(value.get("name") if isinstance(value, dict) else value)
    values = [*loaded, *resident_names] + ([] if current is None else [current])
    if any(not isinstance(value, str) or not value for value in values):
        raise ResourceGateError("Osaurus health model identities are invalid")
    models = tuple(sorted(set(values)))
    return ResourceSnapshot(pressure, models, active_run_id)


class HostResourceProbe:
    @staticmethod
    def parse_free_percentage(output: str) -> int:
        match = re.search(r"free percentage:\s*([0-9]{1,3})%", output)
        if not match:
            raise ResourceGateError("macOS memory pressure output is unrecognized")
        value = int(match.group(1))
        if not 0 <= value <= 100:
            raise ResourceGateError("macOS memory percentage is invalid")
        return value

    def free_memory_percent(self) -> int:
        result = subprocess.run(
            ["/usr/bin/memory_pressure", "-Q"], capture_output=True, text=True,
            check=False, timeout=10,
        )
        if result.returncode != 0:
            raise ResourceGateError("macOS memory pressure probe failed")
        return self.parse_free_percentage(result.stdout)
