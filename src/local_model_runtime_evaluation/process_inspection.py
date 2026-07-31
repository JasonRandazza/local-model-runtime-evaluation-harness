"""Resolve one loopback TCP listener to an exact macOS process identity."""

from __future__ import annotations

import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable


CommandRunner = Callable[
    [tuple[str, ...]],
    subprocess.CompletedProcess[str],
]


class ProcessInspectionError(RuntimeError):
    code = "runtime_process_inspection_failed"

    def __init__(
        self,
        message: str,
        *,
        code: str = "runtime_process_inspection_failed",
    ) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class ProcessIdentity:
    pid: int
    ppid: int
    executable: str
    argv: tuple[str, ...]
    started_at: str
    listener_host: str
    listener_port: int

    def fingerprint(self) -> tuple[object, ...]:
        return (
            self.pid,
            self.ppid,
            self.executable,
            self.argv,
            self.started_at,
            self.listener_host,
            self.listener_port,
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "pid": self.pid,
            "ppid": self.ppid,
            "executable": self.executable,
            "argv": list(self.argv),
            "started_at": self.started_at,
            "listener_host": self.listener_host,
            "listener_port": self.listener_port,
        }


def _default_runner(
    command: tuple[str, ...],
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(command),
        capture_output=True,
        text=True,
        check=False,
        timeout=5,
    )


class ProcessInspector:
    def __init__(self, *, runner: CommandRunner | None = None) -> None:
        self._runner = _default_runner if runner is None else runner

    def _run(
        self,
        command: tuple[str, ...],
    ) -> subprocess.CompletedProcess[str]:
        try:
            result = self._runner(command)
        except (OSError, subprocess.SubprocessError) as error:
            raise ProcessInspectionError(
                f"process inspection command failed: {command[0]}"
            ) from error
        return result

    def inspect_listener(
        self,
        host: str,
        port: int,
    ) -> ProcessIdentity | None:
        if host != "127.0.0.1":
            raise ProcessInspectionError(
                "runtime listener must use 127.0.0.1",
                code="runtime_listener_not_loopback",
            )
        if type(port) is not int or not 0 < port <= 65535:
            raise ProcessInspectionError("runtime listener port is invalid")
        listener_command = (
            "/usr/sbin/lsof",
            "-nP",
            f"-iTCP:{port}",
            "-sTCP:LISTEN",
            "-Fpn",
        )
        listener = self._run(listener_command)
        if listener.returncode != 0:
            if not listener.stdout.strip():
                return None
            raise ProcessInspectionError("listener inventory failed")
        pids = {
            int(line[1:])
            for line in listener.stdout.splitlines()
            if line.startswith("p") and line[1:].isdigit()
        }
        names = [
            line[1:]
            for line in listener.stdout.splitlines()
            if line.startswith("n")
        ]
        if len(pids) != 1:
            raise ProcessInspectionError(
                "listener ownership is ambiguous",
                code="runtime_process_ambiguous",
            )
        expected_name = f"{host}:{port}"
        if not names or any(name != expected_name for name in names):
            raise ProcessInspectionError(
                "runtime listener is not exact loopback",
                code="runtime_listener_not_loopback",
            )
        pid = next(iter(pids))
        executable = self._executable(pid)
        ppid = self._integer_ps(pid, "ppid")
        started_at = self._text_ps(pid, "lstart")
        command = self._text_ps(pid, "command")
        try:
            argv = tuple(shlex.split(command))
        except ValueError as error:
            raise ProcessInspectionError(
                "runtime process command is not parseable"
            ) from error
        if not argv:
            raise ProcessInspectionError("runtime process command is empty")
        return ProcessIdentity(
            pid=pid,
            ppid=ppid,
            executable=executable,
            argv=argv,
            started_at=started_at,
            listener_host=host,
            listener_port=port,
        )

    def _executable(self, pid: int) -> str:
        comm_command = (
            "/bin/ps",
            "-ww",
            "-p",
            str(pid),
            "-o",
            "comm=",
        )
        comm_result = self._run(comm_command)
        comm = comm_result.stdout.strip()
        if comm_result.returncode != 0 or not comm:
            raise ProcessInspectionError("runtime executable lookup failed")
        command = (
            "/usr/sbin/lsof",
            "-a",
            "-p",
            str(pid),
            "-d",
            "txt",
            "-Fn",
        )
        result = self._run(command)
        if result.returncode != 0:
            raise ProcessInspectionError("runtime executable lookup failed")
        paths = [
            line[1:]
            for line in result.stdout.splitlines()
            if line.startswith("n")
        ]
        if not paths:
            raise ProcessInspectionError(
                "runtime executable lookup failed"
            )
        if Path(comm).is_absolute():
            if comm not in paths:
                raise ProcessInspectionError(
                    "runtime executable path is ambiguous",
                    code="runtime_process_ambiguous",
                )
            return comm
        if not Path(paths[0]).is_absolute():
            raise ProcessInspectionError(
                "runtime executable path is ambiguous",
                code="runtime_process_ambiguous",
            )
        return paths[0]

    def _integer_ps(self, pid: int, field: str) -> int:
        value = self._text_ps(pid, field)
        try:
            parsed = int(value)
        except ValueError as error:
            raise ProcessInspectionError(
                f"runtime process {field} is invalid"
            ) from error
        if parsed < 0:
            raise ProcessInspectionError(
                f"runtime process {field} is invalid"
            )
        return parsed

    def _text_ps(self, pid: int, field: str) -> str:
        command = (
            "/bin/ps",
            "-p",
            str(pid),
            "-o",
            f"{field}=",
        )
        result = self._run(command)
        value = result.stdout.strip()
        if result.returncode != 0 or not value:
            raise ProcessInspectionError(
                f"runtime process {field} lookup failed"
            )
        return value

    def still_matches(self, expected: ProcessIdentity) -> bool:
        current = self.inspect_listener(
            expected.listener_host,
            expected.listener_port,
        )
        return (
            current is not None
            and current.fingerprint() == expected.fingerprint()
        )
