from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import MagicMock

from local_model_runtime_evaluation.harness_lifecycle import (
    LifecycleController,
    ServerPin,
)
from local_model_runtime_evaluation.matrix_lifecycle import ManagedProcess
from local_model_runtime_evaluation.omlx_thinking_measure import THINKING_PREFLIGHT_MAX_TOKENS
from local_model_runtime_evaluation.omlx_thinking_runner import (
    OMLX_THINKING_PORT,
    ThinkingChatResult,
    ThinkingMeasureError,
    ThinkingMeasureRunner,
    omlx_server_pin_from_pin,
)
from local_model_runtime_evaluation.omlx_thinking_pin import (
    OmlxThinkingPin,
    OmlxThinkingSuite,
    default_pin_path,
    default_suite_path,
)
from local_model_runtime_evaluation.transport import TransportError


class FakeChatTransport:
    def __init__(
        self,
        *,
        responses: list[ThinkingChatResult] | None = None,
        fail_at: int | None = None,
    ) -> None:
        self.calls: list[tuple[str, str, int]] = []
        self.responses = responses or []
        self.fail_at = fail_at

    def __call__(self, base_url: str, prompt: str, max_tokens: int) -> ThinkingChatResult:
        self.calls.append((base_url, prompt, max_tokens))
        index = len(self.calls)
        if self.fail_at is not None and index == self.fail_at:
            raise TransportError("simulated transport failure")
        if self.responses:
            return self.responses[min(index - 1, len(self.responses) - 1)]
        return ThinkingChatResult(visible_text="visible answer", finish_reason="stop")


