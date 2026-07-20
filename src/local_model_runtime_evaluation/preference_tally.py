"""Score human preference judgments into per-cell tallies and reports."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .preference_config import PreferenceError

VALID_WINNERS = frozenset({"A", "B", "tie"})


def _empty_cell_stats() -> dict[str, int | float | None]:
    return {"wins": 0, "losses": 0, "ties": 0, "win_rate": None}


def _finalize_win_rates(stats: dict[str, dict[str, int | float | None]]) -> None:
    for cell_stats in stats.values():
        wins = int(cell_stats["wins"])
        losses = int(cell_stats["losses"])
        total = wins + losses
        cell_stats["win_rate"] = (wins / total) if total else None


def _collect_cells(pairs: list[dict[str, Any]]) -> set[str]:
    cells: set[str] = set()
    for pair in pairs:
        cell_a = pair.get("cell_a")
        cell_b = pair.get("cell_b")
        if not isinstance(cell_a, str) or not isinstance(cell_b, str):
            raise PreferenceError("pair cell_a and cell_b must be strings")
        cells.add(cell_a)
        cells.add(cell_b)
    return cells


def _judgments_by_pair_id(judgments: list[dict[str, Any]]) -> dict[str, Any]:
    by_id: dict[str, Any] = {}
    for item in judgments:
        if not isinstance(item, dict):
            raise PreferenceError("judgment entries must be objects")
        pair_id = item.get("pair_id")
        if not isinstance(pair_id, str) or not pair_id:
            raise PreferenceError("judgment pair_id must be a non-empty string")
        by_id[pair_id] = item.get("winner")
    return by_id


def tally(
    pairs: list[dict[str, Any]],
    judgments: list[dict[str, Any]],
) -> dict[str, dict[str, int | float | None]]:
    cells = _collect_cells(pairs)
    stats = {cell_id: _empty_cell_stats() for cell_id in sorted(cells)}
    winners = _judgments_by_pair_id(judgments)

    missing: list[str] = []
    for pair in pairs:
        pair_id = pair.get("pair_id")
        if not isinstance(pair_id, str) or not pair_id:
            raise PreferenceError("pair pair_id must be a non-empty string")
        winner = winners.get(pair_id)
        if winner is None:
            missing.append(pair_id)
            continue
        if winner not in VALID_WINNERS:
            raise PreferenceError(
                f"invalid winner for pair {pair_id!r}: {winner!r} "
                "(expected A, B, or tie)"
            )

        cell_a = pair["cell_a"]
        cell_b = pair["cell_b"]
        if winner == "A":
            stats[cell_a]["wins"] = int(stats[cell_a]["wins"]) + 1
            stats[cell_b]["losses"] = int(stats[cell_b]["losses"]) + 1
        elif winner == "B":
            stats[cell_b]["wins"] = int(stats[cell_b]["wins"]) + 1
            stats[cell_a]["losses"] = int(stats[cell_a]["losses"]) + 1
        else:
            stats[cell_a]["ties"] = int(stats[cell_a]["ties"]) + 1
            stats[cell_b]["ties"] = int(stats[cell_b]["ties"]) + 1

    if missing:
        raise PreferenceError(
            "missing or null winner for pair ids: " + ", ".join(sorted(missing))
        )

    _finalize_win_rates(stats)
    return stats


def _format_win_rate(value: int | float | None) -> str:
    if value is None:
        return "—"
    return f"{value:.3f}"


def render_tally_report(
    stats: dict[str, dict[str, int | float | None]],
    *,
    run_id: str,
    suite_id: str | None = None,
) -> str:
    lines = [
        "# Preference tally",
        "",
        f"Run: `{run_id}`",
    ]
    if suite_id:
        lines.append(f"Suite: `{suite_id}`")
    lines.extend([
        "",
        "| Cell | Wins | Losses | Ties | Win rate |",
        "| --- | ---: | ---: | ---: | ---: |",
    ])
    for cell_id in sorted(stats):
        cell_stats = stats[cell_id]
        lines.append(
            f"| {cell_id} | {cell_stats['wins']} | {cell_stats['losses']} | "
            f"{cell_stats['ties']} | {_format_win_rate(cell_stats['win_rate'])} |"
        )
    lines.extend([
        "",
        "Latency was not used for preference scoring.",
        "",
    ])
    return "\n".join(lines)


def _load_pairs(run_dir: Path) -> list[dict[str, Any]]:
    path = run_dir / "pairs.json"
    if not path.is_file():
        raise PreferenceError(f"missing pairs file: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise PreferenceError("pairs.json must be a JSON object")
    pairs = payload.get("pairs")
    if not isinstance(pairs, list):
        raise PreferenceError("pairs.json must contain a pairs array")
    return pairs


def _load_judgments(run_dir: Path) -> list[dict[str, Any]]:
    path = run_dir / "judgments.json"
    if not path.is_file():
        raise PreferenceError(f"missing judgments file: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise PreferenceError("judgments.json must be a JSON object")
    judgments = payload.get("judgments")
    if not isinstance(judgments, list):
        raise PreferenceError("judgments.json must contain a judgments array")
    return judgments


def _load_run_metadata(run_dir: Path) -> tuple[str, str | None]:
    raw_path = run_dir / "raw.json"
    if raw_path.is_file():
        payload = json.loads(raw_path.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            suite_id = payload.get("suite_id")
            if isinstance(suite_id, str) and suite_id:
                return run_dir.name, suite_id
    return run_dir.name, None


def run_tally(run_dir: Path) -> Path:
    pairs = _load_pairs(run_dir)
    judgments = _load_judgments(run_dir)
    stats = tally(pairs, judgments)
    run_id, suite_id = _load_run_metadata(run_dir)
    report = render_tally_report(stats, run_id=run_id, suite_id=suite_id)
    (run_dir / "report.md").write_text(report, encoding="utf-8")
    tally_payload = {
        "run_id": run_id,
        "suite_id": suite_id,
        "cells": stats,
    }
    (run_dir / "tally.json").write_text(
        json.dumps(tally_payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return run_dir
