from __future__ import annotations

import unittest
from pathlib import Path

from local_model_runtime_evaluation.matrix_config import Campaign, Cell, MatrixError

ROOT = Path(__file__).resolve().parents[1]
CELLS = ROOT / "config" / "matrix" / "cells"


class MatrixConfigTests(unittest.TestCase):
    def test_all_nine_cells_load(self) -> None:
        paths = sorted(CELLS.glob("*.json"))
        self.assertEqual(len(paths), 9)
        cells = [Cell.load(path) for path in paths]
        servers = {(c.quant, c.server) for c in cells}
        self.assertEqual(len(servers), 9)
        for cell in cells:
            self.assertTrue(cell.base_url.startswith("http://127.0.0.1:"))
            self.assertTrue(cell.base_url.endswith("/v1"))
            self.assertIn(cell.server, {"osaurus", "omlx", "optiq"})
            self.assertIn(cell.quant, {"jang_4m", "oq4_fp16", "optiq_4bit"})
            self.assertIsInstance(cell.start_command, tuple)
            self.assertTrue(all(isinstance(part, str) for part in cell.start_command))

    def test_campaign_lists_exactly_nine_cells(self) -> None:
        campaign = Campaign.load(ROOT / "config" / "matrix" / "gemma-4-12b-qat-campaign.json")
        self.assertEqual(campaign.campaign_id, "gemma-4-12b-qat-3x3")
        self.assertEqual(campaign.memory_floor_percent, 20)
        self.assertEqual(len(campaign.cell_paths), 9)
        self.assertEqual(campaign.ports, {"osaurus": 1337, "omlx": 8100, "optiq": 8080})

    def test_rejects_non_loopback_base_url(self) -> None:
        with self.assertRaises(MatrixError):
            Cell(
                cell_id="bad", quant="jang_4m", server="osaurus",
                base_url="http://10.0.0.1:1337/v1", model_id="x",
                artifact_path="/tmp/x", start_command=("true",), stop_command=(),
                health_path="/health", notes="",
            )


if __name__ == "__main__":
    unittest.main()
