"""Personal Model Selection Phase A: Osaurus-front-door daily-driver screens.

ponytail: one module, no Stage 0-2B lifecycle; good enough for jumping-off data.
"""

from __future__ import annotations

import argparse
import json
import statistics
import threading
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

from .measurement import validate_response_contract
from .resources import HostResourceProbe
from .transport import LoopbackTransport, TransportError


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SUITE = REPOSITORY_ROOT / "suites" / "personal-selection-v1.json"
DEFAULT_RESULTS = REPOSITORY_ROOT / "results" / "personal-selection"
OSAURUS_BASE = "http://127.0.0.1:1337/v1"

MODES = {
    "screen": {"warmup": 1, "measured": 3},
    "finalist": {"warmup": 1, "measured": 5},
}


class PersonalSelectionError(RuntimeError):
    code = "personal_selection_failed"


@dataclass(frozen=True)
class Lane:
    lane_id: str
    family: str
    comparison_class: str
    path_type: str
    base_url: str
    model_id: str
    artifact_hint: str
    notes: str

    @classmethod
    def load(cls, path: Path) -> "Lane":
        data = json.loads(path.read_text(encoding="utf-8"))
        required = {
            "lane_id", "family", "comparison_class", "path_type",
            "base_url", "model_id", "artifact_hint", "notes",
        }
        if not isinstance(data, dict) or set(data) != required:
            raise PersonalSelectionError("lane fields are invalid")
        if data["base_url"] != OSAURUS_BASE:
            raise PersonalSelectionError("Phase A only allows the Osaurus loopback endpoint")
        if data["comparison_class"] != "native-best-stack":
            raise PersonalSelectionError("Phase A lanes must be native-best-stack")
        return cls(**{key: str(data[key]) for key in required})


@dataclass(frozen=True)
class Workload:
    workload_id: str
    prompt: str
    max_tokens: int
    response_contract: str


@dataclass(frozen=True)
class Suite:
    suite_id: str
    revision: str
    workloads: tuple[Workload, ...]

    @classmethod
    def load(cls, path: Path) -> "Suite":
        data = json.loads(path.read_text(encoding="utf-8"))
        required = {
            "schema_version", "suite_id", "revision", "temperature", "streaming", "workloads",
        }
        if not isinstance(data, dict) or set(data) != required or data["schema_version"] != "1.0.0":
            raise PersonalSelectionError("suite fields are invalid")
        if data["temperature"] != 0 or data["streaming"] is not True:
            raise PersonalSelectionError("suite must be deterministic and streaming")
        items = data["workloads"]
        if not isinstance(items, list) or len(items) != 3:
            raise PersonalSelectionError("suite must contain exactly three workloads")
        workloads = tuple(
            Workload(
                str(item["workload_id"]),
                str(item["prompt"]),
                int(item["max_tokens"]),
                str(item["response_contract"]),
            )
            for item in items
        )
        if len({item.workload_id for item in workloads}) != 3:
            raise PersonalSelectionError("workload IDs must be unique")
        return cls(str(data["suite_id"]), str(data["revision"]), workloads)


@dataclass(frozen=True)
class Observation:
    workload_id: str
    repetition: int
    measured: bool
    success: bool
    total_seconds: float | None
    finish_reason: str | None
    response_contract_valid: bool
    response_contract_status: str
    completion_tokens: int | None
    visible_output_tokens: int | None
    token_accounting_status: str | None
    ttft_seconds: float | None
    streaming_semantics: str | None
    error: str | None

    def as_json(self) -> dict[str, object]:
        return asdict(self)


def _memory_percent(probe: HostResourceProbe | None) -> int | None:
    if probe is None:
        return None
    return probe.free_memory_percent()


def _require_model(transport: LoopbackTransport, lane: Lane) -> tuple[str, ...]:
    try:
        models = transport.list_models(lane.base_url, None)
    except TransportError as error:
        raise PersonalSelectionError(f"Osaurus model inventory failed: {error}") from error
    if lane.model_id not in models:
        raise PersonalSelectionError(
            f"exact model id {lane.model_id!r} not present; inventory={list(models)}"
        )
    return models


