"""Pinned subprocess helpers for matrix server start/stop.

ponytail: thin wrapper over Popen + killpg; not Stage 2 OptiQLifecycleController.
"""

from __future__ import annotations

import os
import signal
import socket
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path


class LifecycleError(RuntimeError):
    code = "matrix_lifecycle_failed"


def port_is_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.settimeout(0.25)
        return probe.connect_ex(("127.0.0.1", port)) != 0


def wait_port_free(port: int, timeout_seconds: float) -> None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if port_is_free(port):
            return
        time.sleep(0.1)
    raise LifecycleError(f"port {port} did not free in time")


@dataclass
class ManagedProcess:
    pid: int
    process_group_id: int
    command: tuple[str, ...]
    _child: subprocess.Popen[bytes]

    @property
    def is_alive(self) -> bool:
        return self._child.poll() is None

    def interrupt(self) -> None:
        interrupt_process_group(self.process_group_id)

    def terminate(self) -> None:
        terminate_process_group(self.process_group_id)

    def wait(self, timeout_seconds: float) -> bool:
        try:
            self._child.wait(timeout=timeout_seconds)
            return True
        except subprocess.TimeoutExpired:
            return False

    def stop(self, timeout_seconds: float = 15) -> None:
        self.interrupt()
        if self.wait(timeout_seconds):
            return
        self.terminate()
        if self.wait(timeout_seconds):
            return
        raise LifecycleError("process group did not exit after termination")


def interrupt_process_group(process_group_id: int) -> None:
    try:
        os.killpg(process_group_id, signal.SIGINT)
    except ProcessLookupError:
        return
    except PermissionError as error:
        raise LifecycleError(
            "permission denied while interrupting process group"
        ) from error


def terminate_process_group(process_group_id: int) -> None:
    try:
        os.killpg(process_group_id, signal.SIGTERM)
    except ProcessLookupError:
        return
    except PermissionError as error:
        raise LifecycleError(
            "permission denied while terminating process group"
        ) from error


def wait_process_exit(
    process: ManagedProcess,
    timeout_seconds: float,
) -> bool:
    return process.wait(timeout_seconds)


def spawn_pinned(command: tuple[str, ...], log_path: Path) -> ManagedProcess:
    if not command:
        raise LifecycleError("start_command is empty")
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("ab") as log:
        child = subprocess.Popen(
            list(command),
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=log,
            start_new_session=True,
            close_fds=True,
        )
    return ManagedProcess(child.pid, child.pid, command, child)


def run_stop_command(command: tuple[str, ...], timeout_seconds: float = 30) -> None:
    if not command:
        return
    result = subprocess.run(
        list(command), capture_output=True, text=True, check=False, timeout=timeout_seconds,
    )
    if result.returncode != 0:
        raise LifecycleError(f"stop_command failed with code {result.returncode}")
