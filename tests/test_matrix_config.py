from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from local_model_runtime_evaluation.matrix_config import (
    Campaign,
    Cell,
    MatrixError,
    MatrixSuite,
    ModelFamily,
    load_family,
)

GEMMA_FAMILY = load_family("gemma-4-12b-qat")
ORNITH_FAMILY = load_family("ornith-35b")
QWEN_FAMILY = load_family("qwen36-35b-a3b")

ROOT = Path(__file__).resolve().parents[1]
CELLS = ROOT / "config" / "matrix" / "cells"
GEMMA_CAMPAIGN = ROOT / "config" / "matrix" / "gemma-4-12b-qat-campaign.json"
ORNITH_CAMPAIGN = ROOT / "config" / "matrix" / "ornith-35b-campaign.json"
QWEN_CAMPAIGN = ROOT / "config" / "matrix" / "qwen36-35b-a3b-campaign.json"


class MatrixConfigTests(unittest.TestCase):
    def test_gemma_native_campaign_loads_three_cells(self) -> None:
        campaign = Campaign.load(GEMMA_CAMPAIGN)
        self.assertEqual(campaign.campaign_id, "gemma-4-12b-qat-native")
        self.assertEqual(campaign.family_id, "gemma-4-12b-qat")
        self.assertEqual(len(campaign.cell_paths), 3)
        cells = [Cell.load(path, family=GEMMA_FAMILY) for path in campaign.cell_paths]
        self.assertEqual(
            {(c.quant, c.server) for c in cells},
            {
                ("jang_4m", "osaurus"),
                ("oq4_fp16", "omlx"),
                ("optiq_4bit", "optiq"),
            },
        )

    def test_gemma_campaign_loads_with_family_id(self) -> None:
        campaign = Campaign.load(ROOT / "config" / "matrix" / "gemma-4-12b-qat-campaign.json")
        self.assertEqual(campaign.family_id, "gemma-4-12b-qat")
        self.assertEqual(campaign.campaign_id, "gemma-4-12b-qat-native")
        self.assertEqual(campaign.family.family_id, "gemma-4-12b-qat")
        self.assertEqual(campaign.memory_floor_percent, 20)
        self.assertEqual(len(campaign.cell_paths), 3)
        self.assertEqual(campaign.ports, {"osaurus": 1337, "omlx": 8100, "optiq": 8080})

    def test_cell_rejects_ornith_quant_on_gemma_family(self) -> None:
        bad = {
            "cell_id": "ornith_jang_4m__osaurus",
            "quant": "ornith_jang_4m",
            "server": "osaurus",
            "base_url": "http://127.0.0.1:1337/v1",
            "model_id": "ornith-1.0-35b-jang_4m",
            "artifact_path": "/Users/jrazz/MLXModels/OsaurusAI/Ornith-1.0-35B-JANG_4M",
            "start_command": ["osaurus", "serve"],
            "stop_command": ["osaurus", "stop"],
            "health_path": "/health",
            "notes": "",
        }
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as handle:
            json.dump(bad, handle)
            path = Path(handle.name)
        try:
            with self.assertRaises(MatrixError):
                Cell.load(path, family=GEMMA_FAMILY)
        finally:
            path.unlink(missing_ok=True)

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
            "campaign_id": "gemma-4-12b-qat-native",
            "family_id": "gemma-4-12b-qat",
            "suite_path": "suites/gemma-matrix-v1.json",
            "results_root": "results/matrix",
            "memory_floor_percent": 20,
            "ready_timeout_seconds": 180,
            "request_timeout_seconds": 120,
            "on_cell_failure": "continue",
            "ports": {"osaurus": 1337, "omlx": 8100, "optiq": 9999},
            "cells": [
                "config/matrix/cells/jang_4m__osaurus.json",
                "config/matrix/cells/oq4_fp16__omlx.json",
                "config/matrix/cells/optiq_4bit__optiq.json",
            ],
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
        bad = {
            "cell_id": "jang_4m__osaurus",
            "quant": "jang_4m",
            "server": "osaurus",
            "base_url": "http://127.0.0.1:1337/v1",
            "model_id": "unknown-model",
            "artifact_path": "/tmp/unknown",
            "start_command": ["osaurus", "serve"],
            "stop_command": [],
            "health_path": "/health",
            "notes": "",
        }
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as handle:
            json.dump(bad, handle)
            path = Path(handle.name)
        try:
            with self.assertRaises(MatrixError):
                Cell.load(path, family=GEMMA_FAMILY)
        finally:
            path.unlink(missing_ok=True)

    def test_rejects_coerced_campaign_port_types(self) -> None:
        bad = {
            "campaign_id": "gemma-4-12b-qat-native",
            "family_id": "gemma-4-12b-qat",
            "suite_path": "suites/gemma-matrix-v1.json",
            "results_root": "results/matrix",
            "memory_floor_percent": 20,
            "ready_timeout_seconds": 180,
            "request_timeout_seconds": 120,
            "on_cell_failure": "continue",
            "ports": {"osaurus": "1337", "omlx": 8100, "optiq": 8080},
            "cells": [
                "config/matrix/cells/jang_4m__osaurus.json",
                "config/matrix/cells/oq4_fp16__omlx.json",
                "config/matrix/cells/optiq_4bit__optiq.json",
            ],
        }
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as handle:
            json.dump(bad, handle)
            path = Path(handle.name)
        try:
            with self.assertRaises(MatrixError):
                Campaign.load(path)
        finally:
            path.unlink(missing_ok=True)

    def test_matrix_suite_loads_gemma_matrix_v1(self) -> None:
        suite = MatrixSuite.load(ROOT / "suites" / "gemma-matrix-v1.json")
        self.assertEqual(suite.suite_id, "gemma-matrix-v1")
        self.assertEqual(suite.revision, "3")
        self.assertEqual(len(suite.workloads), 3)
        by_id = {item.workload_id: item for item in suite.workloads}
        self.assertEqual(by_id["short-instruction"].max_tokens, 2048)
        self.assertEqual(by_id["strict-tool-json"].max_tokens, 512)
        self.assertEqual(by_id["wiki-constraint-summary"].max_tokens, 2048)

    def test_optiq_native_cell_uses_no_think_model_id(self) -> None:
        cell = Cell.load(ROOT / "config/matrix/cells/optiq_4bit__optiq.json", family=GEMMA_FAMILY)
        self.assertTrue(cell.model_id.endswith(":no-think"), cell.model_id)
        self.assertEqual(cell.server, "optiq")

    def test_load_gemma_family_by_id(self) -> None:
        family = load_family("gemma-4-12b-qat")
        self.assertEqual(family.family_id, "gemma-4-12b-qat")
        self.assertEqual(set(family.quants.keys()), {"jang_4m", "oq4_fp16", "optiq_4bit"})

    def test_gemma_family_jang_4m_artifact_path(self) -> None:
        jang = load_family("gemma-4-12b-qat").quants["jang_4m"]
        self.assertEqual(jang.quant, "jang_4m")
        self.assertEqual(
            jang.artifact_path,
            "/Users/jrazz/MLXModels/OsaurusAI/gemma-4-12B-it-qat-JANG_4M",
        )
        self.assertIn("gemma-4-12b-it-qat-jang_4m", jang.model_ids)
        self.assertEqual(jang.role, "osaurus_native")

    def test_gemma_family_oq4_fp16_artifact_path(self) -> None:
        oq4 = load_family("gemma-4-12b-qat").quants["oq4_fp16"]
        self.assertEqual(
            oq4.artifact_path,
            "/Users/jrazz/.cache/huggingface/hub/avneetsb/gemma-4-12B-it-qat-oQ4-fp16",
        )
        self.assertIn("gemma-4-12B-it-qat-oQ4-fp16", oq4.model_ids)
        self.assertIsNone(oq4.role)

    def test_gemma_family_optiq_4bit_artifact_path(self) -> None:
        optiq = load_family("gemma-4-12b-qat").quants["optiq_4bit"]
        self.assertEqual(
            optiq.artifact_path,
            "/Users/jrazz/.cache/huggingface/hub/mlx-community/gemma-4-12B-it-qat-OptiQ-4bit",
        )
        self.assertIn("mlx-community/gemma-4-12B-it-qat-OptiQ-4bit", optiq.model_ids)

    def test_model_family_load_from_path(self) -> None:
        path = ROOT / "config" / "matrix" / "families" / "gemma-4-12b-qat.json"
        family = ModelFamily.load(path)
        self.assertEqual(family.family_id, "gemma-4-12b-qat")
        self.assertEqual(len(family.quants), 3)

    def test_ornith_native_campaign_loads_three_cells(self) -> None:
        campaign = Campaign.load(ORNITH_CAMPAIGN)
        self.assertEqual(campaign.campaign_id, "ornith-35b-native")
        self.assertEqual(len(campaign.cell_paths), 3)
        cells = [Cell.load(path, family=ORNITH_FAMILY) for path in campaign.cell_paths]
        self.assertEqual(
            {(c.quant, c.server) for c in cells},
            {
                ("ornith_jang_4m", "osaurus"),
                ("ornith_oq4", "omlx"),
                ("ornith_optiq_4bit", "optiq"),
            },
        )
        self.assertEqual(campaign.family_id, "ornith-35b")
        self.assertEqual(campaign.memory_floor_percent, 20)
        self.assertEqual(campaign.ready_timeout_seconds, 300)
        self.assertEqual(campaign.request_timeout_seconds, 180)
        self.assertEqual(campaign.ports, {"osaurus": 1337, "omlx": 8100, "optiq": 8080})

    def test_gemma_family_native_servers(self) -> None:
        family = load_family("gemma-4-12b-qat")
        self.assertEqual(family.quants["jang_4m"].native_server, "osaurus")
        self.assertEqual(family.quants["oq4_fp16"].native_server, "omlx")
        self.assertEqual(family.quants["optiq_4bit"].native_server, "optiq")
        self.assertEqual(family.quants["jang_4m"].role, "osaurus_native")

    def test_oq_quant_rejects_non_native_server(self) -> None:
        with self.assertRaises(MatrixError) as context:
            Cell.load(
                ROOT / "config/matrix/cells/oq4_fp16__optiq.json",
                family=GEMMA_FAMILY,
            )
        self.assertIn("native_server", str(context.exception))

    def test_optiq_quant_rejects_non_native_server(self) -> None:
        with self.assertRaises(MatrixError) as context:
            Cell.load(
                ROOT / "config/matrix/cells/optiq_4bit__omlx.json",
                family=GEMMA_FAMILY,
            )
        self.assertIn("native_server", str(context.exception))

    def test_load_ornith_family_by_id(self) -> None:
        family = load_family("ornith-35b")
        self.assertEqual(family.family_id, "ornith-35b")
        self.assertEqual(
            set(family.quants.keys()),
            {"ornith_jang_4m", "ornith_oq4", "ornith_optiq_4bit"},
        )
        self.assertEqual(family.quants["ornith_jang_4m"].native_server, "osaurus")
        self.assertEqual(family.quants["ornith_oq4"].native_server, "omlx")
        self.assertEqual(family.quants["ornith_optiq_4bit"].native_server, "optiq")

    def test_ornith_family_jang_4m_artifact_path(self) -> None:
        jang = load_family("ornith-35b").quants["ornith_jang_4m"]
        self.assertEqual(
            jang.artifact_path,
            "/Users/jrazz/MLXModels/OsaurusAI/Ornith-1.0-35B-JANG_4M",
        )
        self.assertIn("ornith-1.0-35b-jang_4m", jang.model_ids)
        self.assertEqual(jang.role, "osaurus_native")

    def test_ornith_family_oq4_artifact_path(self) -> None:
        oq4 = load_family("ornith-35b").quants["ornith_oq4"]
        self.assertEqual(
            oq4.artifact_path,
            "/Users/jrazz/.cache/huggingface/hub/georgeis55/Ornith-1.0-35B-MLX-oQ4",
        )
        self.assertIn("Ornith-1.0-35B-MLX-oQ4", oq4.model_ids)

    def test_ornith_family_optiq_4bit_artifact_path(self) -> None:
        optiq = load_family("ornith-35b").quants["ornith_optiq_4bit"]
        self.assertEqual(
            optiq.artifact_path,
            "/Users/jrazz/.cache/huggingface/hub/mlx-community/Ornith-1.0-35B-OptiQ-4bit",
        )
        self.assertIn("mlx-community/Ornith-1.0-35B-OptiQ-4bit", optiq.model_ids)

    def test_ornith_optiq_native_cell_uses_no_think_model_id(self) -> None:
        cell = Cell.load(
            ROOT / "config/matrix/cells/ornith_optiq_4bit__optiq.json",
            family=ORNITH_FAMILY,
        )
        self.assertTrue(cell.model_id.endswith(":no-think"), cell.model_id)
        self.assertEqual(cell.server, "optiq")

    def test_osaurus_native_quant_rejects_non_osaurus_server(self) -> None:
        with self.assertRaises(MatrixError) as context:
            Cell.load(
                ROOT / "config/matrix/cells/jang_4m__optiq.json",
                family=GEMMA_FAMILY,
            )
        self.assertIn("native_server", str(context.exception))

    def test_family_quant_rejects_missing_native_server(self) -> None:
        payload = {
            "family_id": "missing-native",
            "quants": {
                "jang_4m": {
                    "artifact_path": "/tmp/x",
                    "model_ids": ["x"],
                }
            },
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "missing-native.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaises(MatrixError):
                ModelFamily.load(path)

    def test_family_quant_rejects_osaurus_native_role_on_non_osaurus(self) -> None:
        payload = {
            "family_id": "bad-role-native",
            "quants": {
                "oq4_fp16": {
                    "role": "osaurus_native",
                    "native_server": "omlx",
                    "artifact_path": "/tmp/x",
                    "model_ids": ["x"],
                }
            },
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad-role-native.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaises(MatrixError):
                ModelFamily.load(path)

    def test_family_quant_rejects_unknown_role(self) -> None:
        payload = {
            "family_id": "bad-role-family",
            "quants": {
                "qwen_mxfp4": {
                    "role": "not_a_role",
                    "native_server": "osaurus",
                    "artifact_path": "/tmp/x",
                    "model_ids": ["x"],
                }
            },
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad-role-family.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaises(MatrixError):
                ModelFamily.load(path)

    def test_qwen_native_campaign_loads_three_cells(self) -> None:
        campaign = Campaign.load(QWEN_CAMPAIGN)
        self.assertEqual(campaign.campaign_id, "qwen36-35b-a3b-native")
        self.assertEqual(len(campaign.cell_paths), 3)
        cells = [Cell.load(path, family=QWEN_FAMILY) for path in campaign.cell_paths]
        self.assertEqual(
            {(c.quant, c.server) for c in cells},
            {
                ("qwen_mxfp4", "osaurus"),
                ("qwen_oq4", "omlx"),
                ("qwen_optiq_4bit", "optiq"),
            },
        )
        self.assertEqual(campaign.family_id, "qwen36-35b-a3b")
        self.assertEqual(campaign.ports, {"osaurus": 1337, "omlx": 8100, "optiq": 8080})

    def test_campaign_rejects_wrong_cell_count(self) -> None:
        bad = {
            "campaign_id": "gemma-4-12b-qat-native",
            "family_id": "gemma-4-12b-qat",
            "suite_path": "suites/gemma-matrix-v1.json",
            "results_root": "results/matrix",
            "memory_floor_percent": 20,
            "ready_timeout_seconds": 180,
            "request_timeout_seconds": 120,
            "on_cell_failure": "continue",
            "ports": {"osaurus": 1337, "omlx": 8100, "optiq": 8080},
            "cells": [
                "config/matrix/cells/jang_4m__osaurus.json",
                "config/matrix/cells/oq4_fp16__omlx.json",
            ],
        }
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as handle:
            json.dump(bad, handle)
            path = Path(handle.name)
        try:
            with self.assertRaises(MatrixError) as context:
                Campaign.load(path)
            self.assertIn("exactly three", str(context.exception))
        finally:
            path.unlink(missing_ok=True)

    def test_campaign_rejects_cross_server_cell(self) -> None:
        bad = {
            "campaign_id": "gemma-4-12b-qat-native",
            "family_id": "gemma-4-12b-qat",
            "suite_path": "suites/gemma-matrix-v1.json",
            "results_root": "results/matrix",
            "memory_floor_percent": 20,
            "ready_timeout_seconds": 180,
            "request_timeout_seconds": 120,
            "on_cell_failure": "continue",
            "ports": {"osaurus": 1337, "omlx": 8100, "optiq": 8080},
            "cells": [
                "config/matrix/cells/jang_4m__osaurus.json",
                "config/matrix/cells/oq4_fp16__osaurus.json",
                "config/matrix/cells/optiq_4bit__optiq.json",
            ],
        }
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as handle:
            json.dump(bad, handle)
            path = Path(handle.name)
        try:
            with self.assertRaises(MatrixError):
                Campaign.load(path)
        finally:
            path.unlink(missing_ok=True)

    def test_load_qwen_family_by_id(self) -> None:
        family = load_family("qwen36-35b-a3b")
        self.assertEqual(family.family_id, "qwen36-35b-a3b")
        self.assertEqual(
            set(family.quants.keys()),
            {"qwen_mxfp4", "qwen_oq4", "qwen_optiq_4bit"},
        )
        self.assertEqual(family.quants["qwen_mxfp4"].role, "osaurus_native")
        self.assertIsNone(family.quants["qwen_oq4"].role)
        self.assertIsNone(family.quants["qwen_optiq_4bit"].role)
        self.assertEqual(family.quants["qwen_mxfp4"].native_server, "osaurus")
        self.assertEqual(family.quants["qwen_oq4"].native_server, "omlx")
        self.assertEqual(family.quants["qwen_optiq_4bit"].native_server, "optiq")

    def test_qwen_family_mxfp4_artifact_path(self) -> None:
        mxfp = load_family("qwen36-35b-a3b").quants["qwen_mxfp4"]
        self.assertEqual(
            mxfp.artifact_path,
            "/Users/jrazz/MLXModels/OsaurusAI/Qwen3.6-35B-A3B-MXFP4-MTP",
        )
        self.assertIn("qwen3.6-35b-a3b-mxfp4-mtp", mxfp.model_ids)

    def test_qwen_optiq_native_cell_uses_no_think_model_id(self) -> None:
        cell = Cell.load(
            ROOT / "config/matrix/cells/qwen_optiq_4bit__optiq.json",
            family=QWEN_FAMILY,
        )
        self.assertTrue(cell.model_id.endswith(":no-think"), cell.model_id)
        self.assertEqual(cell.server, "optiq")


if __name__ == "__main__":
    unittest.main()