class ThinkingMeasureRunnerTest(unittest.TestCase):
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
        self.suite = OmlxThinkingSuite.load(default_suite_path())

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
        chat: FakeChatTransport,
        *,
        lifecycle: LifecycleController | None = None,
        repetitions_per_workload: int = 1,
    ) -> ThinkingMeasureRunner:
        return ThinkingMeasureRunner(
            self.pin,
            self.suite,
            chat,
            controller=lifecycle or self._lifecycle(),
            repetitions_per_workload=repetitions_per_workload,
        )

    def test_omlx_server_pin_from_pin_uses_port_8100(self) -> None:
        pin = omlx_server_pin_from_pin(self.pin)
        self.assertEqual(pin.kind, "omlx")
        self.assertEqual(pin.port, OMLX_THINKING_PORT)
        self.assertEqual(pin.start_command, self.pin.start_command)
        self.assertEqual(pin.stop_command, self.pin.stop_command)

    def test_run_preflight_starts_lifecycle_and_uses_thinking_budget(self) -> None:
        chat = FakeChatTransport()
        lifecycle = self._lifecycle()
        runner = self._runner(chat, lifecycle=lifecycle)

        outcome = runner.run_preflight()

        self.assertEqual(outcome.outcome, "ok")
        self.assertEqual(outcome.phase, "preflight")
        self.assertEqual(lifecycle.lifecycle_actions, 1)
        self.assertEqual(len(self.spawn_calls), 1)
        self.assertEqual(self.spawn_calls[0][0], self.pin.start_command)
        self.assertEqual(len(chat.calls), 1)
        self.assertEqual(chat.calls[0][0], self.pin.base_url)
        self.assertEqual(chat.calls[0][2], THINKING_PREFLIGHT_MAX_TOKENS)
        self.assertGreaterEqual(chat.calls[0][2], 512)

    def test_run_preflight_fails_closed_on_transport_failure(self) -> None:
        chat = FakeChatTransport(fail_at=1)
        runner = self._runner(chat)

        with self.assertRaises(ThinkingMeasureError) as ctx:
            runner.run_preflight()

        self.assertEqual(ctx.exception.code, "preflight_failed")
        self.assertEqual(ctx.exception.outcome, "transport_failed")

    def test_run_smoke_runs_serial_posts_for_each_workload(self) -> None:
        chat = FakeChatTransport()
        runner = self._runner(chat)
        runner.run_preflight()

        outcomes = runner.run_smoke()

        self.assertEqual(len(outcomes), 2)
        self.assertEqual({item.workload_id for item in outcomes}, {
            "thinking-short-reason",
            "thinking-plan-and-answer",
        })
        self.assertTrue(all(item.outcome == "ok" for item in outcomes))
        self.assertEqual(len(chat.calls), 3)
        smoke_calls = chat.calls[1:]
        self.assertEqual(smoke_calls[0][1], self.suite.workloads[0].prompt)
        self.assertEqual(smoke_calls[0][2], self.suite.workloads[0].max_tokens)
        self.assertEqual(smoke_calls[1][1], self.suite.workloads[1].prompt)
        self.assertEqual(smoke_calls[1][2], self.suite.workloads[1].max_tokens)

    def test_run_smoke_classifies_contract_failure(self) -> None:
        chat = FakeChatTransport(responses=[
            ThinkingChatResult(visible_text="visible answer", finish_reason="stop"),
            ThinkingChatResult(visible_text="visible answer", finish_reason="stop"),
            ThinkingChatResult(visible_text="   ", finish_reason="stop"),
        ])
        runner = self._runner(chat)
        runner.run_preflight()
        outcomes = runner.run_smoke()

        self.assertEqual(outcomes[0].outcome, "ok")
        self.assertEqual(outcomes[1].outcome, "empty_visible")

    def test_run_smoke_rejects_more_than_eight_requests(self) -> None:
        runner = self._runner(FakeChatTransport(), repetitions_per_workload=5)
        runner.run_preflight()
        with self.assertRaises(ThinkingMeasureError) as ctx:
            runner.run_smoke()
        self.assertEqual(ctx.exception.code, "smoke_budget")

    def test_cleanup_stops_controller_and_verifies_port_free(self) -> None:
        chat = FakeChatTransport()
        lifecycle = self._lifecycle()
        runner = self._runner(chat, lifecycle=lifecycle)
        runner.run_preflight()
        self.port_free_calls.clear()

        runner.cleanup()

        self.assertEqual(self.stop_runner_calls, [self.pin.stop_command])
        self.assertGreaterEqual(lifecycle.lifecycle_actions, 2)
        self.assertEqual(self.port_free_calls, [OMLX_THINKING_PORT])

    def test_cleanup_fails_closed_when_port_still_busy(self) -> None:
        def port_free(port: int) -> bool:
            self.port_free_calls.append(port)
            return len(self.stop_runner_calls) == 0

        lifecycle = self._lifecycle(port_free=port_free)
        runner = self._runner(FakeChatTransport(), lifecycle=lifecycle)
        runner.run_preflight()
        self.port_free_calls.clear()

        with self.assertRaises(ThinkingMeasureError) as ctx:
            runner.cleanup()

        self.assertEqual(ctx.exception.code, "port_busy")

    def test_lifecycle_actions_reflect_underlying_controller(self) -> None:
        lifecycle = self._lifecycle()
        runner = self._runner(FakeChatTransport(), lifecycle=lifecycle)

        self.assertEqual(runner.lifecycle_actions, 0)
        runner.run_preflight()
        self.assertEqual(runner.lifecycle_actions, 1)
        runner.cleanup()
        self.assertEqual(runner.lifecycle_actions, 2)

    def test_requires_controller_or_factory(self) -> None:
        with self.assertRaises(ThinkingMeasureError) as ctx:
            ThinkingMeasureRunner(
                self.pin,
                self.suite,
                FakeChatTransport(),
            )
        self.assertEqual(ctx.exception.code, "missing_controller")

    def test_run_smoke_requires_preflight(self) -> None:
        runner = self._runner(FakeChatTransport())
        with self.assertRaises(ThinkingMeasureError) as ctx:
            runner.run_smoke()
        self.assertEqual(ctx.exception.code, "preflight_required")


if __name__ == "__main__":
    unittest.main()
