"""Direct vs routed overhead orchestration for Osaurus routing tax."""

from __future__ import annotations

import json
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse

from .matrix_config import Cell, MatrixSuite, load_family
from .matrix_lifecycle import LifecycleError, port_is_free, run_stop_command
from .matrix_measure import CellResult, measure_cell as default_measure_cell
from .matrix_servers import ServerError, ServerHandle, build_server as default_build_server
from .overhead_config import OverheadError, OverheadPair, make_routed_measure_cell
from .overhead_report import pair_deltas, render_overhead_report
from .preference_collect import resolve_credential
from .resources import HostResourceProbe
from .transport import LoopbackTransport

OSAURUS_PORT = 1337
DEFAULT_MEMORY_FLOOR_PERCENT = 20
DEFAULT_READY_TIMEOUT_SECONDS = 180.0
PORT_VERIFY_TIMEOUT_SECONDS = 5.0
OMLX_STOP_WAIT_SECONDS = 30.0

BuildServer = Callable[[Cell, LoopbackTransport, Path, object | None], ServerHandle]
MeasureCell = Callable[
    [
        Cell, MatrixSuite, str, LoopbackTransport, HostResourceProbe | None,
        threading.Event, object | None,
    ],
    CellResult,
]
PortFree = Callable[[int], bool]
CredentialFor = Callable[[str], object | None]
StopRunner = Callable[[tuple[str, ...]], None]


def _stamp() -> str:
    return time.strftime("%Y%m%d-%H%M%S")


def _port_from_base_url(base_url: str) -> int:
    parsed = urlparse(base_url)
    if parsed.port is None:
        raise OverheadError(f"base_url has no port: {base_url}")
    return parsed.port


def require_osaurus_listening(*, port_free: PortFree | None = None) -> None:
    check = port_free or port_is_free
    if check(OSAURUS_PORT):
        raise OverheadError("Osaurus is not listening on port 1337")


def _verify_port_free(
    port: int,
    port_free: PortFree,
    *,
    timeout_seconds: float = PORT_VERIFY_TIMEOUT_SECONDS,
) -> None:
    if port_free(port):
        return
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if port_free(port):
            return
        time.sleep(0.1)
    raise OverheadError(f"port {port} did not free in time")


def _ensure_backend_port_ready(
    backend: Cell,
    check_port: PortFree,
    stop_runner: StopRunner,
) -> None:
    """Free the backend port when possible so this leg can own the serve.

    Matches matrix behavior for oMLX: `omlX stop` then wait. Other backends
    (OptiQ) still require the port already free — same as matrix.
    """
    backend_port = _port_from_base_url(backend.base_url)
    if check_port(backend_port):
        return
    if backend.server == "omlx":
        try:
            stop_runner(("omlX", "stop"))
            _verify_port_free(
                backend_port, check_port, timeout_seconds=OMLX_STOP_WAIT_SECONDS,
            )
        except (LifecycleError, OverheadError, OSError, PermissionError) as error:
            raise OverheadError(
                f"backend port {backend_port} is busy and oMLX stop failed: {error}"
            ) from error
        return
    raise OverheadError(f"backend port {backend_port} is busy")


def _na_result(reason: str, memory_before: int | None) -> CellResult:
    return CellResult(
        status="N/A",
        na_reason=reason,
        observations=(),
        summary={
            "measured_count": 0,
            "success_count": 0,
            "contract_pass_count": 0,
            "median_total_seconds": None,
            "median_ttft_seconds": None,
            "median_decode_tokens_per_second": None,
            "median_estimated_decode_tokens_per_second": None,
            "ttft_sample_count": 0,
            "decode_sample_count": 0,
            "estimated_decode_sample_count": 0,
            "by_workload": {},
        },
        memory_free_percent_before=memory_before,
        memory_free_percent_after=memory_before,
    )


