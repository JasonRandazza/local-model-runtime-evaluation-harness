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

    def _omlx_pin(self, *, stop_command: tuple[str, ...] = ()) -> ServerPin:
        return ServerPin(
            kind="omlx",
            port=8100,
            start_command=("omlX", "serve"),
            stop_command=stop_command,
        )

    def _osaurus_pin(self) -> ServerPin:
        return ServerPin(
            kind="osaurus",
            port=1337,
            start_command=("osaurus", "serve"),
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

    def test_start_rejects_busy_optiq_port(self) -> None:
        controller = self._controller(port_free=lambda port: False)
        with self.assertRaises(HarnessLifecycleError) as ctx:
            controller.start(self._optiq_pin())
        self.assertEqual(ctx.exception.code, "port_busy")
        self.assertEqual(controller.lifecycle_actions, 0)
        self.assertEqual(self.spawn_calls, [])

    def test_osaurus_busy_port_attaches_observe_only_without_spawn(self) -> None:
        controller = self._controller(port_free=lambda port: False)
        pin = self._osaurus_pin()
        controller.start(pin)
        self.assertEqual(self.spawn_calls, [])
        self.assertFalse(controller.owned)
        self.assertIsNone(controller.active_process)
        self.assertEqual(controller.active_pin, pin)
        self.assertEqual(controller.lifecycle_actions, 0)

    def test_osaurus_free_port_spawns_owned(self) -> None:
        controller = self._controller(port_free=lambda port: True)
        pin = self._osaurus_pin()
        controller.start(pin)
        self.assertEqual(len(self.spawn_calls), 1)
        self.assertEqual(self.spawn_calls[0][0], pin.start_command)
        self.assertTrue(controller.owned)
        self.assertIs(controller.active_process, self.fake_process)
        self.assertEqual(controller.lifecycle_actions, 1)

    def test_omlx_busy_port_reclaims_then_spawns_owned(self) -> None:
        stop_calls: list[tuple[str, ...]] = []
        wait_calls: list[tuple[int, float]] = []
        port_busy = {"value": True}

        def port_free(port: int) -> bool:
            return not port_busy["value"]

        def wait_port_free(port: int, timeout_seconds: float) -> None:
            wait_calls.append((port, timeout_seconds))
            port_busy["value"] = False

        controller = self._controller(
            port_free=port_free,
            stop_runner=lambda cmd: stop_calls.append(cmd),
            wait_port_free=wait_port_free,
        )
        pin = self._omlx_pin()
        controller.start(pin)
        self.assertEqual(stop_calls, [("omlX", "stop")])
        self.assertEqual(wait_calls, [(8100, 30.0)])
        self.assertEqual(len(self.spawn_calls), 1)
        self.assertEqual(self.spawn_calls[0][0], pin.start_command)
        self.assertTrue(controller.owned)
        self.assertEqual(controller.lifecycle_actions, 1)

    def test_omlx_busy_port_uses_pin_stop_command(self) -> None:
        stop_calls: list[tuple[str, ...]] = []
        port_busy = {"value": True}

        controller = self._controller(
            port_free=lambda port: not port_busy["value"],
            stop_runner=lambda cmd: stop_calls.append(cmd),
            wait_port_free=lambda port, timeout: port_busy.update(value=False),
        )
        pin = self._omlx_pin(stop_command=("omlX", "stop", "--force"))
        controller.start(pin)
        self.assertEqual(stop_calls, [("omlX", "stop", "--force")])


if __name__ == "__main__":
    unittest.main()
