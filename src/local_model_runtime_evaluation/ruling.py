"""Draw a conclusion from one sealed run, under one rubric.

`build_ruling` is the behavioural seam and it **never raises**. Every failure
mode -- an unsealed bundle, a corrupt one, a run that did not finish, a metric
the evidence cannot supply -- is a value in the returned structure. Callers
render what they are given; they never catch.

A ruling names a cell, never a native server: the diagonal runs a different
quant per server, so stack and quant vary together and the evidence cannot
support a server-level claim (docs/adr/0004). Floors gate and one metric orders
the survivors -- never a weighted score (docs/adr/0005). The rubric is hashed
into the ruling but never into the plan, so changing taste re-rules old
evidence rather than invalidating it (docs/adr/0006).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from .cell_metrics import matrix_rows, preference_rows, rag_rows, step_json
from .evidence_bundle import EvidenceBundle, EvidenceError
from .managed_run_types import ManagedRunPlan, ManagedRunState, ManagedStep, StepState
from .results_browser import HEALTH_SEALED_VERIFIED, classify_bundle
from .rubric import Rubric

SCHEMA_VERSION = "ruling-1.0.0"

# Outcome states. UNAVAILABLE means the harness declined to conclude; it is
# never a quiet fallback to the least-bad cell.
CELL_NAMED = "CELL_NAMED"
NO_CELL_QUALIFIES = "NO_CELL_QUALIFIES"
UNAVAILABLE = "UNAVAILABLE"

# A step in one of these states did not produce evidence a ruling may rest on.
_UNFINISHED = frozenset(
    {
        StepState.PENDING,
        StepState.RUNNING,
        StepState.FAIL,
        StepState.BLOCKED_PROVIDER_RECONNECT,
        StepState.STOPPED,
    }
)

# Which step supplies each metric namespace, and how to read that step's file.
# `rag.*` is deliberately absent: two steps produce RAG scores, so an
# unprefixed name could not say which one a floor gated on.
_SOURCES = {
    "matrix": (ManagedStep.MATRIX, "raw.json", matrix_rows),
    "preference": (ManagedStep.PREFERENCE, "tally.json", preference_rows),
    "rag_oracle": (ManagedStep.RAG_ORACLE, "scores.json", rag_rows),
    "rag_keyword": (ManagedStep.RAG_KEYWORD, "scores.json", rag_rows),
}


def rubric_hash(rubric: Rubric) -> str:
    """Hash a rubric by value, so a ruling cannot be re-read under other criteria."""
    body = json.dumps(asdict(rubric), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def _unavailable(reason: str, code: str) -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "outcome": {"state": UNAVAILABLE, "cell_id": None, "reason": reason},
        "code": code,
        "cells": [],
    }


def _namespaces(rubric: Rubric) -> set[str]:
    metrics = [floor.metric for floor in rubric.floors] + [rubric.order_by.metric]
    return {metric.split(".", 1)[0] for metric in metrics}


def _measured(
    run_dir: Path, plan: ManagedRunPlan, state: ManagedRunState, rubric: Rubric
) -> tuple[dict[str, dict[str, float | None]] | None, str | None]:
    """Map cell_id -> {metric: value}, or (None, reason) if any source is unusable.

    Fails closed as a whole: a rubric that names a metric this run cannot
    supply produces no ruling at all, rather than a ruling that silently
    skipped a floor.
    """
    values: dict[str, dict[str, float | None]] = {
        cell_id: {} for cell_id in plan.cell_ids
    }
    for namespace in sorted(_namespaces(rubric)):
        step, filename, reader = _SOURCES[namespace]
        record = next((item for item in state.steps if item.step is step), None)
        if record is None:
            return None, f"run has no {step.value} step"
        if record.state is StepState.INCOMPARABLE:
            # Evidence that cannot honestly sit beside the others must not win
            # by being fastest.
            return None, f"{step.value} step is INCOMPARABLE"
        if record.state is StepState.NOT_APPLICABLE:
            # Nothing to measure is not the same as measured badly, but a
            # rubric that gates on it still cannot be applied.
            return None, f"{step.value} step is N/A, so it supplies no metric"
        rows = reader(step_json(run_dir, state, step, filename), plan)
        if rows is None:
            return None, f"{step.value} metrics are missing or malformed"
        for row in rows:
            for key, value in row.items():
                if key in ("cell_id", "family_id", "status"):
                    continue
                values[row["cell_id"]][f"{namespace}.{key}"] = value
    return values, None


_COMPARATORS = {
    ">=": lambda a, b: a >= b,
    "<=": lambda a, b: a <= b,
    ">": lambda a, b: a > b,
    "<": lambda a, b: a < b,
    "==": lambda a, b: a == b,
}


def _judge(cell_id: str, measured: dict, rubric: Rubric, family_id: str | None) -> dict:
    """Score one cell against every floor, reporting each measured value."""
    floors = []
    qualified = True
    for floor in rubric.floors:
        value = measured.get(floor.metric)
        passed = value is not None and _COMPARATORS[floor.comparator](
            float(value), floor.value
        )
        if not passed:
            qualified = False
        floors.append(
            {
                "metric": floor.metric,
                "comparator": floor.comparator,
                "value": floor.value,
                "measured": value,
                "passed": passed,
            }
        )
    order_value = measured.get(rubric.order_by.metric)
    if order_value is None:
        # A survivor the ordering metric cannot rank is not a survivor.
        qualified = False
    return {
        "cell_id": cell_id,
        "family_id": family_id,
        "floors": floors,
        "order_by": {"metric": rubric.order_by.metric, "measured": order_value},
        "qualified": qualified,
    }


def pick_winner(survivors: list[dict], direction: str) -> dict:
    """Rank survivors on the ordering metric, breaking ties by cell_id.

    The tie-break is explicit rather than leaning on sort stability, so the
    winner does not depend on the order the cells happened to arrive in.
    """
    reverse = direction == "desc"
    return sorted(
        survivors,
        key=lambda cell: (
            -float(cell["order_by"]["measured"])
            if reverse
            else float(cell["order_by"]["measured"]),
            cell["cell_id"],
        ),
    )[0]


def build_ruling(run_dir: Path, rubric: Rubric, *, now: datetime | None = None) -> dict:
    """Rule over one sealed run. Never raises; every failure is a value."""
    stamp = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    created_at = stamp.isoformat().replace("+00:00", "Z")

    health, detail = classify_bundle(run_dir)
    if health != HEALTH_SEALED_VERIFIED:
        return _unavailable(
            f"bundle is not sealed and verified ({health}): {detail}".rstrip(": "),
            "bundle_not_trusted",
        )
    try:
        bundle = EvidenceBundle.load(run_dir)
    except EvidenceError as error:
        # classify_bundle already loaded this; the tree changed under us.
        return _unavailable(f"bundle could not be loaded: {error}", "bundle_unreadable")

    plan, state = bundle.plan, bundle.state
    unfinished = [
        item.step.value for item in state.steps if item.state in _UNFINISHED
    ]
    if unfinished:
        return _unavailable(
            "run did not complete every step: " + ", ".join(sorted(unfinished)),
            "run_incomplete",
        )
    if not plan.cell_ids:
        return _unavailable("run has no cells to rule over", "no_cells")

    measured, reason = _measured(run_dir, plan, state, rubric)
    if measured is None:
        return _unavailable(reason or "metrics are unavailable", "metrics_unavailable")

    families = {
        row["cell_id"]: row.get("family_id")
        for row in (matrix_rows(step_json(run_dir, state, ManagedStep.MATRIX, "raw.json"), plan) or [])
    }
    cells = [
        _judge(cell_id, measured[cell_id], rubric, families.get(cell_id))
        for cell_id in plan.cell_ids
    ]

    survivors = [cell for cell in cells if cell["qualified"]]
    if survivors:
        winner = pick_winner(survivors, rubric.order_by.direction)
        outcome = {
            "state": CELL_NAMED,
            "cell_id": winner["cell_id"],
            "reason": (
                f"cleared every floor and ordered first on "
                f"{rubric.order_by.metric} ({rubric.order_by.direction})"
            ),
        }
    else:
        outcome = {
            "state": NO_CELL_QUALIFIES,
            "cell_id": None,
            "reason": "no cell cleared every floor",
        }

    return {
        "schema_version": SCHEMA_VERSION,
        "ruling_id": f"{plan.identity.run_id}--{rubric.rubric_id}--{created_at}",
        "created_at": created_at,
        "run_id": plan.identity.run_id,
        "plan_hash": plan.plan_hash,
        "comparison_id": plan.identity.comparison_id,
        "family_id": plan.family_id,
        "rubric": {
            "rubric_id": rubric.rubric_id,
            "revision": rubric.revision,
            "hash": rubric_hash(rubric),
        },
        "cells": cells,
        "outcome": outcome,
    }
