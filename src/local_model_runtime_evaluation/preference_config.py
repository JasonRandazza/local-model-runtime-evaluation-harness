"""Load and validate Gemma preference suite config."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .matrix_config import REPOSITORY_ROOT


DEFAULT_PREFERENCE_ROOT = REPOSITORY_ROOT / "config" / "preference"
DEFAULT_PREFERENCE_DEFAULTS = DEFAULT_PREFERENCE_ROOT / "defaults.json"
DEFAULT_FAMILY_CELLS = DEFAULT_PREFERENCE_ROOT / "family-cells.json"

SUITE_FIELDS = frozenset({
    "schema_version", "suite_id", "revision", "temperature", "streaming", "prompts",
})

PROMPT_FIELDS = frozenset({"prompt_id", "prompt", "max_tokens"})


class PreferenceError(RuntimeError):
    pass


def _require_exact_fields(data: dict[str, Any], expected: frozenset[str], label: str) -> None:
    if set(data) != expected:
        raise PreferenceError(f"{label} fields are invalid")


@dataclass(frozen=True)
class PreferenceDefaults:
    family_id: str
    cells: tuple[str, ...]


@dataclass(frozen=True)
class PreferenceSelection:
    family_id: str
    cells: tuple[str, ...]


def load_preference_defaults(path: Path | None = None) -> PreferenceDefaults:
    config_path = DEFAULT_PREFERENCE_DEFAULTS if path is None else path
    data = json.loads(config_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise PreferenceError("preference defaults must be a JSON object")
    family_id = data.get("family_id")
    cells = data.get("cells")
    if not isinstance(family_id, str):
        raise PreferenceError("preference defaults family_id is invalid")
    if not isinstance(cells, list) or not all(isinstance(cell, str) for cell in cells):
        raise PreferenceError("preference defaults cells are invalid")
    return PreferenceDefaults(family_id, tuple(cells))


def load_family_cell_recipes(path: Path | None = None) -> dict[str, tuple[str, ...]]:
    config_path = DEFAULT_FAMILY_CELLS if path is None else path
    data = json.loads(config_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise PreferenceError("family cell recipes must be a JSON object")
    recipes: dict[str, tuple[str, ...]] = {}
    for family_id, cells in data.items():
        if not isinstance(family_id, str):
            raise PreferenceError("family cell recipe key is invalid")
        if not isinstance(cells, list) or not all(isinstance(cell, str) for cell in cells):
            raise PreferenceError(f"family cell recipe for {family_id!r} is invalid")
        recipes[family_id] = tuple(cells)
    return recipes


def default_preference_cells() -> tuple[str, ...]:
    return load_preference_defaults().cells


DEFAULT_PREFERENCE_CELLS = default_preference_cells()


def resolve_preference_selection(
    *,
    family_id: str | None,
    cells: tuple[str, ...] | None,
    defaults: PreferenceDefaults | None = None,
    recipes: dict[str, tuple[str, ...]] | None = None,
) -> PreferenceSelection:
    resolved_defaults = load_preference_defaults() if defaults is None else defaults
    resolved_recipes = load_family_cell_recipes() if recipes is None else recipes

    resolved_family = family_id if family_id else resolved_defaults.family_id
    if not resolved_family:
        raise PreferenceError("family is required")

    if resolved_family not in resolved_recipes:
        raise PreferenceError("preference family recipe is missing")

    resolved_cells = cells if cells is not None else resolved_recipes[resolved_family]
    if not resolved_cells:
        raise PreferenceError("cells filter is empty")

    return PreferenceSelection(resolved_family, resolved_cells)


@dataclass(frozen=True)
class PreferencePrompt:
    prompt_id: str
    prompt: str
    max_tokens: int


@dataclass(frozen=True)
class PreferenceSuite:
    suite_id: str
    revision: str
    prompts: tuple[PreferencePrompt, ...]

    @classmethod
    def load(cls, path: Path) -> PreferenceSuite:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise PreferenceError("suite must be a JSON object")
        _require_exact_fields(data, SUITE_FIELDS, "suite")
        if data["schema_version"] != "1.0.0":
            raise PreferenceError("suite schema_version is invalid")
        if data["temperature"] != 0 or data["streaming"] is not True:
            raise PreferenceError("suite must be deterministic and streaming")
        items = data["prompts"]
        if not isinstance(items, list) or len(items) != 6:
            raise PreferenceError("suite must contain exactly six prompts")
        prompts: list[PreferencePrompt] = []
        for item in items:
            if not isinstance(item, dict):
                raise PreferenceError("prompt fields are invalid")
            _require_exact_fields(item, PROMPT_FIELDS, "prompt")
            max_tokens = item["max_tokens"]
            if not isinstance(max_tokens, int) or max_tokens <= 0:
                raise PreferenceError("prompt max_tokens must be a positive integer")
            prompts.append(
                PreferencePrompt(
                    str(item["prompt_id"]),
                    str(item["prompt"]),
                    max_tokens,
                )
            )
        if len({prompt.prompt_id for prompt in prompts}) != 6:
            raise PreferenceError("prompt IDs must be unique")
        return cls(str(data["suite_id"]), str(data["revision"]), tuple(prompts))
