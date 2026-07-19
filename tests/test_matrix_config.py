from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from local_model_runtime_evaluation.matrix_config import Campaign, Cell, MatrixError, MatrixSuite

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

    def test_rejects_wrong_port_for_server(self) -> None:
        with self.assertRaises(MatrixError):
            Cell(
                cell_id="jang_4m__osaurus", quant="jang_4m", server="osaurus",
                base_url="http://127.0.0.1:8080/v1",
                model_id="gemma-4-12b-it-qat-jang_4m",
                artifact_path="/Users/jrazz/MLXModels/OsaurusAI/gemma-4-12B-it-qat-JANG_4M",
                start_command=("osaurus", "serve"), stop_command=(), health_path="/health", notes="",
            )

    def test_rejects_wrong_campaign_ports(self) -> None:
        bad = {
            "campaign_id": "gemma-4-12b-qat-3x3",
            "suite_path": "suites/gemma-matrix-v1.json",
            "results_root": "results/matrix",
            "memory_floor_percent": 20,
            "ready_timeout_seconds": 180,
            "request_timeout_seconds": 120,
            "on_cell_failure": "continue",
            "ports": {"osaurus": 1337, "omlx": 8100, "optiq": 9999},
            "cells": [f"config/matrix/cells/jang_4m__osaurus.json"] * 9,
        }
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as handle:
            json.dump(bad, handle)
            path = Path(handle.name)
        try:
            with self.assertRaises(MatrixError):
                Campaign.load(path)
        finally:
            path.unlink(missing_ok=True)

    def test_rejects_wrong_artifact_and_model_id(self) -> None:
        with self.assertRaises(MatrixError):
            Cell(
                cell_id="jang_4m__osaurus", quant="jang_4m", server="osaurus",
                base_url="http://127.0.0.1:1337/v1",
                model_id="unknown-model", artifact_path="/tmp/unknown",
                start_command=("osaurus", "serve"), stop_command=(), health_path="/health", notes="",
            )

    def test_matrix_suite_loads_gemma_matrix_v1(self) -> None:
        suite = MatrixSuite.load(ROOT / "suites" / "gemma-matrix-v1.json")
        self.assertEqual(suite.suite_id, "gemma-matrix-v1")
        self.assertEqual(suite.revision, "1")
        self.assertEqual(len(suite.workloads), 3)


if __name__ == "__main__":
    unittest.main()
