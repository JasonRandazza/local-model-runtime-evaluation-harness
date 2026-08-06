"""Read-only static inspection for checked-in heterogeneous comparisons."""

from __future__ import annotations

import os
from pathlib import Path

from .artifact_profile import DEFAULT_MACHINE_PROFILE_PATH, load_artifact_roots
from .matrix_config import DEFAULT_FAMILIES_ROOT, REPOSITORY_ROOT, MatrixError
from .open_mix import (
    DEFAULT_OPEN_MIXES_ROOT,
    DEFAULT_SUITE_CONTRACTS_ROOT,
    OpenMixError,
    load_open_mix,
)


INSPECTION_SCHEMA_VERSION = "1.0.0"
LIVE_STATUS_NOT_CHECKED = "NOT_CHECKED_LIVE"
STATUS_READY = "READY_FOR_PLAN"
STATUS_ACTION_REQUIRED = "ACTION_REQUIRED"


def _artifact_status(path: Path) -> str:
    if not path.exists():
        return "MISSING"
    if not path.is_dir():
        return "WRONG_KIND"
    if not os.access(path, os.R_OK):
        return "UNREADABLE"
    return "PRESENT"


def inspect_open_mix(
    open_mix_id: str,
    *,
    machine_profile_path: Path = DEFAULT_MACHINE_PROFILE_PATH,
    open_mixes_root: Path = DEFAULT_OPEN_MIXES_ROOT,
    suite_contracts_root: Path = DEFAULT_SUITE_CONTRACTS_ROOT,
    repository_root: Path = REPOSITORY_ROOT,
    families_root: Path = DEFAULT_FAMILIES_ROOT,
    cells_root: Path | None = None,
) -> dict[str, object]:
    """Inspect definitions and artifacts without runtime or credential contact."""

    mix = load_open_mix(
        open_mix_id,
        root=open_mixes_root,
        repository_root=repository_root,
        families_root=families_root,
        cells_root=cells_root,
        suite_contracts_root=suite_contracts_root,
    )
    roots = load_artifact_roots(machine_profile_path)
    findings: list[dict[str, object]] = []
    for member in mix.members:
        try:
            cell = member.cell.resolve(roots)
            artifact_path: str | None = cell.artifact_path
            status = _artifact_status(Path(cell.artifact_path))
        except MatrixError:
            artifact_path = None
            status = "INVALID_TEMPLATE"
        findings.append(
            {
                "family_id": member.family_id,
                "cell_id": member.cell_id,
                "server": member.cell.server,
                "artifact_path": artifact_path,
                "status": status,
            }
        )
    ready = all(finding["status"] == "PRESENT" for finding in findings)
    return {
        "schema_version": INSPECTION_SCHEMA_VERSION,
        "open_mix_id": mix.open_mix_id,
        "revision": mix.revision,
        "suite_contract_id": mix.suite_contract.suite_contract_id,
        "suite_contract_revision": mix.suite_contract.revision,
        "member_count": len(mix.members),
        "members": findings,
        "estimated_minutes": mix.estimated_minutes,
        "status": STATUS_READY if ready else STATUS_ACTION_REQUIRED,
        "ready_for_plan": ready,
        "live_status": LIVE_STATUS_NOT_CHECKED,
        "next_action": (
            "Create and inspect an immutable open-mix plan."
            if ready
            else "Repair member artifact paths or the machine profile before planning."
        ),
    }
