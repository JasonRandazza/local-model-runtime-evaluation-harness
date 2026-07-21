from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from .models import RunState, RunStatus


LEGAL_TRANSITIONS = {
    RunStatus.QUEUED: {RunStatus.PREFLIGHT, RunStatus.CANCELLED, RunStatus.FAILED},
    RunStatus.PREFLIGHT: {RunStatus.READY, RunStatus.RESOURCE_GATE, RunStatus.CANCELLED, RunStatus.FAILED},
    RunStatus.RESOURCE_GATE: {
        RunStatus.ENDPOINT_IDENTITY, RunStatus.READY, RunStatus.CANCELLED, RunStatus.FAILED,
    },
    RunStatus.ENDPOINT_IDENTITY: {
        RunStatus.READY, RunStatus.SERVICE_STOPPING, RunStatus.ARTIFACT_VALIDATION,
        RunStatus.CANCELLED, RunStatus.FAILED,
    },
    RunStatus.READY: {RunStatus.RUNNING, RunStatus.WARMUP, RunStatus.CANCELLED, RunStatus.FAILED},
    RunStatus.WARMUP: {RunStatus.MEASURED, RunStatus.CANCELLED, RunStatus.FAILED},
    RunStatus.MEASURED: {RunStatus.ARTIFACT_VALIDATION, RunStatus.CANCELLED, RunStatus.FAILED},
    RunStatus.ARTIFACT_VALIDATION: {RunStatus.AWAITING_REVIEW, RunStatus.CANCELLED, RunStatus.FAILED},
    RunStatus.AWAITING_REVIEW: {RunStatus.CLEANED},
    RunStatus.RUNNING: {
        RunStatus.WARMUP, RunStatus.SERVICE_STARTING, RunStatus.SERVICE_READY, RunStatus.CANCELLED,
        RunStatus.COMPLETE, RunStatus.FAILED,
    },
    RunStatus.SERVICE_STARTING: {RunStatus.SERVICE_READY, RunStatus.SERVICE_STOPPING, RunStatus.FAILED},
    RunStatus.SERVICE_READY: {RunStatus.ENDPOINT_IDENTITY, RunStatus.SERVICE_STOPPING, RunStatus.FAILED},
    RunStatus.SERVICE_STOPPING: {RunStatus.ARTIFACT_VALIDATION, RunStatus.CANCELLED, RunStatus.FAILED},
    RunStatus.CANCELLED: {RunStatus.CLEANED},
    RunStatus.FAILED: {RunStatus.CLEANED},
    RunStatus.COMPLETE: {RunStatus.CLEANED},
    RunStatus.CLEANED: set(),
}


class LifecycleError(RuntimeError):
    pass


class LifecycleStore:
    def __init__(self, output_root: Path) -> None:
        self.output_root = output_root

    def _directory(self, run_id: str) -> Path:
        return self.output_root / run_id

    def _write(self, state: RunState) -> None:
        directory = self._directory(state.run_id)
        directory.mkdir(parents=True, exist_ok=True)
        payload = asdict(state)
        payload["status"] = state.status.value
        temporary = directory / "state.json.tmp"
        temporary.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")
        temporary.replace(directory / "state.json")
        with (directory / "lifecycle.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, sort_keys=True) + "\n")

    def create(self, run_id: str) -> RunState:
        state_path = self._directory(run_id) / "state.json"
        if state_path.exists():
            return self.read(run_id)
        state = RunState(
            run_id=run_id,
            status=RunStatus.QUEUED,
            sequence=0,
            updated_at=datetime.now(timezone.utc).isoformat(),
            reason="run created",
        )
        self._write(state)
        return state

    def read(self, run_id: str) -> RunState:
        try:
            data = json.loads((self._directory(run_id) / "state.json").read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise LifecycleError(f"state is unavailable for {run_id}") from error
        return RunState(
            run_id=data["run_id"],
            status=RunStatus(data["status"]),
            sequence=int(data["sequence"]),
            updated_at=data["updated_at"],
            reason=data["reason"],
        )

    def history(self, run_id: str) -> list[str]:
        try:
            lines = (self._directory(run_id) / "lifecycle.jsonl").read_text(encoding="utf-8").splitlines()
            return [str(json.loads(line)["status"]) for line in lines]
        except (OSError, KeyError, TypeError, json.JSONDecodeError) as error:
            raise LifecycleError(f"lifecycle history is unavailable for {run_id}") from error

    def raw_lines(self, run_id: str) -> tuple[str, ...]:
        try:
            return tuple(
                (self._directory(run_id) / "lifecycle.jsonl").read_text(encoding="utf-8").splitlines()
            )
        except OSError as error:
            raise LifecycleError(f"lifecycle history is unavailable for {run_id}") from error

    def verified_history(self, run_id: str) -> tuple[str, ...]:
        """Replay every persisted lifecycle row and fail closed on tampering.

        Unlike ``history``/``raw_lines``, this rejects any row that is out of
        sequence, references another run, or is not a legal successor of the
        previous row, so appended, removed, reordered, duplicated, or modified
        rows cannot be re-checksummed as if they were authentic evidence.
        """
        lines = self.raw_lines(run_id)
        previous_status: RunStatus | None = None
        for index, line in enumerate(lines):
            try:
                payload = json.loads(line)
                record_run_id = str(payload["run_id"])
                status = RunStatus(payload["status"])
                sequence = int(payload["sequence"])
            except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
                raise LifecycleError(
                    f"lifecycle history row {index} is malformed for {run_id}"
                ) from error
            if record_run_id != run_id or sequence != index:
                raise LifecycleError(f"lifecycle history is not contiguous for {run_id}")
            if index == 0:
                if status is not RunStatus.QUEUED:
                    raise LifecycleError(f"lifecycle history does not begin at queued for {run_id}")
            elif status not in LEGAL_TRANSITIONS[previous_status] and not (
                status is previous_status and status in {RunStatus.CANCELLED, RunStatus.CLEANED}
            ):
                raise LifecycleError(
                    f"lifecycle history row {index} is an illegal transition for {run_id}"
                )
            previous_status = status
        return lines

    def transition(self, run_id: str, target: RunStatus, reason: str) -> RunState:
        current = self.read(run_id)
        if current.status == target and target in {RunStatus.CANCELLED, RunStatus.CLEANED}:
            return current
        if target not in LEGAL_TRANSITIONS[current.status]:
            raise LifecycleError(f"illegal transition: {current.status.value} -> {target.value}")
        state = RunState(
            run_id=run_id,
            status=target,
            sequence=current.sequence + 1,
            updated_at=datetime.now(timezone.utc).isoformat(),
            reason=reason,
        )
        self._write(state)
        return state
