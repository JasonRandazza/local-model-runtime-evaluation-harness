"""Shared harness-owned lifecycle controller for pinned OptiQ, oMLX, and Osaurus."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Literal

from .matrix_lifecycle import (
    ManagedProcess,
    run_stop_command,
    spawn_pinned,
    wait_port_free as matrix_wait_port_free,
)

ServerKind = Literal["optiq", "omlx", "osaurus"]

DEFAULT_MEMORY_FLOOR_PERCENT = 20

PORT_BY_KIND: dict[ServerKind, int] = {
    "optiq": 8080,
    "omlx": 8100,
    "osaurus": 1337,
}

Spawner = Callable[[tuple[str, ...], Path], ManagedProcess]
PortFree = Callable[[int], bool]
StopRunner = Callable[[tuple[str, ...]], None]
WaitPortFree = Callable[[int, float], None]

DEFAULT_OMLX_STOP_COMMAND = ("omlX", "stop")
DEFAULT_WAIT_PORT_FREE_SECONDS = 30.0


def default_lab_closed() -> bool:
    """Return True when OptiQ Lab is closed.

    Slice 1c / live wiring will probe Lab; Gate A uses injected fakes only.
    """
    return True


class HarnessLifecycleError(RuntimeError):
    def __init__(self, message: str, *, code: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class ServerPin:
    kind: ServerKind
    port: int
    start_command: tuple[str, ...]
    stop_command: tuple[str, ...] = ()
    ready_model_id: str = ""

    def __post_init__(self) -> None:
        expected = PORT_BY_KIND[self.kind]
        if self.port != expected:
            raise HarnessLifecycleError(
                f"port {self.port} does not match {self.kind} pin {expected}",
                code="port_mismatch",
            )


WaitReady = Callable[["ServerPin", ManagedProcess | None], None]


class LifecycleController:
    def __init__(
        self,
        *,
        memory_floor_percent: int = DEFAULT_MEMORY_FLOOR_PERCENT,
        free_memory: Callable[[], float],
        port_free: Callable[[int], bool],
        lab_closed: Callable[[], bool],
        spawner: Spawner | None = None,
        stop_runner: StopRunner | None = None,
        wait_port_free: WaitPortFree | None = None,
        wait_ready: WaitReady | None = None,
        log_dir: Path | None = None,
    ) -> None:
        self.memory_floor_percent = memory_floor_percent
        self._free_memory = free_memory
        self._port_free = port_free
        self._lab_closed = lab_closed
        self._spawner = spawner or spawn_pinned
        self._stop_runner = stop_runner or (lambda cmd: run_stop_command(cmd))
        self._wait_port_free = wait_port_free or matrix_wait_port_free
        self._wait_ready = wait_ready
        self._log_dir = log_dir or Path.cwd() / ".harness-lifecycle"
        self.lifecycle_actions = 0
        self._pin: ServerPin | None = None
        self._process: ManagedProcess | None = None
        self._owned = False
        self._started = False

    @property
    def active_pin(self) -> ServerPin | None:
        return self._pin

    @property
    def active_process(self) -> ManagedProcess | None:
        return self._process

    @property
    def owned(self) -> bool:
        return self._owned

    def start(self, pin: ServerPin) -> None:
        if self._started:
            raise HarnessLifecycleError(
                "server already started",
                code="already_started",
            )
        if self._free_memory() < self.memory_floor_percent:
            raise HarnessLifecycleError(
                f"free memory below {self.memory_floor_percent}% floor",
                code="memory_floor",
            )
        if pin.kind == "optiq" and not self._lab_closed():
            raise HarnessLifecycleError(
                "OptiQ Lab is open",
                code="lab_open",
            )
        if pin.kind == "osaurus":
            if self._port_free(pin.port):
                self._attach_owned(pin)
            else:
                self._attach_observe_only(pin)
            return
        if not self._port_free(pin.port):
            if pin.kind == "omlx":
                stop_command = pin.stop_command or DEFAULT_OMLX_STOP_COMMAND
                self._stop_runner(stop_command)
                self._wait_port_free(pin.port, DEFAULT_WAIT_PORT_FREE_SECONDS)
            else:
                raise HarnessLifecycleError(
                    f"port {pin.port} is busy",
                    code="port_busy",
                )
        self._attach_owned(pin)

    def _attach_owned(self, pin: ServerPin) -> None:
        log_path = self._log_dir / f"{pin.kind}.log"
        process = self._spawner(pin.start_command, log_path)
        self._pin = pin
        self._process = process
        self._owned = True
        self._started = True
        self.lifecycle_actions += 1

    def _attach_observe_only(self, pin: ServerPin) -> None:
        self._pin = pin
        self._process = None
        self._owned = False
        self._started = True
