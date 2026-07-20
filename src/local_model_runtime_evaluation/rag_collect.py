"""Collect RAG oracle and keyword answers one cell at a time."""

from __future__ import annotations

import json
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from .credentials import Credential
from .matrix_config import Cell
from .matrix_servers import ServerError, ServerHandle, build_server as default_build_server
from .preference_collect import (
    DEFAULT_MEMORY_FLOOR_PERCENT,
    DEFAULT_READY_TIMEOUT_SECONDS,
    DEFAULT_REQUEST_TIMEOUT_SECONDS,
    AnswerRecord,
    resolve_credential,
    write_answers,
)
from .rag_config import RagCorpus, RagError, RagSuite
from .rag_prompt import build_keyword_prompt, build_oracle_prompt
from .resources import HostResourceProbe
from .transport import LoopbackTransport, TransportError

BuildServer = Callable[[Cell, LoopbackTransport, Path, Credential | None], ServerHandle]
TransportFactory = Callable[[set[str], int], LoopbackTransport]
CredentialFor = Callable[[str], Credential | None]

_VALID_MODES = frozenset({"oracle", "keyword"})


def _stamp() -> str:
    return time.strftime("%Y%m%d-%H%M%S")


def _validate_mode(mode: str) -> None:
    if mode not in _VALID_MODES:
        raise RagError(f"unknown collect mode {mode!r}")


def collect_cell(
    cell: Cell,
    suite: RagSuite,
    corpus: RagCorpus,
    transport: LoopbackTransport,
    *,
    credential: Credential | None,
    build_server: BuildServer,
    probe: HostResourceProbe | None,
    cancel: threading.Event,
    ready_timeout: float,
    request_timeout: float,
    log_dir: Path,
    mode: str = "oracle",
    top_k: int = 2,
) -> list[AnswerRecord]:
    _validate_mode(mode)
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
        for question in suite.questions:
            if cancel.is_set():
                break
            retrieved_chunk_ids: tuple[str, ...] | None = None
            if mode == "keyword":
                prompt, retrieved_chunk_ids = build_keyword_prompt(
                    question, corpus, k=top_k,
                )
            else:
                prompt = build_oracle_prompt(question, corpus)
            try:
                result = transport.chat(
                    cell.base_url,
                    cell.model_id,
                    prompt,
                    question.max_tokens,
                    credential,
                    cancel,
                )
            except TransportError as error:
                records.append(
                    AnswerRecord(
                        question.prompt_id,
                        cell.cell_id,
                        cell.model_id,
                        None,
                        False,
                        str(error),
                        None,
                        None,
                        retrieved_chunk_ids,
                    )
                )
                continue
            records.append(
                AnswerRecord(
                    question.prompt_id,
                    cell.cell_id,
                    cell.model_id,
                    result.content,
                    True,
                    None,
                    result.total_seconds,
                    result.ttft_seconds,
                    retrieved_chunk_ids,
                )
            )
    finally:
        try:
            handle.stop()
        except (ServerError, OSError, PermissionError):
            pass
    return records


def run_collect(
    cell_ids: tuple[str, ...],
    suite_path: Path,
    corpus_root: Path,
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
    mode: str = "oracle",
    top_k: int = 2,
) -> Path:
    _validate_mode(mode)
    suite = RagSuite.load(suite_path)
    corpus = RagCorpus.load(corpus_root)
    if corpus.corpus_id != suite.corpus_id:
        raise RuntimeError(
            f"corpus id mismatch: suite expects {suite.corpus_id!r}, "
            f"corpus has {corpus.corpus_id!r}"
        )
    loaded_cells = tuple(Cell.load(cells_root / f"{cell_id}.json") for cell_id in cell_ids)
    resource_probe = probe if probe is not None else HostResourceProbe()
    resolve_credential_fn = credential_for or resolve_credential
    build = build_server or (
        lambda cell, transport, log_dir, credential: default_build_server(
            cell, transport, log_dir, credential=credential,
        )
    )
    make_transport = transport_factory or (
        lambda base_urls, timeout: LoopbackTransport(base_urls, timeout_seconds=timeout)
    )

    run_dir = results_root / f"gemma-rag-{_stamp()}"
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
        raw: dict[str, object] = {
            "suite_id": suite.suite_id,
            "suite_revision": suite.revision,
            "corpus_id": suite.corpus_id,
            "cell_ids": list(cell_ids),
            "mode": mode,
            "started_at": started_at,
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "stopped_early": stopped_early,
            "stop_reason": stop_reason,
            "memory_floor_percent": memory_floor_percent,
            "ready_timeout_seconds": ready_timeout,
            "request_timeout_seconds": request_timeout,
        }
        if mode == "keyword":
            raw["top_k"] = top_k
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
                    corpus,
                    transport,
                    credential=credential,
                    build_server=build,
                    probe=resource_probe,
                    cancel=cancel,
                    ready_timeout=ready_timeout,
                    request_timeout=request_timeout,
                    log_dir=log_dir,
                    mode=mode,
                    top_k=top_k,
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
