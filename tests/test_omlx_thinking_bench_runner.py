from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import MagicMock

from local_model_runtime_evaluation.harness_lifecycle import LifecycleController
from local_model_runtime_evaluation.matrix_lifecycle import ManagedProcess
from local_model_runtime_evaluation.omlx_admin_bench_client import (
    BenchMetricRow,
    OmlxAdminBenchError,
    build_external_bench_request,
)
from local_model_runtime_evaluation.omlx_thinking_bench_parity import COMPARISON_CLASS
from local_model_runtime_evaluation.omlx_thinking_bench_runner import (
    GATE_A_PLACEHOLDER_RUN_ID,
    ThinkingBenchParityError,
    ThinkingBenchParityRunner,
)
from local_model_runtime_evaluation.omlx_thinking_pin import OmlxThinkingPin, default_pin_path
from local_model_runtime_evaluation.omlx_thinking_runner import OMLX_THINKING_PORT


class FakeAdminClient:
    def __init__(
        self,
        *,
        login_ok: bool = True,
        bench_status: str = "completed",
        rows: tuple[BenchMetricRow, ...] | None = None,
    ) -> None:
        self.login_calls: list[str] = []
        self.start_calls: list[dict[str, object]] = []
        self.fetch_calls: list[str] = []
        self.login_ok = login_ok
        self.bench_status = bench_status
        self.rows = rows or (
            BenchMetricRow(12.5, 1.2, 40.0, 1.5, 1024, 200, "ok"),
        )

    def login(self, api_key: str) -> None:
        self.login_calls.append(api_key)
        if not self.login_ok:
            raise OmlxAdminBenchError("admin login failed", reason="login_failed")

    def start_external_bench(self, body: dict[str, object]) -> str:
        self.start_calls.append(body)
        return "bench-1"

    def fetch_results(self, bench_id: str) -> tuple[str, tuple[BenchMetricRow, ...]]:
        self.fetch_calls.append(bench_id)
        return self.bench_status, self.rows


class ThinkingBenchParityRunnerTest(unittest.TestCase):
    def setUp(self) -> None:
        self.spawn_calls: list[tuple[tuple[str, ...], Path]] = []
        self.stop_runner_calls: list[tuple[str, ...]] = []
        self.port_free_calls: list[int] = []
        self.fake_process = ManagedProcess(
            pid=8100,
            process_group_id=8100,
            command=("omlX", "serve"),
            _child=MagicMock(),
        )
        self.pin = OmlxThinkingPin.load(default_pin_path())
        self.api_key = "lmre-matrix-local"

    def _fake_spawner(self, command: tuple[str, ...], log_path: Path) -> ManagedProcess:
        self.spawn_calls.append((command, log_path))
        return self.fake_process

    def _port_free(self, port: int) -> bool:
        self.port_free_calls.append(port)
        return True

    def _lifecycle(self, **overrides: object) -> LifecycleController:
        defaults: dict[str, object] = {
            "free_memory": lambda: 50.0,
            "port_free": self._port_free,
            "lab_closed": lambda: True,
            "spawner": self._fake_spawner,
            "stop_runner": lambda cmd: self.stop_runner_calls.append(cmd),
            "wait_port_free": lambda port, timeout: None,
        }
        defaults.update(overrides)
        return LifecycleController(**defaults)

    def _runner(
        self,
        admin_client: FakeAdminClient,
        *,
        lifecycle: LifecycleController | None = None,
    ) -> ThinkingBenchParityRunner:
        return ThinkingBenchParityRunner(
            self.pin,
            controller=lifecycle or self._lifecycle(),
            admin_client=admin_client,
            api_key=self.api_key,
            port_free=self._port_free,
        )

    def test_run_parity_starts_lifecycle_and_runs_admin_bench(self) -> None:
        admin = FakeAdminClient()
        lifecycle = self._lifecycle()
        runner = self._runner(admin, lifecycle=lifecycle)

        result = runner.run_parity()

        self.assertGreater(lifecycle.lifecycle_actions, 0)
        self.assertEqual(runner.lifecycle_actions, lifecycle.lifecycle_actions)
        self.assertEqual(admin.login_calls, [self.api_key])
        self.assertEqual(len(admin.start_calls), 1)
        expected_body = build_external_bench_request(
            model_id=self.pin.model_id,
            base_url=self.pin.base_url,
            api_key=self.api_key,
        )
        self.assertEqual(admin.start_calls[0], expected_body)
        self.assertEqual(admin.fetch_calls, ["bench-1"])
        self.assertEqual(result["comparison_class"], COMPARISON_CLASS)
        self.assertEqual(result["bench_status"], "completed")
        self.assertEqual(result["rows"], admin.rows)
        self.assertIn(GATE_A_PLACEHOLDER_RUN_ID, result["cross_check_markdown"])
        self.assertIn(COMPARISON_CLASS, result["cross_check_markdown"])

    def test_run_parity_login_failure_does_not_start_bench(self) -> None:
        admin = FakeAdminClient(login_ok=False)
        runner = self._runner(admin)

        with self.assertRaises(OmlxAdminBenchError) as ctx:
            runner.run_parity()

        self.assertEqual(ctx.exception.reason, "login_failed")
        self.assertEqual(admin.start_calls, [])
        self.assertEqual(admin.fetch_calls, [])

    def test_cleanup_stops_controller_and_verifies_port_free(self) -> None:
        admin = FakeAdminClient()
        lifecycle = self._lifecycle()
        runner = self._runner(admin, lifecycle=lifecycle)
        runner.run_parity()
        self.port_free_calls.clear()

        runner.cleanup()

        self.assertEqual(self.stop_runner_calls, [self.pin.stop_command])
        self.assertGreaterEqual(lifecycle.lifecycle_actions, 2)
        self.assertEqual(self.port_free_calls, [OMLX_THINKING_PORT, OMLX_THINKING_PORT])

    def test_cleanup_fails_closed_when_port_still_busy(self) -> None:
        def port_free(port: int) -> bool:
            self.port_free_calls.append(port)
            return len(self.stop_runner_calls) == 0

        lifecycle = self._lifecycle(port_free=port_free)
        runner = ThinkingBenchParityRunner(
            self.pin,
            controller=lifecycle,
            admin_client=FakeAdminClient(),
            api_key=self.api_key,
            port_free=port_free,
        )
        runner.run_parity()
        self.port_free_calls.clear()

        with self.assertRaises(ThinkingBenchParityError) as ctx:
            runner.cleanup()

        self.assertEqual(ctx.exception.code, "port_busy")


if __name__ == "__main__":
    unittest.main()
