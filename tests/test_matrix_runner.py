from __future__ import annotations

import json
import threading
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, call

from local_model_runtime_evaluation.matrix_config import Cell
from local_model_runtime_evaluation.matrix_measure import CellResult
from local_model_runtime_evaluation.matrix_runner import run_campaign
from local_model_runtime_evaluation.matrix_servers import ServerError


ROOT = Path(__file__).resolve().parents[1]


class FakeProbe:
    def __init__(self, values: list[int]) -> None:
        self.values = list(values)

    def free_memory_percent(self) -> int:
        return self.values.pop(0)


def _osaurus(**overrides: object) -> Cell:
    data = dict(
        cell_id="jang_4m__osaurus",
        quant="jang_4m",
        server="osaurus",
        base_url="http://127.0.0.1:1337/v1",
        model_id="gemma-4-12b-it-qat-jang_4m",
        artifact_path="/Users/jrazz/MLXModels/OsaurusAI/gemma-4-12B-it-qat-JANG_4M",
        start_command=("true",),
        stop_command=(),
        health_path="/health",
        notes="",
    )
    data.update(overrides)
    return Cell(**data)  # type: ignore[arg-type]


def _omlx(**overrides: object) -> Cell:
    data = dict(
        cell_id="oq4_fp16__omlx",
        quant="oq4_fp16",
        server="omlx",
        base_url="http://127.0.0.1:8100/v1",
        model_id="gemma-4-12B-it-qat-oQ4-fp16",
        artifact_path="/Users/jrazz/.cache/huggingface/hub/avneetsb/gemma-4-12B-it-qat-oQ4-fp16",
        start_command=("true",),
        stop_command=(),
        health_path="/health",
        notes="",
    )
    data.update(overrides)
    return Cell(**data)  # type: ignore[arg-type]


def _pass_result(cell: Cell, median: float = 1.5) -> CellResult:
    return CellResult(
        status="PASS",
        na_reason=None,
        observations=(),
        summary={
            "median_total_seconds": median,
            "median_ttft_seconds": 0.2,
            "median_decode_tokens_per_second": None,
            "measured_count": 9,
            "success_count": 9,
            "contract_pass_count": 9,
            "ttft_sample_count": 9,
            "decode_sample_count": 0,
            "by_workload": {},
        },
        memory_free_percent_before=80,
        memory_free_percent_after=79,
    )


class MatrixRunnerTest(unittest.TestCase):
    def _campaign(self) -> MagicMock:
        return MagicMock(
            campaign_id="test",
            memory_floor_percent=20,
            ready_timeout_seconds=1,
            request_timeout_seconds=5,
            on_cell_failure="continue",
            suite_path=ROOT / "suites/gemma-matrix-v1.json",
            cell_paths=[],
            ports={"osaurus": 1337, "omlx": 8100, "optiq": 8080},
        )

    def test_na_then_pass_continues(self) -> None:
        campaign = self._campaign()
        cells = (_osaurus(cell_id="a__osaurus"), _omlx(cell_id="b__omlx"))
        na_handle = MagicMock()
        na_handle.wait_ready.side_effect = ServerError("unloadable")
        ok_handle = MagicMock()
        with TemporaryDirectory() as tmp:
            out = run_campaign(
                campaign,
                "screen",
                Path(tmp),
                cells=cells,
                build_server=MagicMock(side_effect=[na_handle, ok_handle]),
                measure_cell=MagicMock(return_value=_pass_result(cells[1])),
                probe=FakeProbe([80, 80]),
                port_free=lambda port: True,
                credential_for=lambda server: None,
            )
            raw = json.loads((out / "raw.json").read_text())
            self.assertEqual(raw["cells"][0]["status"], "N/A")
            self.assertEqual(raw["cells"][0]["na_reason"], "unloadable")
            self.assertEqual(raw["cells"][1]["status"], "PASS")
            report = (out / "report.md").read_text()
            self.assertIn("N/A (unloadable)", report)
            self.assertIn("PASS", report)

    def test_memory_floor_stops_campaign(self) -> None:
        campaign = self._campaign()
        cells = (_osaurus(), _omlx())
        build_server = MagicMock()
        with TemporaryDirectory() as tmp:
            out = run_campaign(
                campaign,
                "screen",
                Path(tmp),
                cells=cells,
                build_server=build_server,
                measure_cell=MagicMock(),
                probe=FakeProbe([15]),
                port_free=lambda port: True,
                credential_for=lambda server: None,
            )
            raw = json.loads((out / "raw.json").read_text())
            self.assertTrue(raw["stopped_early"])
            self.assertEqual(raw["stop_reason"], "memory_floor")
            self.assertEqual(len(raw["cells"]), 0)
            build_server.assert_not_called()

    def test_stops_previous_handle_before_next_cell(self) -> None:
        campaign = self._campaign()
        cells = (_osaurus(cell_id="a__osaurus"), _omlx(cell_id="b__omlx"))
        first = MagicMock()
        second = MagicMock()
        with TemporaryDirectory() as tmp:
            run_campaign(
                campaign,
                "screen",
                Path(tmp),
                cells=cells,
                build_server=MagicMock(side_effect=[first, second]),
                measure_cell=MagicMock(side_effect=[_pass_result(cells[0]), _pass_result(cells[1])]),
                probe=FakeProbe([80, 80, 80, 80]),
                port_free=lambda port: True,
                credential_for=lambda server: None,
            )
            first.stop.assert_has_calls([call(), call()])
            second.stop.assert_called_once()

    def test_cell_filter_runs_subset(self) -> None:
        campaign = self._campaign()
        cells = (_osaurus(), _omlx())
        build_server = MagicMock(return_value=MagicMock())
        with TemporaryDirectory() as tmp:
            out = run_campaign(
                campaign,
                "screen",
                Path(tmp),
                cells=cells,
                cell_filter=("oq4_fp16__omlx",),
                build_server=build_server,
                measure_cell=MagicMock(return_value=_pass_result(cells[1])),
                probe=FakeProbe([80, 80]),
                port_free=lambda port: True,
                credential_for=lambda server: None,
            )
            raw = json.loads((out / "raw.json").read_text())
            self.assertEqual(len(raw["cells"]), 1)
            self.assertEqual(raw["cells"][0]["cell_id"], "oq4_fp16__omlx")
            build_server.assert_called_once()


if __name__ == "__main__":
    unittest.main()
