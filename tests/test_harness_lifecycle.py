from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import MagicMock

from local_model_runtime_evaluation.harness_lifecycle import (
    HarnessLifecycleError,
    LifecycleController,
    PORT_BY_KIND,
    ServerPin,
)
from local_model_runtime_evaluation.matrix_lifecycle import ManagedProcess


class HarnessLifecyclePinTest(unittest.TestCase):
    def test_port_by_kind_matches_spec(self) -> None:
        self.assertEqual(PORT_BY_KIND["optiq"], 8080)
        self.assertEqual(PORT_BY_KIND["omlx"], 8100)
        self.assertEqual(PORT_BY_KIND["osaurus"], 1337)

    def test_server_pin_rejects_port_mismatch(self) -> None:
        with self.assertRaises(HarnessLifecycleError) as ctx:
            ServerPin(kind="optiq", port=9999, start_command=("optiq", "serve"))
        self.assertEqual(ctx.exception.code, "port_mismatch")


class HarnessLifecycleStartTest(unittest.TestCase):
    def setUp(self) -> None:
        self.spawn_calls: list[tuple[tuple[str, ...], Path]] = []
        self.fake_process = ManagedProcess(
            pid=4242,
            process_group_id=4242,
            command=("optiq", "serve"),
            _child=MagicMock(),
        )

    def _fake_spawner(self, command: tuple[str, ...], log_path: Path) -> ManagedProcess:
        self.spawn_calls.append((command, log_path))
        return self.fake_process

    def _controller(self, **overrides: object) -> LifecycleController:
        defaults: dict[str, object] = {
            "free_memory": lambda: 50.0,
            "port_free": lambda port: True,
            "lab_closed": lambda: True,
            "spawner": self._fake_spawner,
            "stop_runner": lambda cmd: None,
        }
        defaults.update(overrides)
        return LifecycleController(**defaults)

    def _optiq_pin(self) -> ServerPin:
        return ServerPin(
            kind="optiq",
            port=8080,
            start_command=("optiq", "serve"),
            stop_command=("optiq", "stop"),
        )

    def test_start_rejects_memory_below_floor(self) -> None:
        controller = self._controller(free_memory=lambda: 19.0)
        with self.assertRaises(HarnessLifecycleError) as ctx:
            controller.start(self._optiq_pin())
        self.assertEqual(ctx.exception.code, "memory_floor")
        self.assertEqual(controller.lifecycle_actions, 0)
        self.assertEqual(self.spawn_calls, [])

    def test_start_rejects_busy_port_for_non_osaurus(self) -> None:
        controller = self._controller(port_free=lambda port: False)
        with self.assertRaises(HarnessLifecycleError) as ctx:
            controller.start(self._optiq_pin())
        self.assertEqual(ctx.exception.code, "port_busy")
        self.assertEqual(controller.lifecycle_actions, 0)
        self.assertEqual(self.spawn_calls, [])

    def test_start_rejects_optiq_when_lab_open(self) -> None:
        controller = self._controller(lab_closed=lambda: False)
        with self.assertRaises(HarnessLifecycleError) as ctx:
            controller.start(self._optiq_pin())
        self.assertEqual(ctx.exception.code, "lab_open")
        self.assertEqual(controller.lifecycle_actions, 0)
        self.assertEqual(self.spawn_calls, [])

    def test_start_rejects_double_start(self) -> None:
        controller = self._controller()
        pin = self._optiq_pin()
        controller.start(pin)
        with self.assertRaises(HarnessLifecycleError) as ctx:
            controller.start(pin)
        self.assertEqual(ctx.exception.code, "already_started")
        self.assertEqual(controller.lifecycle_actions, 1)
        self.assertEqual(len(self.spawn_calls), 1)

    def test_start_happy_path_records_owned_process(self) -> None:
        controller = self._controller()
        pin = self._optiq_pin()
        controller.start(pin)
        self.assertEqual(controller.lifecycle_actions, 1)
        self.assertEqual(len(self.spawn_calls), 1)
        self.assertEqual(self.spawn_calls[0][0], pin.start_command)
        self.assertIs(controller.active_process, self.fake_process)
        self.assertTrue(controller.owned)
        self.assertEqual(controller.active_pin, pin)


if __name__ == "__main__":
    unittest.main()
