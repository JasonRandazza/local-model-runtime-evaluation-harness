from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType

from .omlx_thinking_measure import preflight_budget_ok

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]

PIN_ID = "omlx-0.5.3-thinking"
PIN_REVISION = "2"
PIN_VERSION = "0.5.3"
PIN_BASE_URL = "http://127.0.0.1:8100/v1"
COMPARISON_CLASS = "omlx-thinking-measure-v1"
PIN_MODEL_ID = "Qwen3.6-35B-A3B-OptiQ-4bit"
PIN_MODEL_DIR = "/Users/jrazz/.cache/huggingface/hub/mlx-community/Qwen3.6-35B-A3B-OptiQ-4bit"
PIN_OWNERSHIP_MODE = "dedicated_serve"
PIN_API_KEY_SOURCE = "matrix_local"
REQUIRED_CHAT_TEMPLATE_KWARGS: Mapping[str, object] = MappingProxyType(
    {"enable_thinking": True}
)
PIN_START_COMMAND = (
    "omlX",
    "serve",
    "--model-dir",
    PIN_MODEL_DIR,
    "--host",
    "127.0.0.1",
    "--port",
    "8100",
)

SUITE_ID = "omlx-thinking-smoke-v1"
SUITE_REVISION = "1"
MEASURE_SUITE_ID = "omlx-thinking-measure-v1"
MEASURE_SUITE_REVISION = "1"
SMOKE_WORKLOAD_COUNT = 2
MEASURE_WORKLOAD_COUNT = 5

_PIN_REQUIRED = frozenset({
    "schema_version",
    "pin_id",
    "revision",
    "version",
    "base_url",
    "comparison_class",
    "model_id",
    "model_dir",
    "ownership_mode",
    "api_key_source",
    "extra_body_allowlist",
    "required_chat_template_kwargs",
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
    return REPOSITORY_ROOT / "config" / "omlx-pins" / "omlx-0.5.3-thinking-r2.json"


def default_suite_path() -> Path:
    return REPOSITORY_ROOT / "suites" / "omlx-thinking-smoke-v1.json"


def default_measure_suite_path() -> Path:
    return REPOSITORY_ROOT / "suites" / "omlx-thinking-measure-v1.json"


@dataclass(frozen=True)
class OmlxThinkingPin:
    pin_id: str
    revision: str
    version: str
    base_url: str
    comparison_class: str
    model_id: str
    model_dir: str
    ownership_mode: str
    api_key_source: str
    extra_body_allowlist: tuple[str, ...]
    required_chat_template_kwargs: Mapping[str, object]
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
        if data["model_id"] != PIN_MODEL_ID:
            raise OmlxThinkingPinError("pin model_id does not match approved contract")
        if data["model_dir"] != PIN_MODEL_DIR:
            raise OmlxThinkingPinError("pin model_dir does not match approved contract")
        if data["ownership_mode"] != PIN_OWNERSHIP_MODE:
            raise OmlxThinkingPinError("pin ownership_mode does not match approved contract")
        if data["api_key_source"] != PIN_API_KEY_SOURCE:
            raise OmlxThinkingPinError("pin api_key_source does not match approved contract")
        allowlist = _string_list(data["extra_body_allowlist"], field="extra_body_allowlist")
        start_command = _string_list(data["start_command"], field="start_command")
        stop_command = _string_list(data["stop_command"], field="stop_command")
        if not start_command:
            raise OmlxThinkingPinError("pin start_command must not be empty")
        if "--model-dir" not in start_command:
            raise OmlxThinkingPinError("pin start_command must include --model-dir")
        if tuple(start_command) != PIN_START_COMMAND:
            raise OmlxThinkingPinError("pin start_command does not match approved contract")
        kwargs = _required_chat_template_kwargs(data["required_chat_template_kwargs"])
        return cls(
            PIN_ID,
            PIN_REVISION,
            PIN_VERSION,
            PIN_BASE_URL,
            COMPARISON_CLASS,
            PIN_MODEL_ID,
            PIN_MODEL_DIR,
            PIN_OWNERSHIP_MODE,
            PIN_API_KEY_SOURCE,
            allowlist,
            kwargs,
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
        suite_id = data["suite_id"]
        if suite_id == SUITE_ID:
            expected_revision = SUITE_REVISION
            expected_count = SMOKE_WORKLOAD_COUNT
        elif suite_id == MEASURE_SUITE_ID:
            expected_revision = MEASURE_SUITE_REVISION
            expected_count = MEASURE_WORKLOAD_COUNT
        else:
            raise OmlxThinkingPinError("suite_id does not match approved contract")
        if data["revision"] != expected_revision:
            raise OmlxThinkingPinError("suite revision does not match approved contract")
        if data["temperature"] != 0:
            raise OmlxThinkingPinError("suite must be deterministic")
        if data["streaming"] is not True:
            raise OmlxThinkingPinError("suite must be streaming")
        items = data["workloads"]
        if not isinstance(items, list) or len(items) != expected_count:
            raise OmlxThinkingPinError(
                f"suite must contain exactly {expected_count} workloads"
            )
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
        if len({item.workload_id for item in workloads}) != expected_count:
            raise OmlxThinkingPinError("workload IDs must be unique")
        return cls(str(suite_id), expected_revision, 0, True, tuple(workloads))


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


def _required_chat_template_kwargs(value: object) -> Mapping[str, object]:
    if not isinstance(value, dict):
        raise OmlxThinkingPinError("pin required_chat_template_kwargs must be an object")
    if set(value) != {"enable_thinking"}:
        raise OmlxThinkingPinError("pin required_chat_template_kwargs keys are invalid")
    if value.get("enable_thinking") is not True:
        raise OmlxThinkingPinError(
            "pin required_chat_template_kwargs.enable_thinking must be true"
        )
    return MappingProxyType({"enable_thinking": True})
