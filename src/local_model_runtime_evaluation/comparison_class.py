"""Fail-closed declarations for controlled managed-run expansion."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, replace
from pathlib import Path, PurePosixPath

from .matrix_config import (
    DEFAULT_FAMILIES_ROOT,
    REPOSITORY_ROOT,
    Campaign,
    Cell,
    MatrixError,
)


DEFAULT_COMPARISON_CLASSES_ROOT = REPOSITORY_ROOT / "config" / "comparison-classes"
COMPARISON_CLASS_FIELDS = frozenset(
    {
        "schema_version",
        "comparison_class_id",
        "revision",
        "family_id",
        "baseline_campaign_path",
        "extra_cell_ids",
        "estimated_minutes",
        "notes",
    }
)
SAFE_ID = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
SAFE_CELL_ID = re.compile(r"[a-z0-9][a-z0-9_-]*__(?:osaurus|omlx|optiq)")


class ComparisonClassError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        code: str = "comparison_class_invalid",
    ) -> None:
        super().__init__(message)
        self.code = code


def _safe_id(value: object, label: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) > 80
        or not SAFE_ID.fullmatch(value)
    ):
        raise ComparisonClassError(f"{label} is invalid")
    return value


def _repo_relative_path(value: object, label: str) -> PurePosixPath:
    if not isinstance(value, str) or not value:
        raise ComparisonClassError(f"{label} is invalid")
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts:
        raise ComparisonClassError(f"{label} is invalid")
    return path


@dataclass(frozen=True)
class ComparisonClass:
    comparison_class_id: str
    revision: str
    family_id: str
    baseline_campaign_path: Path
    baseline_cell_ids: tuple[str, ...]
    extra_cell_ids: tuple[str, ...]
    estimated_minutes: int
    cell_paths: tuple[Path, ...]
    cells: tuple[Cell, ...]
    notes: str
    path: Path
    campaign: Campaign

    @property
    def cell_ids(self) -> tuple[str, ...]:
        return self.baseline_cell_ids + self.extra_cell_ids

    def materialize_campaign(self) -> Campaign:
        return replace(
            self.campaign,
            campaign_id=(
                f"{self.campaign.campaign_id}--{self.comparison_class_id}"
            ),
            cell_paths=self.cell_paths,
            cells=self.cells,
        )

    @classmethod
    def load(
        cls,
        path: Path,
        *,
        repository_root: Path = REPOSITORY_ROOT,
        families_root: Path = DEFAULT_FAMILIES_ROOT,
        cells_root: Path | None = None,
    ) -> ComparisonClass:
        if path.is_symlink():
            raise ComparisonClassError("comparison class must not be a symlink")
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise ComparisonClassError(
                "comparison class JSON is unreadable",
                code="comparison_class_unreadable",
            ) from error
        if not isinstance(data, dict) or set(data) != COMPARISON_CLASS_FIELDS:
            raise ComparisonClassError("comparison class fields are invalid")
        if data["schema_version"] != "1.0.0":
            raise ComparisonClassError("comparison class schema_version is invalid")

        class_id = _safe_id(data["comparison_class_id"], "comparison_class_id")
        if path.stem != class_id:
            raise ComparisonClassError("comparison_class_id must match filename")
        family_id = _safe_id(data["family_id"], "family_id")
        revision = data["revision"]
        if (
            not isinstance(revision, str)
            or not revision.isdecimal()
            or int(revision) < 1
        ):
            raise ComparisonClassError("comparison class revision is invalid")
        if not isinstance(data["notes"], str):
            raise ComparisonClassError("comparison class notes are invalid")
        if (
            type(data["estimated_minutes"]) is not int
            or data["estimated_minutes"] < 1
        ):
            raise ComparisonClassError("comparison class estimated_minutes is invalid")

        relative_campaign = _repo_relative_path(
            data["baseline_campaign_path"],
            "baseline_campaign_path",
        )
        expected_campaign = PurePosixPath(
            f"config/matrix/{family_id}-campaign.json"
        )
        if relative_campaign != expected_campaign:
            raise ComparisonClassError(
                "baseline_campaign_path must name the family's native campaign"
            )
        unresolved_campaign_path = repository_root / Path(relative_campaign)
        if unresolved_campaign_path.is_symlink():
            raise ComparisonClassError("baseline campaign must not be a symlink")
        campaign_path = unresolved_campaign_path.resolve()
        if not campaign_path.is_relative_to(repository_root.resolve()):
            raise ComparisonClassError("baseline_campaign_path escaped repository")
        try:
            campaign = Campaign.load(
                campaign_path,
                repository_root=repository_root,
                families_root=families_root,
            )
        except (MatrixError, OSError, ValueError, KeyError, TypeError) as error:
            raise ComparisonClassError("baseline campaign is invalid") from error
        if campaign.family_id != family_id:
            raise ComparisonClassError("comparison class family mismatch")

        raw_extras = data["extra_cell_ids"]
        if not isinstance(raw_extras, list) or not all(
            isinstance(item, str) and SAFE_CELL_ID.fullmatch(item)
            for item in raw_extras
        ):
            raise ComparisonClassError("extra_cell_ids must be a string array")
        extra_cell_ids = tuple(raw_extras)
        if len(set(extra_cell_ids)) != len(extra_cell_ids):
            raise ComparisonClassError("extra_cell_ids must be unique")
        baseline_cell_ids = tuple(cell.cell_id for cell in campaign.cells)
        if set(extra_cell_ids) & set(baseline_cell_ids):
            raise ComparisonClassError(
                "extra_cell_ids must not repeat native baseline cells"
            )

        resolved_cells_root = (
            cells_root
            or repository_root / "config" / "matrix" / "cells"
        )
        extra_paths = tuple(
            resolved_cells_root / f"{cell_id}.json"
            for cell_id in extra_cell_ids
        )
        if any(path.is_symlink() for path in extra_paths):
            raise ComparisonClassError("comparison class cell must not be a symlink")
        try:
            extra_cells = tuple(
                Cell.load(cell_path, family=campaign.family)
                for cell_path in extra_paths
            )
        except (MatrixError, OSError, ValueError, KeyError, TypeError) as error:
            raise ComparisonClassError(
                "comparison class extra cell is invalid"
            ) from error

        return cls(
            comparison_class_id=class_id,
            revision=revision,
            family_id=family_id,
            baseline_campaign_path=campaign_path,
            baseline_cell_ids=baseline_cell_ids,
            extra_cell_ids=extra_cell_ids,
            estimated_minutes=data["estimated_minutes"],
            cell_paths=campaign.cell_paths + extra_paths,
            cells=campaign.cells + extra_cells,
            notes=data["notes"],
            path=path.resolve(),
            campaign=campaign,
        )


def load_comparison_class(
    comparison_class_id: str,
    *,
    root: Path = DEFAULT_COMPARISON_CLASSES_ROOT,
) -> ComparisonClass:
    resolved_id = _safe_id(comparison_class_id, "comparison_class_id")
    path = root / f"{resolved_id}.json"
    if not path.is_file():
        raise ComparisonClassError(
            f"comparison class is unknown: {resolved_id}",
            code="comparison_class_missing",
        )
    return ComparisonClass.load(path)
