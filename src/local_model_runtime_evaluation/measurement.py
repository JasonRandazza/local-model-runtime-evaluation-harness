from __future__ import annotations

import json
import statistics
import threading
from collections import Counter
from dataclasses import asdict, dataclass
from typing import Callable

from .benchmark_suite import BenchmarkSuite, ScheduledRequest, Workload
from .transport import TransportResult


class MeasurementError(RuntimeError):
    code = "measurement_invalid"


STREAMING_MIN_CONTENT_SPAN_SECONDS = 0.01


@dataclass(frozen=True)
class Sample:
    workload_id: str
    route: str
    repetition: int
    measured: bool
    success: bool
    ttft_seconds: float
    total_seconds: float
    completion_tokens: int | None
    finish_reason: str | None
    output_sha256: str
    content_event_count: int
    content_span_seconds: float
    streaming_semantics: str
    response_contract_valid: bool
    response_contract_status: str
    reasoning_tokens: int | None
    visible_output_tokens: int | None
    token_accounting_status: str

    def as_json(self) -> dict[str, object]:
        return asdict(self)


def validate_response_contract(contract: str, content: str) -> tuple[bool, str]:
    if contract == "text":
        return (True, "PASS") if content.strip() else (False, "EMPTY_TEXT")
    try:
        payload = json.loads(content)
    except (json.JSONDecodeError, TypeError):
        return False, "INVALID_JSON"
    if contract == "json":
        return (True, "PASS") if isinstance(payload, (dict, list)) else (False, "JSON_ROOT_INVALID")
    if contract == "status-tool-json":
        expected = {
            "name": "status",
            "arguments": {"run_id": "stage1-test", "include_details": False},
        }
        return (True, "PASS") if payload == expected else (False, "JSON_CONTRACT_MISMATCH")
    return False, "UNSUPPORTED_CONTRACT"


def run_schedule(
    suite: BenchmarkSuite,
    repetitions: int,
    execute: Callable[[ScheduledRequest, Workload], TransportResult],
    cancel: threading.Event,
) -> tuple[Sample, ...]:
    workloads = {item.workload_id: item for item in suite.workloads}
    samples: list[Sample] = []
    for request in suite.schedule(repetitions):
        if cancel.is_set():
            raise MeasurementError("measurement cancelled before next request")
        workload = workloads[request.workload_id]
        result = execute(request, workload)
        content_span = max(0.0, result.last_content_seconds - result.ttft_seconds)
        streaming_semantics = (
            "incremental"
            if result.content_event_count >= 2 and content_span >= STREAMING_MIN_CONTENT_SPAN_SECONDS
            else "buffered"
        )
        contract_valid, contract_status = validate_response_contract(
            workload.response_contract, result.content
        )
        samples.append(Sample(
            request.workload_id, request.route, request.repetition, request.measured,
            True, result.ttft_seconds, result.total_seconds, result.completion_tokens,
            result.finish_reason, result.content_sha256, result.content_event_count,
            content_span, streaming_semantics, contract_valid, contract_status,
            result.reasoning_tokens, result.visible_output_tokens,
            result.token_accounting_status,
        ))
    return tuple(samples)


