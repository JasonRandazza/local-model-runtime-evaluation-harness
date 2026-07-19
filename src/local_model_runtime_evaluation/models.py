from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Mapping


class Operation(str, Enum):
    INVENTORY = "inventory"
    PREFLIGHT = "preflight"
    RUN_SCENARIO = "run-scenario"
    STATUS = "status"
    CANCEL = "cancel"
    CLEANUP = "cleanup"


class Disposition(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    STOPPED = "STOPPED"


class RunStatus(str, Enum):
    QUEUED = "queued"
    PREFLIGHT = "preflight"
    READY = "ready"
    RUNNING = "running"
    SERVICE_STARTING = "service_starting"
    SERVICE_READY = "service_ready"
    SERVICE_STOPPING = "service_stopping"
    RESOURCE_GATE = "resource_gate"
    ENDPOINT_IDENTITY = "endpoint_identity"
    WARMUP = "warmup"
    MEASURED = "measured"
    ARTIFACT_VALIDATION = "artifact_validation"
    AWAITING_REVIEW = "awaiting_review"
    CANCELLED = "cancelled"
    FAILED = "failed"
    COMPLETE = "complete"
    CLEANED = "cleaned"


@dataclass(frozen=True)
class BenchmarkManifest:
    schema_version: str
    run_id: str
    stage: int
    mode: str
    operations: tuple[Operation, ...]
    output_root: Path
    approved_by: str
    approved_at: datetime
    expires_at: datetime
    simulation: Mapping[str, str]
    raw: Mapping[str, object]
    comparison_class: str | None = None
    model_profile_id: str | None = None
    model_profile_revision: str | None = None
    suite_id: str | None = None
    suite_revision: str | None = None
    repetitions: int | None = None
    route_order: str | None = None
    routes: Mapping[str, str] | None = None
    limits: Mapping[str, object] | None = None
    runtime_profile_id: str | None = None
    runtime_profile_revision: str | None = None


@dataclass(frozen=True)
class RunState:
    run_id: str
    status: RunStatus
    sequence: int
    updated_at: str
    reason: str
