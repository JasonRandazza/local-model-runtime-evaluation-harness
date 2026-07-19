from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping

from .models import BenchmarkManifest, Operation


STAGE_ZERO_RUN_ID_PATTERN = re.compile(r"^stage0-[0-9]{8}-[0-9]{3}$")
STAGE_ONE_RUN_ID_PATTERN = re.compile(r"^stage1-[0-9]{8}-[0-9]{3}$")
STAGE_TWO_RUN_ID_PATTERN = re.compile(r"^stage2-[0-9]{8}-[0-9]{3}$")
CANONICAL_OUTPUT_ROOT = Path("/Users/jrazz/.osaurus/container/output/benchmark-runs")
COMMON_KEYS = {
    "schema_version",
    "run_id",
    "stage",
    "mode",
    "operations",
    "output_root",
    "approved_by",
    "approved_at",
    "expires_at",
}
STAGE_ZERO_KEYS = COMMON_KEYS | {"simulation"}
STAGE_ONE_KEYS = COMMON_KEYS | {
    "comparison_class", "model_profile_id", "model_profile_revision", "suite_id",
    "suite_revision", "repetitions", "route_order", "routes", "limits",
}
STAGE_TWO_KEYS = COMMON_KEYS | {
    "comparison_class", "runtime_profile_id", "runtime_profile_revision", "routes", "limits",
}
STAGE_TWO_INFERENCE_KEYS = STAGE_TWO_KEYS | {
    "suite_id", "suite_revision", "repetitions", "route_order",
}


class ManifestError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _timestamp(value: object, field: str) -> datetime:
    if not isinstance(value, str):
        raise ManifestError("invalid_timestamp", f"{field} must be an ISO 8601 string")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ManifestError("invalid_timestamp", f"{field} is not valid ISO 8601") from error
    if parsed.tzinfo is None:
        raise ManifestError("invalid_timestamp", f"{field} must include a timezone")
    return parsed


