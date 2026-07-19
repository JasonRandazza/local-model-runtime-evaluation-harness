from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from local_model_runtime_evaluation.stage_two_smoke_suite import (
    SmokeRequest,
    SmokeSuiteError,
    StageTwoSmokeSuite,
)


class StageTwoSmokeSuiteTest(unittest.TestCase):
    def setUp(self) -> None:
        self.path = Path(__file__).parents[1] / "suites" / "optiq-route-smoke-v1.json"

    def test_fixed_schedule_is_eight_serial_counterbalanced_requests(self) -> None:
        suite = StageTwoSmokeSuite.load(self.path)
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
                (3, "short-chat", "direct", True, 1),
                (4, "short-chat", "routed", True, 1),
                (5, "structured-tool-json", "routed", False, 0),
                (6, "structured-tool-json", "direct", False, 0),
                (7, "structured-tool-json", "routed", True, 1),
                (8, "structured-tool-json", "direct", True, 1),
            ],
        )
        self.assertTrue(all(isinstance(item, SmokeRequest) for item in suite.schedule()))
        self.assertEqual(sum(item.measured for item in suite.schedule()), 4)

    def test_loaded_content_is_fixed(self) -> None:
        suite = StageTwoSmokeSuite.load(self.path)
        self.assertEqual(suite.suite_id, "optiq-route-smoke-v1")
        self.assertEqual(suite.revision, "1")
        self.assertEqual(suite.temperature, 0)
        self.assertTrue(suite.streaming)
        self.assertEqual(
            suite.workloads[0].prompt,
            "In two sentences, explain why reproducible measurements matter.",
        )
        self.assertEqual(suite.workloads[1].max_tokens, 512)
        self.assertEqual(suite.workloads[1].response_contract, "stage2b-status-tool-json")

    def test_rejects_suite_contract_drift(self) -> None:
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
                    with self.assertRaises(SmokeSuiteError):
                        StageTwoSmokeSuite.load(changed)

    def test_schedule_is_not_configurable(self) -> None:
        suite = StageTwoSmokeSuite.load(self.path)
        with self.assertRaises(TypeError):
            suite.schedule("anything")  # type: ignore[call-arg]

    def test_validates_only_supported_response_contracts(self) -> None:
        self.assertEqual(StageTwoSmokeSuite.validate_response("text", " response "), (True, "PASS"))
        self.assertEqual(StageTwoSmokeSuite.validate_response("text", "\n\t"), (False, "EMPTY_TEXT"))
        self.assertEqual(
            StageTwoSmokeSuite.validate_response(
                "stage2b-status-tool-json",
                '{"name":"status","arguments":{"run_id":"stage2b-test","include_details":false}}',
            ),
            (True, "PASS"),
        )
        self.assertEqual(
            StageTwoSmokeSuite.validate_response("stage2b-status-tool-json", "not-json"),
            (False, "INVALID_JSON"),
        )
        self.assertEqual(
            StageTwoSmokeSuite.validate_response("stage2b-status-tool-json", "{}"),
            (False, "JSON_CONTRACT_MISMATCH"),
        )
        self.assertEqual(
            StageTwoSmokeSuite.validate_response(
                "stage2b-status-tool-json",
                '{"name":"status","arguments":{"run_id":"stage2b-test","include_details":0}}',
            ),
            (False, "JSON_CONTRACT_MISMATCH"),
        )
        self.assertEqual(
            StageTwoSmokeSuite.validate_response("unsupported", "anything"),
            (False, "UNSUPPORTED_CONTRACT"),
        )


if __name__ == "__main__":
    unittest.main()
