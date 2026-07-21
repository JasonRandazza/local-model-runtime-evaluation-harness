from __future__ import annotations

import unittest
from pathlib import Path

from local_model_runtime_evaluation.stage_two import StageTwoError
from local_model_runtime_evaluation.stage_two_benchmark_measurement import summarize_benchmark
from local_model_runtime_evaluation.stage_two_benchmark_suite import StageTwoBenchmarkSuite
from local_model_runtime_evaluation.stage_two_smoke_measurement import SmokeObservation


REPO = Path(__file__).parents[1]


def observation(
    *,
    sequence: int,
    workload_id: str,
    route: str,
    measured: bool,
    repetition: int,
    total_seconds: float,
    output_sha256: str = "a" * 64,
    **overrides: object,
) -> SmokeObservation:
    fields = {
        "http_status": 200,
        "stream_valid": True,
        "ttft_seconds": 0.2,
        "completion_tokens": 10,
        "reasoning_tokens": None,
        "visible_output_tokens": 8,
        "token_accounting_status": "EXACT_VISIBLE",
        "content_event_count": 2,
        "content_span_seconds": 0.5,
        "streaming_semantics": "incremental",
        "finish_reason": "stop",
        "response_contract_valid": True,
        "response_contract_status": "PASS",
        "output_sha256": output_sha256,
    }
    fields.update(overrides)
    return SmokeObservation(
        sequence=sequence,
        workload_id=workload_id,
        route=route,
        measured=measured,
        repetition=repetition,
        total_seconds=total_seconds,
        **fields,  # type: ignore[arg-type]
    )


def complete_cohort(
    *,
    short_chat_direct_total: float | None = None,
    short_chat_routed_total: float | None = None,
    structured_direct_total: float | None = None,
    structured_routed_total: float | None = None,
) -> tuple[SmokeObservation, ...]:
    suite = StageTwoBenchmarkSuite.load(REPO / "suites" / "gemma-optiq-route-benchmark-v1.json")
    observations: list[SmokeObservation] = []
    for request in suite.schedule():
        if request.measured:
            if request.workload_id == "short-chat" and request.route == "direct":
                total = (
                    float(request.repetition + 1)
                    if short_chat_direct_total is None
                    else short_chat_direct_total
                )
            elif request.workload_id == "short-chat" and request.route == "routed":
                total = (
                    float(request.repetition + 2)
                    if short_chat_routed_total is None
                    else short_chat_routed_total
                )
            elif request.workload_id == "structured-tool-json" and request.route == "direct":
                total = structured_direct_total if structured_direct_total is not None else 10.0
            else:
                total = structured_routed_total if structured_routed_total is not None else 9.0
        else:
            total = 0.5
        observations.append(
            observation(
                sequence=request.sequence,
                workload_id=request.workload_id,
                route=request.route,
                measured=request.measured,
                repetition=request.repetition,
                total_seconds=total,
            )
        )
    return tuple(observations)


class StageTwoBenchmarkMeasurementTest(unittest.TestCase):
    def test_summarize_benchmark_requires_sixty_measured_and_twelve_warmups(self) -> None:
        observations = complete_cohort()[:-1]
        with self.assertRaises(StageTwoError) as raised:
            summarize_benchmark(observations)
        self.assertEqual(raised.exception.code, "evidence_incomplete")

    def test_route_overhead_medians_and_deltas(self) -> None:
        observations = complete_cohort()
        summary = summarize_benchmark(observations)

        self.assertEqual(summary["excluded_warmups"], 12)
        self.assertEqual(summary["measured_requests"], 60)
        self.assertEqual(summary["inference_path_acceptance"], "PASS")
        self.assertEqual(summary["behavioral_contract_acceptance"], "PASS")

        by_cell = {
            (item["workload_id"], item["route"]): item
            for item in summary["route_overhead_summary"]
        }
        self.assertAlmostEqual(by_cell[("short-chat", "direct")]["median_total_seconds"], 8.0)
        self.assertAlmostEqual(by_cell[("short-chat", "routed")]["median_total_seconds"], 9.0)
        self.assertAlmostEqual(by_cell[("structured-tool-json", "direct")]["median_total_seconds"], 10.0)
        self.assertAlmostEqual(by_cell[("structured-tool-json", "routed")]["median_total_seconds"], 9.0)
        self.assertEqual(
            by_cell[("short-chat", "direct")]["ttft_qualification"],
            "QUALIFIED_INCREMENTAL_DELIVERY",
        )
        self.assertEqual(
            by_cell[("short-chat", "direct")]["decode_qualification"],
            "QUALIFIED_EXACT_VISIBLE_TOKENS",
        )
        self.assertAlmostEqual(by_cell[("short-chat", "direct")]["median_ttft_seconds"], 0.2)
        self.assertAlmostEqual(
            by_cell[("short-chat", "direct")]["median_decode_tokens_per_second"],
            16.0,
        )

        deltas = {item["workload_id"]: item for item in summary["route_overhead_deltas"]}
        self.assertAlmostEqual(deltas["short-chat"]["direct_median_total_seconds"], 8.0)
        self.assertAlmostEqual(deltas["short-chat"]["routed_median_total_seconds"], 9.0)
        self.assertAlmostEqual(deltas["short-chat"]["routed_minus_direct_total_seconds"], 1.0)
        self.assertAlmostEqual(deltas["structured-tool-json"]["direct_median_total_seconds"], 10.0)
        self.assertAlmostEqual(deltas["structured-tool-json"]["routed_median_total_seconds"], 9.0)
        self.assertAlmostEqual(
            deltas["structured-tool-json"]["routed_minus_direct_total_seconds"],
            -1.0,
        )


if __name__ == "__main__":
    unittest.main()