def _leg_json(cell: Cell, result: CellResult) -> dict[str, Any]:
    return {
        "cell_id": cell.cell_id,
        "server": cell.server,
        "base_url": cell.base_url,
        "model_id": cell.model_id,
        "status": result.status,
        "na_reason": result.na_reason,
        "summary": result.summary,
        "memory_free_percent_before": result.memory_free_percent_before,
        "memory_free_percent_after": result.memory_free_percent_after,
        "observations": [item.as_json() for item in result.observations],
    }


def _run_leg(
    *,
    measure_cell_obj: Cell,
    backend: Cell,
    suite: MatrixSuite,
    mode: str,
    transport: LoopbackTransport,
    probe: HostResourceProbe,
    cancel: threading.Event,
    build: BuildServer,
    measure: MeasureCell,
    resolve_credential_fn: CredentialFor,
    log_dir: Path,
    ready_timeout: float,
    check_port: PortFree,
    stop_runner: StopRunner,
    measure_credential_server: str,
) -> CellResult:
    backend_port = _port_from_base_url(backend.base_url)
    memory_before = probe.free_memory_percent()
    try:
        _ensure_backend_port_ready(backend, check_port, stop_runner)
    except OverheadError as error:
        return _na_result(str(error), memory_before)

    backend_credential = resolve_credential(backend.server, resolve_credential_fn)
    handle = build(backend, transport, log_dir, backend_credential)
    try:
        handle.start()
        handle.wait_ready(backend.model_id, ready_timeout)
    except ServerError as error:
        try:
            handle.stop()
        except (ServerError, OSError, PermissionError):
            pass
        try:
            _verify_port_free(backend_port, check_port)
        except OverheadError:
            pass
        return _na_result(str(error), memory_before)

    measure_credential = resolve_credential(measure_credential_server, resolve_credential_fn)
    result = measure(
        measure_cell_obj, suite, mode, transport, probe, cancel, measure_credential,
    )
    try:
        handle.stop()
    except (ServerError, OSError, PermissionError):
        pass
    try:
        _verify_port_free(backend_port, check_port)
    except OverheadError as error:
        return _na_result(str(error), memory_before)
    return result


