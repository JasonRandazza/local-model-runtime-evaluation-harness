"""Approach 3 free-form cell recipes (Gate A scaffold)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

from .artifact_profile import ArtifactRoots
from .matrix_config import REPOSITORY_ROOT, Cell, MatrixError, ModelFamily, load_family

DEFAULT_APPROACH3_ROOT = REPOSITORY_ROOT / "config" / "approach3"
DEFAULT_CELLS_ROOT = REPOSITORY_ROOT / "config" / "matrix" / "cells"
RECIPE_FIELDS = frozenset(
    {
        "schema_version",
        "recipe_id",
        "revision",
        "family_id",
        "require_native_server",
        "cell_ids",
        "suites",
        "notes",
    }
)


class Approach3Error(RuntimeError):
    def __init__(self, message: str, *, code: str = "approach3_error") -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class FreeFormRecipe:
    recipe_id: str
    revision: str
    family_id: str
    require_native_server: bool
    cell_ids: tuple[str, ...]
    suites: tuple[str, ...]
    notes: str
    path: Path

    @classmethod
    def load(cls, path: Path) -> FreeFormRecipe:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise Approach3Error(
                f"recipe unreadable: {path}", code="recipe_unreadable",
            ) from error
        if not isinstance(data, dict):
            raise Approach3Error("recipe must be a JSON object", code="recipe_shape")
        unknown = set(data) - RECIPE_FIELDS
        if unknown:
            raise Approach3Error(
                f"unknown recipe fields: {sorted(unknown)}",
                code="unknown_fields",
            )
        missing = RECIPE_FIELDS - set(data)
        if missing:
            raise Approach3Error(
                f"missing recipe fields: {sorted(missing)}",
                code="missing_fields",
            )
        if data["schema_version"] != "1.0.0":
            raise Approach3Error(
                "recipe schema_version is invalid", code="schema_version",
            )
        cell_ids = data["cell_ids"]
        suites = data["suites"]
        if not isinstance(cell_ids, list) or not cell_ids:
            raise Approach3Error("cell_ids must be a non-empty list", code="cell_ids")
        if not all(isinstance(item, str) and item for item in cell_ids):
            raise Approach3Error("cell_ids entries must be non-empty strings", code="cell_ids")
        if len(set(cell_ids)) != len(cell_ids):
            raise Approach3Error("cell_ids must be unique", code="duplicate_cells")
        if not isinstance(suites, list) or not suites:
            raise Approach3Error("suites must be a non-empty list", code="suites")
        if not all(isinstance(item, str) and item for item in suites):
            raise Approach3Error("suites entries must be non-empty strings", code="suites")
        if not isinstance(data["require_native_server"], bool):
            raise Approach3Error(
                "require_native_server must be a bool",
                code="require_native_server",
            )
        return cls(
            recipe_id=str(data["recipe_id"]),
            revision=str(data["revision"]),
            family_id=str(data["family_id"]),
            require_native_server=bool(data["require_native_server"]),
            cell_ids=tuple(str(item) for item in cell_ids),
            suites=tuple(str(item) for item in suites),
            notes=str(data["notes"]),
            path=path.resolve(),
        )


def resolve_recipe_path(recipe: str | Path, *, root: Path | None = None) -> Path:
    root = root or DEFAULT_APPROACH3_ROOT
    path = Path(recipe)
    if path.suffix != ".json":
        path = root / f"{path.name}.json"
    elif not path.is_absolute():
        candidate = root / path.name
        path = candidate if candidate.is_file() else (REPOSITORY_ROOT / path)
    if not path.is_file():
        raise Approach3Error(f"recipe not found: {path}", code="recipe_missing")
    return path.resolve()


def load_recipe_cells(
    recipe: FreeFormRecipe,
    *,
    cells_root: Path | None = None,
    family: ModelFamily | None = None,
    artifact_roots: ArtifactRoots | None = None,
) -> tuple[Cell, ...]:
    cells_root = cells_root or DEFAULT_CELLS_ROOT
    loaded_family = family or load_family(recipe.family_id)
    if loaded_family.family_id != recipe.family_id:
        raise Approach3Error("family_id mismatch", code="family_mismatch")
    cells: list[Cell] = []
    for cell_id in recipe.cell_ids:
        path = cells_root / f"{cell_id}.json"
        if not path.is_file():
            raise Approach3Error(f"cell missing: {cell_id}", code="cell_missing")
        try:
            cells.append(
                Cell.load(
                    path,
                    family=loaded_family,
                    require_native_server=recipe.require_native_server,
                )
            )
        except MatrixError as error:
            raise Approach3Error(
                f"cell invalid ({cell_id}): {error}",
                code="cell_invalid",
            ) from error
    if artifact_roots is None:
        return tuple(cells)
    resolved_family = loaded_family.resolve(artifact_roots)
    resolved_cells = tuple(cell.resolve(artifact_roots) for cell in cells)
    for cell in resolved_cells:
        cell.validate_for_family(
            resolved_family,
            require_native_server=recipe.require_native_server,
        )
    return resolved_cells


def dry_config(
    recipe_ref: str | Path,
    *,
    approach3_root: Path | None = None,
    cells_root: Path | None = None,
    artifact_roots: ArtifactRoots | None = None,
) -> dict[str, object]:
    path = resolve_recipe_path(recipe_ref, root=approach3_root)
    recipe = FreeFormRecipe.load(path)
    cells = load_recipe_cells(
        recipe,
        cells_root=cells_root,
        artifact_roots=artifact_roots,
    )
    return {
        "ok": True,
        "status": "DRY_CONFIG_OK",
        "live_collect": "UNTESTED",
        "recipe_id": recipe.recipe_id,
        "revision": recipe.revision,
        "family_id": recipe.family_id,
        "require_native_server": recipe.require_native_server,
        "cell_ids": list(recipe.cell_ids),
        "servers": [cell.server for cell in cells],
        "suites": list(recipe.suites),
        "notes": recipe.notes,
        "path": str(recipe.path),
    }


def list_recipes(*, root: Path | None = None) -> tuple[Path, ...]:
    root = root or DEFAULT_APPROACH3_ROOT
    if not root.is_dir():
        return ()
    return tuple(sorted(root.glob("*.json")))
