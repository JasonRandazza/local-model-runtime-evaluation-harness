"""Server start/ready/stop adapters for the Gemma 3×3 matrix."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Callable, Protocol
from urllib.parse import urlparse

from .matrix_config import Cell
from .matrix_lifecycle import ManagedProcess, port_is_free, run_stop_command, spawn_pinned


class ServerError(RuntimeError):
    code = "matrix_server_failed"


class TransportProtocol(Protocol):
    def list_models(self, base_url: str, credential: object | None) -> tuple[str, ...]: ...


class ServerHandle(Protocol):
    def start(self) -> None: ...

    def wait_ready(self, model_id: str, timeout_seconds: float) -> None: ...

    def stop(self) -> None: ...


Spawner = Callable[[tuple[str, ...], Path], ManagedProcess]
PortFree = Callable[[int], bool]


class SubprocessServerHandle:
    def __init__(
        self,
        cell: Cell,
        transport: TransportProtocol,
        log_dir: Path,
        *,
        spawner: Spawner | None = None,
        port_free: PortFree | None = None,
    ) -> None:
        self._cell = cell
        self._transport = transport
        self._log_path = log_dir / f"{cell.cell_id}.log"
        self._spawner = spawner or spawn_pinned
        self._port_free = port_free or port_is_free
        self._process: ManagedProcess | None = None
        self._started = False

    def start(self) -> None:
        if self._started:
            return
        if self._cell.server == "osaurus":
            port = _port_from_base_url(self._cell.base_url)
            if self._port_free(port):
                self._process = self._spawner(self._cell.start_command, self._log_path)
        else:
            self._process = self._spawner(self._cell.start_command, self._log_path)
        self._started = True

    def wait_ready(self, model_id: str, timeout_seconds: float) -> None:
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            try:
                models = self._transport.list_models(self._cell.base_url, None)
            except Exception:
                models = ()
            if model_id in models:
                return
            time.sleep(0.1)
        raise ServerError(f"model {model_id!r} not ready within {timeout_seconds}s")

    def stop(self) -> None:
        if self._cell.stop_command:
            run_stop_command(self._cell.stop_command)
        elif self._process is not None:
            self._process.stop()
        self._process = None
        self._started = False


def _port_from_base_url(base_url: str) -> int:
    parsed = urlparse(base_url)
    if parsed.port is None:
        raise ServerError(f"base_url has no port: {base_url}")
    return parsed.port


def build_server(
    cell: Cell,
    transport: TransportProtocol,
    log_dir: Path,
    *,
    spawner: Spawner | None = None,
    port_free: PortFree | None = None,
) -> ServerHandle:
    return SubprocessServerHandle(
        cell, transport, log_dir, spawner=spawner, port_free=port_free,
    )
