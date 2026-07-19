from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


class SmokeSuiteError(ValueError):
    pass


@dataclass(frozen=True)
class SmokeWorkload:
    workload_id: str
    prompt: str
    max_tokens: int
    response_contract: str


@dataclass(frozen=True)
class SmokeRequest:
    workload_id: str
    route: str
    measured: bool
    sequence: int
    repetition: int


_WORKLOADS = (
    SmokeWorkload(
        "short-chat",
        "In two sentences, explain why reproducible measurements matter.",
        128,
        "text",
    ),
    SmokeWorkload(
        "structured-tool-json",
        "Return exactly this JSON object with no markdown or extra text: "
        '{"name":"status","arguments":{"run_id":"stage2b-test","include_details":false}}',
        512,
        "stage2b-status-tool-json",
    ),
)
_EXPECTED_SUITE = {
    "schema_version": "1.0.0",
    "suite_id": "optiq-route-smoke-v1",
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
_SCHEDULE = (
    SmokeRequest("short-chat", "direct", False, 1, 0),
    SmokeRequest("short-chat", "routed", False, 2, 0),
    SmokeRequest("short-chat", "direct", True, 3, 1),
    SmokeRequest("short-chat", "routed", True, 4, 1),
    SmokeRequest("structured-tool-json", "routed", False, 5, 0),
    SmokeRequest("structured-tool-json", "direct", False, 6, 0),
    SmokeRequest("structured-tool-json", "routed", True, 7, 1),
    SmokeRequest("structured-tool-json", "direct", True, 8, 1),
)


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
class StageTwoSmokeSuite:
    suite_id: str
    revision: str
    temperature: int
    streaming: bool
    workloads: tuple[SmokeWorkload, ...]

    @classmethod
    def load(cls, path: Path) -> "StageTwoSmokeSuite":
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise SmokeSuiteError("smoke suite is unreadable") from error
        if not _matches_exact(data, _EXPECTED_SUITE):
            raise SmokeSuiteError("smoke suite does not match the approved contract")
        return cls("optiq-route-smoke-v1", "1", 0, True, _WORKLOADS)

    def schedule(self) -> tuple[SmokeRequest, ...]:
        return _SCHEDULE

    @staticmethod
    def validate_response(contract: str, content: str) -> tuple[bool, str]:
        if contract == "text":
            return (True, "PASS") if content.strip() else (False, "EMPTY_TEXT")
        if contract != "stage2b-status-tool-json":
            return False, "UNSUPPORTED_CONTRACT"
        try:
            payload = json.loads(content)
        except (json.JSONDecodeError, TypeError):
            return False, "INVALID_JSON"
        expected = {
            "name": "status",
            "arguments": {"run_id": "stage2b-test", "include_details": False},
        }
        return (
            (True, "PASS")
            if _matches_exact(payload, expected)
            else (False, "JSON_CONTRACT_MISMATCH")
        )
