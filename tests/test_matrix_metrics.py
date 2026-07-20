from __future__ import annotations

import unittest

from local_model_runtime_evaluation.matrix_measure import Observation, summarize
from local_model_runtime_evaluation.matrix_runner import render_report


def _obs(**overrides: object) -> Observation:
    data = dict(
        workload_id="short-instruction",
        repetition=1,
        measured=True,
        success=True,
        total_seconds=2.0,
        finish_reason="stop",
        response_contract_valid=True,
        response_contract_status="PASS",
        completion_tokens=20,
        visible_output_tokens=16,
        token_accounting_status="EXACT_VISIBLE",
        ttft_seconds=0.4,
        content_span_seconds=1.2,
        streaming_semantics="incremental",
        error=None,
    )
    data.update(overrides)
    return Observation(**data)  # type: ignore[arg-type]


class MatrixMetricsTest(unittest.TestCase):
    def test_option_a_decode_requires_exact_visible(self) -> None:
        exact = _obs()
        incomparable = _obs(
            token_accounting_status="INCOMPARABLE_TOKEN_ACCOUNTING",
            visible_output_tokens=None,
        )
        buffered = _obs(streaming_semantics="buffered", ttft_seconds=None, content_span_seconds=None)
        summary = summarize((exact, incomparable, buffered))
        self.assertEqual(summary["ttft_sample_count"], 2)
        self.assertEqual(summary["decode_sample_count"], 1)
        self.assertEqual(summary["estimated_decode_sample_count"], 2)
        self.assertAlmostEqual(summary["median_ttft_seconds"], 0.4)
        self.assertAlmostEqual(summary["median_decode_tokens_per_second"], 16 / 1.2)
        # Option B: completion_tokens / (total - ttft) = 20 / 1.6
        self.assertAlmostEqual(summary["median_estimated_decode_tokens_per_second"], 20 / 1.6)

    def test_report_includes_metric_tables(self) -> None:
        raw = {
            "campaign_id": "gemma-4-12b-qat-3x3",
            "mode": "screen",
            "suite_id": "gemma-matrix-v1",
            "suite_revision": "1",
            "cells": [
                {
                    "cell_id": "jang_4m__osaurus",
                    "quant": "jang_4m",
                    "server": "osaurus",
                    "status": "PASS",
                    "na_reason": None,
                    "summary": {
                        "median_total_seconds": 2.16,
                        "median_ttft_seconds": 1.2,
                        "median_decode_tokens_per_second": None,
                        "median_estimated_decode_tokens_per_second": 18.5,
                        "measured_count": 9,
                        "success_count": 9,
                        "contract_pass_count": 9,
                    },
                },
                {
                    "cell_id": "optiq_4bit__optiq",
                    "quant": "optiq_4bit",
                    "server": "optiq",
                    "status": "PASS",
                    "na_reason": None,
                    "summary": {
                        "median_total_seconds": 2.7,
                        "median_ttft_seconds": 0.5,
                        "median_decode_tokens_per_second": 40.0,
                        "median_estimated_decode_tokens_per_second": 42.0,
                        "measured_count": 9,
                        "success_count": 9,
                        "contract_pass_count": 9,
                    },
                },
            ],
        }
        report = render_report(raw)
        self.assertIn("## Metrics", report)
        self.assertIn("### Median TTFT", report)
        self.assertIn("### Median decode tok/s (exact)", report)
        self.assertIn("### Median decode tok/s (estimated)", report)
        self.assertIn("1.20s", report)
        self.assertIn("40.0", report)
        self.assertIn("18.5 est.", report)
        self.assertIn("9/9", report)


if __name__ == "__main__":
    unittest.main()
