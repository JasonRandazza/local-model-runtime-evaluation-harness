from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .omlx_thinking_measure import preflight_budget_ok

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]

PIN_ID = "omlx-0.5.2-thinking"
PIN_REVISION = "1"
PIN_VERSION = "0.5.2"
PIN_BASE_URL = "http://127.0.0.1:8100/v1"
COMPARISON_CLASS = "omlx-thinking-measure-v1"

SUITE_ID = "omlx-thinking-smoke-v1"
SUITE_REVISION = "1"

_PIN_REQUIRED = frozenset({
    "schema_version",
    "pin_id",
    "revision",
    "version",
    "base_url",
    "comparison_class",
    "extra_body_allowlist",
    "start_command",
    "stop_command",
})
_SUITE_REQUIRED = frozenset({
    "schema_version",
    "suite_id",
    "revision",
    "temperature",
    "streaming",
    "workloads",
})
_WORKLOAD_REQUIRED = frozenset({
    "workload_id",
    "prompt",
    "max_tokens",
    "response_contract",
})


class OmlxThinkingPinError(ValueError):
    pass


def default_pin_path() -> Path:
    return REPOSITORY_ROOT / "config" / "omlx-pins" / "omlx-0.5.2-thinking-r1.json"


def default_suite_path() -> Path:
    return REPOSITORY_ROOT / "suites" / "omlx-thinking-smoke-v1.json"


@dataclass(frozen=True)
class OmlxThinkingPin:
    pin_id: str
    revision: str
    version: str
    base_url: str
    comparison_class: str
    extra_body_allowlist: tuple[str, ...]
    start_command: tuple[str, ...]
    stop_command: tuple[str, ...]

    @classmethod
    def load(cls, path: Path) -> OmlxThinkingPin:
        data = _read_json(path, "pin")
        if set(data) != _PIN_REQUIRED:
            raise OmlxThinkingPinError("pin fields are invalid")
        if data["schema_version"] != "1.0.0":
            raise OmlxThinkingPinError("pin schema_version is invalid")
        if data["pin_id"] != PIN_ID:
            raise OmlxThinkingPinError("pin_id does not match approved contract")
        if data["revision"] != PIN_REVISION:
            raise OmlxThinkingPinError("pin revision does not match approved contract")
        if data["version"] != PIN_VERSION:
            raise OmlxThinkingPinError("pin version does not match approved contract")
        if data["base_url"] != PIN_BASE_URL:
            raise OmlxThinkingPinError("pin base_url does not match approved contract")
        if data["comparison_class"] != COMPARISON_CLASS:
            raise OmlxThinkingPinError("pin comparison_class does not match approved contract")
        allowlist = _string_list(data["extra_body_allowlist"], field="extra_body_allowlist")
        start_command = _string_list(data["start_command"], field="start_command")
        stop_command = _string_list(data["stop_command"], field="stop_command")
        if not start_command:
            raise OmlxThinkingPinError("pin start_command must not be empty")
        return cls(
            PIN_ID,
            PIN_REVISION,
            PIN_VERSION,
            PIN_BASE_URL,
            COMPARISON_CLASS,
            allowlist,
            tuple(start_command),
            tuple(stop_command),
        )


@dataclass(frozen=True)
class OmlxThinkingWorkload:
    workload_id: str
    prompt: str
    max_tokens: int
    response_contract: str


@dataclass(frozen=True)
class OmlxThinkingSuite:
    suite_id: str
    revision: str
    temperature: int
    streaming: bool
    workloads: tuple[OmlxThinkingWorkload, ...]

    @classmethod
    def load(cls, path: Path) -> OmlxThinkingSuite:
        data = _read_json(path, "suite")
        if set(data) != _SUITE_REQUIRED:
            raise OmlxThinkingPinError("suite fields are invalid")
        if data["schema_version"] != "1.0.0":
            raise OmlxThinkingPinError("suite schema_version is invalid")
        if data["suite_id"] != SUITE_ID:
            raise OmlxThinkingPinError("suite_id does not match approved contract")
        if data["revision"] != SUITE_REVISION:
            raise OmlxThinkingPinError("suite revision does not match approved contract")
        if data["temperature"] != 0:
            raise OmlxThinkingPinError("suite must be deterministic")
        if data["streaming"] is not True:
            raise OmlxThinkingPinError("suite must be streaming")
        items = data["workloads"]
        if not isinstance(items, list) or len(items) != 2:
            raise OmlxThinkingPinError("suite must contain exactly two workloads")
        workloads: list[OmlxThinkingWorkload] = []
        for item in items:
            if not isinstance(item, dict) or set(item) != _WORKLOAD_REQUIRED:
                raise OmlxThinkingPinError("workload fields are invalid")
            max_tokens = item["max_tokens"]
            if not isinstance(max_tokens, int) or isinstance(max_tokens, bool):
                raise OmlxThinkingPinError("workload max_tokens must be an integer")
            if not preflight_budget_ok(max_tokens):
                raise OmlxThinkingPinError("workload max_tokens is below thinking preflight floor")
            workloads.append(
                OmlxThinkingWorkload(
                    str(item["workload_id"]),
                    str(item["prompt"]),
                    max_tokens,
                    str(item["response_contract"]),
                )
            )
        if len({item.workload_id for item in workloads}) != 2:
            raise OmlxThinkingPinError("workload IDs must be unique")
        return cls(SUITE_ID, SUITE_REVISION, 0, True, tuple(workloads))


def _read_json(path: Path, label: str) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise OmlxThinkingPinError(f"{label} is unreadable") from error
    if not isinstance(payload, dict):
        raise OmlxThinkingPinError(f"{label} fields are invalid")
    return payload


def _string_list(value: object, *, field: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise OmlxThinkingPinError(f"pin {field} must be a list")
    items: list[str] = []
    for item in value:
        if not isinstance(item, str):
            raise OmlxThinkingPinError(f"pin {field} must contain only strings")
        items.append(item)
    return tuple(items)
