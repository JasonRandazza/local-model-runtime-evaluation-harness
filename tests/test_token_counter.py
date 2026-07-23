from __future__ import annotations

import unittest

from local_model_runtime_evaluation.token_counter import (
    FixedMapTokenCounter,
    resolve_token_accounting,
)


class ResolveTokenAccountingTest(unittest.TestCase):
    def test_usage_reasoning_wins_exact_visible(self) -> None:
        counter = FixedMapTokenCounter({"think": 99, "answer": 99})
        reasoning, visible, status = resolve_token_accounting(
            reasoning_text="think",
            visible_text="answer",
            completion_tokens=10,
            usage_reasoning_tokens=2,
            token_counter=counter,
        )
        self.assertEqual(reasoning, 2)
        self.assertEqual(visible, 8)
        self.assertEqual(status, "EXACT_VISIBLE")

    def test_derived_when_counter_reconciles_with_completion_total(self) -> None:
        counter = FixedMapTokenCounter({"think hard": 3, "ok": 2})
        reasoning, visible, status = resolve_token_accounting(
            reasoning_text="think hard",
            visible_text="ok",
            completion_tokens=5,
            usage_reasoning_tokens=None,
            token_counter=counter,
        )
        self.assertEqual(reasoning, 3)
        self.assertEqual(visible, 2)
        self.assertEqual(status, "DERIVED_REASONING_CONTENT")

    def test_mismatch_with_completion_total_is_incomparable(self) -> None:
        counter = FixedMapTokenCounter({"think": 3, "ok": 2})
        reasoning, visible, status = resolve_token_accounting(
            reasoning_text="think",
            visible_text="ok",
            completion_tokens=9,
            usage_reasoning_tokens=None,
            token_counter=counter,
        )
        self.assertIsNone(reasoning)
        self.assertIsNone(visible)
        self.assertEqual(status, "INCOMPARABLE_TOKEN_ACCOUNTING")

    def test_derived_without_completion_total_when_both_positive(self) -> None:
        counter = FixedMapTokenCounter({"think": 3, "ok": 2})
        reasoning, visible, status = resolve_token_accounting(
            reasoning_text="think",
            visible_text="ok",
            completion_tokens=None,
            usage_reasoning_tokens=None,
            token_counter=counter,
        )
        self.assertEqual(reasoning, 3)
        self.assertEqual(visible, 2)
        self.assertEqual(status, "DERIVED_REASONING_CONTENT")

    def test_no_counter_without_usage_reasoning_is_incomparable(self) -> None:
        reasoning, visible, status = resolve_token_accounting(
            reasoning_text="think",
            visible_text="ok",
            completion_tokens=5,
            usage_reasoning_tokens=None,
            token_counter=None,
        )
        self.assertIsNone(reasoning)
        self.assertIsNone(visible)
        self.assertEqual(status, "INCOMPARABLE_TOKEN_ACCOUNTING")

    def test_usage_reasoning_rejects_invalid_visible(self) -> None:
        reasoning, visible, status = resolve_token_accounting(
            reasoning_text="",
            visible_text="ok",
            completion_tokens=2,
            usage_reasoning_tokens=2,
            token_counter=None,
        )
        self.assertIsNone(reasoning)
        self.assertIsNone(visible)
        self.assertEqual(status, "INCOMPARABLE_TOKEN_ACCOUNTING")


if __name__ == "__main__":
    unittest.main()