def _run_one(
    transport: LoopbackTransport,
    lane: Lane,
    workload: Workload,
    repetition: int,
    measured: bool,
    cancel: threading.Event,
) -> Observation:
    if cancel.is_set():
        raise PersonalSelectionError("cancelled before request")
    try:
        result = transport.chat(
            lane.base_url, lane.model_id, workload.prompt, workload.max_tokens, None, cancel,
        )
    except TransportError as error:
        return Observation(
            workload.workload_id, repetition, measured, False, None, None,
            False, "TRANSPORT_FAILED", None, None, None, None, None, str(error),
        )
    content_span = max(0.0, result.last_content_seconds - result.ttft_seconds)
    streaming = (
        "incremental"
        if result.content_event_count >= 2 and content_span >= 0.01
        else "buffered"
    )
    # ponytail: leave TTFT null when buffered; Stage 1 already proved that path lies
    ttft = None if streaming != "incremental" else result.ttft_seconds
    valid, status = validate_response_contract(workload.response_contract, result.content)
    return Observation(
        workload.workload_id, repetition, measured, True, result.total_seconds,
        result.finish_reason, valid, status, result.completion_tokens,
        result.visible_output_tokens, result.token_accounting_status, ttft, streaming, None,
    )


def _median(values: list[float]) -> float | None:
    return None if not values else float(statistics.median(values))


def summarize(observations: tuple[Observation, ...]) -> dict[str, object]:
    measured = [item for item in observations if item.measured]
    by_workload: dict[str, object] = {}
    for workload_id in sorted({item.workload_id for item in measured}):
        rows = [item for item in measured if item.workload_id == workload_id]
        times = [item.total_seconds for item in rows if item.success and item.total_seconds is not None]
        contracts = sum(1 for item in rows if item.response_contract_valid)
        by_workload[workload_id] = {
            "measured_count": len(rows),
            "success_count": sum(1 for item in rows if item.success),
            "contract_pass_count": contracts,
            "median_total_seconds": _median(times),
            "min_total_seconds": min(times) if times else None,
            "max_total_seconds": max(times) if times else None,
        }
    overall_times = [
        item.total_seconds for item in measured
        if item.success and item.total_seconds is not None
    ]
    return {
        "measured_count": len(measured),
        "success_count": sum(1 for item in measured if item.success),
        "contract_pass_count": sum(1 for item in measured if item.response_contract_valid),
        "median_total_seconds": _median(overall_times),
        "by_workload": by_workload,
    }


def render_report(bundle: dict[str, object]) -> str:
    lane = bundle["lane"]
    summary = bundle["summary"]
    lines = [
        "# Personal Model Selection Draft Report",
        "",
        f"- lane: `{lane['lane_id']}`",
        f"- family: `{lane['family']}`",
        f"- path: `{lane['path_type']}`",
        f"- model_id: `{lane['model_id']}`",
        f"- comparison_class: `{lane['comparison_class']}`",
        f"- mode: `{bundle['mode']}`",
        f"- suite: `{bundle['suite_id']}` revision `{bundle['suite_revision']}`",
        f"- started: `{bundle['started_at']}`",
        f"- finished: `{bundle['finished_at']}`",
        f"- memory free % before/after: `{bundle['memory_free_percent_before']}` / `{bundle['memory_free_percent_after']}`",
        "",
        "## Summary",
        "",
        f"- measured: {summary['measured_count']}",
        f"- success: {summary['success_count']}",
        f"- contract passes: {summary['contract_pass_count']}",
        f"- median total seconds: {summary['median_total_seconds']}",
        "",
        "## By workload",
        "",
    ]
    for workload_id, stats in summary["by_workload"].items():
        lines.append(
            f"- `{workload_id}`: median={stats['median_total_seconds']}s "
            f"success={stats['success_count']}/{stats['measured_count']} "
            f"contracts={stats['contract_pass_count']}/{stats['measured_count']}"
        )
    lines.extend([
        "",
        "## Interpretation guardrails",
        "",
        "- This is a native-best-stack / cross-quant jumping-off point, not same-artifact science.",
        "- TTFT and decode are omitted when streaming evidence is buffered or untrusted.",
        "- Do not update Deep Wiki policy until a human reviews this draft.",
        "",
    ])
    return "\n".join(lines)


