"""Per-cell preference and RAG metric extraction from a sealed bundle, for rulings.

Every function here is a pure reader: it takes an already-sealed run directory,
its state, and its plan, and returns rows or `None`. None of them raise on bad
input -- a malformed, absent, or unreadable payload yields `None`, exactly like
`_matrix_metric_rows` in results_browser. Partial rows are never produced:
either every cell in the plan gets a complete row, or the function returns
`None`.
"""

from __future__ import annotations

import json
from pathlib import Path

from .managed_run_types import ManagedRunPlan, ManagedRunState, ManagedStep


def _is_int(value: object) -> bool:
    # `isinstance(True, int)` is True in Python; reject bools explicitly.
    return isinstance(value, int) and not isinstance(value, bool)


def _is_number(value: object) -> bool:
    """A real number for comparison; rejects bool explicitly."""
    return (
        value is not None
        and not isinstance(value, bool)
        and isinstance(value, (int, float))
    )


def step_json(
    run_dir: Path, state: ManagedRunState, step: ManagedStep, filename: str
) -> dict | None:
    """Read one named JSON file out of a step's output directory."""
    record = next((item for item in state.steps if item.step is step), None)
    if record is None or not record.output_path:
        return None
    target = run_dir / record.output_path / filename
    try:
        if target.is_symlink() or not target.resolve().is_relative_to(
            run_dir.resolve()
        ):
            return None
    except OSError:
        return None
    try:
        raw = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return raw if isinstance(raw, dict) else None


def preference_rows(payload: dict | None, plan: ManagedRunPlan) -> list[dict] | None:
    """Emit one preference row per cell from a parsed `tally.json`."""
    if not isinstance(payload, dict):
        return None
    cells = payload.get("cells")
    if not isinstance(cells, dict):
        return None
    if set(cells) != set(plan.cell_ids):
        return None
    rows = []
    for cell_id in plan.cell_ids:
        entry = cells.get(cell_id)
        if not isinstance(entry, dict):
            return None
        wins = entry.get("wins")
        losses = entry.get("losses")
        ties = entry.get("ties")
        win_rate = entry.get("win_rate")
        if (
            not _is_int(wins)
            or not _is_int(losses)
            or not _is_int(ties)
            or not (win_rate is None or _is_number(win_rate))
        ):
            return None
        rows.append(
            {
                "cell_id": cell_id,
                "wins": wins,
                "losses": losses,
                "ties": ties,
                "win_rate": win_rate,
            }
        )
    return rows


def rag_rows(payload: dict | None, plan: ManagedRunPlan) -> list[dict] | None:
    """Emit one RAG row per cell from a parsed `scores.json`."""
    if not isinstance(payload, dict):
        return None
    mode = payload.get("mode")
    if mode not in ("oracle", "keyword"):
        return None
    cells = payload.get("cells")
    if not isinstance(cells, dict):
        return None
    if set(cells) != set(plan.cell_ids):
        return None
    rows = []
    for cell_id in plan.cell_ids:
        entry = cells.get(cell_id)
        if not isinstance(entry, dict):
            return None
        fact_hit_rate = entry.get("mean_hit_rate")
        if not _is_number(fact_hit_rate):
            return None
        retrieval_recall: float | None = None
        retrieval_precision: float | None = None
        if mode == "keyword":
            retrieval_recall = entry.get("mean_recall")
            retrieval_precision = entry.get("mean_precision")
            if not _is_number(retrieval_recall) or not _is_number(
                retrieval_precision
            ):
                return None
        rows.append(
            {
                "cell_id": cell_id,
                "fact_hit_rate": fact_hit_rate,
                "retrieval_recall": retrieval_recall,
                "retrieval_precision": retrieval_precision,
            }
        )
    return rows


def summary_values(raw: object) -> dict | None:
    """Pull the five matrix summary numbers, or None if any is not a number."""
    summary = raw.get("summary") if isinstance(raw, dict) else None
    if not isinstance(summary, dict):
        return None
    values = {
        key: summary.get(key)
        for key in (
            "median_total_seconds",
            "median_ttft_seconds",
            "success_count",
            "contract_pass_count",
            "measured_count",
        )
    }
    if any(
        value is not None
        and (isinstance(value, bool) or not isinstance(value, (int, float)))
        for value in values.values()
    ):
        return None
    return values


def matrix_rows(raw: dict | None, plan: ManagedRunPlan) -> list[dict] | None:
    """Emit one matrix row per cell from a parsed matrix `raw.json`."""
    cells = raw.get("cells") if isinstance(raw, dict) else None
    if not isinstance(cells, list):
        return None
    by_id: dict[str, dict] = {}
    for cell in cells:
        cell_id = cell.get("cell_id") if isinstance(cell, dict) else None
        if not isinstance(cell_id, str) or cell_id in by_id:
            return None
        by_id[cell_id] = cell
    if set(by_id) != set(plan.cell_ids):
        return None
    rows = []
    for cell_id in plan.cell_ids:
        cell = by_id[cell_id]
        family_id = cell.get("family_id")
        status = cell.get("status")
        summary = summary_values(cell)
        if (
            (family_id is not None and not isinstance(family_id, str))
            or not isinstance(status, str)
            or summary is None
        ):
            return None
        rows.append(
            {
                "cell_id": cell_id,
                "family_id": family_id,
                "status": status,
                **summary,
            }
        )
    return rows