def _stats(samples: list[Sample], token_counter: Callable[[Sample], int] | None) -> dict[str, object]:
    if not samples or any(not item.success for item in samples):
        raise MeasurementError("cohort is incomplete")
    token_counts: list[int] = []
    for sample in samples:
        if sample.completion_tokens is None:
            if token_counter is None:
                raise MeasurementError("exact completion-token accounting is unavailable")
            token_counts.append(token_counter(sample))
        else:
            token_counts.append(sample.completion_tokens)
    totals = [item.total_seconds for item in samples]
    streaming_comparable = all(item.streaming_semantics == "incremental" for item in samples)
    token_accounting_comparable = all(
        item.token_accounting_status == "EXACT_VISIBLE"
        and item.visible_output_tokens is not None
        for item in samples
    )
    ttft_status = "COMPARABLE" if streaming_comparable else "INCOMPARABLE_BUFFERED_STREAM"
    if not streaming_comparable:
        decode_status = "INCOMPARABLE_BUFFERED_STREAM"
    elif not token_accounting_comparable:
        decode_status = "INCOMPARABLE_TOKEN_ACCOUNTING"
    else:
        decode_status = "COMPARABLE"
    ttfts = [item.ttft_seconds for item in samples] if streaming_comparable else []
    decode_rates = [] if decode_status != "COMPARABLE" else [
        item.visible_output_tokens / item.content_span_seconds
        for item in samples
        if item.visible_output_tokens is not None and item.content_span_seconds > 0
    ]
    reasoning_counts = [item.reasoning_tokens for item in samples if item.reasoning_tokens is not None]
    visible_counts = [
        item.visible_output_tokens for item in samples if item.visible_output_tokens is not None
    ]
    contract_valid = sum(item.response_contract_valid for item in samples)
    return {
        "sample_count": len(samples),
        "streaming_metric_status": ttft_status,
        "ttft_metric_status": ttft_status,
        "decode_metric_status": decode_status,
        "token_accounting_status": (
            "EXACT_VISIBLE" if token_accounting_comparable
            else "INCOMPARABLE_TOKEN_ACCOUNTING"
        ),
        "streaming_semantics_counts": dict(sorted(Counter(
            item.streaming_semantics for item in samples
        ).items())),
        "ttft_seconds_median": statistics.median(ttfts) if ttfts else None,
        "total_seconds_median": statistics.median(totals),
        "total_seconds_min": min(totals),
        "total_seconds_max": max(totals),
        "total_seconds_pstdev": statistics.pstdev(totals),
        "decode_tokens_per_second_median": statistics.median(decode_rates) if decode_rates else None,
        "completion_tokens_median": statistics.median(token_counts),
        "reasoning_tokens_median": (
            statistics.median(reasoning_counts) if len(reasoning_counts) == len(samples) else None
        ),
        "visible_output_tokens_median": (
            statistics.median(visible_counts) if len(visible_counts) == len(samples) else None
        ),
        "response_contract_valid_count": contract_valid,
        "response_contract_invalid_count": len(samples) - contract_valid,
        "finish_reason_counts": dict(sorted(Counter(
            item.finish_reason or "missing" for item in samples
        ).items())),
        "p95": None if len(samples) < 20 else sorted(totals)[int(len(totals) * 0.95) - 1],
    }


def _paired_total_seconds(samples: list[Sample]) -> dict[str, object]:
    pairs: dict[tuple[str, int], dict[str, Sample]] = {}
    for sample in samples:
        key = (sample.workload_id, sample.repetition)
        route_samples = pairs.setdefault(key, {})
        if sample.route in route_samples:
            raise MeasurementError("paired cohort contains a duplicate route")
        route_samples[sample.route] = sample
    deltas: list[float] = []
    percentages: list[float] = []
    for routes in pairs.values():
        if set(routes) != {"direct", "routed"}:
            raise MeasurementError("paired cohort is incomplete")
        direct = routes["direct"].total_seconds
        routed = routes["routed"].total_seconds
        if direct <= 0:
            raise MeasurementError("paired direct duration is invalid")
        delta = routed - direct
        deltas.append(delta)
        percentages.append((delta / direct) * 100)
    if not deltas:
        raise MeasurementError("paired cohort is empty")
    return {
        "pair_count": len(deltas),
        "delta_seconds_median": statistics.median(deltas),
        "delta_seconds_min": min(deltas),
        "delta_seconds_max": max(deltas),
        "delta_seconds_pstdev": statistics.pstdev(deltas),
        "delta_percent_median": statistics.median(percentages),
        "routed_slower_pair_count": sum(delta > 0 for delta in deltas),
        "direct_slower_pair_count": sum(delta < 0 for delta in deltas),
        "tie_pair_count": sum(delta == 0 for delta in deltas),
    }


