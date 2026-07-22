from __future__ import annotations

import unittest

from local_model_runtime_evaluation.omlx_thinking_measure import (
    THINKING_PREFLIGHT_MAX_TOKENS,
    classify_thinking_outcome,
    preflight_budget_ok,
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


if __name__ == "__main__":
    unittest.main()
