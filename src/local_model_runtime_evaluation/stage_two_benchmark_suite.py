from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from local_model_runtime_evaluation.stage_two_smoke_suite import StageTwoSmokeSuite


class BenchmarkSuiteError(ValueError):
    pass


@dataclass(frozen=True)
class BenchmarkWorkload:
    workload_id: str
    prompt: str
    max_tokens: int
    response_contract: str


@dataclass(frozen=True)
class BenchmarkRequest:
    workload_id: str
    route: str
    measured: bool
    sequence: int
    repetition: int


_WORKLOADS = (
    BenchmarkWorkload(
        "short-chat",
        "In two sentences, explain why reproducible measurements matter.",
        128,
        "text",
    ),
    BenchmarkWorkload(
        "structured-tool-json",
        "Return exactly this JSON object with no markdown or extra text: "
        '{"name":"status","arguments":{"run_id":"stage2b-test","include_details":false}}',
        512,
        "stage2b-status-tool-json",
    ),
)
_APPROVED_SUITE_IDS = frozenset({
    "gemma-optiq-route-benchmark-v1",
    "gemma-optiq-042-operator-route-benchmark-v1",
})


def _build_schedule() -> tuple[BenchmarkRequest, ...]:
    requests: list[BenchmarkRequest] = []
    sequence = 1
    for workload_id in ("short-chat", "structured-tool-json"):
        start_routed_first = workload_id == "structured-tool-json"
        for rep in range(3):
            routes = ("routed", "direct") if start_routed_first else ("direct", "routed")
            for route in routes:
                requests.append(
                    BenchmarkRequest(workload_id, route, False, sequence, rep)
                )
                sequence += 1
        for rep in range(15):
            routes = ("routed", "direct") if start_routed_first else ("direct", "routed")
            for route in routes:
                requests.append(
                    BenchmarkRequest(workload_id, route, True, sequence, rep)
                )
                sequence += 1
    assert len(requests) == 72 and sequence == 73
    return tuple(requests)


_SCHEDULE = _build_schedule()


def _expected_suite(suite_id: str) -> dict[str, object]:
    return {
        "schema_version": "1.0.0",
        "suite_id": suite_id,
        "revision": "1",
        "temperature": 0,
        "streaming": True,
        "workloads": [
            {
                "workload_id": workload.workload_id,
                "prompt": workload.prompt,
                "max_tokens": workload.max_tokens,
                "response_contract": workload.response_contract,
            }
            for workload in _WORKLOADS
        ],
    }


def _matches_exact(value: object, expected: object) -> bool:
    if type(value) is not type(expected):
        return False
    if isinstance(expected, dict):
        return isinstance(value, dict) and set(value) == set(expected) and all(
            _matches_exact(value[key], expected[key]) for key in expected
        )
    if isinstance(expected, list):
        return isinstance(value, list) and len(value) == len(expected) and all(
            _matches_exact(item, target) for item, target in zip(value, expected)
        )
    return value == expected


@dataclass(frozen=True)
class StageTwoBenchmarkSuite:
    suite_id: str
    revision: str
    temperature: int
    streaming: bool
    workloads: tuple[BenchmarkWorkload, ...]

    @classmethod
    def load(cls, path: Path) -> "StageTwoBenchmarkSuite":
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise BenchmarkSuiteError("benchmark suite is unreadable") from error
        suite_id = data.get("suite_id") if isinstance(data, dict) else None
        if suite_id not in _APPROVED_SUITE_IDS:
            raise BenchmarkSuiteError("benchmark suite does not match the approved contract")
        if not _matches_exact(data, _expected_suite(str(suite_id))):
            raise BenchmarkSuiteError("benchmark suite does not match the approved contract")
        return cls(str(suite_id), "1", 0, True, _WORKLOADS)

    def schedule(self) -> tuple[BenchmarkRequest, ...]:
        return _SCHEDULE

    @staticmethod
    def validate_response(contract: str, content: str) -> tuple[bool, str]:
        return StageTwoSmokeSuite.validate_response(contract, content)
