from __future__ import annotations

import json
import unittest
from pathlib import Path

from local_model_runtime_evaluation.stage_two import StageTwoError
from local_model_runtime_evaluation.stage_two_smoke_measurement import (
    SmokeObservation,
    summarize_smoke,
)
from local_model_runtime_evaluation.stage_two_smoke_suite import (
    SmokeRequest,
    SmokeWorkload,
    StageTwoSmokeSuite,
)
from local_model_runtime_evaluation.transport import TransportResult


def request(
    sequence: int,
    route: str,
    measured: bool,
    repetition: int,
    workload_id: str = "short-chat",
) -> SmokeRequest:
    return SmokeRequest(
        workload_id=workload_id,
        route=route,
        measured=measured,
        sequence=sequence,
        repetition=repetition,
    )


def workload(workload_id: str = "short-chat") -> SmokeWorkload:
    return SmokeWorkload(workload_id, "test prompt", 128, "text")


def result(
    *,
    content_sha256: str = "a" * 64,
    finish_reason: str | None = "stop",
    content_event_count: int = 2,
    ttft_seconds: float = 0.2,
    last_content_seconds: float = 0.7,
    token_accounting_status: str = "EXACT_VISIBLE",
    visible_output_tokens: int | None = 8,
) -> TransportResult:
    return TransportResult(
        "private response content",
        content_sha256,
        ttft_seconds,
        1.0,
        10,
        finish_reason,
        200,
        True,
        content_event_count,
        last_content_seconds,
        2,
        visible_output_tokens,
        token_accounting_status,
    )


def observation(
    sequence: int,
    route: str,
    measured: bool,
    repetition: int,
    workload_id: str = "short-chat",
    **result_options: object,
) -> SmokeObservation:
    return SmokeObservation.from_result(
        request(sequence, route, measured, repetition, workload_id),
        workload(workload_id),
        result(**result_options),
        (True, "PASS"),
    )


def complete_cohort() -> tuple[SmokeObservation, ...]:
    return (
        observation(1, "direct", False, 0),
        observation(2, "routed", False, 0),
        observation(3, "direct", True, 1),
        observation(4, "routed", True, 1),
        observation(5, "routed", False, 0, "structured-tool-json"),
        observation(6, "direct", False, 0, "structured-tool-json"),
        observation(7, "routed", True, 1, "structured-tool-json"),
        observation(8, "direct", True, 1, "structured-tool-json"),
    )


