"""Campaign orchestration and 3×3 report for the Gemma matrix."""

from __future__ import annotations

import argparse
import json
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Sequence
from urllib.parse import urlparse

from .credentials import (
    OSAURUS_KEYCHAIN_SERVICE,
    Credential,
    CredentialError,
    KeychainCredentialProvider,
)
from .matrix_config import REPOSITORY_ROOT, Cell, Campaign, MatrixSuite
from .matrix_lifecycle import port_is_free
from .matrix_measure import MODES, CellResult, measure_cell as default_measure_cell
from .matrix_servers import (
    MATRIX_OMLX_API_KEY,
    ServerError,
    ServerHandle,
    build_server as default_build_server,
)
from .resources import HostResourceProbe
from .transport import LoopbackTransport

QUANT_ORDER = ("jang_4m", "oq4_fp16", "optiq_4bit")
SERVER_ORDER = ("osaurus", "omlx", "optiq")
PORT_VERIFY_TIMEOUT_SECONDS = 5.0

BuildServer = Callable[[Cell, LoopbackTransport, Path, Credential | None], ServerHandle]
MeasureCell = Callable[
    [
        Cell, MatrixSuite, str, LoopbackTransport, HostResourceProbe | None,
        threading.Event, Credential | None,
    ],
    CellResult,
]
PortFree = Callable[[int], bool]
CredentialFor = Callable[[str], Credential | None]


class MatrixRunnerError(RuntimeError):
    pass


def _stamp() -> str:
    return time.strftime("%Y%m%d-%H%M%S")


def _port_from_base_url(base_url: str) -> int:
    parsed = urlparse(base_url)
    if parsed.port is None:
        raise MatrixRunnerError(f"base_url has no port: {base_url}")
    return parsed.port


def _short_reason(reason: str | None) -> str:
    if not reason:
        return "unavailable"
    return reason.split("\n", maxsplit=1)[0].strip()


def _format_table_cell(entry: dict[str, Any] | None) -> str:
    if entry is None:
        return "-"
    status = entry["status"]
    if status == "N/A":
        return f"N/A {_short_reason(entry.get('na_reason'))}"
    if status == "PASS":
        median = (entry.get("summary") or {}).get("median_total_seconds")
        if isinstance(median, (int, float)):
            return f"PASS {median:.1f}s"
        return "PASS"
    if status == "FAIL":
        return "FAIL"
    return "-"


def _format_metric_cell(
    entry: dict[str, Any] | None,
    *,
    key: str,
    kind: str,
) -> str:
    if entry is None or entry.get("status") != "PASS":
        return "—"
    summary = entry.get("summary") or {}
    if kind == "ratio":
        success = summary.get("success_count")
        contract = summary.get("contract_pass_count")
        measured = summary.get("measured_count")
        if not isinstance(measured, int) or measured <= 0:
            return "—"
        if not isinstance(success, int) or not isinstance(contract, int):
            return "—"
        return f"{contract}/{success}"
    value = summary.get(key)
    if not isinstance(value, (int, float)):
        return "—"
    if kind == "seconds":
        return f"{value:.2f}s"
    if kind == "toks":
        return f"{value:.1f}"
    if kind == "toks_est":
        return f"{value:.1f} est."
    return "—"


def _metric_table(
    by_key: dict[tuple[str, str], dict[str, Any]],
    *,
    title: str,
    key: str,
    kind: str,
) -> list[str]:
    lines = [
        f"### {title}",
        "",
        "| quant \\\\ server | osaurus | omlx | optiq |",
        "|---|---|---|---|",
    ]
    for quant in QUANT_ORDER:
        cells = [
            _format_metric_cell(by_key.get((quant, server)), key=key, kind=kind)
            for server in SERVER_ORDER
        ]
        lines.append(f"| {quant} | {' | '.join(cells)} |")
    lines.append("")
    return lines


def _cell_json(cell: Cell, result: CellResult) -> dict[str, Any]:
    return {
        "cell_id": cell.cell_id,
        "quant": cell.quant,
        "server": cell.server,
        "status": result.status,
        "na_reason": result.na_reason,
        "summary": result.summary,
        "memory_free_percent_before": result.memory_free_percent_before,
        "memory_free_percent_after": result.memory_free_percent_after,
        "observations": [item.as_json() for item in result.observations],
    }


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


