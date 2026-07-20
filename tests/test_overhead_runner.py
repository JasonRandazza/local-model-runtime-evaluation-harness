from __future__ import annotations

import json
import threading
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock

from local_model_runtime_evaluation.matrix_config import Cell
from local_model_runtime_evaluation.matrix_measure import CellResult
from local_model_runtime_evaluation.overhead_config import DEFAULT_PAIR_IDS, OverheadError
from local_model_runtime_evaluation.overhead_runner import require_osaurus_listening, run_overhead

ROOT = Path(__file__).resolve().parents[1]


class FakeProbe:
    def __init__(self, values: list[int]) -> None:
        self.values = list(values)

    def free_memory_percent(self) -> int:
        return self.values.pop(0)


class FakeHandle:
    def start(self) -> None:
        return None

    def wait_ready(self, model_id: str, timeout_seconds: float) -> None:
        return None

    def stop(self) -> None:
        return None


def _pass_result(median: float = 1.5) -> CellResult:
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


class RequireOsaurusListeningTests(unittest.TestCase):
    def test_require_osaurus_listening_fails_when_port_free(self) -> None:
        with self.assertRaises(OverheadError):
            require_osaurus_listening(port_free=lambda port: True)

    def test_require_osaurus_listening_ok_when_port_busy(self) -> None:
        require_osaurus_listening(port_free=lambda port: port != 1337)