class StageTwoSmokeMeasurementTest(unittest.TestCase):
    def test_fixed_schedule_requests_preserve_sequence_and_repetition_in_observations(self) -> None:
        suite_path = Path(__file__).parents[1] / "suites" / "optiq-route-smoke-v1.json"
        suite = StageTwoSmokeSuite.load(suite_path)
        workloads = {item.workload_id: item for item in suite.workloads}

        observations = tuple(
            SmokeObservation.from_result(
                item,
                workloads[item.workload_id],
                result(),
                (True, "PASS"),
            )
            for item in suite.schedule()
        )

        self.assertEqual(
            [(item.sequence, item.repetition) for item in observations],
            [(1, 0), (2, 0), (3, 1), (4, 1), (5, 0), (6, 0), (7, 1), (8, 1)],
        )
        self.assertEqual(summarize_smoke(observations)["measured_requests"], 4)

    def test_observation_is_sanitized_and_summary_is_non_benchmarking(self) -> None:
        observations = complete_cohort()

        serialized = observations[0].as_json()
        self.assertNotIn("content", serialized)
        self.assertNotIn("prompt", serialized)
        self.assertEqual(serialized["output_sha256"], "a" * 64)

        summary = summarize_smoke(observations)
        self.assertEqual(summary["total_requests"], 8)
        self.assertEqual(summary["excluded_warmups"], 4)
        self.assertEqual(summary["measured_requests"], 4)
        self.assertEqual(summary["inference_path_acceptance"], "PASS")
        self.assertEqual(summary["behavioral_contract_acceptance"], "PASS")
        self.assertNotIn("median", json.dumps(summary).lower())
        self.assertNotIn("p95", json.dumps(summary).lower())

    def test_invalid_measured_contract_fails_behavioral_not_infrastructure(self) -> None:
        observations = list(complete_cohort())
        observations[2] = SmokeObservation.from_result(
            request(3, "direct", True, 1), workload(), result(), (False, "EMPTY_TEXT")
        )

        summary = summarize_smoke(tuple(observations))

        self.assertEqual(summary["inference_path_acceptance"], "PASS")
        self.assertEqual(summary["behavioral_contract_acceptance"], "FAIL")
        self.assertEqual(summary["response_contract_counts"], {"valid": 3, "invalid": 1})

    def test_hash_mismatch_suppresses_performance_qualification(self) -> None:
        observations = list(complete_cohort())
        observations[3] = observation(4, "routed", True, 1, content_sha256="b" * 64)

        summary = summarize_smoke(tuple(observations))

        self.assertEqual(summary["output_hash_pair_status"], "MISMATCH")
        self.assertIn("OUTPUT_HASH_MISMATCH", summary["behavioral_findings"])
        self.assertEqual(summary["metric_qualification"], {
            "ttft": "SUPPRESSED_OUTPUT_HASH_MISMATCH",
            "decode": "SUPPRESSED_OUTPUT_HASH_MISMATCH",
        })
        self.assertEqual(summary["behavioral_contract_acceptance"], "PASS")

    def test_token_capped_finish_suppresses_performance_qualification(self) -> None:
        observations = list(complete_cohort())
        observations[2] = observation(3, "direct", True, 1, finish_reason="length")

        summary = summarize_smoke(tuple(observations))

        self.assertEqual(summary["finish_reason_counts"], {"length": 1, "stop": 3})
        self.assertIn("TOKEN_CAPPED", summary["behavioral_findings"])
        self.assertEqual(summary["metric_qualification"], {
            "ttft": "SUPPRESSED_TOKEN_CAPPED",
            "decode": "SUPPRESSED_TOKEN_CAPPED",
        })
        self.assertEqual(summary["behavioral_contract_acceptance"], "PASS")

    def test_nonqualifying_metrics_are_recorded_without_fabricated_claims(self) -> None:
        observations = list(complete_cohort())
        observations[2] = observation(
            3,
            "direct",
            True,
            1,
            finish_reason="length",
            content_event_count=1,
            last_content_seconds=0.2,
            token_accounting_status="INCOMPARABLE_TOKEN_ACCOUNTING",
            visible_output_tokens=None,
        )

        summary = summarize_smoke(tuple(observations))
        direct = next(item for item in summary["direct_observations"] if item["sequence"] == 3)

        self.assertIsNone(direct["ttft_seconds"])
        self.assertEqual(direct["streaming_semantics"], "buffered")
        self.assertNotIn("decode_tokens_per_second", direct)
        self.assertEqual(summary["metric_qualification"]["ttft"], "SUPPRESSED_BUFFERED_DELIVERY")
        self.assertEqual(summary["metric_qualification"]["decode"], "SUPPRESSED_BUFFERED_DELIVERY")
        self.assertEqual(summary["finish_reason_counts"], {"length": 1, "stop": 3})
        self.assertIn("TOKEN_CAPPED", summary["behavioral_findings"])
        self.assertIn("BUFFERED_DELIVERY", summary["behavioral_findings"])
        self.assertIn("AMBIGUOUS_TOKEN_ACCOUNTING", summary["behavioral_findings"])

    def test_incomplete_or_duplicate_cohort_fails_closed(self) -> None:
        observations = complete_cohort()
        for invalid in (observations[:-1], observations[:-1] + (observations[-2],)):
            with self.subTest(observation_count=len(invalid)), self.assertRaises(StageTwoError) as raised:
                summarize_smoke(invalid)
            self.assertEqual(raised.exception.code, "evidence_incomplete")

    def test_pair_deltas_include_one_direct_and_one_routed_measured_observation(self) -> None:
        summary = summarize_smoke(complete_cohort())

        self.assertEqual(len(summary["measured_pair_deltas"]), 2)
        for pair in summary["measured_pair_deltas"]:
            self.assertEqual(pair["direct_sequence"], 3 if pair["pair"] == 1 else 8)
            self.assertEqual(pair["routed_sequence"], 4 if pair["pair"] == 1 else 7)
            self.assertEqual(pair["routed_minus_direct_seconds"], 0.0)


if __name__ == "__main__":
    unittest.main()
