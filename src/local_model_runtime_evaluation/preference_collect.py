"""Collect preference answers one cell at a time."""

from __future__ import annotations

import json
import threading
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from .credentials import (
    OSAURUS_KEYCHAIN_SERVICE,
    Credential,
    CredentialError,
    KeychainCredentialProvider,
)
from .matrix_config import Cell, load_family
from .matrix_servers import (
    MATRIX_OMLX_API_KEY,
    ServerError,
    ServerHandle,
    build_server as default_build_server,
)
from .preference_config import PreferenceSuite
from .resources import HostResourceProbe
from .transport import LoopbackTransport, TransportError

DEFAULT_READY_TIMEOUT_SECONDS = 180.0
DEFAULT_REQUEST_TIMEOUT_SECONDS = 120.0
DEFAULT_MEMORY_FLOOR_PERCENT = 20
DEFAULT_CELL_FAMILY = load_family("gemma-4-12b-qat")

BuildServer = Callable[[Cell, LoopbackTransport, Path, Credential | None], ServerHandle]
TransportFactory = Callable[[set[str], int], LoopbackTransport]
CredentialFor = Callable[[str], Credential | None]


class PreferenceCollectError(RuntimeError):
    pass


@dataclass(frozen=True)
class AnswerRecord:
    prompt_id: str
    cell_id: str
    model_id: str
    content: str | None
    success: bool
    error: str | None
    total_seconds: float | None
    ttft_seconds: float | None
    retrieved_chunk_ids: tuple[str, ...] | None = None


def _stamp() -> str:
    return time.strftime("%Y%m%d-%H%M%S")


def _credential_for(server: str) -> Credential | None:
    if server == "optiq":
        return None
    if server == "omlx":
        return Credential(MATRIX_OMLX_API_KEY)
    if server == "osaurus":
        try:
            return KeychainCredentialProvider(OSAURUS_KEYCHAIN_SERVICE).get()
        except CredentialError as error:
            raise PreferenceCollectError(
                "Osaurus harness Keychain item missing: "
                "create local.jrazz.lmre.osaurus / benchmark-harness "
                "(see docs/matrix.md). Do not paste the key into chat."
            ) from error
    raise PreferenceCollectError(f"unknown server {server!r}")


def resolve_credential(server: str, credential_for: CredentialFor | None = None) -> Credential | None:
    resolve = credential_for or _credential_for
    return resolve(server)


def collect_cell(
    cell: Cell,
    suite: PreferenceSuite,
    transport: LoopbackTransport,
    *,
    credential: Credential | None,
    build_server: BuildServer,
    probe: HostResourceProbe | None,
    cancel: threading.Event,
    ready_timeout: float,
    request_timeout: float,
    log_dir: Path,
) -> list[AnswerRecord]:
    del probe, request_timeout
    handle = build_server(cell, transport, log_dir, credential)
    try:
        handle.start()
        handle.wait_ready(cell.model_id, ready_timeout)
    except ServerError:
        try:
            handle.stop()
        except (ServerError, OSError, PermissionError):
            pass
        raise

    records: list[AnswerRecord] = []
    try:
        for prompt in suite.prompts:
            if cancel.is_set():
                break
            try:
                result = transport.chat(
                    cell.base_url,
                    cell.model_id,
                    prompt.prompt,
                    prompt.max_tokens,
                    credential,
                    cancel,
                )
            except TransportError as error:
                records.append(
                    AnswerRecord(
                        prompt.prompt_id,
                        cell.cell_id,
                        cell.model_id,
                        None,
                        False,
                        str(error),
                        None,
                        None,
                    )
                )
                continue
            records.append(
                AnswerRecord(
                    prompt.prompt_id,
                    cell.cell_id,
                    cell.model_id,
                    result.content,
                    True,
                    None,
                    result.total_seconds,
                    result.ttft_seconds,
                )
            )
    finally:
        try:
            handle.stop()
        except (ServerError, OSError, PermissionError):
            pass
    return records


def write_answers(
    path: Path,
    cell_id: str,
    model_id: str,
    records: list[AnswerRecord],
    *,
    error: str | None = None,
) -> None:
    payload: dict[str, object] = {
        "cell_id": cell_id,
        "model_id": model_id,
        "answers": [asdict(record) for record in records],
    }
    if error is not None:
        payload["error"] = error
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run_collect(
    cell_ids: tuple[str, ...],
    suite_path: Path,
    cells_root: Path,
    results_root: Path,
    *,
    build_server: BuildServer | None = None,
    transport_factory: TransportFactory | None = None,
    probe: HostResourceProbe | None = None,
    credential_for: CredentialFor | None = None,
    ready_timeout: float = DEFAULT_READY_TIMEOUT_SECONDS,
    request_timeout: float = DEFAULT_REQUEST_TIMEOUT_SECONDS,
    memory_floor_percent: int = DEFAULT_MEMORY_FLOOR_PERCENT,
) -> Path:
    suite = PreferenceSuite.load(suite_path)
    loaded_cells = tuple(
        Cell.load(cells_root / f"{cell_id}.json", family=DEFAULT_CELL_FAMILY)
        for cell_id in cell_ids
    )
    resource_probe = probe if probe is not None else HostResourceProbe()
    resolve_credential_fn = credential_for or _credential_for
    build = build_server or (
        lambda cell, transport, log_dir, credential: default_build_server(
            cell, transport, log_dir, credential=credential,
        )
    )
    make_transport = transport_factory or (
        lambda base_urls, timeout: LoopbackTransport(base_urls, timeout_seconds=timeout)
    )

    run_dir = results_root / f"gemma-preference-{_stamp()}"
    run_dir.mkdir(parents=True, exist_ok=False)
    answers_dir = run_dir / "answers"
    answers_dir.mkdir(parents=True, exist_ok=True)
    log_dir = run_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    base_urls = {cell.base_url for cell in loaded_cells}
    transport = make_transport(base_urls, int(request_timeout))
    cancel = threading.Event()

    started_at = datetime.now(timezone.utc).isoformat()
    stopped_early = False
    stop_reason: str | None = None

    def _persist_raw() -> None:
        raw = {
            "suite_id": suite.suite_id,
            "suite_revision": suite.revision,
            "cell_ids": list(cell_ids),
            "started_at": started_at,
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "stopped_early": stopped_early,
            "stop_reason": stop_reason,
            "memory_floor_percent": memory_floor_percent,
            "ready_timeout_seconds": ready_timeout,
            "request_timeout_seconds": request_timeout,
        }
        (run_dir / "raw.json").write_text(
            json.dumps(raw, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    try:
        for cell in loaded_cells:
            memory_before = resource_probe.free_memory_percent()
            if memory_before < memory_floor_percent:
                stopped_early = True
                stop_reason = "memory_floor"
                break

            credential = resolve_credential_fn(cell.server)
            try:
                records = collect_cell(
                    cell,
                    suite,
                    transport,
                    credential=credential,
                    build_server=build,
                    probe=resource_probe,
                    cancel=cancel,
                    ready_timeout=ready_timeout,
                    request_timeout=request_timeout,
                    log_dir=log_dir,
                )
            except ServerError as error:
                write_answers(
                    answers_dir / f"{cell.cell_id}.json",
                    cell.cell_id,
                    cell.model_id,
                    [],
                    error=str(error),
                )
                _persist_raw()
                continue

            write_answers(
                answers_dir / f"{cell.cell_id}.json",
                cell.cell_id,
                cell.model_id,
                records,
            )
            _persist_raw()
    finally:
        _persist_raw()

    return run_dir
