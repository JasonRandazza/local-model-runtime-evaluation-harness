"""Read-only offline inspection for controlled comparison classes."""

from __future__ import annotations

import os
from pathlib import Path

from .artifact_profile import (
    DEFAULT_MACHINE_PROFILE_PATH,
    ArtifactRoots,
    load_artifact_roots,
)
from .comparison_class import (
    DEFAULT_COMPARISON_CLASSES_ROOT,
    SAFE_ID,
    ComparisonClass,
    ComparisonClassError,
)
from .matrix_config import (
    DEFAULT_FAMILIES_ROOT,
    REPOSITORY_ROOT,
    Cell,
    MatrixError,
)


INSPECTION_SCHEMA_VERSION = "1.0.0"
LIVE_STATUS_NOT_CHECKED = "NOT_CHECKED_LIVE"
STATUS_BASELINE_ONLY = "BASELINE_ONLY"
STATUS_REVIEWED_CANDIDATES_AVAILABLE = "REVIEWED_CANDIDATES_AVAILABLE"
STATUS_DECLARED_EXPANSION_READY = "DECLARED_EXPANSION_READY"
STATUS_ACTION_REQUIRED = "ACTION_REQUIRED"

ARTIFACT_PRESENT = "PRESENT"
ARTIFACT_MISSING = "MISSING"
ARTIFACT_WRONG_KIND = "WRONG_KIND"
ARTIFACT_UNREADABLE = "UNREADABLE"
ARTIFACT_INVALID_TEMPLATE = "INVALID_TEMPLATE"


def _artifact_status(path: Path) -> str:
    if not path.exists():
        return ARTIFACT_MISSING
    if not path.is_dir():
        return ARTIFACT_WRONG_KIND
    if not os.access(path, os.R_OK):
        return ARTIFACT_UNREADABLE
    return ARTIFACT_PRESENT


def _artifact_finding(
    cell: Cell,
    roots: ArtifactRoots,
    *,
    role: str,
) -> dict[str, object]:
    try:
        resolved = cell.resolve(roots)
    except MatrixError:
        return {
            "cell_id": cell.cell_id,
            "role": role,
            "server": cell.server,
            "artifact_path": None,
            "status": ARTIFACT_INVALID_TEMPLATE,
        }
    path = Path(resolved.artifact_path)
    return {
        "cell_id": cell.cell_id,
        "role": role,
        "server": cell.server,
        "artifact_path": str(path),
        "status": _artifact_status(path),
    }


def _reviewed_candidates(
    definition: ComparisonClass,
    roots: ArtifactRoots,
    cells_root: Path,
) -> list[dict[str, object]]:
    baseline_quants = {cell.quant for cell in definition.campaign.cells}
    candidates: list[dict[str, object]] = []
    for quant_id, quant in sorted(definition.campaign.family.quants.items()):
        if quant_id in baseline_quants:
            continue
        cell_id = f"{quant_id}__{quant.native_server}"
        path = cells_root / f"{cell_id}.json"
        if not path.is_file() or path.is_symlink():
            continue
        try:
            cell = Cell.load(path, family=definition.campaign.family)
        except (MatrixError, OSError, ValueError, KeyError, TypeError):
            continue
        finding = _artifact_finding(cell, roots, role="candidate")
        finding["selected"] = cell.cell_id in definition.extra_cell_ids
        candidates.append(finding)
    return candidates


def inspect_comparison_class(
    comparison_class_id: str,
    *,
    machine_profile_path: Path = DEFAULT_MACHINE_PROFILE_PATH,
    comparison_classes_root: Path = DEFAULT_COMPARISON_CLASSES_ROOT,
    repository_root: Path = REPOSITORY_ROOT,
    families_root: Path = DEFAULT_FAMILIES_ROOT,
    cells_root: Path | None = None,
) -> dict[str, object]:
    """Inspect checked-in class and artifact readiness without live contact."""

    if not isinstance(comparison_class_id, str) or not SAFE_ID.fullmatch(
        comparison_class_id
    ):
        raise ComparisonClassError("comparison_class_id is invalid")
    resolved_cells_root = (
        cells_root
        or repository_root / "config" / "matrix" / "cells"
    )
    definition = ComparisonClass.load(
        comparison_classes_root / f"{comparison_class_id}.json",
        repository_root=repository_root,
        families_root=families_root,
        cells_root=resolved_cells_root,
    )
    roots = load_artifact_roots(machine_profile_path)
    selected_artifacts = [
        _artifact_finding(
            cell,
            roots,
            role=(
                "baseline"
                if cell.cell_id in definition.baseline_cell_ids
                else "extra"
            ),
        )
        for cell in definition.cells
    ]
    candidates = _reviewed_candidates(
        definition,
        roots,
        resolved_cells_root,
    )
    selected_ready = all(
        item["status"] == ARTIFACT_PRESENT
        for item in selected_artifacts
    )
    if not selected_ready:
        status = STATUS_ACTION_REQUIRED
        next_action = (
            "Repair the selected artifact paths or machine profile before "
            "creating an expansion plan."
        )
    elif definition.extra_cell_ids:
        status = STATUS_DECLARED_EXPANSION_READY
        next_action = (
            "Review adopted policy limits, then create and inspect an "
            "immutable class-bound plan."
        )
    elif candidates:
        status = STATUS_REVIEWED_CANDIDATES_AVAILABLE
        next_action = (
            "Review an available candidate and add it only through a new "
            "versioned comparison class."
        )
    else:
        status = STATUS_BASELINE_ONLY
        next_action = (
            "Add a reviewed same-family native quant and cell before creating "
            "a new versioned expansion class."
        )

    return {
        "schema_version": INSPECTION_SCHEMA_VERSION,
        "comparison_class_id": definition.comparison_class_id,
        "family_id": definition.family_id,
        "revision": definition.revision,
        "status": status,
        "class_shape": (
            "EXPANDED" if definition.extra_cell_ids else STATUS_BASELINE_ONLY
        ),
        "live_status": LIVE_STATUS_NOT_CHECKED,
        "ready_for_expansion_plan": (
            status == STATUS_DECLARED_EXPANSION_READY
        ),
        "estimated_minutes": definition.estimated_minutes,
        "baseline_cell_ids": list(definition.baseline_cell_ids),
        "extra_cell_ids": list(definition.extra_cell_ids),
        "selected_cell_ids": list(definition.cell_ids),
        "selected_artifacts": selected_artifacts,
        "reviewed_candidates": candidates,
        "next_action": next_action,
    }
