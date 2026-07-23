from __future__ import annotations

import unittest

from local_model_runtime_evaluation.omlx_admin_bench_client import BenchMetricRow
from local_model_runtime_evaluation.omlx_thinking_bench_parity import (
    build_cross_check_markdown,
    decide_parity_outcome,
)


class DecideParityOutcomeTest(unittest.TestCase):
    def test_pass_requires_all_three(self) -> None:
        self.assertEqual(
            decide_parity_outcome(
                bench_completed=True, cleanup_ok=True, cross_check_written=True
            ),
            "PASS",
        )

    def test_fail_cleanup_when_bench_ok_cleanup_bad(self) -> None:
        self.assertEqual(
            decide_parity_outcome(
                bench_completed=True, cleanup_ok=False, cross_check_written=True
            ),
            "FAIL_CLEANUP",
        )

    def test_fail_when_bench_incomplete(self) -> None:
        self.assertEqual(
            decide_parity_outcome(
                bench_completed=False, cleanup_ok=True, cross_check_written=True
            ),
            "FAIL",
        )

    def test_fail_when_cross_check_missing(self) -> None:
        self.assertEqual(
            decide_parity_outcome(
                bench_completed=True, cleanup_ok=True, cross_check_written=False
            ),
            "FAIL",
        )


class BuildCrossCheckMarkdownTest(unittest.TestCase):
    def test_mentions_ttft_divergence_and_reference(self) -> None:
        md = build_cross_check_markdown(
            run_id="omlx-thinking-bench-20260722-001",
            decision="PASS",
            bench_status="completed",
            rows=(BenchMetricRow(12.5, 1.2, 40.0, 1.5, 1024, 200, "ok"),),
        )
        self.assertIn("omlx-thinking-measure-20260722-004", md)
        self.assertIn("reasoning_content", md)
        self.assertIn("content-only", md)
        self.assertIn("1024", md)
        self.assertIn("ttft_ms", md.lower() or md)


if __name__ == "__main__":
    unittest.main()