class RunOverheadTests(unittest.TestCase):
    def test_run_overhead_writes_raw_and_report(self) -> None:
        build_calls: list[Cell] = []
        measure_calls: list[Cell] = []
        medians = iter([1.0, 1.2, 2.0, 2.3])

        def fake_build(cell: Cell, transport: object, log_dir: Path, credential: object | None) -> FakeHandle:
            build_calls.append(cell)
            return FakeHandle()

        def fake_measure(
            cell: Cell,
            suite: object,
            mode: str,
            transport: object,
            probe: object | None,
            cancel: threading.Event,
            credential: object | None = None,
        ) -> CellResult:
            measure_calls.append(cell)
            return _pass_result(next(medians))

        def fake_port_free(port: int) -> bool:
            return port != 1337

        with TemporaryDirectory() as tmp:
            out = run_overhead(
                DEFAULT_PAIR_IDS,
                ROOT / "config/overhead/pairs",
                ROOT / "config/matrix/cells",
                ROOT / "suites/gemma-matrix-v1.json",
                Path(tmp),
                build_server=fake_build,
                measure_cell=fake_measure,
                probe=FakeProbe([80] * 10),
                port_free=fake_port_free,
                credential_for=lambda server: None,
            )
            raw = json.loads((out / "raw.json").read_text(encoding="utf-8"))
            self.assertEqual(len(raw["pairs"]), 2)
            for pair in raw["pairs"]:
                self.assertIn("direct", pair)
                self.assertIn("routed", pair)
                self.assertIn("deltas", pair)
            self.assertEqual(len(build_calls), 4)
            for cell in build_calls:
                self.assertIn(cell.server, ("omlx", "optiq"))
            self.assertEqual(len(measure_calls), 4)
            self.assertEqual(
                [cell.cell_id for cell in measure_calls],
                [
                    "oq4_fp16__omlx",
                    "oq4_fp16__osaurus",
                    "optiq_4bit__optiq",
                    "optiq_4bit__osaurus",
                ],
            )
            report = (out / "report.md").read_text(encoding="utf-8")
            self.assertRegex(report, r"Δ total|delta.*total", report)

    def test_osaurus_down_skips_routed_leg(self) -> None:
        build_calls: list[Cell] = []
        measure_calls: list[Cell] = []

        def fake_build(cell: Cell, transport: object, log_dir: Path, credential: object | None) -> FakeHandle:
            build_calls.append(cell)
            return FakeHandle()

        def fake_measure(
            cell: Cell,
            suite: object,
            mode: str,
            transport: object,
            probe: object | None,
            cancel: threading.Event,
            credential: object | None = None,
        ) -> CellResult:
            measure_calls.append(cell)
            return _pass_result(1.0)

        with TemporaryDirectory() as tmp:
            out = run_overhead(
                ("oq4_fp16",),
                ROOT / "config/overhead/pairs",
                ROOT / "config/matrix/cells",
                ROOT / "suites/gemma-matrix-v1.json",
                Path(tmp),
                build_server=fake_build,
                measure_cell=fake_measure,
                probe=FakeProbe([80] * 10),
                port_free=lambda port: True,  # 1337 free → Osaurus down
                credential_for=lambda server: None,
            )
            raw = json.loads((out / "raw.json").read_text(encoding="utf-8"))
            self.assertEqual(len(raw["pairs"]), 1)
            self.assertEqual(raw["pairs"][0]["direct"]["status"], "PASS")
            self.assertEqual(raw["pairs"][0]["routed"]["status"], "N/A")
            self.assertEqual(len(build_calls), 1)  # direct only
            self.assertEqual(len(measure_calls), 1)
            self.assertEqual(measure_calls[0].cell_id, "oq4_fp16__omlx")

    def test_busy_omlx_port_stops_then_runs(self) -> None:
        build_calls: list[Cell] = []
        stop_calls: list[tuple[str, ...]] = []
        omlx_busy = {"value": True}

        def fake_build(cell: Cell, transport: object, log_dir: Path, credential: object | None) -> FakeHandle:
            build_calls.append(cell)
            return FakeHandle()

        def fake_measure(
            cell: Cell,
            suite: object,
            mode: str,
            transport: object,
            probe: object | None,
            cancel: threading.Event,
            credential: object | None = None,
        ) -> CellResult:
            return _pass_result(1.1)

        def fake_port_free(port: int) -> bool:
            if port == 1337:
                return False
            if port == 8100:
                return not omlx_busy["value"]
            return True

        def fake_stop(command: tuple[str, ...]) -> None:
            stop_calls.append(command)
            omlx_busy["value"] = False

        with TemporaryDirectory() as tmp:
            out = run_overhead(
                ("oq4_fp16",),
                ROOT / "config/overhead/pairs",
                ROOT / "config/matrix/cells",
                ROOT / "suites/gemma-matrix-v1.json",
                Path(tmp),
                build_server=fake_build,
                measure_cell=fake_measure,
                probe=FakeProbe([80] * 10),
                port_free=fake_port_free,
                stop_runner=fake_stop,
                credential_for=lambda server: None,
            )
            raw = json.loads((out / "raw.json").read_text(encoding="utf-8"))
            self.assertEqual(raw["pairs"][0]["direct"]["status"], "PASS")
            self.assertEqual(raw["pairs"][0]["routed"]["status"], "PASS")
            self.assertEqual(stop_calls[0], ("omlX", "stop"))
            self.assertGreaterEqual(len(stop_calls), 1)
            self.assertEqual(len(build_calls), 2)

    def test_busy_optiq_port_stays_na(self) -> None:
        build_server = MagicMock()

        def fake_port_free(port: int) -> bool:
            if port == 1337:
                return False
            return False  # 8080 busy

        with TemporaryDirectory() as tmp:
            out = run_overhead(
                ("optiq_4bit",),
                ROOT / "config/overhead/pairs",
                ROOT / "config/matrix/cells",
                ROOT / "suites/gemma-matrix-v1.json",
                Path(tmp),
                build_server=build_server,
                measure_cell=MagicMock(),
                probe=FakeProbe([80] * 10),
                port_free=fake_port_free,
                stop_runner=MagicMock(),
                credential_for=lambda server: None,
            )
            raw = json.loads((out / "raw.json").read_text(encoding="utf-8"))
            self.assertEqual(raw["pairs"][0]["direct"]["status"], "N/A")
            self.assertIn("busy", raw["pairs"][0]["direct"]["na_reason"])
            build_server.assert_not_called()

    def test_memory_floor_stops_before_legs(self) -> None:
        build_server = MagicMock()
        with TemporaryDirectory() as tmp:
            out = run_overhead(
                DEFAULT_PAIR_IDS,
                ROOT / "config/overhead/pairs",
                ROOT / "config/matrix/cells",
                ROOT / "suites/gemma-matrix-v1.json",
                Path(tmp),
                build_server=build_server,
                measure_cell=MagicMock(),
                probe=FakeProbe([15]),
                port_free=lambda port: port != 1337,
                credential_for=lambda server: None,
            )
            raw = json.loads((out / "raw.json").read_text(encoding="utf-8"))
            self.assertTrue(raw["stopped_early"])
            self.assertEqual(raw["stop_reason"], "memory_floor")
            self.assertEqual(len(raw["pairs"]), 0)
            build_server.assert_not_called()


if __name__ == "__main__":
    unittest.main()
