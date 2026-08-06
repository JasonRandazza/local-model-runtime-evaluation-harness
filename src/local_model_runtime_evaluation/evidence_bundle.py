"""Atomic, checksummed evidence bundles for managed local runs."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from .managed_run_types import (
    ManagedRunPlan,
    ManagedRunState,
    ManagedStep,
    Ownership,
    RunSummaryState,
    StepRecord,
    StepState,
)
from .operator_policy import AdoptedPolicy
from .run_identity import RunIdentityError, verify_plan_hash


CHECKSUM_FILENAME = "checksums.sha256"
EPHEMERAL_FILENAMES = frozenset({".resume.lock"})
SECRET_KEY_FRAGMENTS = (
    "api_key",
    "authorization",
    "credential",
    "password",
    "secret",
    "token",
)
CHECKSUM_LINE = re.compile(r"([0-9a-f]{64})  (.+)")
ALLOWED_STEP_TRANSITIONS = {
    StepState.PENDING: {
        StepState.RUNNING,
        StepState.STOPPED,
    },
    StepState.RUNNING: {
        StepState.PASS,
        StepState.FAIL,
        StepState.BLOCKED_PROVIDER_RECONNECT,
        StepState.STOPPED,
        StepState.INCOMPARABLE,
    },
    StepState.BLOCKED_PROVIDER_RECONNECT: {
        StepState.RUNNING,
    },
    StepState.PASS: set(),
    StepState.FAIL: set(),
    StepState.STOPPED: set(),
    StepState.INCOMPARABLE: set(),
}


def resume_is_allowed(state: ManagedRunState) -> bool:
    overhead = next(
        (
            record
            for record in state.steps
            if record.step is ManagedStep.OVERHEAD
        ),
        None,
    )
    if not state.sealed or not state.cleanup_complete or overhead is None:
        return False
    provider_blocked = (
        state.summary_state is RunSummaryState.PARTIAL_BLOCKED
        and overhead.state is StepState.BLOCKED_PROVIDER_RECONNECT
    )
    overhead_failed = (
        state.summary_state is RunSummaryState.FAIL
        and overhead.state is StepState.FAIL
        and all(
            record.state is StepState.PASS
            for record in state.steps
            if record.step is not ManagedStep.OVERHEAD
        )
    )
    return provider_blocked or overhead_failed


class EvidenceError(RuntimeError):
    code = "evidence_invalid"

    def __init__(
        self,
        message: str,
        *,
        code: str = "evidence_invalid",
    ) -> None:
        super().__init__(message)
        self.code = code


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def _reject_secrets(value: object, path: str = "payload") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if not isinstance(key, str):
                raise EvidenceError(
                    f"{path} contains a non-string key",
                    code="evidence_secret_rejected",
                )
            lowered = key.lower()
            if any(fragment in lowered for fragment in SECRET_KEY_FRAGMENTS):
                raise EvidenceError(
                    f"{path} contains a secret-shaped key",
                    code="evidence_secret_rejected",
                )
            _reject_secrets(child, f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            _reject_secrets(child, f"{path}[{index}]")


def _atomic_json(path: Path, body: dict[str, object]) -> None:
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(
        json.dumps(body, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class EvidenceBundle:
    def __init__(self, run_dir: Path, plan: ManagedRunPlan) -> None:
        self.run_dir = run_dir
        self.plan = plan

    @classmethod
    def create(
        cls,
        results_root: Path,
        plan: ManagedRunPlan,
        adopted_policy: AdoptedPolicy,
        environment: dict[str, object],
    ) -> EvidenceBundle:
        try:
            verify_plan_hash(plan)
        except RunIdentityError as error:
            raise EvidenceError(
                str(error),
                code="evidence_plan_invalid",
            ) from error
        _reject_secrets(environment, "environment")
        run_dir = results_root / plan.identity.run_id
        try:
            run_dir.mkdir(parents=True, exist_ok=False)
        except FileExistsError as error:
            raise EvidenceError(
                f"run evidence already exists: {plan.identity.run_id}",
                code="evidence_run_exists",
            ) from error

        _atomic_json(run_dir / "plan.json", plan.to_dict())
        _atomic_json(
            run_dir / "policy-snapshot.json",
            {
                "adopted_at": adopted_policy.adopted_at,
                "policy": adopted_policy.policy.to_dict(),
                "policy_hash": adopted_policy.policy_hash,
            },
        )
        _atomic_json(run_dir / "environment.json", environment)
        state = ManagedRunState(
            run_id=plan.identity.run_id,
            attempt=1,
            summary_state=RunSummaryState.PENDING,
            steps=tuple(
                StepRecord(
                    step=step,
                    state=StepState.PENDING,
                    attempt=1,
                )
                for step in plan.steps
            ),
            cleanup_complete=False,
            sealed=False,
        )
        _atomic_json(run_dir / "state.json", state.to_dict())
        return cls(run_dir, plan)

    @classmethod
    def load(cls, run_dir: Path) -> EvidenceBundle:
        plan_path = run_dir / "plan.json"
        if not plan_path.is_file():
            raise EvidenceError(
                "managed run plan is missing",
                code="evidence_file_missing",
            )
        try:
            raw = json.loads(plan_path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                raise ValueError("plan must be an object")
            plan = ManagedRunPlan.from_dict(raw)
            verify_plan_hash(plan)
        except (
            OSError,
            json.JSONDecodeError,
            ValueError,
            RunIdentityError,
        ) as error:
            raise EvidenceError(
                "managed run plan is invalid",
                code="evidence_plan_invalid",
            ) from error
        return cls(run_dir, plan)

    @property
    def state(self) -> ManagedRunState:
        path = self.run_dir / "state.json"
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                raise ValueError("state must be an object")
            return ManagedRunState.from_dict(raw)
        except (OSError, json.JSONDecodeError, ValueError) as error:
            raise EvidenceError(
                "managed run state is invalid",
                code="evidence_state_invalid",
            ) from error

    def _write_state(self, state: ManagedRunState) -> None:
        _atomic_json(self.run_dir / "state.json", state.to_dict())

    def _require_mutable(self) -> ManagedRunState:
        state = self.state
        if state.sealed:
            raise EvidenceError(
                "sealed evidence is immutable",
                code="evidence_sealed",
            )
        return state

    def _append_jsonl(self, filename: str, body: dict[str, object]) -> None:
        _reject_secrets(body)
        path = self.run_dir / filename
        with path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(body, sort_keys=True) + "\n")
            stream.flush()

    def append_event(
        self,
        event_type: str,
        payload: dict[str, object],
    ) -> None:
        state = self._require_mutable()
        self._append_jsonl(
            "events.jsonl",
            {
                "attempt": state.attempt,
                "event_type": event_type,
                "payload": payload,
                "timestamp": _utc_timestamp(),
            },
        )

    def append_lifecycle(
        self,
        runtime: str,
        action: str,
        payload: dict[str, object],
    ) -> None:
        state = self._require_mutable()
        self._append_jsonl(
            "lifecycle.jsonl",
            {
                "action": action,
                "attempt": state.attempt,
                "payload": payload,
                "runtime": runtime,
                "timestamp": _utc_timestamp(),
            },
        )

    def transition_step(
        self,
        step: ManagedStep,
        new_state: StepState,
        *,
        detail: dict[str, object] | None = None,
        output_path: str | None = None,
    ) -> None:
        state = self._require_mutable()
        records = list(state.steps)
        try:
            index = next(
                position
                for position, record in enumerate(records)
                if record.step is step
            )
        except StopIteration as error:
            raise EvidenceError(
                f"step is not in managed plan: {step.value}",
                code="evidence_transition_invalid",
            ) from error
        current = records[index]
        if new_state not in ALLOWED_STEP_TRANSITIONS[current.state]:
            raise EvidenceError(
                f"invalid transition {current.state.value} -> {new_state.value}",
                code="evidence_transition_invalid",
            )
        resolved_detail = {} if detail is None else detail
        _reject_secrets(resolved_detail, "step detail")
        if output_path is not None:
            pure = PurePosixPath(output_path)
            if pure.is_absolute() or ".." in pure.parts:
                raise EvidenceError(
                    "step output_path must be run-relative",
                    code="evidence_path_invalid",
                )
        records[index] = StepRecord(
            step=step,
            state=new_state,
            attempt=state.attempt,
            output_path=output_path,
            detail=resolved_detail,
        )
        summary_state = state.summary_state
        if (
            new_state is StepState.RUNNING
            and summary_state is RunSummaryState.PENDING
        ):
            summary_state = RunSummaryState.RUNNING
        self._write_state(
            replace(
                state,
                summary_state=summary_state,
                steps=tuple(records),
            )
        )
        self.append_event(
            "step_transition",
            {
                "from": current.state.value,
                "step": step.value,
                "to": new_state.value,
            },
        )

    def mark_cleanup_complete(self) -> None:
        state = self._require_mutable()
        self._write_state(replace(state, cleanup_complete=True))

    def write_summary(self, summary: dict[str, object]) -> None:
        state = self._require_mutable()
        _reject_secrets(summary, "summary")
        status = summary.get("status")
        if not isinstance(status, str):
            raise EvidenceError("summary status is missing")
        try:
            summary_state = RunSummaryState(status)
        except ValueError as error:
            raise EvidenceError("summary status is invalid") from error
        _atomic_json(self.run_dir / "summary.json", summary)
        self._write_state(replace(state, summary_state=summary_state))

    def step_attempt_dir(
        self,
        step: ManagedStep,
        attempt: int,
    ) -> Path:
        if step not in self.plan.steps or type(attempt) is not int or attempt <= 0:
            raise EvidenceError(
                "step attempt path is invalid",
                code="evidence_path_invalid",
            )
        return self.run_dir / "steps" / step.value / f"attempt-{attempt:03d}"

    def begin_attempt(self) -> int:
        state = self.state
        if not resume_is_allowed(state):
            raise EvidenceError(
                "only a sealed overhead-only retry may resume",
                code="evidence_resume_not_allowed",
            )
        attempts_dir = self.run_dir / "attempts"
        attempts_dir.mkdir(parents=True, exist_ok=True)
        summary_path = self.run_dir / "summary.json"
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        snapshot: dict[str, object] = {
            "attempt": state.attempt,
            "state": state.to_dict(),
            "summary": summary,
        }
        manifest = self.run_dir / CHECKSUM_FILENAME
        if manifest.is_file():
            snapshot["checksums_sha256"] = manifest.read_text(encoding="utf-8")
        _atomic_json(
            attempts_dir / f"attempt-{state.attempt:03d}.json",
            snapshot,
        )
        records = tuple(
            StepRecord(
                step=record.step,
                state=(
                    StepState.PENDING
                    if record.step is ManagedStep.OVERHEAD
                    else record.state
                ),
                attempt=(
                    state.attempt + 1
                    if record.step is ManagedStep.OVERHEAD
                    else record.attempt
                ),
                output_path=None if record.step is ManagedStep.OVERHEAD else record.output_path,
                detail={} if record.step is ManagedStep.OVERHEAD else record.detail,
            )
            for record in state.steps
        )
        next_state = replace(
            state,
            attempt=state.attempt + 1,
            steps=records,
            cleanup_complete=False,
            sealed=False,
        )
        self._write_state(next_state)
        self.append_event(
            "attempt_started",
            {"attempt": next_state.attempt},
        )
        return next_state.attempt

    def _lifecycle_is_closed(self) -> bool:
        path = self.run_dir / "lifecycle.jsonl"
        if not path.is_file():
            return True
        acquired: dict[tuple[int, str], Ownership] = {}
        terminal: dict[tuple[int, str], str] = {}
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
            for line in lines:
                entry = json.loads(line)
                if not isinstance(entry, dict):
                    return False
                action = entry.get("action")
                payload = entry.get("payload")
                if not isinstance(action, str) or not isinstance(payload, dict):
                    return False
                lease_id = payload.get("lease_id")
                if not isinstance(lease_id, str) or not lease_id:
                    continue
                attempt = entry.get("attempt")
                if type(attempt) is not int or attempt < 1:
                    return False
                lease_key = (attempt, lease_id)
                if action == "lease_acquired":
                    ownership = payload.get("ownership")
                    if lease_key in acquired or not isinstance(ownership, str):
                        return False
                    acquired[lease_key] = Ownership(ownership)
                elif action in {"released", "untouched"}:
                    if lease_key in terminal:
                        return False
                    terminal[lease_key] = action
        except (OSError, json.JSONDecodeError, ValueError):
            return False
        for lease_key, ownership in acquired.items():
            expected = (
                "untouched"
                if ownership is Ownership.ATTACHED
                else "released"
            )
            if terminal.get(lease_key) != expected:
                return False
        return not (set(terminal) - set(acquired))

    def _evidence_files(self) -> dict[str, Path]:
        files: dict[str, Path] = {}
        for path in self.run_dir.rglob("*"):
            if not path.is_file() or path.is_symlink():
                continue
            if (
                path.name == CHECKSUM_FILENAME
                or path.name in EPHEMERAL_FILENAMES
                or path.name.endswith(".tmp")
            ):
                continue
            relative = path.relative_to(self.run_dir).as_posix()
            files[relative] = path
        return files

    def seal(self) -> Path:
        state = self._require_mutable()
        if not state.cleanup_complete:
            raise EvidenceError(
                "owned runtime cleanup is incomplete",
                code="evidence_cleanup_incomplete",
            )
        if not self._lifecycle_is_closed():
            raise EvidenceError(
                "runtime lifecycle evidence is incomplete",
                code="evidence_lifecycle_incomplete",
            )
        if not (self.run_dir / "summary.json").is_file():
            raise EvidenceError("summary is missing")
        if state.summary_state in {
            RunSummaryState.PENDING,
            RunSummaryState.RUNNING,
        }:
            raise EvidenceError("summary is not terminal")
        try:
            verify_plan_hash(self.plan)
        except RunIdentityError as error:
            raise EvidenceError(
                "managed run plan hash mismatch",
                code="evidence_plan_invalid",
            ) from error

        self._write_state(replace(state, sealed=True))
        lines = [
            f"{_sha256(path)}  {relative}"
            for relative, path in sorted(self._evidence_files().items())
        ]
        manifest = self.run_dir / CHECKSUM_FILENAME
        temporary = manifest.with_name(f"{manifest.name}.tmp")
        temporary.write_text("\n".join(lines) + "\n", encoding="utf-8")
        temporary.replace(manifest)
        return manifest

    def verify(self) -> None:
        loaded = EvidenceBundle.load(self.run_dir)
        if not loaded.state.sealed:
            raise EvidenceError(
                "evidence bundle is not sealed",
                code="evidence_not_sealed",
            )
        manifest = self.run_dir / CHECKSUM_FILENAME
        if not manifest.is_file():
            raise EvidenceError(
                "checksum manifest is missing",
                code="evidence_file_missing",
            )
        expected: dict[str, str] = {}
        try:
            for line in manifest.read_text(encoding="utf-8").splitlines():
                match = CHECKSUM_LINE.fullmatch(line)
                if match is None:
                    raise EvidenceError(
                        "checksum manifest line is invalid",
                        code="evidence_manifest_invalid",
                    )
                digest, relative = match.groups()
                pure = PurePosixPath(relative)
                if (
                    pure.is_absolute()
                    or ".." in pure.parts
                    or relative in expected
                    or relative == CHECKSUM_FILENAME
                ):
                    raise EvidenceError(
                        "checksum manifest path is invalid",
                        code="evidence_manifest_invalid",
                    )
                expected[relative] = digest
        except OSError as error:
            raise EvidenceError(
                "checksum manifest could not be read",
                code="evidence_manifest_invalid",
            ) from error
        actual = self._evidence_files()
        if set(expected) != set(actual):
            raise EvidenceError(
                "evidence file set does not match checksum manifest",
                code="evidence_checksum_mismatch",
            )
        for relative, path in actual.items():
            if _sha256(path) != expected[relative]:
                raise EvidenceError(
                    f"evidence checksum mismatch: {relative}",
                    code="evidence_checksum_mismatch",
                )
