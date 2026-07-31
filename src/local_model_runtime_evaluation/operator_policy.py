"""Standing local operator authority for managed LMRE runs."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


POLICY_SCHEMA_VERSION = "1.0.0"
ADOPTED_POLICY_FILENAME = "operator-policy.json"
APPROVED_RUNTIMES = frozenset({"osaurus", "omlx", "optiq"})
APPROVED_ENDPOINTS = frozenset({
    "http://127.0.0.1:1337/v1",
    "http://127.0.0.1:8100/v1",
    "http://127.0.0.1:8080/v1",
})
POLICY_FIELDS = frozenset({
    "schema_version",
    "policy_id",
    "authorization_mode",
    "loopback_only",
    "allowed_runtimes",
    "allow_inference",
    "allow_start",
    "allow_exact_reclaim",
    "reclaim_grace_seconds",
    "allow_terminate_after_interrupt",
    "allow_force_kill",
    "allow_provider_edits",
    "max_parallel_models",
    "memory_floor_percent",
    "max_run_minutes",
    "max_requests_per_run",
    "expires_at",
})
ADOPTION_FIELDS = frozenset({"adopted_at", "policy", "policy_hash"})
SAFE_POLICY_ID = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")


class PolicyError(RuntimeError):
    code = "operator_policy_invalid"

    def __init__(
        self,
        message: str,
        *,
        code: str = "operator_policy_invalid",
    ) -> None:
        super().__init__(message)
        self.code = code


def _require_bool(value: Any, field: str) -> bool:
    if type(value) is not bool:
        raise PolicyError(f"{field} must be a boolean")
    return value


def _require_positive_int(value: Any, field: str) -> int:
    if type(value) is not int or value <= 0:
        raise PolicyError(f"{field} must be a positive integer")
    return value


def _parse_utc_timestamp(value: str, field: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise PolicyError(f"{field} must be an RFC 3339 UTC timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise PolicyError(
            f"{field} must be an RFC 3339 UTC timestamp"
        ) from error
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise PolicyError(f"{field} must use UTC")
    if not (value.endswith("Z") or value.endswith("+00:00")):
        raise PolicyError(f"{field} must use UTC")
    return parsed


def _utc_now(now: datetime | None) -> datetime:
    current = datetime.now(timezone.utc) if now is None else now
    if current.tzinfo is None or current.utcoffset() != timezone.utc.utcoffset(current):
        raise PolicyError("current time must use UTC")
    return current


def canonical_hash(body: dict[str, object]) -> str:
    encoded = json.dumps(
        body,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class OperatorPolicy:
    schema_version: str
    policy_id: str
    authorization_mode: str
    loopback_only: bool
    allowed_runtimes: frozenset[str]
    allow_inference: bool
    allow_start: bool
    allow_exact_reclaim: bool
    reclaim_grace_seconds: int
    allow_terminate_after_interrupt: bool
    allow_force_kill: bool
    allow_provider_edits: bool
    max_parallel_models: int
    memory_floor_percent: int
    max_run_minutes: int
    max_requests_per_run: int
    expires_at: str | None

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> OperatorPolicy:
        if set(data) != POLICY_FIELDS:
            raise PolicyError("operator policy fields are invalid")
        if data["schema_version"] != POLICY_SCHEMA_VERSION:
            raise PolicyError("operator policy schema_version is invalid")
        policy_id = data["policy_id"]
        if not isinstance(policy_id, str) or not SAFE_POLICY_ID.fullmatch(policy_id):
            raise PolicyError("operator policy policy_id is invalid")
        if data["authorization_mode"] != "standing_local":
            raise PolicyError("authorization_mode must be standing_local")
        if not _require_bool(data["loopback_only"], "loopback_only"):
            raise PolicyError("loopback_only must be true")

        raw_runtimes = data["allowed_runtimes"]
        if (
            not isinstance(raw_runtimes, list)
            or not raw_runtimes
            or not all(isinstance(item, str) for item in raw_runtimes)
            or len(set(raw_runtimes)) != len(raw_runtimes)
        ):
            raise PolicyError("allowed_runtimes must be a unique string array")
        allowed_runtimes = frozenset(raw_runtimes)
        if not allowed_runtimes.issubset(APPROVED_RUNTIMES):
            raise PolicyError("allowed_runtimes contains an unknown runtime")

        allow_inference = _require_bool(
            data["allow_inference"], "allow_inference"
        )
        allow_start = _require_bool(data["allow_start"], "allow_start")
        allow_exact_reclaim = _require_bool(
            data["allow_exact_reclaim"], "allow_exact_reclaim"
        )
        reclaim_grace_seconds = _require_positive_int(
            data["reclaim_grace_seconds"], "reclaim_grace_seconds"
        )
        if reclaim_grace_seconds != 60:
            raise PolicyError("reclaim_grace_seconds must be 60")
        allow_terminate_after_interrupt = _require_bool(
            data["allow_terminate_after_interrupt"],
            "allow_terminate_after_interrupt",
        )
        allow_force_kill = _require_bool(
            data["allow_force_kill"], "allow_force_kill"
        )
        if allow_force_kill:
            raise PolicyError("allow_force_kill must be false")
        allow_provider_edits = _require_bool(
            data["allow_provider_edits"], "allow_provider_edits"
        )
        if allow_provider_edits:
            raise PolicyError("allow_provider_edits must be false")

        max_parallel_models = _require_positive_int(
            data["max_parallel_models"], "max_parallel_models"
        )
        if max_parallel_models != 1:
            raise PolicyError("max_parallel_models must be 1")
        memory_floor_percent = _require_positive_int(
            data["memory_floor_percent"], "memory_floor_percent"
        )
        if memory_floor_percent > 100:
            raise PolicyError("memory_floor_percent must not exceed 100")
        max_run_minutes = _require_positive_int(
            data["max_run_minutes"], "max_run_minutes"
        )
        max_requests_per_run = _require_positive_int(
            data["max_requests_per_run"], "max_requests_per_run"
        )

        expires_at = data["expires_at"]
        if expires_at is not None:
            if not isinstance(expires_at, str):
                raise PolicyError("expires_at must be null or a UTC timestamp")
            _parse_utc_timestamp(expires_at, "expires_at")

        return cls(
            schema_version=POLICY_SCHEMA_VERSION,
            policy_id=policy_id,
            authorization_mode="standing_local",
            loopback_only=True,
            allowed_runtimes=allowed_runtimes,
            allow_inference=allow_inference,
            allow_start=allow_start,
            allow_exact_reclaim=allow_exact_reclaim,
            reclaim_grace_seconds=reclaim_grace_seconds,
            allow_terminate_after_interrupt=allow_terminate_after_interrupt,
            allow_force_kill=False,
            allow_provider_edits=False,
            max_parallel_models=max_parallel_models,
            memory_floor_percent=memory_floor_percent,
            max_run_minutes=max_run_minutes,
            max_requests_per_run=max_requests_per_run,
            expires_at=expires_at,
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "policy_id": self.policy_id,
            "authorization_mode": self.authorization_mode,
            "loopback_only": self.loopback_only,
            "allowed_runtimes": sorted(self.allowed_runtimes),
            "allow_inference": self.allow_inference,
            "allow_start": self.allow_start,
            "allow_exact_reclaim": self.allow_exact_reclaim,
            "reclaim_grace_seconds": self.reclaim_grace_seconds,
            "allow_terminate_after_interrupt": (
                self.allow_terminate_after_interrupt
            ),
            "allow_force_kill": self.allow_force_kill,
            "allow_provider_edits": self.allow_provider_edits,
            "max_parallel_models": self.max_parallel_models,
            "memory_floor_percent": self.memory_floor_percent,
            "max_run_minutes": self.max_run_minutes,
            "max_requests_per_run": self.max_requests_per_run,
            "expires_at": self.expires_at,
        }


@dataclass(frozen=True)
class PolicyRequest:
    runtimes: frozenset[str]
    endpoints: tuple[str, ...]
    inference: bool
    start: bool
    exact_reclaim: bool
    parallel_models: int
    memory_floor_percent: int
    estimated_minutes: int
    request_count: int


@dataclass(frozen=True)
class AdoptedPolicy:
    policy: OperatorPolicy
    policy_hash: str
    adopted_at: str


def _require_not_expired(
    policy: OperatorPolicy,
    *,
    now: datetime | None,
) -> None:
    if policy.expires_at is None:
        return
    if _utc_now(now) >= _parse_utc_timestamp(policy.expires_at, "expires_at"):
        raise PolicyError(
            "operator policy has expired",
            code="operator_policy_expired",
        )


def load_policy(
    path: Path,
    *,
    now: datetime | None = None,
) -> OperatorPolicy:
    if not path.is_file():
        raise PolicyError(
            "operator policy file is missing",
            code="operator_policy_missing",
        )
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise PolicyError("operator policy JSON is invalid") from error
    if not isinstance(data, dict):
        raise PolicyError("operator policy must be a JSON object")
    policy = OperatorPolicy.from_dict(data)
    _require_not_expired(policy, now=now)
    return policy


def adopt_policy(
    source: Path,
    state_root: Path,
    *,
    now: datetime | None = None,
) -> AdoptedPolicy:
    current = _utc_now(now)
    policy = load_policy(source, now=current)
    adopted_at = current.astimezone(timezone.utc).isoformat()
    policy_body = policy.to_dict()
    policy_hash = canonical_hash(policy_body)
    body: dict[str, object] = {
        "adopted_at": adopted_at,
        "policy": policy_body,
        "policy_hash": policy_hash,
    }
    state_root.mkdir(parents=True, exist_ok=True)
    path = state_root / ADOPTED_POLICY_FILENAME
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(
        json.dumps(body, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.chmod(0o600)
    temporary.replace(path)
    return AdoptedPolicy(policy, policy_hash, adopted_at)


def load_adopted_policy(
    state_root: Path,
    *,
    now: datetime | None = None,
) -> AdoptedPolicy:
    path = state_root / ADOPTED_POLICY_FILENAME
    if not path.is_file():
        raise PolicyError(
            "adopted operator policy is missing",
            code="operator_policy_missing",
        )
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise PolicyError("adopted operator policy JSON is invalid") from error
    if not isinstance(data, dict) or set(data) != ADOPTION_FIELDS:
        raise PolicyError("adopted operator policy fields are invalid")
    raw_policy = data["policy"]
    policy_hash = data["policy_hash"]
    adopted_at = data["adopted_at"]
    if not isinstance(raw_policy, dict) or not isinstance(policy_hash, str):
        raise PolicyError("adopted operator policy record is invalid")
    if canonical_hash(raw_policy) != policy_hash:
        raise PolicyError(
            "adopted operator policy hash mismatch",
            code="operator_policy_hash_mismatch",
        )
    if not isinstance(adopted_at, str):
        raise PolicyError("adopted_at is invalid")
    _parse_utc_timestamp(adopted_at, "adopted_at")
    policy = OperatorPolicy.from_dict(raw_policy)
    _require_not_expired(policy, now=now)
    return AdoptedPolicy(policy, policy_hash, adopted_at)


def authorize(policy: OperatorPolicy, request: PolicyRequest) -> None:
    denied: list[str] = []
    if not request.runtimes.issubset(policy.allowed_runtimes):
        denied.append("runtime")
    if (
        not request.endpoints
        or any(endpoint not in APPROVED_ENDPOINTS for endpoint in request.endpoints)
    ):
        denied.append("endpoint")
    if request.inference and not policy.allow_inference:
        denied.append("inference")
    if request.start and not policy.allow_start:
        denied.append("start")
    if request.exact_reclaim and not policy.allow_exact_reclaim:
        denied.append("exact_reclaim")
    if (
        request.parallel_models <= 0
        or request.parallel_models > policy.max_parallel_models
    ):
        denied.append("parallel_models")
    if (
        request.memory_floor_percent < policy.memory_floor_percent
        or request.memory_floor_percent > 100
    ):
        denied.append("memory_floor_percent")
    if (
        request.estimated_minutes <= 0
        or request.estimated_minutes > policy.max_run_minutes
    ):
        denied.append("estimated_minutes")
    if (
        request.request_count <= 0
        or request.request_count > policy.max_requests_per_run
    ):
        denied.append("request_count")
    if denied:
        raise PolicyError(
            "operator policy denied: " + ", ".join(denied),
            code="operator_policy_denied",
        )