def aggregate(
    samples: list[Sample] | tuple[Sample, ...], repetitions: int,
    token_counter: Callable[[Sample], int] | None = None,
) -> dict[str, object]:
    measured = [item for item in samples if item.measured]
    warmups = [item for item in samples if not item.measured]
    workload_ids = sorted({item.workload_id for item in measured})
    workloads: dict[str, object] = {}
    for workload_id in workload_ids:
        direct = [item for item in measured if item.workload_id == workload_id and item.route == "direct"]
        routed = [item for item in measured if item.workload_id == workload_id and item.route == "routed"]
        if len(direct) != repetitions or len(routed) != repetitions:
            raise MeasurementError("measured cohort does not match approved repetition count")
        direct_stats = _stats(direct, token_counter)
        routed_stats = _stats(routed, token_counter)
        direct_median = float(direct_stats["total_seconds_median"])
        routed_median = float(routed_stats["total_seconds_median"])
        workloads[workload_id] = {
            "direct": direct_stats,
            "routed": routed_stats,
            "total_seconds_delta": routed_median - direct_median,
            "total_seconds_delta_percent": (
                ((routed_median - direct_median) / direct_median) * 100
            ),
            "paired_total_seconds": _paired_total_seconds([*direct, *routed]),
        }
    direct_all = [item for item in measured if item.route == "direct"]
    routed_all = [item for item in measured if item.route == "routed"]
    direct_stats = _stats(direct_all, token_counter)
    routed_stats = _stats(routed_all, token_counter)
    direct_median = float(direct_stats["total_seconds_median"])
    routed_median = float(routed_stats["total_seconds_median"])
    streaming_comparable = (
        direct_stats["ttft_metric_status"] == "COMPARABLE"
        and routed_stats["ttft_metric_status"] == "COMPARABLE"
    )
    token_accounting_comparable = (
        direct_stats["token_accounting_status"] == "EXACT_VISIBLE"
        and routed_stats["token_accounting_status"] == "EXACT_VISIBLE"
    )
    if not streaming_comparable:
        decode_status = "INCOMPARABLE_BUFFERED_STREAM"
    elif not token_accounting_comparable:
        decode_status = "INCOMPARABLE_TOKEN_ACCOUNTING"
    else:
        decode_status = "COMPARABLE"
    contract_valid_count = sum(item.response_contract_valid for item in measured)
    finish_reason_counts = dict(sorted(Counter(
        item.finish_reason or "missing" for item in measured
    ).items()))
    completion_status = (
        "TOKEN_CAPPED" if "length" in finish_reason_counts
        else "NATURAL" if set(finish_reason_counts) == {"stop"}
        else "MIXED"
    )
    return {
        "measured_sample_count": len(measured), "warmup_sample_count": len(warmups),
        "workloads": workloads,
        "overall": {
            "direct": direct_stats, "routed": routed_stats,
            "streaming_metric_status": (
                "COMPARABLE" if streaming_comparable else "INCOMPARABLE_BUFFERED_STREAM"
            ),
            "ttft_metric_status": (
                "COMPARABLE" if streaming_comparable else "INCOMPARABLE_BUFFERED_STREAM"
            ),
            "decode_metric_status": decode_status,
            "token_accounting_status": (
                "EXACT_VISIBLE" if token_accounting_comparable
                else "INCOMPARABLE_TOKEN_ACCOUNTING"
            ),
            "response_contract_validation": (
                "PASS" if contract_valid_count == len(measured) else "FAIL"
            ),
            "response_contract_valid_count": contract_valid_count,
            "response_contract_invalid_count": len(measured) - contract_valid_count,
            "completion_status": completion_status,
            "finish_reason_counts": finish_reason_counts,
            "total_seconds_delta": routed_median - direct_median,
            "total_seconds_delta_percent": ((routed_median - direct_median) / direct_median) * 100,
            "paired_total_seconds": _paired_total_seconds(measured),
        },
    }
