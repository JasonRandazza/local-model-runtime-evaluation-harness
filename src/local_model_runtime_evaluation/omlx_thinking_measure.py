from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

THINKING_PREFLIGHT_MAX_TOKENS = 512

ThinkingOutcome = Literal[
    "ok",
    "transport_failed",
    "empty_visible",
    "contract_failed",
    "token_capped",
]


@dataclass(frozen=True)
class ThinkingMetricSample:
    outcome: ThinkingOutcome
    streaming_semantics: str
    token_accounting_status: str
    visible_output_tokens: int | None
    content_span_seconds: float
    finish_reason: str | None = None


def preflight_budget_ok(max_tokens: int) -> bool:
    return max_tokens >= THINKING_PREFLIGHT_MAX_TOKENS


def classify_thinking_outcome(
    *,
    transport_ok: bool,
    visible_text: str,
    finish_reason: str | None,
    contract_ok: bool,
) -> ThinkingOutcome:
    if not transport_ok:
        return "transport_failed"
    if not visible_text.strip():
        return "empty_visible"
    if finish_reason == "length":
        return "token_capped"
    if not contract_ok:
        return "contract_failed"
    return "ok"


def qualify_thinking_metrics(
    samples: tuple[ThinkingMetricSample, ...],
) -> dict[str, str]:
    """Return ttft/decode qualification labels for reasoning-heavy samples."""
    if any(
        item.outcome == "token_capped" or item.finish_reason == "length"
        for item in samples
    ):
        return {
            "ttft": "SUPPRESSED_TOKEN_CAPPED",
            "decode": "SUPPRESSED_TOKEN_CAPPED",
        }
    measured = [item for item in samples if item.outcome == "ok"]
    if not measured:
        return {
            "ttft": "SUPPRESSED_NO_OK_SAMPLES",
            "decode": "SUPPRESSED_NO_OK_SAMPLES",
        }
    if not all(item.streaming_semantics == "incremental" for item in measured):
        return {
            "ttft": "SUPPRESSED_BUFFERED_DELIVERY",
            "decode": "SUPPRESSED_BUFFERED_DELIVERY",
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
