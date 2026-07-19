from __future__ import annotations

import threading
import unittest
from pathlib import Path

from local_model_runtime_evaluation.benchmark_suite import BenchmarkSuite
from local_model_runtime_evaluation.measurement import MeasurementError, Sample, aggregate, run_schedule
from local_model_runtime_evaluation.transport import TransportResult


def result(route: str, repetition: int) -> TransportResult:
    base = 1.0 if route == "direct" else 1.1
    return TransportResult(
        "ok", "hash", base / 10, base + repetition / 100, 10, "stop", 200, True,
        2, base / 10 + 0.5, 2, 8, "EXACT_VISIBLE",
    )


class MeasurementTest(unittest.TestCase):
    def setUp(self) -> None:
        self.suite = BenchmarkSuite.load(Path(__file__).parents[1] / "suites" / "route-overhead-v1.json")

    def test_runner_excludes_warmups_and_aggregates_five_samples_per_route(self) -> None:
        samples = run_schedule(
            self.suite, 5,
            lambda request, workload: result(request.route, request.repetition),
            threading.Event(),
        )
        self.assertEqual(len(samples), 72)
        summary = aggregate(samples, repetitions=5)
        self.assertEqual(summary["measured_sample_count"], 60)
        self.assertEqual(summary["warmup_sample_count"], 12)
        self.assertEqual(summary["workloads"]["short-chat"]["direct"]["sample_count"], 5)
        self.assertGreater(summary["workloads"]["short-chat"]["total_seconds_delta"], 0)
        self.assertEqual(summary["overall"]["streaming_metric_status"], "COMPARABLE")
        self.assertGreater(summary["overall"]["total_seconds_delta_percent"], 0)

    def test_aggregation_fails_without_exact_token_accounting(self) -> None:
        samples = [
            Sample("short-chat", "direct", 1, True, True, 0.1, 1.0, None, "stop", "a", 2, 0.5, "incremental", True, "PASS", None, None, "INCOMPARABLE_TOKEN_ACCOUNTING"),
            Sample("short-chat", "routed", 1, True, True, 0.1, 1.1, 10, "stop", "b", 2, 0.5, "incremental", True, "PASS", 2, 8, "EXACT_VISIBLE"),
        ]
        with self.assertRaises(MeasurementError):
            aggregate(samples, repetitions=1)

    def test_buffered_stream_suppresses_ttft_and_decode_claims(self) -> None:
        samples = [
            Sample("short-chat", "direct", 1, True, True, 0.2, 1.0, 10, "length", "a", 1, 0.0, "buffered", True, "PASS", 2, 8, "EXACT_VISIBLE"),
            Sample("short-chat", "routed", 1, True, True, 0.3, 1.1, 10, "length", "b", 1, 0.0, "buffered", True, "PASS", 2, 8, "EXACT_VISIBLE"),
        ]
        summary = aggregate(samples, repetitions=1)
        direct = summary["overall"]["direct"]
        self.assertEqual(summary["overall"]["streaming_metric_status"], "INCOMPARABLE_BUFFERED_STREAM")
        self.assertIsNone(direct["ttft_seconds_median"])
        self.assertIsNone(direct["decode_tokens_per_second_median"])
        self.assertEqual(summary["overall"]["completion_status"], "TOKEN_CAPPED")
        self.assertEqual(summary["overall"]["finish_reason_counts"], {"length": 2})

    def test_missing_visible_token_evidence_suppresses_decode_but_not_ttft(self) -> None:
        samples = [
            Sample("structured", "direct", 1, True, True, 4.6, 4.8, 405, "stop", "a", 3, 0.2, "incremental", True, "PASS", None, None, "INCOMPARABLE_TOKEN_ACCOUNTING"),
            Sample("structured", "routed", 1, True, True, 4.7, 4.9, 405, "stop", "b", 3, 0.2, "incremental", True, "PASS", None, None, "INCOMPARABLE_TOKEN_ACCOUNTING"),
        ]
        summary = aggregate(samples, repetitions=1)
        direct = summary["overall"]["direct"]
        self.assertEqual(direct["ttft_metric_status"], "COMPARABLE")
        self.assertIsNotNone(direct["ttft_seconds_median"])
        self.assertEqual(direct["decode_metric_status"], "INCOMPARABLE_TOKEN_ACCOUNTING")
        self.assertIsNone(direct["decode_tokens_per_second_median"])

    def test_decode_uses_exact_visible_tokens_and_observed_content_span(self) -> None:
        samples = [
            Sample("structured", "direct", 1, True, True, 4.6, 4.9, 120, "stop", "a", 3, 0.2, "incremental", True, "PASS", 100, 20, "EXACT_VISIBLE"),
            Sample("structured", "routed", 1, True, True, 4.7, 5.0, 120, "stop", "b", 3, 0.25, "incremental", True, "PASS", 100, 20, "EXACT_VISIBLE"),
        ]
        summary = aggregate(samples, repetitions=1)
        direct = summary["overall"]["direct"]
        self.assertEqual(direct["decode_metric_status"], "COMPARABLE")
        self.assertEqual(direct["decode_tokens_per_second_median"], 100.0)
        self.assertEqual(direct["reasoning_tokens_median"], 100)
        self.assertEqual(direct["visible_output_tokens_median"], 20)

    def test_paired_delta_median_resists_one_large_timing_outlier(self) -> None:
        samples = []
        for repetition, direct, routed in [(1, 1.0, 1.1), (2, 2.0, 50.0), (3, 100.0, 100.1)]:
            samples.extend([
                Sample("drift", "direct", repetition, True, True, 0.1, direct, 10, "stop", "a", 2, 0.5, "incremental", True, "PASS", 2, 8, "EXACT_VISIBLE"),
                Sample("drift", "routed", repetition, True, True, 0.1, routed, 10, "stop", "b", 2, 0.5, "incremental", True, "PASS", 2, 8, "EXACT_VISIBLE"),
            ])
        summary = aggregate(samples, repetitions=3)
        self.assertEqual(summary["overall"]["total_seconds_delta"], 48.0)
        paired = summary["overall"]["paired_total_seconds"]
        self.assertAlmostEqual(paired["delta_seconds_median"], 0.1)
        self.assertEqual(paired["pair_count"], 3)

    def test_response_contract_is_validated_without_retaining_content(self) -> None:
        valid_status = '{"name":"status","arguments":{"run_id":"stage1-test","include_details":false}}'

        def execute(request, workload):
            content = valid_status if workload.response_contract == "status-tool-json" else "ok"
            if request.route == "routed" and workload.response_contract == "status-tool-json":
                content = "not-json"
            return TransportResult(content, "hash", 0.1, 1.0, 10, "stop", 200, True, 2, 0.6, 2, 8, "EXACT_VISIBLE")

        samples = run_schedule(self.suite, 5, execute, threading.Event())
        structured = [item for item in samples if item.workload_id == "structured-tool-json"]
        self.assertTrue(any(item.response_contract_valid for item in structured))
        self.assertTrue(any(not item.response_contract_valid for item in structured))
        self.assertFalse(hasattr(structured[0], "content"))

    def test_cancellation_stops_before_new_request(self) -> None:
        cancel = threading.Event()
        calls = 0

        def execute(request, workload):
            nonlocal calls
            calls += 1
            cancel.set()
            return result(request.route, request.repetition)

        with self.assertRaises(MeasurementError):
            run_schedule(self.suite, 5, execute, cancel)
        self.assertEqual(calls, 1)


if __name__ == "__main__":
    unittest.main()
