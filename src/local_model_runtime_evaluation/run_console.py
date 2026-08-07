"""View-model and exact-child boundary for the local LMRE run console."""

from __future__ import annotations

import secrets
import signal
import subprocess
import sys
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from .evidence_bundle import EvidenceBundle, EvidenceError, resume_is_allowed
from .managed_run_types import RunSummaryState
from .results_browser import SAFE_RUN_ID, build_index, build_run_view

ACTION_START = "start"
ACTION_RESUME = "resume"
_LIVE_ACTIONS = frozenset({ACTION_START, ACTION_RESUME})
GRANT_TTL_SECONDS = 600.0
SHUTDOWN_TERM_TIMEOUT_SECONDS = 10.0


class ConsoleError(RuntimeError):
    """A user-safe, status-qualified console failure."""

    def __init__(self, message: str, *, status: int = 400) -> None:
        super().__init__(message)
        self.status = status


class ChildProcess(Protocol):
    pid: int
    returncode: int | None

    def poll(self) -> int | None: ...

    def send_signal(self, sig: int) -> None: ...

    def wait(self, timeout: float | None = None) -> int: ...


ProcessFactory = Callable[[list[str]], ChildProcess]


def _spawn_child(arguments: list[str]) -> ChildProcess:
    return subprocess.Popen(
        arguments,
        stdin=subprocess.DEVNULL,
    )


@dataclass(frozen=True)
class ActionGrant:
    action: str
    run_id: str
    plan_hash: str
    expires_at: float


@dataclass
class ActiveChild:
    action: str
    run_id: str
    process: ChildProcess
    started_at: float
    cancel_requested: bool = False