def render_report(raw: dict[str, Any]) -> str:
    by_key = {(item["quant"], item["server"]): item for item in raw["cells"]}
    lines = [
        f"# Matrix campaign {raw['campaign_id']}",
        "",
        f"Mode: `{raw['mode']}`",
        f"Suite: `{raw['suite_id']}` revision `{raw['suite_revision']}`",
        "",
        "## 3×3 results",
        "",
        "| quant \\\\ server | osaurus | omlx | optiq |",
        "|---|---|---|---|",
    ]
    for quant in QUANT_ORDER:
        cells = [_format_table_cell(by_key.get((quant, server))) for server in SERVER_ORDER]
        lines.append(f"| {quant} | {' | '.join(cells)} |")
    if raw.get("stopped_early"):
        lines.extend(["", f"Campaign stopped early: `{raw.get('stop_reason')}`"])
    lines.extend([
        "",
        "## Metrics",
        "",
        "Option A decode tok/s requires incremental streaming and `EXACT_VISIBLE` token accounting. "
        "Option B estimated decode tok/s uses `completion_tokens / (total − TTFT)` when incremental "
        "timing exists (labeled `est.`). Incomparable cells show `—`.",
        "",
    ])
    lines.extend(_metric_table(
        by_key, title="Median total latency", key="median_total_seconds", kind="seconds",
    ))
    lines.extend(_metric_table(
        by_key, title="Median TTFT", key="median_ttft_seconds", kind="seconds",
    ))
    lines.extend(_metric_table(
        by_key,
        title="Median decode tok/s (exact)",
        key="median_decode_tokens_per_second",
        kind="toks",
    ))
    lines.extend(_metric_table(
        by_key,
        title="Median decode tok/s (estimated)",
        key="median_estimated_decode_tokens_per_second",
        kind="toks_est",
    ))
    lines.extend(_metric_table(
        by_key, title="Contract passes / successes", key="", kind="ratio",
    ))
    return "\n".join(lines)


def _credential_for(server: str) -> Credential | None:
    if server == "optiq":
        return None
    if server == "omlx":
        # Matrix-owned oMLX serve gets a fixed loopback API key at spawn time.
        return Credential(MATRIX_OMLX_API_KEY)
    if server == "osaurus":
        try:
            return KeychainCredentialProvider(OSAURUS_KEYCHAIN_SERVICE).get()
        except CredentialError as error:
            raise MatrixRunnerError(
                "Osaurus harness Keychain item missing: "
                "create local.jrazz.lmre.osaurus / benchmark-harness "
                "(see docs/matrix.md). Do not paste the key into chat."
            ) from error
    raise MatrixRunnerError(f"unknown server {server!r}")


def _verify_port_free(port: int, port_free: PortFree) -> None:
    if port_free(port):
        return
    deadline = time.monotonic() + PORT_VERIFY_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        if port_free(port):
            return
        time.sleep(0.1)
    raise MatrixRunnerError(f"port {port} did not free in time")


