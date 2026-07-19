"""Server start/ready/stop adapters for the Gemma 3×3 matrix."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Callable, Protocol
from urllib.parse import urlparse

from .credentials import Credential
from .matrix_config import Cell
from .matrix_lifecycle import LifecycleError, ManagedProcess, port_is_free, run_stop_command, spawn_pinned, wait_port_free
from .transport import TransportError


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
StopRunner = Callable[[tuple[str, ...]], None]


class SubprocessServerHandle:
    def __init__(
        self,
        cell: Cell,
        transport: TransportProtocol,
        log_dir: Path,
        *,
        credential: Credential | None = None,
        spawner: Spawner | None = None,
        port_free: PortFree | None = None,
        stop_runner: StopRunner | None = None,
    ) -> None:
        self._cell = cell
        self._transport = transport
        self._credential = credential
        self._log_path = log_dir / f"{cell.cell_id}.log"
        self._spawner = spawner or spawn_pinned
        self._port_free = port_free or port_is_free
        self._stop_runner = stop_runner or (lambda cmd: run_stop_command(cmd))
        self._process: ManagedProcess | None = None
        self._owned = False
        self._started = False

    def start(self) -> None:
        if self._started:
            return
        port = _port_from_base_url(self._cell.base_url)
        try:
            if self._cell.server == "osaurus":
                if self._port_free(port):
                    self._process = self._spawner(self._cell.start_command, self._log_path)
                    self._owned = True
            else:
                if not self._port_free(port):
                    if self._cell.server == "omlx":
                        # Free managed oMLX so this cell can own a pinned serve.
                        self._stop_runner(("omlX", "stop"))
                        wait_port_free(port, timeout_seconds=30)
                    else:
                        raise ServerError(f"port {port} is busy")
                self._process = self._spawner(self._cell.start_command, self._log_path)
                self._owned = True
        except (LifecycleError, OSError, ValueError) as error:
            raise ServerError(str(error)) from error
        self._started = True

    def wait_ready(self, model_id: str, timeout_seconds: float) -> None:
        deadline = time.monotonic() + timeout_seconds
        last_error: str | None = None
        while time.monotonic() < deadline:
            try:
                models = self._transport.list_models(self._cell.base_url, self._credential)
            except TransportError as error:
                message = str(error)
                last_error = message
                # Auth failures will not recover by waiting.
                if "HTTP 401" in message or "HTTP 403" in message:
                    raise ServerError(message) from error
                models = ()
            except (OSError, TimeoutError, ValueError, KeyError, TypeError) as error:
                last_error = str(error)
                models = ()
            if model_id in models:
                return
            time.sleep(0.1)
        detail = f" ({last_error})" if last_error else ""
        raise ServerError(f"model {model_id!r} not ready within {timeout_seconds}s{detail}")

    def stop(self) -> None:
        # ponytail: never stop a pre-existing Osaurus/oMLX we did not spawn
        if self._owned:
            if self._cell.stop_command:
                self._stop_runner(self._cell.stop_command)
            elif self._process is not None:
                self._process.stop()
        self._process = None
        self._owned = False
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
    credential: Credential | None = None,
    spawner: Spawner | None = None,
    port_free: PortFree | None = None,
    stop_runner: StopRunner | None = None,
) -> ServerHandle:
    return SubprocessServerHandle(
        cell, transport, log_dir,
        credential=credential,
        spawner=spawner, port_free=port_free, stop_runner=stop_runner,
    )