class RunConsoleController:
    """Coordinate one fixed managed-CLI child without becoming run truth."""

    def __init__(
        self,
        results_root: Path,
        state_root: Path,
        *,
        process_factory: ProcessFactory = _spawn_child,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.results_root = results_root
        self.state_root = state_root
        self._process_factory = process_factory
        self._clock = clock
        self._grants: dict[str, ActionGrant] = {}
        self._active: ActiveChild | None = None
        self._last_actions: dict[str, dict[str, object]] = {}
        self._lock = threading.Lock()

    def _run_dir(self, run_id: str) -> Path:
        if SAFE_RUN_ID.fullmatch(run_id) is None:
            raise ConsoleError("Run identity is not recognized.", status=404)
        run_dir = self.results_root / run_id
        if run_dir.is_symlink() or not run_dir.is_dir():
            raise ConsoleError("Run identity is not recognized.", status=404)
        return run_dir

    def _bundle(self, run_id: str) -> EvidenceBundle:
        try:
            return EvidenceBundle.load(self._run_dir(run_id))
        except EvidenceError as error:
            raise ConsoleError(
                "Managed run evidence is unreadable.", status=422
            ) from error

    def _refresh_child(self) -> ActiveChild | None:
        active = self._active
        if active is None:
            return None
        return_code = active.process.poll()
        if return_code is None:
            return active
        self._last_actions[active.run_id] = {
            "action": active.action,
            "cancel_requested": active.cancel_requested,
            "return_code": return_code,
        }
        self._active = None
        return None

    def _action_eligibility(self, bundle: EvidenceBundle) -> tuple[bool, bool]:
        state = bundle.state
        can_start = not state.sealed and state.summary_state is RunSummaryState.PENDING
        can_resume = resume_is_allowed(state)
        return can_start, can_resume

    def issue_grant(self, run_id: str, action: str) -> str | None:
        if action not in _LIVE_ACTIONS:
            raise ConsoleError("Live action is not supported.")
        with self._lock:
            if self._refresh_child() is not None:
                return None
            bundle = self._bundle(run_id)
            can_start, can_resume = self._action_eligibility(bundle)
            if not (
                (action == ACTION_START and can_start)
                or (action == ACTION_RESUME and can_resume)
            ):
                return None
            return self._issue_grant_unlocked(bundle, action)

    def dashboard(self, selected_run_id: str | None = None) -> dict[str, object]:
        with self._lock:
            active = self._refresh_child()
            index = build_index(self.results_root)
            entries = [
                entry for entry in index["entries"] if entry.get("run_id") is not None
            ]
            selected = selected_run_id
            if selected is None and entries:
                selected = str(entries[0]["run_id"])
            detail = None
            grants: dict[str, str | None] = {}
            if selected is not None:
                bundle = self._bundle(selected)
                detail = build_run_view(bundle.run_dir)
                can_start, can_resume = self._action_eligibility(bundle)
                detail["can_start"] = can_start and active is None
                detail["can_resume"] = can_resume and active is None
                detail["active_action"] = (
                    {
                        "action": active.action,
                        "cancel_requested": active.cancel_requested,
                        "pid": active.process.pid,
                        "run_id": active.run_id,
                    }
                    if active is not None
                    else None
                )
                detail["last_action"] = self._last_actions.get(selected)
                if detail["can_start"]:
                    grants[ACTION_START] = self._issue_grant_unlocked(
                        bundle, ACTION_START
                    )
                if detail["can_resume"]:
                    grants[ACTION_RESUME] = self._issue_grant_unlocked(
                        bundle, ACTION_RESUME
                    )
            return {
                "entries": entries,
                "missing_root": index["missing_root"],
                "selected_run_id": selected,
                "detail": detail,
                "grants": grants,
            }

    def _issue_grant_unlocked(self, bundle: EvidenceBundle, action: str) -> str:
        """Issue a grant while dashboard already owns the controller lock."""
        now = self._clock()
        self._grants = {
            nonce: grant
            for nonce, grant in self._grants.items()
            if grant.expires_at >= now
            and not (
                grant.run_id == bundle.plan.identity.run_id and grant.action == action
            )
        }
        nonce = secrets.token_urlsafe(32)
        self._grants[nonce] = ActionGrant(
            action=action,
            run_id=bundle.plan.identity.run_id,
            plan_hash=bundle.plan.plan_hash,
            expires_at=now + GRANT_TTL_SECONDS,
        )
        return nonce

    def _consume_grant(
        self,
        *,
        nonce: str,
        action: str,
        run_id: str,
        confirmed_plan_hash: str,
    ) -> EvidenceBundle:
        grant = self._grants.pop(nonce, None)
        bundle = self._bundle(run_id)
        if (
            grant is None
            or grant.expires_at < self._clock()
            or grant.action != action
            or grant.run_id != run_id
            or grant.plan_hash != bundle.plan.plan_hash
            or confirmed_plan_hash != bundle.plan.plan_hash
        ):
            raise ConsoleError(
                "Live authority did not match this exact immutable plan.",
                status=403,
            )
        return bundle

    def start_action(
        self,
        *,
        action: str,
        run_id: str,
        nonce: str,
        confirmed_plan_hash: str,
        acknowledged: bool,
    ) -> None:
        if action not in _LIVE_ACTIONS:
            raise ConsoleError("Live action is not supported.")
        if not acknowledged:
            raise ConsoleError("Live-action acknowledgement is required.")
        with self._lock:
            if self._refresh_child() is not None:
                raise ConsoleError(
                    "Another console-owned managed action is active.", status=409
                )
            bundle = self._consume_grant(
                nonce=nonce,
                action=action,
                run_id=run_id,
                confirmed_plan_hash=confirmed_plan_hash,
            )
            can_start, can_resume = self._action_eligibility(bundle)
            if not (
                (action == ACTION_START and can_start)
                or (action == ACTION_RESUME and can_resume)
            ):
                raise ConsoleError(
                    "Managed run state no longer permits this action.", status=409
                )
            arguments = [
                sys.executable,
                "-m",
                "local_model_runtime_evaluation.managed_run_cli",
                "--state-dir",
                str(self.state_root),
                "--results-dir",
                str(self.results_root),
                action,
                run_id,
            ]
            process = self._process_factory(arguments)
            self._active = ActiveChild(
                action=action,
                run_id=run_id,
                process=process,
                started_at=self._clock(),
            )

    def cancel(self, run_id: str) -> None:
        with self._lock:
            active = self._refresh_child()
            if active is None or active.run_id != run_id:
                raise ConsoleError(
                    "This run has no active console-owned child.", status=409
                )
            if active.cancel_requested:
                raise ConsoleError("Cancellation was already requested.", status=409)
            active.process.send_signal(signal.SIGINT)
            active.cancel_requested = True

    def shutdown(self, *, timeout: float = 30.0) -> None:
        with self._lock:
            active = self._refresh_child()
            if active is None:
                return
            if not active.cancel_requested:
                active.process.send_signal(signal.SIGINT)
                active.cancel_requested = True
            process = active.process
        try:
            process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            process.send_signal(signal.SIGTERM)
            try:
                process.wait(timeout=SHUTDOWN_TERM_TIMEOUT_SECONDS)
            except subprocess.TimeoutExpired:
                # Deliberately do not force-kill. The exact managed child retains
                # cleanup responsibility; broad process matching is forbidden.
                return
