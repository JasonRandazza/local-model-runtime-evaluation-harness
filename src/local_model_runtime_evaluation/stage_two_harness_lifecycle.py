"""Stage 2 harness-owned OptiQ lifecycle adapter."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Callable

from .harness_lifecycle import (
    HarnessLifecycleError,
    LifecycleController,
    PORT_BY_KIND,
    ServerPin,
    Spawner,
    StopRunner,
    WaitPortFree,
    WaitReady,
)
from .matrix_lifecycle import ManagedProcess
from .stage_two import ProcessOwnership, StageTwoError
from .stage_two_profiles import RuntimeProfile

OPTIQ_PORT = PORT_BY_KIND["optiq"]


def _command_sha256(command: tuple[str, ...]) -> str:
    return hashlib.sha256(" ".join(command).encode("utf-8")).hexdigest()


def _process_identity(process: ManagedProcess) -> ProcessOwnership:
    return ProcessOwnership(
        process.pid,
        process.pid,
        process.process_group_id,
        "harness-owned",
        _command_sha256(process.command),
    )


def optiq_server_pin_from_profile(profile: RuntimeProfile) -> ServerPin:
    executable = str(profile.runtime_executable)
    return ServerPin(
        kind="optiq",
        port=OPTIQ_PORT,
        start_command=(executable, *profile.serve_arguments),
        stop_command=(executable, "stop"),
        ready_model_id=profile.direct_model_identities[0]
        if profile.direct_model_identities
        else profile.routed_model_id,
    )


class HarnessOptiQController:
    """Start and stop harness-owned OptiQ via LifecycleController."""

    def __init__(
        self,
        *,
        controller: LifecycleController | None = None,
        memory_floor_percent: int | None = None,
        free_memory: Callable[[], float] | None = None,
        port_free: Callable[[int], bool] | None = None,
        lab_closed: Callable[[], bool] | None = None,
        spawner: Spawner | None = None,
        stop_runner: StopRunner | None = None,
        wait_port_free: WaitPortFree | None = None,
        wait_ready: WaitReady | None = None,
        log_dir: Path | None = None,
        profile: RuntimeProfile | None = None,
        server_pin: ServerPin | None = None,
    ) -> None:
        self._server_pin = server_pin or (
            optiq_server_pin_from_profile(profile) if profile is not None else None
        )
        self._identity: ProcessOwnership | None = None
        if controller is not None:
            self._controller = controller
            self._port_free = controller._port_free
            return

        missing = [
            name
            for name, value in (
                ("free_memory", free_memory),
                ("port_free", port_free),
                ("lab_closed", lab_closed),
            )
            if value is None
        ]
        if missing:
            raise HarnessLifecycleError(
                "HarnessOptiQController requires "
                + ", ".join(missing)
                + " when controller is not injected",
                code="missing_probes",
            )

        self._port_free = port_free
        controller_kwargs: dict[str, object] = {
            "free_memory": free_memory,
            "port_free": port_free,
            "lab_closed": lab_closed,
        }
        if memory_floor_percent is not None:
            controller_kwargs["memory_floor_percent"] = memory_floor_percent
        if spawner is not None:
            controller_kwargs["spawner"] = spawner
        if stop_runner is not None:
            controller_kwargs["stop_runner"] = stop_runner
        if wait_port_free is not None:
            controller_kwargs["wait_port_free"] = wait_port_free
        if wait_ready is not None:
            controller_kwargs["wait_ready"] = wait_ready
        if log_dir is not None:
            controller_kwargs["log_dir"] = log_dir
        self._controller = LifecycleController(**controller_kwargs)

    @property
    def lifecycle_actions(self) -> int:
        return self._controller.lifecycle_actions

    def ensure_started(self, pin: ServerPin) -> None:
        if pin.kind != "optiq":
            raise HarnessLifecycleError(
                f"expected optiq pin, got {pin.kind}",
                code="pin_kind_mismatch",
            )
        self._controller.start(pin)

    def _can_stop_owned_process(self) -> bool:
        if not self._controller.owned:
            return False
        process = self._controller.active_process
        if process is None:
            return False
        if self._identity is not None and process.pid != self._identity.pid:
            return False
        return process.is_alive

    def ensure_stopped(self) -> None:
        if self._can_stop_owned_process():
            self._controller.stop()
        elif self._controller.owned or self._controller.active_process is not None:
            self._controller.release_without_stop()
        else:
            self._controller.stop()
        if not self._port_free(OPTIQ_PORT):
            raise HarnessLifecycleError(
                f"port {OPTIQ_PORT} is still busy after harness clearance",
                code="port_busy",
            )
        if not self._port_free(OPTIQ_PORT):
            raise HarnessLifecycleError(
                f"port {OPTIQ_PORT} must be free twice after harness stop",
                code="port_not_free",
            )
        self._identity = None

    def capture(self) -> ProcessOwnership:
        if self._server_pin is None:
            raise StageTwoError(
                "operator_identity_failed",
                "harness OptiQ server pin is unavailable",
            )
        self.ensure_started(self._server_pin)
        process = self._controller.active_process
        if process is None:
            raise StageTwoError(
                "operator_identity_failed",
                "harness OptiQ process is unavailable after start",
            )
        identity = _process_identity(process)
        self._identity = identity
        return identity

    def matches(self, identity: ProcessOwnership) -> bool:
        if self._identity != identity:
            return False
        if not self._controller.owned:
            return False
        process = self._controller.active_process
        if process is None or identity.pid != process.pid:
            return False
        if not process.is_alive:
            return False
        if self._port_free(OPTIQ_PORT):
            return False
        return True

    def assert_stopped(self, identity: ProcessOwnership) -> None:
        if self._identity is not None and identity != self._identity:
            raise StageTwoError(
                "operator_shutdown_pending",
                "harness OptiQ identity does not match recorded service",
            )
        try:
            self.ensure_stopped()
        except HarnessLifecycleError as error:
            raise StageTwoError(
                "operator_shutdown_pending",
                "harness OptiQ stop verification failed",
            ) from error
