from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING

from .stage_two import StageTwoError
from .transport import TransportResult

if TYPE_CHECKING:
    from .stage_two_smoke_suite import SmokeRequest, SmokeWorkload


INCREMENTAL_CONTENT_SPAN_SECONDS = 0.01


@dataclass(frozen=True)
class SmokeObservation:
    sequence: int
    workload_id: str
    route: str
    measured: bool
    repetition: int
    http_status: int
    stream_valid: bool
    total_seconds: float
    ttft_seconds: float | None
    completion_tokens: int | None
    reasoning_tokens: int | None
    visible_output_tokens: int | None
    token_accounting_status: str
    content_event_count: int
    content_span_seconds: float
    streaming_semantics: str
    finish_reason: str | None
    response_contract_valid: bool
    response_contract_status: str
    output_sha256: str

    @classmethod
    def from_result(
        cls,
        request: SmokeRequest,
        workload: SmokeWorkload,
        result: TransportResult,
        contract_result: tuple[bool, str],
    ) -> SmokeObservation:
        content_span = max(0.0, result.last_content_seconds - result.ttft_seconds)
        incremental = (
            result.content_event_count >= 2
            and content_span >= INCREMENTAL_CONTENT_SPAN_SECONDS
        )
        contract_valid, contract_status = contract_result
        return cls(
            sequence=request.sequence,
            workload_id=workload.workload_id,
            route=request.route,
            measured=request.measured,
            repetition=request.repetition,
            http_status=result.http_status,
            stream_valid=result.stream_valid,
            total_seconds=result.total_seconds,
            ttft_seconds=result.ttft_seconds if incremental else None,
            completion_tokens=result.completion_tokens,
            reasoning_tokens=result.reasoning_tokens,
            visible_output_tokens=result.visible_output_tokens,
            token_accounting_status=result.token_accounting_status,
            content_event_count=result.content_event_count,
            content_span_seconds=content_span,
            streaming_semantics="incremental" if incremental else "buffered",
            finish_reason=result.finish_reason,
            response_contract_valid=contract_valid,
            response_contract_status=contract_status,
            output_sha256=result.content_sha256,
        )

    def as_json(self) -> dict[str, object]:
        return asdict(self)


def _evidence_error(message: str) -> None:
    raise StageTwoError("evidence_incomplete", message)


def _validate_cohort(observations: tuple[SmokeObservation, ...]) -> None:
    if len(observations) != 8:
        _evidence_error("Stage 2B-1 requires exactly eight observations")
    if {item.sequence for item in observations} != set(range(1, 9)):
        _evidence_error("Stage 2B-1 observation sequences are incomplete or duplicated")
    if any(item.route not in {"direct", "routed"} for item in observations):
        _evidence_error("Stage 2B-1 observations contain an unapproved route")
    if sum(item.measured for item in observations) != 4:
        _evidence_error("Stage 2B-1 requires four measured observations")
    if sum(not item.measured for item in observations) != 4:
        _evidence_error("Stage 2B-1 requires four warmup observations")
    if any(item.repetition != 1 for item in observations if item.measured):
        _evidence_error("Stage 2B-1 measured observations must use repetition one")
    if any(item.repetition != 0 for item in observations if not item.measured):
        _evidence_error("Stage 2B-1 warmups must use repetition zero")
    if {item.route for item in observations if item.measured} != {"direct", "routed"}:
        _evidence_error("Stage 2B-1 measured routes are incomplete")
    if {item.route for item in observations if not item.measured} != {"direct", "routed"}:
        _evidence_error("Stage 2B-1 warmup routes are incomplete")

    for workload_id in {item.workload_id for item in observations}:
        items = [item for item in observations if item.workload_id == workload_id]
        if len(items) != 4:
            _evidence_error("Stage 2B-1 workload evidence is incomplete or duplicated")
        for measured in (False, True):
            routes = [item.route for item in items if item.measured is measured]
            if sorted(routes) != ["direct", "routed"]:
                _evidence_error("Stage 2B-1 workload route evidence is incomplete or duplicated")


