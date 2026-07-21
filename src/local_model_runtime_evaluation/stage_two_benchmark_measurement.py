from __future__ import annotations

from typing import Protocol

from .stage_two import StageTwoError
from .stage_two_smoke_measurement import _metric_qualification


class BenchmarkObservation(Protocol):
    sequence: int
    workload_id: str
    route: str
    measured: bool
    repetition: int
    http_status: int
    stream_valid: bool
    total_seconds: float
    ttft_seconds: float | None
    streaming_semantics: str
    token_accounting_status: str
    visible_output_tokens: int | None
    content_span_seconds: float
    response_contract_valid: bool
    finish_reason: str | None
    output_sha256: str


_APPROVED_WORKLOADS = ("short-chat", "structured-tool-json")
_APPROVED_ROUTES = frozenset({"direct", "routed"})
_WARMUP_REPETITIONS = frozenset(range(3))
_MEASURED_REPETITIONS = frozenset(range(15))


def _evidence_error(message: str) -> None:
    raise StageTwoError("evidence_incomplete", message)


def _median(values: list[float]) -> float:
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / 2


def _decode_tokens_per_second(item: BenchmarkObservation) -> float | None:
    if item.streaming_semantics != "incremental":
        return None
    if item.token_accounting_status != "EXACT_VISIBLE":
        return None
    if item.visible_output_tokens is None or item.visible_output_tokens <= 0:
        return None
    if item.content_span_seconds <= 0:
        return None
    return float(item.visible_output_tokens) / float(item.content_span_seconds)


def _validate_cohort(observations: tuple[BenchmarkObservation, ...]) -> None:
    if len(observations) != 72:
        _evidence_error("Stage 2B-2 requires exactly seventy-two observations")
    if {item.sequence for item in observations} != set(range(1, 73)):
        _evidence_error("Stage 2B-2 observation sequences are incomplete or duplicated")
    if any(item.route not in _APPROVED_ROUTES for item in observations):
        _evidence_error("Stage 2B-2 observations contain an unapproved route")
    if sum(item.measured for item in observations) != 60:
        _evidence_error("Stage 2B-2 requires sixty measured observations")
    if sum(not item.measured for item in observations) != 12:
        _evidence_error("Stage 2B-2 requires twelve warmup observations")

    for workload_id in _APPROVED_WORKLOADS:
        items = [item for item in observations if item.workload_id == workload_id]
        if len(items) != 36:
            _evidence_error("Stage 2B-2 workload evidence is incomplete or duplicated")
        for route in _APPROVED_ROUTES:
            warmups = [item for item in items if item.route == route and not item.measured]
            measured = [item for item in items if item.route == route and item.measured]
            if len(warmups) != 3:
                _evidence_error("Stage 2B-2 warmup route evidence is incomplete or duplicated")
            if len(measured) != 15:
                _evidence_error("Stage 2B-2 measured route evidence is incomplete or duplicated")
            if {item.repetition for item in warmups} != _WARMUP_REPETITIONS:
                _evidence_error("Stage 2B-2 warmup repetitions are incomplete or duplicated")
            if {item.repetition for item in measured} != _MEASURED_REPETITIONS:
                _evidence_error("Stage 2B-2 measured repetitions are incomplete or duplicated")


def _workload_hash_pairs_match(
    observations: tuple[BenchmarkObservation, ...],
    workload_id: str,
) -> bool:
    measured = [item for item in observations if item.workload_id == workload_id and item.measured]
    by_repetition: dict[int, dict[str, BenchmarkObservation]] = {}
    for item in measured:
        routes = by_repetition.setdefault(item.repetition, {})
        routes[item.route] = item
    for routes in by_repetition.values():
        if set(routes) != _APPROVED_ROUTES:
            return False
        if routes["direct"].output_sha256 != routes["routed"].output_sha256:
            return False
    return True


def _cell_summary(
    cell: list[BenchmarkObservation],
    *,
    output_hashes_match: bool,
) -> dict[str, object]:
    totals = [item.total_seconds for item in cell]
    finish_reason_counts = {
        reason: sum(1 for item in cell if (item.finish_reason or "missing") == reason)
        for reason in sorted({item.finish_reason or "missing" for item in cell})
    }
    qualification = _metric_qualification(
        cell,
        output_hashes_match=output_hashes_match,
        token_capped="length" in finish_reason_counts,
    )
    summary: dict[str, object] = {
        "workload_id": cell[0].workload_id,
        "route": cell[0].route,
        "measured_count": len(cell),
        "median_total_seconds": _median(totals),
        "ttft_qualification": qualification["ttft"],
        "decode_qualification": qualification["decode"],
        "median_ttft_seconds": None,
        "median_decode_tokens_per_second": None,
    }
    if qualification["ttft"] == "QUALIFIED_INCREMENTAL_DELIVERY":
        ttfts = [item.ttft_seconds for item in cell if item.ttft_seconds is not None]
        summary["median_ttft_seconds"] = _median(ttfts)
    if qualification["decode"] == "QUALIFIED_EXACT_VISIBLE_TOKENS":
        decode_rates = [rate for item in cell if (rate := _decode_tokens_per_second(item)) is not None]
        summary["median_decode_tokens_per_second"] = _median(decode_rates)
    return summary


def summarize_benchmark(
    observations: tuple[BenchmarkObservation, ...],
) -> dict[str, object]:
    _validate_cohort(observations)
    measured = [item for item in observations if item.measured]
    workload_order = sorted(
        _APPROVED_WORKLOADS,
        key=lambda workload_id: min(
            item.sequence for item in observations if item.workload_id == workload_id
        ),
    )
    route_overhead_summary: list[dict[str, object]] = []
    route_overhead_deltas: list[dict[str, object]] = []
    for workload_id in workload_order:
        hashes_match = _workload_hash_pairs_match(observations, workload_id)
        cell_totals: dict[str, float] = {}
        for route in ("direct", "routed"):
            cell = [
                item
                for item in measured
                if item.workload_id == workload_id and item.route == route
            ]
            summary = _cell_summary(cell, output_hashes_match=hashes_match)
            route_overhead_summary.append(summary)
            cell_totals[route] = summary["median_total_seconds"]  # type: ignore[assignment]
        route_overhead_deltas.append({
            "workload_id": workload_id,
            "direct_median_total_seconds": cell_totals["direct"],
            "routed_median_total_seconds": cell_totals["routed"],
            "routed_minus_direct_total_seconds": cell_totals["routed"] - cell_totals["direct"],
        })

    return {
        "total_requests": len(observations),
        "excluded_warmups": len(observations) - len(measured),
        "measured_requests": len(measured),
        "route_overhead_summary": route_overhead_summary,
        "route_overhead_deltas": route_overhead_deltas,
        "inference_path_acceptance": (
            "PASS"
            if all(item.http_status == 200 and item.stream_valid for item in observations)
            else "FAIL"
        ),
        "behavioral_contract_acceptance": (
            "PASS" if all(item.response_contract_valid for item in measured) else "FAIL"
        ),
    }
