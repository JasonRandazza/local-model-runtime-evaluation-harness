from __future__ import annotations

import unittest

from local_model_runtime_evaluation.omlx_thinking_measure import (
    THINKING_PREFLIGHT_MAX_TOKENS,
    ThinkingMetricSample,
    classify_thinking_outcome,
    preflight_budget_ok,
    qualify_thinking_metrics,
)


class PreflightBudgetTest(unittest.TestCase):
    def test_floor_constant_is_512(self) -> None:
        self.assertEqual(THINKING_PREFLIGHT_MAX_TOKENS, 512)

    def test_rejects_budget_below_floor(self) -> None:
        self.assertFalse(preflight_budget_ok(511))

    def test_accepts_budget_at_floor(self) -> None:
        self.assertTrue(preflight_budget_ok(512))

    def test_accepts_budget_above_floor(self) -> None:
        self.assertTrue(preflight_budget_ok(1024))


class ClassifyThinkingOutcomeTest(unittest.TestCase):
    def test_ok_when_transport_visible_contract_pass(self) -> None:
        self.assertEqual(
            classify_thinking_outcome(
                transport_ok=True,
                visible_text="visible answer",
                finish_reason="stop",
                contract_ok=True,
            ),
            "ok",
        )

    def test_transport_failed_has_highest_priority(self) -> None:
        self.assertEqual(
            classify_thinking_outcome(
                transport_ok=False,
                visible_text="",
                finish_reason="length",
                contract_ok=False,
            ),
            "transport_failed",
        )

    def test_empty_visible_beats_token_cap_and_contract(self) -> None:
        self.assertEqual(
            classify_thinking_outcome(
                transport_ok=True,
                visible_text="   ",
                finish_reason="length",
                contract_ok=False,
            ),
            "empty_visible",
        )

    def test_token_capped_when_finish_reason_is_length(self) -> None:
        self.assertEqual(
            classify_thinking_outcome(
                transport_ok=True,
                visible_text="partial answer",
                finish_reason="length",
                contract_ok=False,
            ),
            "token_capped",
        )

    def test_contract_failed_when_visible_answer_invalid(self) -> None:
        self.assertEqual(
            classify_thinking_outcome(
                transport_ok=True,
                visible_text="wrong shape",
                finish_reason="stop",
                contract_ok=False,
            ),
            "contract_failed",
        )

    def test_none_finish_reason_does_not_imply_token_cap(self) -> None:
        self.assertEqual(
            classify_thinking_outcome(
                transport_ok=True,
                visible_text="answer",
                finish_reason=None,
                contract_ok=True,
            ),
            "ok",
        )


def _sample(**overrides: object) -> ThinkingMetricSample:
    defaults: dict[str, object] = {
        "outcome": "ok",
        "streaming_semantics": "incremental",
        "token_accounting_status": "EXACT_VISIBLE",
        "visible_output_tokens": 12,
        "content_span_seconds": 0.05,
        "finish_reason": "stop",
    }
    defaults.update(overrides)
    return ThinkingMetricSample(**defaults)


class QualifyThinkingMetricsTest(unittest.TestCase):
    def test_qualified_when_incremental_and_exact_visible(self) -> None:
        labels = qualify_thinking_metrics((_sample(),))
        self.assertEqual(labels["ttft"], "QUALIFIED_INCREMENTAL_DELIVERY")
        self.assertEqual(labels["decode"], "QUALIFIED_EXACT_VISIBLE_TOKENS")

    def test_suppresses_decode_when_token_accounting_ambiguous(self) -> None:
        labels = qualify_thinking_metrics((
            _sample(token_accounting_status="AMBIGUOUS"),
        ))
        self.assertEqual(labels["ttft"], "QUALIFIED_INCREMENTAL_DELIVERY")
        self.assertEqual(labels["decode"], "SUPPRESSED_AMBIGUOUS_TOKEN_ACCOUNTING")

    def test_suppresses_when_streaming_buffered(self) -> None:
        labels = qualify_thinking_metrics((
            _sample(streaming_semantics="buffered"),
        ))
        self.assertEqual(labels["ttft"], "SUPPRESSED_BUFFERED_DELIVERY")
        self.assertEqual(labels["decode"], "SUPPRESSED_BUFFERED_DELIVERY")

    def test_suppresses_when_token_capped(self) -> None:
        labels = qualify_thinking_metrics((
            _sample(finish_reason="length"),
        ))
        self.assertEqual(labels["ttft"], "SUPPRESSED_TOKEN_CAPPED")
        self.assertEqual(labels["decode"], "SUPPRESSED_TOKEN_CAPPED")

    def test_ignores_non_ok_samples(self) -> None:
        labels = qualify_thinking_metrics((
            _sample(outcome="transport_failed"),
            _sample(),
        ))
        self.assertEqual(labels["decode"], "QUALIFIED_EXACT_VISIBLE_TOKENS")

    def test_suppresses_when_no_ok_samples(self) -> None:
        labels = qualify_thinking_metrics((
            _sample(outcome="empty_visible"),
            _sample(outcome="contract_failed"),
        ))
        self.assertEqual(labels["ttft"], "SUPPRESSED_NO_OK_SAMPLES")
        self.assertEqual(labels["decode"], "SUPPRESSED_NO_OK_SAMPLES")


if __name__ == "__main__":
    unittest.main()
