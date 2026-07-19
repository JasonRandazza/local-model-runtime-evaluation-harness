from __future__ import annotations

import argparse
import json
import subprocess
import time
from typing import Callable, Mapping, Sequence

from .lifecycle import LifecycleStore
from .manifest import CANONICAL_OUTPUT_ROOT, STAGE_ONE_RUN_ID_PATTERN, STAGE_TWO_RUN_ID_PATTERN


TERMINAL_STATES = frozenset({"awaiting_review", "failed", "cancelled", "cleaned"})


def wait_for_review(
    run_id: str,
    read_status: Callable[[str], Mapping[str, object]],
    sleep: Callable[[float], None] = time.sleep,
    poll_seconds: float = 30,
    on_poll: Callable[[Mapping[str, object]], None] | None = None,
) -> dict[str, object]:
    if not (STAGE_ONE_RUN_ID_PATTERN.fullmatch(run_id) or STAGE_TWO_RUN_ID_PATTERN.fullmatch(run_id)):
        raise ValueError("a valid Stage 1 or Stage 2 run ID is required")
    if poll_seconds <= 0:
        raise ValueError("poll interval must be positive")
    poll_count = 0
    while True:
        status = dict(read_status(run_id))
        poll_count += 1
        if on_poll is not None:
            on_poll(status)
        state = status.get("state")
        if not isinstance(state, str):
            raise RuntimeError("persisted run state is unavailable")
        if state in TERMINAL_STATES:
            operator_shutdown_required = (
                run_id.startswith("stage2-")
                and state in {"awaiting_review", "failed", "cancelled"}
            )
            result: dict[str, object] = {
                "overall": (
                    "OPERATOR_SHUTDOWN_REQUIRED"
                    if operator_shutdown_required
                    else "READY_FOR_COORDINATOR"
                    if state == "awaiting_review"
                    else "MANAGER_REVIEW_REQUIRED"
                ),
                "run_id": run_id,
                "state": state,
                "sequence": status.get("sequence"),
                "poll_count": poll_count,
                "manager_review_required": True,
            }
            if operator_shutdown_required:
                result.update({
                    "operator_action_required": True,
                    "operator_action": (
                        "Stop the foreground OptiQ service before requesting Coordinator cleanup."
                    ),
                })
            return result
        sleep(poll_seconds)


def _read_status(run_id: str) -> dict[str, object]:
    state = LifecycleStore(CANONICAL_OUTPUT_ROOT).read(run_id)
    return {"run_id": run_id, "state": state.status.value, "sequence": state.sequence}


def _notify(run_id: str, state: str) -> None:
    message = f"{run_id} reached {state}."
    stage = "Stage 2" if run_id.startswith("stage2-") else "Stage 1"
    subprocess.run(
        [
            "/usr/bin/osascript", "-e",
            f'display notification "{message}" with title "LMRE {stage}"',
        ],
        capture_output=True, check=False, timeout=10,
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="lmre-stage-wait")
    parser.add_argument("run_id")
    parser.add_argument("--poll-seconds", type=float, default=30)
    parser.add_argument("--no-notify", action="store_true")
    arguments = parser.parse_args(argv)
    last_state: str | None = None

    def report(status: Mapping[str, object]) -> None:
        nonlocal last_state
        state = str(status.get("state", "unknown"))
        if state != last_state:
            print(f"{arguments.run_id}: {state}", flush=True)
            last_state = state

    try:
        result = wait_for_review(
            arguments.run_id, _read_status, time.sleep, arguments.poll_seconds, report,
        )
        if not arguments.no_notify:
            _notify(arguments.run_id, str(result["state"]))
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0 if result["state"] == "awaiting_review" else 1
    except Exception as error:
        print(json.dumps({
            "overall": "STOPPED",
            "error_kind": getattr(error, "code", error.__class__.__name__),
            "message": str(error),
            "manager_review_required": True,
        }, indent=2, sort_keys=True))
        return 1
