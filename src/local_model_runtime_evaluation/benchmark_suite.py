from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


class BenchmarkSuiteError(ValueError):
    code = "benchmark_suite_invalid"


@dataclass(frozen=True)
class Workload:
    workload_id: str
    prompt: str
    max_tokens: int
    response_contract: str


@dataclass(frozen=True)
class ScheduledRequest:
    workload_id: str
    route: str
    repetition: int
    measured: bool


@dataclass(frozen=True)
class BenchmarkSuite:
    suite_id: str
    revision: str
    temperature: float
    streaming: bool
    workloads: tuple[Workload, ...]

    @classmethod
    def load(cls, path: Path) -> "BenchmarkSuite":
        data = json.loads(path.read_text(encoding="utf-8"))
        required = {"schema_version", "suite_id", "revision", "temperature", "streaming", "workloads"}
        if not isinstance(data, dict) or set(data) != required or data["schema_version"] != "1.0.0":
            raise BenchmarkSuiteError("suite fields are invalid")
        if data["temperature"] != 0 or data["streaming"] is not True:
            raise BenchmarkSuiteError("suite must be deterministic and streaming")
        items = data["workloads"]
        if not isinstance(items, list) or len(items) != 6:
            raise BenchmarkSuiteError("suite must contain six workloads")
        workloads = tuple(Workload(**item) for item in items)
        if len({item.workload_id for item in workloads}) != 6:
            raise BenchmarkSuiteError("workload IDs must be unique")
        return cls(str(data["suite_id"]), str(data["revision"]), 0.0, True, workloads)

    def schedule(self, repetitions: int) -> tuple[ScheduledRequest, ...]:
        if repetitions != 5:
            raise BenchmarkSuiteError("Stage 1 requires five repetitions")
        result: list[ScheduledRequest] = []
        for index, workload in enumerate(self.workloads):
            first = "direct" if index % 2 == 0 else "routed"
            second = "routed" if first == "direct" else "direct"
            result.extend([
                ScheduledRequest(workload.workload_id, first, 0, False),
                ScheduledRequest(workload.workload_id, second, 0, False),
            ])
            for repetition in range(1, repetitions + 1):
                pair = (first, second) if repetition % 2 else (second, first)
                result.extend(ScheduledRequest(workload.workload_id, route, repetition, True) for route in pair)
        return tuple(result)
