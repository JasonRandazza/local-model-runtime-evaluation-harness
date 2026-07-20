"""Paired delta report for Osaurus routing overhead runs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def pair_deltas(direct_summary: dict[str, Any], routed_summary: dict[str, Any]) -> dict[str, Any]:
    direct_total = direct_summary.get("median_total_seconds")
    routed_total = routed_summary.get("median_total_seconds")
    direct_ttft = direct_summary.get("median_ttft_seconds")
    routed_ttft = routed_summary.get("median_ttft_seconds")

    delta_total: float | None = None
    if isinstance(direct_total, (int, float)) and isinstance(routed_total, (int, float)):
        delta_total = float(routed_total) - float(direct_total)

    delta_ttft: float | None = None
    if isinstance(direct_ttft, (int, float)) and isinstance(routed_ttft, (int, float)):
        delta_ttft = float(routed_ttft) - float(direct_ttft)

    return {
        "direct_median_total_seconds": direct_total,
        "routed_median_total_seconds": routed_total,
        "delta_median_total_seconds": delta_total,
        "direct_median_ttft_seconds": direct_ttft,
        "routed_median_ttft_seconds": routed_ttft,
        "delta_median_ttft_seconds": delta_ttft,
    }


def _format_seconds(value: object) -> str:
    if not isinstance(value, (int, float)):
        return "—"
    return f"{value:.2f}s"


def _format_delta(value: object) -> str:
    if not isinstance(value, (int, float)):
        return "—"
    sign = "+" if value >= 0 else ""
    return f"{sign}{value:.2f}s"


def render_overhead_report(raw: dict[str, Any]) -> str:
    lines = [
        "# Osaurus routing overhead",
        "",
        f"Mode: `{raw.get('mode', 'screen')}`",
        f"Suite: `{raw.get('suite_id', '')}` revision `{raw.get('suite_revision', '')}`",
        "",
        "Primary metric: Δ median total latency (routed − direct). "
        "Secondary: Δ median TTFT.",
        "",
        "| Pair | Direct median total | Routed median total | Δ total | Δ TTFT | Direct status | Routed status |",
        "|---|---|---|---|---|---|---|",
    ]
    for pair in raw.get("pairs", []):
        deltas = pair.get("deltas") or pair_deltas(
            (pair.get("direct") or {}).get("summary") or {},
            (pair.get("routed") or {}).get("summary") or {},
        )
        direct = pair.get("direct") or {}
        routed = pair.get("routed") or {}
        lines.append(
            "| {pair_id} | {direct_total} | {routed_total} | {delta_total} | {delta_ttft} | {direct_status} | {routed_status} |".format(
                pair_id=pair.get("pair_id", ""),
                direct_total=_format_seconds(deltas.get("direct_median_total_seconds")),
                routed_total=_format_seconds(deltas.get("routed_median_total_seconds")),
                delta_total=_format_delta(deltas.get("delta_median_total_seconds")),
                delta_ttft=_format_delta(deltas.get("delta_median_ttft_seconds")),
                direct_status=direct.get("status", "—"),
                routed_status=routed.get("status", "—"),
            )
        )
    if raw.get("stopped_early"):
        lines.extend(["", f"Run stopped early: `{raw.get('stop_reason')}`"])
    lines.extend([
        "",
        "Note: a full equal-weight metric pack (including estimated decode tok/s) is a later expansion.",
        "",
    ])
    return "\n".join(lines)


def write_report(run_dir: Path) -> Path:
    raw = json.loads((run_dir / "raw.json").read_text(encoding="utf-8"))
    report_path = run_dir / "report.md"
    report_path.write_text(render_overhead_report(raw), encoding="utf-8")
    return report_path
