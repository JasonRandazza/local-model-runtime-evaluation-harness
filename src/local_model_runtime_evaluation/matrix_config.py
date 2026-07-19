"""Load and validate Gemma 3×3 matrix cell, campaign, and suite config."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]

ALLOWED_SERVERS = frozenset({"osaurus", "omlx", "optiq"})
ALLOWED_QUANTS = frozenset({"jang_4m", "oq4_fp16", "optiq_4bit"})

SERVER_PORTS = {"osaurus": 1337, "omlx": 8100, "optiq": 8080}
EXPECTED_CAMPAIGN_PORTS = dict(SERVER_PORTS)

QUANT_CONTROL_ARTIFACTS = {
    "jang_4m": {
        "model_id": "gemma-4-12b-it-qat-jang_4m",
        "artifact_path": "/Users/jrazz/MLXModels/OsaurusAI/gemma-4-12B-it-qat-JANG_4M",
    },
    "oq4_fp16": {
        "model_id": "gemma-4-12B-it-qat-oQ4-fp16",
        "artifact_path": "/Users/jrazz/.cache/huggingface/hub/models--avneetsb--gemma-4-12B-it-qat-oQ4-fp16",
    },
    "optiq_4bit": {
        "model_id": "mlx-community/gemma-4-12B-it-qat-OptiQ-4bit",
        "artifact_path": "/Users/jrazz/.cache/huggingface/hub/models--mlx-community--gemma-4-12B-it-qat-OptiQ-4bit",
    },
}

CELL_FIELDS = frozenset({
    "cell_id", "quant", "server", "base_url", "model_id", "artifact_path",
    "start_command", "stop_command", "health_path", "notes",
})

CAMPAIGN_FIELDS = frozenset({
    "campaign_id", "suite_path", "results_root", "memory_floor_percent",
    "ready_timeout_seconds", "request_timeout_seconds", "on_cell_failure",
    "ports", "cells",
})

SUITE_FIELDS = frozenset({
    "schema_version", "suite_id", "revision", "temperature", "streaming", "workloads",
})


class MatrixError(RuntimeError):
    pass


def _validate_loopback_base_url(base_url: str) -> None:
    if not base_url.startswith("http://127.0.0.1:") or not base_url.endswith("/v1"):
        raise MatrixError("base_url must be a loopback /v1 endpoint")


def _validate_server_base_url(server: str, base_url: str) -> None:
    expected = f"http://127.0.0.1:{SERVER_PORTS[server]}/v1"
    if base_url != expected:
        raise MatrixError("base_url must match server port mapping")


def _validate_quant_artifact(quant: str, model_id: str, artifact_path: str) -> None:
    control = QUANT_CONTROL_ARTIFACTS[quant]
    if model_id != control["model_id"] or artifact_path != control["artifact_path"]:
        raise MatrixError("model_id and artifact_path must match quant control artifact")


def _require_exact_fields(data: dict[str, Any], expected: frozenset[str], label: str) -> None:
    if set(data) != expected:
        raise MatrixError(f"{label} fields are invalid")


def _command_tuple(value: Any, label: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(isinstance(part, str) for part in value):
        raise MatrixError(f"{label} must be a string array")
    return tuple(value)


def _resolve_repo_path(path: Path | str, base: Path = REPOSITORY_ROOT) -> Path:
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate
    return (base / candidate).resolve()


@dataclass(frozen=True)
class Cell:
    cell_id: str
    quant: str
    server: str
    base_url: str
    model_id: str
    artifact_path: str
    start_command: tuple[str, ...]
    stop_command: tuple[str, ...]
    health_path: str
    notes: str

    def __post_init__(self) -> None:
        _validate_loopback_base_url(self.base_url)
        if self.quant not in ALLOWED_QUANTS:
            raise MatrixError("quant is invalid")
        if self.server not in ALLOWED_SERVERS:
            raise MatrixError("server is invalid")
        _validate_server_base_url(self.server, self.base_url)
        _validate_quant_artifact(self.quant, self.model_id, self.artifact_path)
        if not self.start_command:
            raise MatrixError("start_command must not be empty")

    @classmethod
    def load(cls, path: Path) -> Cell:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise MatrixError("cell must be a JSON object")
        _require_exact_fields(data, CELL_FIELDS, "cell")
        expected_cell_id = f"{data['quant']}__{data['server']}"
        if data["cell_id"] != expected_cell_id:
            raise MatrixError("cell_id must match quant__server")
        return cls(
            cell_id=str(data["cell_id"]),
            quant=str(data["quant"]),
            server=str(data["server"]),
            base_url=str(data["base_url"]),
            model_id=str(data["model_id"]),
            artifact_path=str(data["artifact_path"]),
            start_command=_command_tuple(data["start_command"], "start_command"),
            stop_command=_command_tuple(data["stop_command"], "stop_command"),
            health_path=str(data["health_path"]),
            notes=str(data["notes"]),
        )


@dataclass(frozen=True)
class Workload:
    workload_id: str
    prompt: str
    max_tokens: int
    response_contract: str


@dataclass(frozen=True)
class MatrixSuite:
    suite_id: str
    revision: str
    workloads: tuple[Workload, ...]

    @classmethod
    def load(cls, path: Path) -> MatrixSuite:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise MatrixError("suite must be a JSON object")
        _require_exact_fields(data, SUITE_FIELDS, "suite")
        if data["schema_version"] != "1.0.0":
            raise MatrixError("suite schema_version is invalid")
        if data["temperature"] != 0 or data["streaming"] is not True:
            raise MatrixError("suite must be deterministic and streaming")
        items = data["workloads"]
        if not isinstance(items, list) or len(items) != 3:
            raise MatrixError("suite must contain exactly three workloads")
        workloads = tuple(
            Workload(
                str(item["workload_id"]),
                str(item["prompt"]),
                int(item["max_tokens"]),
                str(item["response_contract"]),
            )
            for item in items
        )
        if len({item.workload_id for item in workloads}) != 3:
            raise MatrixError("workload IDs must be unique")
        return cls(str(data["suite_id"]), str(data["revision"]), workloads)


@dataclass(frozen=True)
class Campaign:
    campaign_id: str
    suite_path: Path
    results_root: Path
    memory_floor_percent: int
    ready_timeout_seconds: int
    request_timeout_seconds: int
    on_cell_failure: str
    ports: dict[str, int]
    cell_paths: tuple[Path, ...]

    @classmethod
    def load(cls, path: Path) -> Campaign:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise MatrixError("campaign must be a JSON object")
        _require_exact_fields(data, CAMPAIGN_FIELDS, "campaign")
        if data["campaign_id"] != "gemma-4-12b-qat-3x3":
            raise MatrixError("campaign_id is invalid")
        if data["on_cell_failure"] != "continue":
            raise MatrixError("on_cell_failure is invalid")
        ports = data["ports"]
        if not isinstance(ports, dict) or set(ports) != ALLOWED_SERVERS:
            raise MatrixError("ports are invalid")
        normalized_ports = {str(key): int(ports[key]) for key in sorted(ports)}
        if normalized_ports != EXPECTED_CAMPAIGN_PORTS:
            raise MatrixError("ports values are invalid")
        cells = data["cells"]
        if not isinstance(cells, list) or len(cells) != 9:
            raise MatrixError("campaign must list exactly nine cells")
        cell_paths = tuple(_resolve_repo_path(str(item)) for item in cells)
        return cls(
            str(data["campaign_id"]),
            _resolve_repo_path(str(data["suite_path"])),
            _resolve_repo_path(str(data["results_root"])),
            int(data["memory_floor_percent"]),
            int(data["ready_timeout_seconds"]),
            int(data["request_timeout_seconds"]),
            str(data["on_cell_failure"]),
            normalized_ports,
            cell_paths,
        )
