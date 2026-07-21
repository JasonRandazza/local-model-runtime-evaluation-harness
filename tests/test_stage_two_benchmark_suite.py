from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from local_model_runtime_evaluation.stage_two_benchmark_suite import (
    BenchmarkRequest,
    BenchmarkSuiteError,
    StageTwoBenchmarkSuite,
)

REPO = Path(__file__).parents[1]


class StageTwoBenchmarkSuiteTest(unittest.TestCase):
    def setUp(self) -> None:
        self.path = REPO / "suites" / "gemma-optiq-route-benchmark-v1.json"

    def test_counterbalanced_schedule_order_is_golden_locked(self) -> None:
        suite = StageTwoBenchmarkSuite.load(self.path)
        self.assertEqual(
            [
                (
                    item.sequence,
                    item.workload_id,
                    item.route,
                    item.measured,
                    item.repetition,
                )
                for item in suite.schedule()
            ],
            [
                (1, "short-chat", "direct", False, 0),
                (2, "short-chat", "routed", False, 0),
                (3, "short-chat", "direct", False, 1),
                (4, "short-chat", "routed", False, 1),
                (5, "short-chat", "direct", False, 2),
                (6, "short-chat", "routed", False, 2),
                (7, "short-chat", "direct", True, 0),
                (8, "short-chat", "routed", True, 0),
                (9, "short-chat", "direct", True, 1),
                (10, "short-chat", "routed", True, 1),
                (11, "short-chat", "direct", True, 2),
                (12, "short-chat", "routed", True, 2),
                (13, "short-chat", "direct", True, 3),
                (14, "short-chat", "routed", True, 3),
                (15, "short-chat", "direct", True, 4),
                (16, "short-chat", "routed", True, 4),
                (17, "short-chat", "direct", True, 5),
                (18, "short-chat", "routed", True, 5),
                (19, "short-chat", "direct", True, 6),
                (20, "short-chat", "routed", True, 6),
                (21, "short-chat", "direct", True, 7),
                (22, "short-chat", "routed", True, 7),
                (23, "short-chat", "direct", True, 8),
                (24, "short-chat", "routed", True, 8),
                (25, "short-chat", "direct", True, 9),
                (26, "short-chat", "routed", True, 9),
                (27, "short-chat", "direct", True, 10),
                (28, "short-chat", "routed", True, 10),
                (29, "short-chat", "direct", True, 11),
                (30, "short-chat", "routed", True, 11),
                (31, "short-chat", "direct", True, 12),
                (32, "short-chat", "routed", True, 12),
                (33, "short-chat", "direct", True, 13),
                (34, "short-chat", "routed", True, 13),
                (35, "short-chat", "direct", True, 14),
                (36, "short-chat", "routed", True, 14),
                (37, "structured-tool-json", "routed", False, 0),
                (38, "structured-tool-json", "direct", False, 0),
                (39, "structured-tool-json", "routed", False, 1),
                (40, "structured-tool-json", "direct", False, 1),
                (41, "structured-tool-json", "routed", False, 2),
                (42, "structured-tool-json", "direct", False, 2),
                (43, "structured-tool-json", "routed", True, 0),
                (44, "structured-tool-json", "direct", True, 0),
                (45, "structured-tool-json", "routed", True, 1),
                (46, "structured-tool-json", "direct", True, 1),
                (47, "structured-tool-json", "routed", True, 2),
                (48, "structured-tool-json", "direct", True, 2),
                (49, "structured-tool-json", "routed", True, 3),
                (50, "structured-tool-json", "direct", True, 3),
                (51, "structured-tool-json", "routed", True, 4),
                (52, "structured-tool-json", "direct", True, 4),
                (53, "structured-tool-json", "routed", True, 5),
                (54, "structured-tool-json", "direct", True, 5),
                (55, "structured-tool-json", "routed", True, 6),
                (56, "structured-tool-json", "direct", True, 6),
                (57, "structured-tool-json", "routed", True, 7),
                (58, "structured-tool-json", "direct", True, 7),
                (59, "structured-tool-json", "routed", True, 8),
                (60, "structured-tool-json", "direct", True, 8),
                (61, "structured-tool-json", "routed", True, 9),
                (62, "structured-tool-json", "direct", True, 9),
                (63, "structured-tool-json", "routed", True, 10),
                (64, "structured-tool-json", "direct", True, 10),
                (65, "structured-tool-json", "routed", True, 11),
                (66, "structured-tool-json", "direct", True, 11),
                (67, "structured-tool-json", "routed", True, 12),
                (68, "structured-tool-json", "direct", True, 12),
                (69, "structured-tool-json", "routed", True, 13),
                (70, "structured-tool-json", "direct", True, 13),
                (71, "structured-tool-json", "routed", True, 14),
                (72, "structured-tool-json", "direct", True, 14),
            ],
        )

    def test_schedule_has_seventy_two_counterbalanced_requests(self) -> None:
        suite = StageTwoBenchmarkSuite.load(self.path)
        schedule = suite.schedule()
        self.assertEqual(len(schedule), 72)
        self.assertEqual([r.sequence for r in schedule], list(range(1, 73)))
        self.assertEqual(sum(1 for r in schedule if not r.measured), 12)
        self.assertEqual(sum(1 for r in schedule if r.measured), 60)
        for workload in ("short-chat", "structured-tool-json"):
            for route in ("direct", "routed"):
                warm = [
                    r
                    for r in schedule
                    if r.workload_id == workload and r.route == route and not r.measured
                ]
                measured = [
                    r
                    for r in schedule
                    if r.workload_id == workload and r.route == route and r.measured
                ]
                self.assertEqual(len(warm), 3)
                self.assertEqual(len(measured), 15)
        self.assertTrue(all(isinstance(item, BenchmarkRequest) for item in schedule))

    def test_loaded_content_matches_gemma_benchmark_contract(self) -> None:
        suite = StageTwoBenchmarkSuite.load(self.path)
        self.assertEqual(suite.suite_id, "gemma-optiq-route-benchmark-v1")
        self.assertEqual(suite.revision, "1")
        self.assertEqual(suite.temperature, 0)
        self.assertTrue(suite.streaming)
        self.assertEqual(len(suite.workloads), 2)
        self.assertEqual(
            suite.workloads[0].prompt,
            "In two sentences, explain why reproducible measurements matter.",
        )
        self.assertEqual(suite.workloads[1].max_tokens, 512)
        self.assertEqual(suite.workloads[1].response_contract, "stage2b-status-tool-json")

    def test_rejects_tampered_suite_file(self) -> None:
        cases = [
            ("third workload", lambda data: data["workloads"].append(dict(data["workloads"][0]))),
            ("changed prompt", lambda data: data["workloads"][0].__setitem__("prompt", "changed")),
            ("changed token limit", lambda data: data["workloads"][0].__setitem__("max_tokens", 127)),
            ("duplicate workload", lambda data: data["workloads"][1].__setitem__("workload_id", "short-chat")),
            ("nonzero temperature", lambda data: data.__setitem__("temperature", 0.1)),
            ("boolean temperature", lambda data: data.__setitem__("temperature", False)),
            ("non-streaming mode", lambda data: data.__setitem__("streaming", False)),
            ("changed response contract", lambda data: data["workloads"][1].__setitem__("response_contract", "text")),
            ("configured schedule", lambda data: data.__setitem__("schedule", [])),
        ]
        for label, mutate in cases:
            with self.subTest(label=label):
                data = json.loads(self.path.read_text())
                mutate(data)
                with tempfile.TemporaryDirectory() as directory:
                    changed = Path(directory) / "changed-suite.json"
                    changed.write_text(json.dumps(data))
                    with self.assertRaises(BenchmarkSuiteError):
                        StageTwoBenchmarkSuite.load(changed)

    def test_schedule_is_not_configurable(self) -> None:
        suite = StageTwoBenchmarkSuite.load(self.path)
        with self.assertRaises(TypeError):
            suite.schedule("anything")  # type: ignore[call-arg]

    def test_validates_only_supported_response_contracts(self) -> None:
        self.assertEqual(StageTwoBenchmarkSuite.validate_response("text", " response "), (True, "PASS"))
        self.assertEqual(StageTwoBenchmarkSuite.validate_response("text", "\n\t"), (False, "EMPTY_TEXT"))
        self.assertEqual(
            StageTwoBenchmarkSuite.validate_response(
                "stage2b-status-tool-json",
                '{"name":"status","arguments":{"run_id":"stage2b-test","include_details":false}}',
            ),
            (True, "PASS"),
        )
        self.assertEqual(
            StageTwoBenchmarkSuite.validate_response("stage2b-status-tool-json", "not-json"),
            (False, "INVALID_JSON"),
        )
        self.assertEqual(
            StageTwoBenchmarkSuite.validate_response("stage2b-status-tool-json", "{}"),
            (False, "JSON_CONTRACT_MISMATCH"),
        )
        self.assertEqual(
            StageTwoBenchmarkSuite.validate_response("unsupported", "anything"),
            (False, "UNSUPPORTED_CONTRACT"),
        )


if __name__ == "__main__":
    unittest.main()
