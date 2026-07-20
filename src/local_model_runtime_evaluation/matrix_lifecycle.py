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

    def stop(self, timeout_seconds: float = 15) -> None:
        try:
            os.killpg(self.process_group_id, signal.SIGTERM)
        except (ProcessLookupError, PermissionError):
            return
        try:
            self._child.wait(timeout=timeout_seconds)
        except subprocess.TimeoutExpired:
            pass
        # Always escalate: leader exit after SIGTERM can leave descendants alive.
        try:
            os.killpg(self.process_group_id, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            return
        try:
            self._child.wait(timeout=5)
        except subprocess.TimeoutExpired:
            raise LifecycleError("process group did not exit after SIGKILL") from None


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
