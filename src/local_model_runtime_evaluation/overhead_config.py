"""Load and validate Osaurus routing overhead pair configs."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .matrix_config import REPOSITORY_ROOT, Cell, ModelFamily


DEFAULT_OVERHEAD_ROOT = REPOSITORY_ROOT / "config" / "overhead"
DEFAULT_OVERHEAD_DEFAULTS = DEFAULT_OVERHEAD_ROOT / "defaults.json"
DEFAULT_FAMILY_PAIRS = DEFAULT_OVERHEAD_ROOT / "family-pairs.json"
DEFAULT_PAIRS_ROOT = DEFAULT_OVERHEAD_ROOT / "pairs"
ROUTED_BASE_URL = "http://127.0.0.1:1337/v1"

PAIR_FIELDS = frozenset({
    "pair_id", "direct_cell_id", "backend_cell_id", "routed_base_url", "routed_model_id",
})


class OverheadError(RuntimeError):
    pass


def _require_exact_fields(data: dict[str, Any], expected: frozenset[str], label: str) -> None:
    if set(data) != expected:
        raise OverheadError(f"{label} fields are invalid")


@dataclass(frozen=True)
class OverheadDefaults:
    family_id: str
    pairs: tuple[str, ...]


@dataclass(frozen=True)
class OverheadSelection:
    family_id: str
    pairs: tuple[str, ...]


def load_overhead_defaults(path: Path | None = None) -> OverheadDefaults:
    config_path = DEFAULT_OVERHEAD_DEFAULTS if path is None else path
    data = json.loads(config_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise OverheadError("overhead defaults must be a JSON object")
    family_id = data.get("family_id")
    pairs = data.get("pairs")
    if not isinstance(family_id, str):
        raise OverheadError("overhead defaults family_id is invalid")
    if not isinstance(pairs, list) or not all(isinstance(pair, str) for pair in pairs):
        raise OverheadError("overhead defaults pairs are invalid")
    return OverheadDefaults(family_id, tuple(pairs))


def load_family_pair_recipes(path: Path | None = None) -> dict[str, tuple[str, ...]]:
    config_path = DEFAULT_FAMILY_PAIRS if path is None else path
    data = json.loads(config_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise OverheadError("overhead family pair recipes must be a JSON object")
    recipes: dict[str, tuple[str, ...]] = {}
    for family_id, pairs in data.items():
        if not isinstance(family_id, str):
            raise OverheadError("overhead family pair recipe key is invalid")
        if not isinstance(pairs, list) or not all(isinstance(pair, str) for pair in pairs):
            raise OverheadError(f"overhead family pair recipe for {family_id!r} is invalid")
        recipes[family_id] = tuple(pairs)
    return recipes


def default_overhead_pairs() -> tuple[str, ...]:
    return load_overhead_defaults().pairs


DEFAULT_PAIR_IDS = default_overhead_pairs()


def resolve_overhead_selection(
    *,
    family_id: str | None,
    pairs: tuple[str, ...] | None,
    defaults: OverheadDefaults | None = None,
    recipes: dict[str, tuple[str, ...]] | None = None,
) -> OverheadSelection:
    resolved_defaults = load_overhead_defaults() if defaults is None else defaults
    resolved_recipes = load_family_pair_recipes() if recipes is None else recipes

    resolved_family = family_id if family_id else resolved_defaults.family_id
    if not resolved_family:
        raise OverheadError("family is required")

    if resolved_family not in resolved_recipes:
        raise OverheadError("overhead family recipe is missing")

    recipe_pairs = resolved_recipes[resolved_family]
    resolved_pairs = pairs if pairs is not None else recipe_pairs
    if not resolved_pairs:
        raise OverheadError("pairs filter is empty")

    unknown = set(resolved_pairs) - set(recipe_pairs)
    if unknown:
        raise OverheadError("pairs filter is not in family recipe")

    return OverheadSelection(resolved_family, resolved_pairs)


@dataclass(frozen=True)
class OverheadPair:
    pair_id: str
    direct_cell_id: str
    backend_cell_id: str
    routed_base_url: str
    routed_model_id: str

    @classmethod
    def load(cls, path: Path) -> OverheadPair:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise OverheadError("pair must be a JSON object")
        _require_exact_fields(data, PAIR_FIELDS, "pair")

        pair_id = str(data["pair_id"])
        if not pair_id:
            raise OverheadError("pair_id is invalid")

        direct_cell_id = str(data["direct_cell_id"])
        backend_cell_id = str(data["backend_cell_id"])
        if not direct_cell_id or not backend_cell_id:
            raise OverheadError("direct_cell_id and backend_cell_id must not be empty")

        routed_base_url = str(data["routed_base_url"])
        if routed_base_url != ROUTED_BASE_URL:
            raise OverheadError("routed_base_url must be the Osaurus loopback endpoint")

        routed_model_id = str(data["routed_model_id"])
        if not routed_model_id:
            raise OverheadError("routed_model_id must not be empty")

        return cls(
            pair_id=pair_id,
            direct_cell_id=direct_cell_id,
            backend_cell_id=backend_cell_id,
            routed_base_url=routed_base_url,
            routed_model_id=routed_model_id,
        )


def make_routed_measure_cell(backend: Cell, pair: OverheadPair, *, family: ModelFamily) -> Cell:
    cell = Cell(
        cell_id=f"{backend.quant}__osaurus",
        quant=backend.quant,
        server="osaurus",
        base_url=pair.routed_base_url,
        model_id=pair.routed_model_id,
        artifact_path=backend.artifact_path,
        start_command=backend.start_command,
        stop_command=(),
        health_path=backend.health_path,
        notes="overhead routed measure cell; do not spawn via this cell",
    )
    cell.validate_for_family(family, require_native_server=False)
    return cell