def validate_manifest(
    data: Mapping[str, object], now: datetime | None = None
) -> BenchmarkManifest:
    stage = data.get("stage")
    if stage not in {0, 1, 2}:
        raise ManifestError("stage_forbidden", "stage must be 0, 1, or 2")
    schema_version = data.get("schema_version")
    if stage == 2 and schema_version == "3.2.0":
        required_keys = STAGE_TWO_INFERENCE_KEYS
    else:
        required_keys = (
            STAGE_ZERO_KEYS if stage == 0
            else STAGE_ONE_KEYS if stage == 1
            else STAGE_TWO_KEYS
        )
    unknown = set(data) - required_keys
    missing = required_keys - set(data)
    if unknown:
        raise ManifestError("unknown_property", f"unknown properties: {sorted(unknown)}")
    if missing:
        raise ManifestError("missing_property", f"missing properties: {sorted(missing)}")
    if stage == 0:
        allowed_schemas = {"1.0.0"}
    elif stage == 1:
        allowed_schemas = {"2.0.0"}
    else:
        allowed_schemas = {"3.0.0", "3.1.0", "3.2.0"}
    if data["schema_version"] not in allowed_schemas:
        raise ManifestError("unsupported_schema", "schema_version does not match stage")
    if stage == 0:
        expected_mode = "dry_run"
    elif stage == 1:
        expected_mode = "live_route_comparison"
    elif data["schema_version"] == "3.0.0":
        expected_mode = "lifecycle_probe"
    elif data["schema_version"] == "3.1.0":
        expected_mode = "operator_route_probe"
    else:
        expected_mode = "operator_inference_probe"
    if data["mode"] != expected_mode:
        raise ManifestError("live_mode_forbidden", f"mode must be {expected_mode}")

    run_id = data["run_id"]
    pattern = (
        STAGE_ZERO_RUN_ID_PATTERN if stage == 0
        else STAGE_ONE_RUN_ID_PATTERN if stage == 1
        else STAGE_TWO_RUN_ID_PATTERN
    )
    if not isinstance(run_id, str) or not pattern.fullmatch(run_id):
        raise ManifestError("invalid_run_id", f"run_id does not match the Stage {stage} format")

    operation_values = data["operations"]
    if not isinstance(operation_values, list):
        raise ManifestError("invalid_operations", "operations must be a list")
    try:
        operations = tuple(Operation(value) for value in operation_values)
    except (ValueError, TypeError) as error:
        raise ManifestError("unknown_operation", "manifest contains an unknown operation") from error
    if set(operations) != set(Operation) or len(operations) != len(Operation):
        raise ManifestError("operations_incomplete", "manifest must authorize exactly six operations")

    output_value = data["output_root"]
    if not isinstance(output_value, str):
        raise ManifestError("output_root_forbidden", "output_root must be the canonical path")
    output_root = Path(output_value).expanduser()
    if output_root != CANONICAL_OUTPUT_ROOT:
        raise ManifestError("output_root_forbidden", "output_root must be the canonical path")

    approved_by = data["approved_by"]
    if not isinstance(approved_by, str) or not approved_by.strip():
        raise ManifestError("approval_missing", "approved_by is required")
    approved_at = _timestamp(data["approved_at"], "approved_at")
    expires_at = _timestamp(data["expires_at"], "expires_at")
    current = now or datetime.now(timezone.utc)
    if approved_at >= expires_at:
        raise ManifestError("approval_window_invalid", "approval must precede expiration")
    if current > expires_at:
        raise ManifestError("approval_expired", "manifest approval has expired")

    simulation: Mapping[str, str] = {}
    stage_specific: dict[str, object] = {}
    if stage == 0:
        simulation_value = data["simulation"]
        if simulation_value != {"pause_after": "running"}:
            raise ManifestError("simulation_invalid", "Stage 0 must pause after running")
        simulation = dict(simulation_value)  # type: ignore[arg-type]
    elif stage == 1:
        if data["comparison_class"] != "route-overhead":
            raise ManifestError("comparison_forbidden", "Stage 1 requires route-overhead")
        for field in ("model_profile_id", "model_profile_revision", "suite_id", "suite_revision"):
            if not isinstance(data[field], str) or not str(data[field]).strip():
                raise ManifestError("invalid_reference", f"{field} must be a non-empty string")
        if data["repetitions"] != 5 or data["route_order"] != "counterbalanced":
            raise ManifestError("cohort_forbidden", "Stage 1 requires five counterbalanced repetitions")
        routes = data["routes"]
        expected_routes = {
            "direct": "http://127.0.0.1:8100/v1",
            "routed": "http://127.0.0.1:1337/v1",
        }
        if routes != expected_routes:
            raise ManifestError("route_forbidden", "Stage 1 routes must match approved loopback endpoints")
        limits = data["limits"]
        if not isinstance(limits, dict) or set(limits) != {"request_timeout_seconds", "memory_stop_level"}:
            raise ManifestError("limits_invalid", "Stage 1 limits are incomplete")
        if limits["memory_stop_level"] != "critical" or not isinstance(limits["request_timeout_seconds"], int):
            raise ManifestError("limits_invalid", "Stage 1 limits are invalid")
        stage_specific = {
            "comparison_class": str(data["comparison_class"]),
            "model_profile_id": str(data["model_profile_id"]),
            "model_profile_revision": str(data["model_profile_revision"]),
            "suite_id": str(data["suite_id"]),
            "suite_revision": str(data["suite_revision"]),
            "repetitions": int(data["repetitions"]),
            "route_order": str(data["route_order"]),
            "routes": dict(routes),  # type: ignore[arg-type]
            "limits": dict(limits),
        }
    else:
        if data["schema_version"] == "3.2.0":
            if data["comparison_class"] != "optiq-operator-route-smoke":
                raise ManifestError("comparison_forbidden", "Stage 2B comparison contract is not approved")
            if data["runtime_profile_id"] != "vibethinker-3b-optiq-4bit":
                raise ManifestError("profile_forbidden", "Stage 2B requires the approved runtime profile")
            if data["runtime_profile_revision"] != "3":
                raise ManifestError("profile_revision_forbidden", "Stage 2B requires runtime profile revision 3")
            if data["suite_id"] != "optiq-route-smoke-v1" or data["suite_revision"] != "1":
                raise ManifestError("suite_forbidden", "Stage 2B requires the approved smoke suite")
            if (
                type(data["repetitions"]) is not int
                or data["repetitions"] != 1
                or data["route_order"] != "counterbalanced"
            ):
                raise ManifestError("cohort_forbidden", "Stage 2B requires one counterbalanced repetition")
            routes = data["routes"]
            if routes != {
                "direct": "http://127.0.0.1:8080/v1",
                "routed": "http://127.0.0.1:1337/v1",
            }:
                raise ManifestError("route_forbidden", "Stage 2B routes must match approved loopback endpoints")
            limits = data["limits"]
            expected_limits = {
                "request_timeout_seconds": 120,
                "memory_stop_level": "warning",
                "maximum_in_flight_requests": 1,
                "total_request_limit": 8,
            }
            if (
                not isinstance(limits, dict)
                or limits != expected_limits
                or any(
                    type(limits[field]) is not int
                    for field in (
                        "request_timeout_seconds",
                        "maximum_in_flight_requests",
                        "total_request_limit",
                    )
                )
            ):
                raise ManifestError("limits_invalid", "Stage 2B limits must match the approved bounded values")
            stage_specific = {
                "comparison_class": str(data["comparison_class"]),
                "runtime_profile_id": str(data["runtime_profile_id"]),
                "runtime_profile_revision": str(data["runtime_profile_revision"]),
                "suite_id": str(data["suite_id"]),
                "suite_revision": str(data["suite_revision"]),
                "repetitions": int(data["repetitions"]),
                "route_order": str(data["route_order"]),
                "routes": dict(routes),
                "limits": dict(limits),
            }
        else:
            historical = data["schema_version"] == "3.0.0"
            expected_comparison = (
                "optiq-lifecycle-route-discovery"
                if historical else "optiq-operator-route-discovery"
            )
            if data["comparison_class"] != expected_comparison:
                raise ManifestError("comparison_forbidden", "Stage 2A comparison contract is not approved")
            for field in ("runtime_profile_id", "runtime_profile_revision"):
                if not isinstance(data[field], str) or not str(data[field]).strip():
                    raise ManifestError("invalid_reference", f"{field} must be a non-empty string")
            if historical:
                if data["runtime_profile_revision"] not in {"1", "2"}:
                    raise ManifestError("profile_revision_forbidden", "historical Stage 2A requires revision 1 or 2")
            elif data["runtime_profile_revision"] != "3":
                raise ManifestError("profile_revision_forbidden", "active Stage 2A requires runtime profile revision 3")
            routes = data["routes"]
            if routes != {
                "direct": "http://127.0.0.1:8080/v1",
                "routed": "http://127.0.0.1:1337/v1",
            }:
                raise ManifestError("route_forbidden", "Stage 2A routes must match approved loopback endpoints")
            limits = data["limits"]
            expected_limits = (
                {
                    "startup_timeout_seconds": 120,
                    "shutdown_timeout_seconds": 30,
                    "request_timeout_seconds": 10,
                    "memory_stop_level": "critical",
                }
                if historical else {
                    "request_timeout_seconds": 10,
                    "memory_stop_level": "critical",
                }
            )
            if limits != expected_limits:
                raise ManifestError("limits_invalid", "Stage 2A limits must match the approved bounded values")
            stage_specific = {
                "comparison_class": str(data["comparison_class"]),
                "runtime_profile_id": str(data["runtime_profile_id"]),
                "runtime_profile_revision": str(data["runtime_profile_revision"]),
                "routes": dict(routes),
                "limits": dict(limits),
            }

    return BenchmarkManifest(
        schema_version=str(data["schema_version"]),
        run_id=run_id,
        stage=int(stage),
        mode=str(data["mode"]),
        operations=operations,
        output_root=output_root,
        approved_by=approved_by,
        approved_at=approved_at,
        expires_at=expires_at,
        simulation=simulation,
        raw=dict(data),
        **stage_specific,
    )


def load_manifest(path: Path, now: datetime | None = None) -> BenchmarkManifest:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ManifestError("manifest_unreadable", f"could not read manifest: {path}") from error
    if not isinstance(data, dict):
        raise ManifestError("manifest_invalid", "manifest root must be an object")
    return validate_manifest(data, now=now)