def run_campaign(
    campaign: Campaign,
    mode: str,
    results_dir: Path,
    *,
    cell_filter: tuple[str, ...] | None = None,
    cells: tuple[Cell, ...] | None = None,
    build_server: BuildServer | None = None,
    measure_cell: MeasureCell | None = None,
    probe: HostResourceProbe | None = None,
    port_free: PortFree | None = None,
    credential_for: CredentialFor | None = None,
) -> Path:
    if mode not in MODES:
        raise MatrixRunnerError(f"unknown mode {mode!r}")

    suite = MatrixSuite.load(campaign.suite_path)
    loaded_cells = cells if cells is not None else tuple(
        Cell.load(path, family=campaign.family) for path in campaign.cell_paths
    )
    if cell_filter is not None:
        allowed = set(cell_filter)
        loaded_cells = tuple(cell for cell in loaded_cells if cell.cell_id in allowed)

    resource_probe = probe if probe is not None else HostResourceProbe()
    check_port = port_free or port_is_free
    resolve_credential = credential_for or _credential_for
    build = build_server or (
        lambda cell, transport, log_dir, credential: default_build_server(
            cell, transport, log_dir, credential=credential,
        )
    )
    measure = measure_cell or default_measure_cell

    run_dir = results_dir / f"{campaign.campaign_id}-{mode}-{_stamp()}"
    run_dir.mkdir(parents=True, exist_ok=False)
    log_dir = run_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    base_urls = {cell.base_url for cell in loaded_cells}
    transport = LoopbackTransport(base_urls)
    cancel = threading.Event()

    started_at = datetime.now(timezone.utc).isoformat()
    records: list[dict[str, Any]] = []
    stopped_early = False
    stop_reason: str | None = None
    previous: ServerHandle | None = None

    def _persist(finished: str) -> None:
        raw = {
            "schema_version": "matrix-campaign-1.0.0",
            "campaign_id": campaign.campaign_id,
            "mode": mode,
            "suite_id": suite.suite_id,
            "suite_revision": suite.revision,
            "memory_floor_percent": campaign.memory_floor_percent,
            "ready_timeout_seconds": campaign.ready_timeout_seconds,
            "request_timeout_seconds": campaign.request_timeout_seconds,
            "on_cell_failure": campaign.on_cell_failure,
            "started_at": started_at,
            "finished_at": finished,
            "stopped_early": stopped_early,
            "stop_reason": stop_reason,
            "cells": records,
        }
        (run_dir / "raw.json").write_text(
            json.dumps(raw, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        (run_dir / "report.md").write_text(render_report(raw), encoding="utf-8")

    try:
        for cell in loaded_cells:
            memory_before = resource_probe.free_memory_percent()
            if memory_before < campaign.memory_floor_percent:
                stopped_early = True
                stop_reason = "memory_floor"
                break

            if previous is not None:
                try:
                    previous.stop()
                except (ServerError, OSError, PermissionError):
                    pass

            credential = resolve_credential(cell.server)
            handle = build(cell, transport, log_dir, credential)
            try:
                handle.start()
                handle.wait_ready(cell.model_id, campaign.ready_timeout_seconds)
            except ServerError as error:
                records.append(_cell_json(cell, _na_result(str(error), memory_before)))
                try:
                    handle.stop()
                except (ServerError, OSError, PermissionError):
                    pass
                if cell.server != "osaurus":
                    _verify_port_free(_port_from_base_url(cell.base_url), check_port)
                previous = handle
                _persist(datetime.now(timezone.utc).isoformat())
                if campaign.on_cell_failure != "continue":
                    stopped_early = True
                    stop_reason = "cell_failure"
                    break
                continue

            result = measure(cell, suite, mode, transport, resource_probe, cancel, credential)
            records.append(_cell_json(cell, result))
            try:
                handle.stop()
            except (ServerError, OSError, PermissionError):
                pass
            if cell.server != "osaurus":
                _verify_port_free(_port_from_base_url(cell.base_url), check_port)
            previous = handle
            _persist(datetime.now(timezone.utc).isoformat())

            if result.status == "FAIL" and campaign.on_cell_failure != "continue":
                stopped_early = True
                stop_reason = "cell_failure"
                break
    finally:
        _persist(datetime.now(timezone.utc).isoformat())

    return run_dir


DEFAULT_CAMPAIGN = REPOSITORY_ROOT / "config" / "matrix" / "gemma-4-12b-qat-campaign.json"


def _resolve_repo_path(path: Path) -> Path:
    if path.is_absolute():
        return path
    return (REPOSITORY_ROOT / path).resolve()


def _parse_cell_filter(raw: str | None) -> tuple[str, ...] | None:
    if raw is None:
        return None
    parts = tuple(part.strip() for part in raw.split(",") if part.strip())
    return parts or None


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="lmre-matrix",
        description="Gemma 4 12B QAT 3×3 matrix campaign across Osaurus, oMLX, and OptiQ.",
    )
    parser.add_argument(
        "--campaign",
        type=Path,
        default=DEFAULT_CAMPAIGN,
        help="Campaign JSON under config/matrix/",
    )
    parser.add_argument("--mode", choices=sorted(MODES), default="screen")
    parser.add_argument(
        "--cells",
        help="Comma-separated cell ids to run (default: all nine)",
    )
    parser.add_argument(
        "--results-dir",
        type=Path,
        default=None,
        help="Output root (default: campaign results_root)",
    )
    parser.add_argument(
        "--dry-config",
        action="store_true",
        help="Load and validate campaign, suite, and cells only; no network contact.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        campaign = Campaign.load(_resolve_repo_path(args.campaign))
        suite = MatrixSuite.load(campaign.suite_path)
        cell_filter = _parse_cell_filter(args.cells)
        cells = tuple(Cell.load(path, family=campaign.family) for path in campaign.cell_paths)
        if cell_filter is not None:
            allowed = set(cell_filter)
            cells = tuple(cell for cell in cells if cell.cell_id in allowed)

        if args.dry_config:
            artifact_paths = sorted({cell.artifact_path for cell in cells})
            artifact_missing = [
                path for path in artifact_paths if not Path(path).exists()
            ]
            print(json.dumps({
                "ok": True,
                "campaign_id": campaign.campaign_id,
                "family_id": campaign.family_id,
                "mode": args.mode,
                "suite_id": suite.suite_id,
                "suite_revision": suite.revision,
                "cell_count": len(cells),
                "cells": [cell.cell_id for cell in cells],
                "artifact_missing": artifact_missing,
            }, sort_keys=True))
            return 0

        results_dir = campaign.results_root if args.results_dir is None else _resolve_repo_path(
            args.results_dir
        )
        run_dir = run_campaign(
            campaign,
            args.mode,
            results_dir,
            cell_filter=cell_filter,
        )
        print(json.dumps({"ok": True, "run_dir": str(run_dir)}, sort_keys=True))
        return 0
    except Exception as error:
        print(json.dumps({
            "ok": False,
            "error": {
                "kind": getattr(error, "code", error.__class__.__name__),
                "message": str(error),
            },
        }, sort_keys=True))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
