from __future__ import annotations

from typing import Literal

THINKING_PREFLIGHT_MAX_TOKENS = 512

ThinkingOutcome = Literal[
    "ok",
    "transport_failed",
    "empty_visible",
    "contract_failed",
    "token_capped",
]


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
