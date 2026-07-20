from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from local_model_runtime_evaluation.matrix_config import Cell
from local_model_runtime_evaluation.overhead_config import (
    DEFAULT_PAIR_IDS,
    DEFAULT_PAIRS_ROOT,
    OverheadError,
    OverheadPair,
    make_routed_measure_cell,
)

ROOT = Path(__file__).resolve().parents[1]


class OverheadConfigTests(unittest.TestCase):
    def test_load_oq4_pair(self) -> None:
        pair = OverheadPair.load(ROOT / "config/overhead/pairs/oq4_fp16.json")
        self.assertEqual(pair.pair_id, "oq4_fp16")
        self.assertEqual(pair.routed_base_url, "http://127.0.0.1:1337/v1")
        self.assertEqual(pair.routed_model_id, "omlx/gemma-4-12B-it-qat-oQ4-fp16")

    def test_reject_non_osaurus_routed_base_url(self) -> None:
        bad = {
            "pair_id": "oq4_fp16",
            "direct_cell_id": "oq4_fp16__omlx",
            "backend_cell_id": "oq4_fp16__omlx",
            "routed_base_url": "http://127.0.0.1:8100/v1",
            "routed_model_id": "omlx/gemma-4-12B-it-qat-oQ4-fp16",
        }
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as handle:
            json.dump(bad, handle)
            path = Path(handle.name)
        try:
            with self.assertRaises(OverheadError):
                OverheadPair.load(path)
        finally:
            path.unlink(missing_ok=True)

    def test_make_routed_measure_cell_uses_osaurus_endpoint(self) -> None:
        backend = Cell.load(ROOT / "config/matrix/cells/oq4_fp16__omlx.json")
        pair = OverheadPair.load(ROOT / "config/overhead/pairs/oq4_fp16.json")
        routed = make_routed_measure_cell(backend, pair)
        self.assertEqual(routed.server, "osaurus")
        self.assertEqual(routed.base_url, "http://127.0.0.1:1337/v1")
        self.assertEqual(routed.model_id, pair.routed_model_id)
        self.assertEqual(routed.cell_id, "oq4_fp16__osaurus")
        self.assertEqual(routed.quant, backend.quant)
        self.assertEqual(routed.artifact_path, backend.artifact_path)
        self.assertEqual(routed.start_command, backend.start_command)
        self.assertEqual(routed.stop_command, ())
        self.assertEqual(routed.health_path, backend.health_path)
        self.assertEqual(routed.notes, "overhead routed measure cell; do not spawn via this cell")

    def test_default_pair_ids_and_root(self) -> None:
        self.assertEqual(DEFAULT_PAIR_IDS, ("oq4_fp16", "optiq_4bit"))
        self.assertEqual(DEFAULT_PAIRS_ROOT, ROOT / "config" / "overhead" / "pairs")


if __name__ == "__main__":
    unittest.main()