def run_lane(
    lane: Lane,
    suite: Suite,
    mode: str,
    results_dir: Path,
    transport: LoopbackTransport | None = None,
    resource_probe: HostResourceProbe | None = None,
    cancel: threading.Event | None = None,
) -> Path:
    if mode not in MODES:
        raise PersonalSelectionError(f"unknown mode {mode!r}")
    counts = MODES[mode]
    cancel = cancel or threading.Event()
    transport = transport or LoopbackTransport({lane.base_url})
    probe = resource_probe if resource_probe is not None else HostResourceProbe()

    inventory = _require_model(transport, lane)
    memory_before = _memory_percent(probe)
    started = datetime.now(timezone.utc).isoformat()
    observations: list[Observation] = []

    for workload in suite.workloads:
        for repetition in range(counts["warmup"]):
            observations.append(
                _run_one(transport, lane, workload, repetition, False, cancel)
            )
        for repetition in range(1, counts["measured"] + 1):
            observations.append(
                _run_one(transport, lane, workload, repetition, True, cancel)
            )

    finished = datetime.now(timezone.utc).isoformat()
    memory_after = _memory_percent(probe)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    run_dir = results_dir / f"{lane.lane_id}-{mode}-{stamp}"
    run_dir.mkdir(parents=True, exist_ok=False)

    bundle = {
        "schema_version": "personal-selection-1.0.0",
        "mode": mode,
        "suite_id": suite.suite_id,
        "suite_revision": suite.revision,
        "lane": asdict(lane),
        "inventory_model_ids": list(inventory),
        "started_at": started,
        "finished_at": finished,
        "memory_free_percent_before": memory_before,
        "memory_free_percent_after": memory_after,
        "warmup_per_workload": counts["warmup"],
        "measured_per_workload": counts["measured"],
        "observations": [item.as_json() for item in observations],
        "summary": summarize(tuple(observations)),
    }
    (run_dir / "raw.json").write_text(json.dumps(bundle, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report = render_report(bundle)
    (run_dir / "report.md").write_text(report, encoding="utf-8")
    return run_dir


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="lmre-personal-select",
        description="Phase A personal model selection via the Osaurus endpoint only.",
    )
    parser.add_argument("--lane", type=Path, required=True, help="Lane JSON under config/personal-selection/lanes/")
    parser.add_argument("--mode", choices=sorted(MODES), default="screen")
    parser.add_argument("--suite", type=Path, default=DEFAULT_SUITE)
    parser.add_argument("--results-dir", type=Path, default=DEFAULT_RESULTS)
    parser.add_argument(
        "--dry-inventory",
        action="store_true",
        help="Only verify the exact model id is present; no chat requests.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        lane = Lane.load(args.lane)
        suite = Suite.load(args.suite)
        transport = LoopbackTransport({lane.base_url})
        if args.dry_inventory:
            models = _require_model(transport, lane)
            print(json.dumps({"ok": True, "model_id": lane.model_id, "inventory": list(models)}, sort_keys=True))
            return 0
        run_dir = run_lane(lane, suite, args.mode, args.results_dir, transport=transport)
        print(json.dumps({"ok": True, "run_dir": str(run_dir)}, sort_keys=True))
        return 0
    except Exception as error:
        print(json.dumps({
            "ok": False,
            "error": {"kind": getattr(error, "code", error.__class__.__name__), "message": str(error)},
        }, sort_keys=True))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