def run_overhead(
    pair_ids: tuple[str, ...],
    pairs_root: Path,
    cells_root: Path,
    suite_path: Path,
    results_root: Path,
    *,
    family_id: str = "gemma-4-12b-qat",
    mode: str = "screen",
    build_server: BuildServer | None = None,
    measure_cell: MeasureCell | None = None,
    probe: HostResourceProbe | None = None,
    port_free: PortFree | None = None,
    stop_runner: StopRunner | None = None,
    credential_for: CredentialFor | None = None,
    ready_timeout_seconds: float = DEFAULT_READY_TIMEOUT_SECONDS,
    memory_floor_percent: int = DEFAULT_MEMORY_FLOOR_PERCENT,
) -> Path:
    suite = MatrixSuite.load(suite_path)
    family = load_family(family_id)
    resource_probe = probe if probe is not None else HostResourceProbe()
    check_port = port_free or port_is_free
    stop = stop_runner or run_stop_command
    resolve_credential_fn = credential_for
    build = build_server or (
        lambda cell, transport, log_dir, credential: default_build_server(
            cell, transport, log_dir, credential=credential,
        )
    )
    measure = measure_cell or default_measure_cell

    run_dir = results_root / f"overhead-{_stamp()}"
    run_dir.mkdir(parents=True, exist_ok=False)
    log_dir = run_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    cancel = threading.Event()
    started_at = datetime.now(timezone.utc).isoformat()
    pair_records: list[dict[str, Any]] = []
    stopped_early = False
    stop_reason: str | None = None

    def _persist(finished: str) -> None:
        raw = {
            "schema_version": "overhead-run-1.0.0",
            "mode": mode,
            "suite_id": suite.suite_id,
            "suite_revision": suite.revision,
            "memory_floor_percent": memory_floor_percent,
            "ready_timeout_seconds": ready_timeout_seconds,
            "started_at": started_at,
            "finished_at": finished,
            "stopped_early": stopped_early,
            "stop_reason": stop_reason,
            "pairs": pair_records,
        }
        (run_dir / "raw.json").write_text(
            json.dumps(raw, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        (run_dir / "report.md").write_text(render_overhead_report(raw), encoding="utf-8")

    try:
        for pair_id in pair_ids:
            memory_before = resource_probe.free_memory_percent()
            if memory_before < memory_floor_percent:
                stopped_early = True
                stop_reason = "memory_floor"
                break

            pair = OverheadPair.load(pairs_root / f"{pair_id}.json")
            direct = Cell.load(cells_root / f"{pair.direct_cell_id}.json", family=family)
            backend = Cell.load(cells_root / f"{pair.backend_cell_id}.json", family=family)

            base_urls = {direct.base_url, pair.routed_base_url}
            transport = LoopbackTransport(base_urls)

            direct_result = _run_leg(
                measure_cell_obj=direct,
                backend=backend,
                suite=suite,
                mode=mode,
                transport=transport,
                probe=resource_probe,
                cancel=cancel,
                build=build,
                measure=measure,
                resolve_credential_fn=resolve_credential_fn,
                log_dir=log_dir,
                ready_timeout=ready_timeout_seconds,
                check_port=check_port,
                stop_runner=stop,
                measure_credential_server=direct.server,
            )

            memory_before = resource_probe.free_memory_percent()
            if memory_before < memory_floor_percent:
                pair_records.append({
                    "pair_id": pair.pair_id,
                    "direct_cell_id": pair.direct_cell_id,
                    "backend_cell_id": pair.backend_cell_id,
                    "routed_model_id": pair.routed_model_id,
                    "direct": _leg_json(direct, direct_result),
                    "routed": _leg_json(
                        make_routed_measure_cell(backend, pair, family=family),
                        _na_result("skipped: memory_floor", memory_before),
                    ),
                    "deltas": pair_deltas(
                        direct_result.summary,
                        _na_result("skipped: memory_floor", memory_before).summary,
                    ),
                })
                stopped_early = True
                stop_reason = "memory_floor"
                _persist(datetime.now(timezone.utc).isoformat())
                break

            try:
                require_osaurus_listening(port_free=check_port)
            except OverheadError as error:
                routed_cell = make_routed_measure_cell(backend, pair, family=family)
                routed_result = _na_result(str(error), memory_before)
                pair_records.append({
                    "pair_id": pair.pair_id,
                    "direct_cell_id": pair.direct_cell_id,
                    "backend_cell_id": pair.backend_cell_id,
                    "routed_model_id": pair.routed_model_id,
                    "direct": _leg_json(direct, direct_result),
                    "routed": _leg_json(routed_cell, routed_result),
                    "deltas": pair_deltas(direct_result.summary, routed_result.summary),
                })
                _persist(datetime.now(timezone.utc).isoformat())
                continue

            routed_cell = make_routed_measure_cell(backend, pair, family=family)
            routed_result = _run_leg(
                measure_cell_obj=routed_cell,
                backend=backend,
                suite=suite,
                mode=mode,
                transport=transport,
                probe=resource_probe,
                cancel=cancel,
                build=build,
                measure=measure,
                resolve_credential_fn=resolve_credential_fn,
                log_dir=log_dir,
                ready_timeout=ready_timeout_seconds,
                check_port=check_port,
                stop_runner=stop,
                measure_credential_server="osaurus",
            )

            pair_records.append({
                "pair_id": pair.pair_id,
                "direct_cell_id": pair.direct_cell_id,
                "backend_cell_id": pair.backend_cell_id,
                "routed_model_id": pair.routed_model_id,
                "direct": _leg_json(direct, direct_result),
                "routed": _leg_json(routed_cell, routed_result),
                "deltas": pair_deltas(direct_result.summary, routed_result.summary),
            })
            _persist(datetime.now(timezone.utc).isoformat())
    finally:
        _persist(datetime.now(timezone.utc).isoformat())

    return run_dir
