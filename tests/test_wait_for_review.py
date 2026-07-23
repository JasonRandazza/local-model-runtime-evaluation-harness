from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from local_model_runtime_evaluation import wait_for_review as wait_for_review_module
from local_model_runtime_evaluation.wait_for_review import (
    _require_operator_shutdown,
    wait_for_review,
)


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

    def test_harness_unattended_stage_two_skips_operator_shutdown(self) -> None:
        result = wait_for_review(
            "stage2-20260723-003",
            lambda run_id: {"run_id": run_id, "state": "awaiting_review", "sequence": 9},
            lambda seconds: None,
            30,
            require_operator_shutdown=False,
        )
        self.assertEqual(result["overall"], "READY_FOR_COORDINATOR")
        self.assertEqual(result["state"], "awaiting_review")
        self.assertNotIn("operator_action_required", result)

    def test_harness_route_benchmark_skips_operator_shutdown(self) -> None:
        run_id = "stage2-20260723-903"
        with tempfile.TemporaryDirectory() as temp:
            manifests = Path(temp) / "manifests"
            manifests.mkdir()
            (manifests / "harness-bench.json").write_text(
                json.dumps({"run_id": run_id, "mode": "harness_route_benchmark"}),
                encoding="utf-8",
            )
            mock_module_path = MagicMock()
            mock_resolved = MagicMock()
            mock_resolved.parents.__getitem__.return_value = Path(temp)
            mock_module_path.resolve.return_value = mock_resolved

            def path_factory(arg: str | Path) -> Path | MagicMock:
                if arg == wait_for_review_module.__file__:
                    return mock_module_path
                return Path(arg)

            with patch.object(
                wait_for_review_module, "Path", side_effect=path_factory,
            ):
                self.assertFalse(_require_operator_shutdown(run_id))
                result = wait_for_review(
                    run_id,
                    lambda requested: {
                        "run_id": requested, "state": "awaiting_review", "sequence": 9,
                    },
                    lambda seconds: None,
                    30,
                    require_operator_shutdown=_require_operator_shutdown(run_id),
                )
        self.assertEqual(result["overall"], "READY_FOR_COORDINATOR")
        self.assertEqual(result["state"], "awaiting_review")
        self.assertNotIn("operator_action_required", result)

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
