from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from local_model_runtime_evaluation.matrix_config import Cell, load_family
from local_model_runtime_evaluation.overhead_config import (
    DEFAULT_PAIR_IDS,
    DEFAULT_PAIRS_ROOT,
    OverheadDefaults,
    OverheadError,
    OverheadPair,
    load_family_pair_recipes,
    load_overhead_defaults,
    make_routed_measure_cell,
    resolve_overhead_selection,
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
        backend = Cell.load(
            ROOT / "config/matrix/cells/oq4_fp16__omlx.json",
            family=load_family("gemma-4-12b-qat"),
        )
        pair = OverheadPair.load(ROOT / "config/overhead/pairs/oq4_fp16.json")
        routed = make_routed_measure_cell(backend, pair, family=load_family("gemma-4-12b-qat"))
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

    def test_defaults_load_gemma_family(self) -> None:
        defaults = load_overhead_defaults()
        self.assertEqual(defaults.family_id, "gemma-4-12b-qat")
        self.assertEqual(defaults.pairs, ("oq4_fp16", "optiq_4bit"))

    def test_gemma_defaults_match_recipe(self) -> None:
        defaults = load_overhead_defaults()
        recipes = load_family_pair_recipes()
        self.assertEqual(defaults.pairs, recipes["gemma-4-12b-qat"])

    def test_load_ornith_oq4_pair(self) -> None:
        pair = OverheadPair.load(ROOT / "config/overhead/pairs/ornith_oq4.json")
        self.assertEqual(pair.pair_id, "ornith_oq4")
        self.assertEqual(pair.direct_cell_id, "ornith_oq4__omlx")
        self.assertEqual(pair.routed_model_id, "omlx/Ornith-1.0-35B-MLX-oQ4")

    def test_load_ornith_optiq_4bit_pair(self) -> None:
        pair = OverheadPair.load(ROOT / "config/overhead/pairs/ornith_optiq_4bit.json")
        self.assertEqual(pair.pair_id, "ornith_optiq_4bit")
        self.assertEqual(pair.direct_cell_id, "ornith_optiq_4bit__optiq")
        self.assertIn("Ornith-1.0-35B-OptiQ-4bit", pair.routed_model_id)

    def test_resolve_family_override_ornith(self) -> None:
        selection = resolve_overhead_selection(family_id="ornith-35b", pairs=None)
        self.assertEqual(selection.family_id, "ornith-35b")
        self.assertEqual(selection.pairs, ("ornith_oq4", "ornith_optiq_4bit"))

    def test_load_qwen_oq4_pair(self) -> None:
        pair = OverheadPair.load(ROOT / "config/overhead/pairs/qwen_oq4.json")
        self.assertEqual(pair.pair_id, "qwen_oq4")
        self.assertEqual(pair.direct_cell_id, "qwen_oq4__omlx")
        self.assertEqual(pair.routed_model_id, "omlx/Qwen3.6-35B-A3B-oQ4-mtp")

    def test_load_qwen_optiq_4bit_pair(self) -> None:
        pair = OverheadPair.load(ROOT / "config/overhead/pairs/qwen_optiq_4bit.json")
        self.assertEqual(pair.pair_id, "qwen_optiq_4bit")
        self.assertEqual(pair.direct_cell_id, "qwen_optiq_4bit__optiq")
        self.assertIn(":no-think", pair.routed_model_id)

    def test_resolve_family_override_qwen(self) -> None:
        selection = resolve_overhead_selection(family_id="qwen36-35b-a3b", pairs=None)
        self.assertEqual(selection.family_id, "qwen36-35b-a3b")
        self.assertEqual(selection.pairs, ("qwen_oq4", "qwen_optiq_4bit"))

    def test_resolve_missing_family_fails(self) -> None:
        empty = OverheadDefaults(family_id="", pairs=())
        with self.assertRaises(OverheadError):
            resolve_overhead_selection(family_id=None, pairs=None, defaults=empty)

    def test_reject_ornith_pair_under_gemma_family(self) -> None:
        with self.assertRaises(OverheadError):
            resolve_overhead_selection(
                family_id="gemma-4-12b-qat",
                pairs=("ornith_oq4",),
            )


if __name__ == "__main__":
    unittest.main()
