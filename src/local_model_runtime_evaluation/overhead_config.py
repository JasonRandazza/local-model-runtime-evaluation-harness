"""Load and validate Osaurus routing overhead pair configs."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .matrix_config import REPOSITORY_ROOT, Cell


DEFAULT_PAIR_IDS: tuple[str, ...] = ("oq4_fp16", "optiq_4bit")
DEFAULT_PAIRS_ROOT = REPOSITORY_ROOT / "config" / "overhead" / "pairs"
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
        if pair_id not in DEFAULT_PAIR_IDS:
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


def make_routed_measure_cell(backend: Cell, pair: OverheadPair) -> Cell:
    return Cell(
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
