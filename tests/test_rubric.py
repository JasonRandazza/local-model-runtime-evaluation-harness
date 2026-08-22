from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from local_model_runtime_evaluation.rubric import Rubric, RubricError

VALID = {
    "rubric_id": "serve-fastest-that-passes",
    "revision": "1",
    "floors": [
        {"metric": "rag_oracle.fact_hit_rate", "comparator": ">=", "value": 0.8},
    ],
    "order_by": {"metric": "matrix.median_total_seconds", "direction": "asc"},
}


def _write(root: Path, payload: dict, name: str = "serve-fastest-that-passes.json") -> Path:
    path = root / name
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


class RubricLoadTests(unittest.TestCase):
    def test_loads_a_valid_rubric(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            rubric = Rubric.load(_write(Path(root), VALID))
        self.assertEqual(rubric.rubric_id, "serve-fastest-that-passes")
        self.assertEqual(rubric.revision, "1")
        self.assertEqual(len(rubric.floors), 1)
        self.assertEqual(rubric.floors[0].metric, "rag_oracle.fact_hit_rate")
        self.assertEqual(rubric.floors[0].comparator, ">=")
        self.assertEqual(rubric.floors[0].value, 0.8)
        self.assertEqual(rubric.order_by.metric, "matrix.median_total_seconds")
        self.assertEqual(rubric.order_by.direction, "asc")

    def test_rejects_an_unknown_metric_name(self) -> None:
        """A typo must fail at load, not silently skip the floor it names."""

        bad_floor = {
            **VALID,
            "floors": [
                {"metric": "rag_oracle.fact_hit_rat", "comparator": ">=", "value": 0.8}
            ],
        }
        bad_order = {
            **VALID,
            "order_by": {"metric": "matrix.medain_total_seconds", "direction": "asc"},
        }
        for label, payload in (("floor", bad_floor), ("order_by", bad_order)):
            with (
                self.subTest(label),
                tempfile.TemporaryDirectory() as root,
                self.assertRaises(RubricError),
            ):
                Rubric.load(_write(Path(root), payload))

    def test_rejects_a_rubric_id_that_disagrees_with_its_file_name(self) -> None:
        """A ruling records the rubric by id, so the id must find the file."""

        with tempfile.TemporaryDirectory() as root:
            path = _write(Path(root), VALID, name="something-else.json")
            with self.assertRaises(RubricError):
                Rubric.load(path)

    def test_rejects_a_malformed_rubric(self) -> None:
        """A rubric that cannot decide must never load."""

        cases = {
            "not an object": [],
            "missing order_by": {k: v for k, v in VALID.items() if k != "order_by"},
            "unknown field": {**VALID, "weight": 3},
            "no floors": {**VALID, "floors": []},
            "floor not an object": {**VALID, "floors": ["fast"]},
            "floor missing comparator": {
                **VALID,
                "floors": [{"metric": "rag_oracle.fact_hit_rate", "value": 0.8}],
            },
            "unknown comparator": {
                **VALID,
                "floors": [
                    {"metric": "rag_oracle.fact_hit_rate", "comparator": "~=", "value": 0.8}
                ],
            },
            "value not numeric": {
                **VALID,
                "floors": [
                    {"metric": "rag_oracle.fact_hit_rate", "comparator": ">=", "value": "0.8"}
                ],
            },
            "unknown direction": {
                **VALID,
                "order_by": {
                    "metric": "matrix.median_total_seconds",
                    "direction": "fastest",
                },
            },
        }
        for label, payload in cases.items():
            with (
                self.subTest(label),
                tempfile.TemporaryDirectory() as root,
                self.assertRaises(RubricError),
            ):
                Rubric.load(_write(Path(root), payload))

    def test_rejects_input_that_is_not_readable_json(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "serve-fastest-that-passes.json"
            path.write_text("{not json", encoding="utf-8")
            with self.assertRaises(RubricError):
                Rubric.load(path)
            with self.assertRaises(RubricError):
                Rubric.load(Path(root) / "absent.json")


if __name__ == "__main__":
    unittest.main()
