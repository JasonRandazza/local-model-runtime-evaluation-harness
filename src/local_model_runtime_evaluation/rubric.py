"""Load and validate rubrics: the criteria a ruling is made under.

A rubric names the quality floors a cell must clear and the single metric that
orders whatever clears them. It never enters a plan or its input hashes -- see
docs/adr/0006-rubric-stays-out-of-the-plan-hash.md -- so changing a rubric
leaves sealed evidence untouched and still comparable.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

# The closed vocabulary a rubric may name, prefixed by the step that has to
# have run to produce it. `hits` alone would be ambiguous: both RAG scorers
# report one.
METRICS = frozenset({
    "matrix.median_total_seconds",
    "matrix.median_ttft_seconds",
    "matrix.success_count",
    "matrix.contract_pass_count",
    "matrix.measured_count",
    "preference.win_rate",
    "preference.wins",
    "preference.losses",
    "preference.ties",
    "rag.fact_hit_rate",
    "rag.retrieval_recall",
    "rag.retrieval_precision",
})


RUBRIC_FIELDS = frozenset({"rubric_id", "revision", "floors", "order_by"})
FLOOR_FIELDS = frozenset({"metric", "comparator", "value"})
ORDER_BY_FIELDS = frozenset({"metric", "direction"})
COMPARATORS = frozenset({">=", "<=", ">", "<", "=="})
DIRECTIONS = frozenset({"asc", "desc"})


class RubricError(RuntimeError):
    pass


def _require_exact_fields(data: object, expected: frozenset[str], label: str) -> None:
    if not isinstance(data, dict) or set(data) != expected:
        raise RubricError(f"{label} fields are invalid")


def _floor(raw: object) -> Floor:
    _require_exact_fields(raw, FLOOR_FIELDS, "floor")
    assert isinstance(raw, dict)
    comparator = raw["comparator"]
    value = raw["value"]
    if comparator not in COMPARATORS:
        raise RubricError("floor comparator is invalid")
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise RubricError("floor value is invalid")
    return Floor(_require_known_metric(raw["metric"], "floor"), comparator, float(value))


def _require_known_metric(metric: object, label: str) -> str:
    if metric not in METRICS:
        raise RubricError(f"{label} names an unknown metric")
    return str(metric)


@dataclass(frozen=True)
class Floor:
    metric: str
    comparator: str
    value: float


@dataclass(frozen=True)
class OrderBy:
    metric: str
    direction: str


@dataclass(frozen=True)
class Rubric:
    rubric_id: str
    revision: str
    floors: tuple[Floor, ...]
    order_by: OrderBy

    @staticmethod
    def load(path: Path) -> Rubric:
        """Read one rubric, or raise RubricError.

        Every failure is a RubricError, including unreadable or non-JSON
        input. Unlike the older config loaders this deliberately lets nothing
        else escape, because `build_ruling` must never raise and a single
        exception type makes that contract total.
        """

        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as error:
            raise RubricError("rubric is unreadable") from error
        _require_exact_fields(data, RUBRIC_FIELDS, "rubric")
        rubric_id = data["rubric_id"]
        revision = data["revision"]
        if not isinstance(rubric_id, str) or not isinstance(revision, str):
            raise RubricError("rubric identity is invalid")
        if rubric_id != path.stem:
            raise RubricError("rubric_id must match its file name")

        raw_floors = data["floors"]
        if not isinstance(raw_floors, list) or not raw_floors:
            raise RubricError("rubric declares no floors")
        floors = tuple(_floor(raw) for raw in raw_floors)

        raw_order_by = data["order_by"]
        _require_exact_fields(raw_order_by, ORDER_BY_FIELDS, "order_by")
        direction = raw_order_by["direction"]
        if direction not in DIRECTIONS:
            raise RubricError("order_by direction is invalid")
        order_by = OrderBy(
            _require_known_metric(raw_order_by["metric"], "order_by"), direction
        )
        return Rubric(rubric_id, revision, floors, order_by)
