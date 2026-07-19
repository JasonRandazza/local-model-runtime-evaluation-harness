"""Per-cell matrix measurement via LoopbackTransport."""

from __future__ import annotations

import math
import statistics
import threading
from dataclasses import asdict, dataclass
from typing import Literal

from .credentials import Credential
from .matrix_config import Cell, MatrixSuite, Workload
from .measurement import validate_response_contract
from .resources import HostResourceProbe
from .transport import LoopbackTransport, TransportError


MODES = {
    "screen": {"warmup": 1, "measured": 3},
    "finalist": {"warmup": 1, "measured": 5},
}


class MatrixMeasureError(RuntimeError):
    code = "matrix_measure_failed"


@dataclass(frozen=True)
class Observation:
    workload_id: str
    repetition: int
    measured: bool
    success: bool
    total_seconds: float | None
    finish_reason: str | None
    response_contract_valid: bool
    response_contract_status: str
    completion_tokens: int | None
    visible_output_tokens: int | None
    token_accounting_status: str | None
    ttft_seconds: float | None
    streaming_semantics: str | None
    error: str | None

    def as_json(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class CellResult:
    status: Literal["PASS", "FAIL", "N/A"]
    na_reason: str | None
    observations: tuple[Observation, ...]
    summary: dict[str, object]
    memory_free_percent_before: int | None
    memory_free_percent_after: int | None


def _memory_percent(probe: HostResourceProbe | None) -> int | None:
    if probe is None:
        return None
    return probe.free_memory_percent()


def _median(values: list[float]) -> float | None:
    return None if not values else float(statistics.median(values))


def _p95(values: list[float]) -> float | None:
    if len(values) < 2:
        return None
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, int(math.ceil(0.95 * len(ordered)) - 1)))
    return float(ordered[index])


def summarize(
    observations: tuple[Observation, ...],
    *,
    include_p95: bool = False,
) -> dict[str, object]:
    measured = [item for item in observations if item.measured]
    by_workload: dict[str, object] = {}
    for workload_id in sorted({item.workload_id for item in measured}):
        rows = [item for item in measured if item.workload_id == workload_id]
        times = [item.total_seconds for item in rows if item.success and item.total_seconds is not None]
        contracts = sum(1 for item in rows if item.response_contract_valid)
        stats: dict[str, object] = {
            "measured_count": len(rows),
            "success_count": sum(1 for item in rows if item.success),
            "contract_pass_count": contracts,
            "median_total_seconds": _median(times),
            "min_total_seconds": min(times) if times else None,
            "max_total_seconds": max(times) if times else None,
        }
        if include_p95:
            stats["p95_total_seconds"] = _p95(times)
        by_workload[workload_id] = stats
    overall_times = [
        item.total_seconds for item in measured
        if item.success and item.total_seconds is not None
    ]
    summary: dict[str, object] = {
        "measured_count": len(measured),
        "success_count": sum(1 for item in measured if item.success),
        "contract_pass_count": sum(1 for item in measured if item.response_contract_valid),
        "median_total_seconds": _median(overall_times),
        "min_total_seconds": min(overall_times) if overall_times else None,
        "max_total_seconds": max(overall_times) if overall_times else None,
        "by_workload": by_workload,
    }
    if include_p95:
        summary["p95_total_seconds"] = _p95(overall_times)
    return summary


def _run_one(
    transport: LoopbackTransport,
    cell: Cell,
    workload: Workload,
    repetition: int,
    measured: bool,
    cancel: threading.Event,
    credential: Credential | None,
) -> Observation:
    if cancel.is_set():
        raise MatrixMeasureError("cancelled before request")
    try:
        result = transport.chat(
            cell.base_url, cell.model_id, workload.prompt, workload.max_tokens,
            credential, cancel,
        )
    except TransportError as error:
        return Observation(
            workload.workload_id, repetition, measured, False, None, None,
            False, "TRANSPORT_FAILED", None, None, None, None, None, str(error),
        )
    content_span = max(0.0, result.last_content_seconds - result.ttft_seconds)
    streaming = (
        "incremental"
        if result.content_event_count >= 2 and content_span >= 0.01
        else "buffered"
    )
    ttft = None if streaming != "incremental" else result.ttft_seconds
    valid, status = validate_response_contract(workload.response_contract, result.content)
    return Observation(
        workload.workload_id, repetition, measured, True, result.total_seconds,
        result.finish_reason, valid, status, result.completion_tokens,
        result.visible_output_tokens, result.token_accounting_status, ttft, streaming, None,
    )


def _cell_status(observations: tuple[Observation, ...]) -> Literal["PASS", "FAIL"]:
    measured = [item for item in observations if item.measured]
    if any(not item.success for item in measured):
        return "FAIL"
    if any(not item.response_contract_valid for item in measured):
        return "FAIL"
    return "PASS"


def measure_cell(
    cell: Cell,
    suite: MatrixSuite,
    mode: str,
    transport: LoopbackTransport,
    probe: HostResourceProbe | None,
    cancel: threading.Event,
    credential: Credential | None = None,
) -> CellResult:
    if mode not in MODES:
        raise MatrixMeasureError(f"unknown mode {mode!r}")
    counts = MODES[mode]
    memory_before = _memory_percent(probe)

    try:
        models = transport.list_models(cell.base_url, credential)
    except TransportError as error:
        memory_after = _memory_percent(probe)
        return CellResult(
            status="N/A",
            na_reason=f"model inventory failed: {error}",
            observations=(),
            summary=summarize(()),
            memory_free_percent_before=memory_before,
            memory_free_percent_after=memory_after,
        )

    if cell.model_id not in models:
        memory_after = _memory_percent(probe)
        return CellResult(
            status="N/A",
            na_reason=(
                f"exact model id {cell.model_id!r} not present; inventory={list(models)}"
            ),
            observations=(),
            summary=summarize(()),
            memory_free_percent_before=memory_before,
            memory_free_percent_after=memory_after,
        )

    observations: list[Observation] = []
    for workload in suite.workloads:
        for repetition in range(counts["warmup"]):
            if cancel.is_set():
                break
            observations.append(
                _run_one(transport, cell, workload, repetition, False, cancel, credential)
            )
        if cancel.is_set():
            break
        for repetition in range(1, counts["measured"] + 1):
            if cancel.is_set():
                break
            observations.append(
                _run_one(transport, cell, workload, repetition, True, cancel, credential)
            )
        if cancel.is_set():
            break

    obs_tuple = tuple(observations)
    memory_after = _memory_percent(probe)
    return CellResult(
        status=_cell_status(obs_tuple),
        na_reason=None,
        observations=obs_tuple,
        summary=summarize(obs_tuple, include_p95=(mode == "finalist")),
        memory_free_percent_before=memory_before,
        memory_free_percent_after=memory_after,
    )