def _measured_pair_deltas(
    observations: tuple[SmokeObservation, ...],
) -> tuple[list[dict[str, object]], list[bool]]:
    measured = [item for item in observations if item.measured]
    workload_ids = sorted(
        {item.workload_id for item in measured},
        key=lambda workload_id: min(item.sequence for item in measured if item.workload_id == workload_id),
    )
    deltas: list[dict[str, object]] = []
    hashes_match: list[bool] = []
    for pair, workload_id in enumerate(workload_ids, start=1):
        items = [item for item in measured if item.workload_id == workload_id]
        direct = next(item for item in items if item.route == "direct")
        routed = next(item for item in items if item.route == "routed")
        deltas.append({
            "pair": pair,
            "workload_id": workload_id,
            "direct_sequence": direct.sequence,
            "routed_sequence": routed.sequence,
            "direct_seconds": direct.total_seconds,
            "routed_seconds": routed.total_seconds,
            "routed_minus_direct_seconds": routed.total_seconds - direct.total_seconds,
        })
        hashes_match.append(direct.output_sha256 == routed.output_sha256)
    return deltas, hashes_match


def _metric_qualification(
    measured: list[SmokeObservation],
    *,
    output_hashes_match: bool,
    token_capped: bool,
) -> dict[str, str]:
    all_incremental = all(item.streaming_semantics == "incremental" for item in measured)
    if not all_incremental:
        return {
            "ttft": "SUPPRESSED_BUFFERED_DELIVERY",
            "decode": "SUPPRESSED_BUFFERED_DELIVERY",
        }
    if not output_hashes_match:
        return {
            "ttft": "SUPPRESSED_OUTPUT_HASH_MISMATCH",
            "decode": "SUPPRESSED_OUTPUT_HASH_MISMATCH",
        }
    if token_capped:
        return {
            "ttft": "SUPPRESSED_TOKEN_CAPPED",
            "decode": "SUPPRESSED_TOKEN_CAPPED",
        }
    exact_visible = all(
        item.token_accounting_status == "EXACT_VISIBLE"
        and item.visible_output_tokens is not None
        and item.visible_output_tokens > 0
        and item.content_span_seconds > 0
        for item in measured
    )
    return {
        "ttft": "QUALIFIED_INCREMENTAL_DELIVERY",
        "decode": (
            "QUALIFIED_EXACT_VISIBLE_TOKENS"
            if exact_visible
            else "SUPPRESSED_AMBIGUOUS_TOKEN_ACCOUNTING"
        ),
    }


def summarize_smoke(observations: tuple[SmokeObservation, ...]) -> dict[str, object]:
    _validate_cohort(observations)
    measured = [item for item in observations if item.measured]
    direct = [item for item in observations if item.route == "direct"]
    routed = [item for item in observations if item.route == "routed"]
    pair_deltas, hashes_match = _measured_pair_deltas(observations)
    finish_reason_counts = dict(sorted(Counter(
        item.finish_reason or "missing" for item in measured
    ).items()))
    metric_qualification = _metric_qualification(
        measured,
        output_hashes_match=all(hashes_match),
        token_capped="length" in finish_reason_counts,
    )
    response_contract_counts = {
        "valid": sum(item.response_contract_valid for item in measured),
        "invalid": sum(not item.response_contract_valid for item in measured),
    }
    behavioral_findings: list[str] = []
    if not all(hashes_match):
        behavioral_findings.append("OUTPUT_HASH_MISMATCH")
    if "length" in finish_reason_counts:
        behavioral_findings.append("TOKEN_CAPPED")
    if any(item.streaming_semantics == "buffered" for item in measured):
        behavioral_findings.append("BUFFERED_DELIVERY")
    if any(
        item.token_accounting_status != "EXACT_VISIBLE"
        or item.visible_output_tokens is None
        or item.visible_output_tokens <= 0
        for item in measured
    ):
        behavioral_findings.append("AMBIGUOUS_TOKEN_ACCOUNTING")

    return {
        "total_requests": len(observations),
        "excluded_warmups": len(observations) - len(measured),
        "measured_requests": len(measured),
        "direct_observations": [item.as_json() for item in direct],
        "routed_observations": [item.as_json() for item in routed],
        "measured_pair_deltas": pair_deltas,
        "metric_qualification": metric_qualification,
        "response_contract_counts": response_contract_counts,
        "finish_reason_counts": finish_reason_counts,
        "output_hash_pair_status": "MATCH" if all(hashes_match) else "MISMATCH",
        "behavioral_findings": behavioral_findings,
        "inference_path_acceptance": (
            "PASS"
            if all(item.http_status == 200 and item.stream_valid for item in observations)
            else "FAIL"
        ),
        "behavioral_contract_acceptance": (
            "PASS" if response_contract_counts["invalid"] == 0 else "FAIL"
        ),
    }
