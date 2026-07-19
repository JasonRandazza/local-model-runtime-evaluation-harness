from __future__ import annotations

import unittest

from local_model_runtime_evaluation.wait_for_review import wait_for_review


class WaitForReviewTest(unittest.TestCase):
    def test_waits_until_review_and_returns_bounded_summary(self) -> None:
        states = iter([
            {"run_id": "stage1-20260714-001", "state": "running", "sequence": 4},
            {"run_id": "stage1-20260714-001", "state": "measured", "sequence": 7},
            {"run_id": "stage1-20260714-001", "state": "awaiting_review", "sequence": 9},
        ])
        sleeps: list[float] = []
        result = wait_for_review(
            "stage1-20260714-001", lambda run_id: next(states), sleeps.append, 30,
        )
        self.assertEqual(result["overall"], "READY_FOR_COORDINATOR")
        self.assertEqual(result["state"], "awaiting_review")
        self.assertEqual(result["poll_count"], 3)
        self.assertEqual(sleeps, [30, 30])

    def test_stops_on_failed_state(self) -> None:
        result = wait_for_review(
            "stage1-20260714-001",
            lambda run_id: {"run_id": run_id, "state": "failed", "sequence": 5},
            lambda seconds: None,
            30,
        )
        self.assertEqual(result["overall"], "MANAGER_REVIEW_REQUIRED")
        self.assertEqual(result["state"], "failed")

    def test_stage_two_requires_operator_shutdown_before_cleanup(self) -> None:
        states = iter([
            {"run_id": "stage2-20260714-001", "state": "service_ready", "sequence": 5},
            {"run_id": "stage2-20260714-001", "state": "endpoint_identity", "sequence": 6},
            {"run_id": "stage2-20260714-001", "state": "awaiting_review", "sequence": 10},
        ])
        result = wait_for_review(
            "stage2-20260714-001", lambda run_id: next(states), lambda seconds: None, 1,
        )
        self.assertEqual(result["overall"], "OPERATOR_SHUTDOWN_REQUIRED")
        self.assertEqual(result["state"], "awaiting_review")
        self.assertTrue(result["operator_action_required"])
        self.assertIn("foreground OptiQ service", result["operator_action"])

    def test_failed_stage_two_still_requires_operator_shutdown(self) -> None:
        result = wait_for_review(
            "stage2-20260714-001",
            lambda run_id: {"run_id": run_id, "state": "failed", "sequence": 7},
            lambda seconds: None,
            30,
        )
        self.assertEqual(result["overall"], "OPERATOR_SHUTDOWN_REQUIRED")
        self.assertTrue(result["operator_action_required"])

    def test_stage_two_inference_run_uses_the_preserved_waiter_shutdown_boundary(self) -> None:
        result = wait_for_review(
            "stage2-20260715-901",
            lambda run_id: {"run_id": run_id, "state": "awaiting_review", "sequence": 12},
            lambda seconds: None,
            30,
        )
        self.assertEqual(result["overall"], "OPERATOR_SHUTDOWN_REQUIRED")
        self.assertTrue(result["operator_action_required"])

    def test_rejects_non_waitable_run_id(self) -> None:
        with self.assertRaises(ValueError):
            wait_for_review("stage0-20260714-001", lambda run_id: {}, lambda seconds: None, 30)


if __name__ == "__main__":
    unittest.main()
