from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import MagicMock

from local_model_runtime_evaluation.harness_lifecycle import (
    HarnessLifecycleError,
    LifecycleController,
    ServerPin,
)
from local_model_runtime_evaluation.matrix_lifecycle import ManagedProcess
from local_model_runtime_evaluation.stage_two import ProcessOwnership, StageTwoError
from local_model_runtime_evaluation.stage_two_harness_lifecycle import (
    HarnessOptiQController,
    optiq_server_pin_from_profile,
)
from local_model_runtime_evaluation.stage_two_profiles import RuntimeProfile


class HarnessOptiQControllerTest(unittest.TestCase):
    def setUp(self) -> None:
        self.spawn_calls: list[tuple[tuple[str, ...], Path]] = []
        self.stop_runner_calls: list[tuple[str, ...]] = []
        self.wait_port_free_calls: list[tuple[int, float]] = []
        self.port_free_calls: list[int] = []
        self.fake_process = ManagedProcess(
            pid=4242,
            process_group_id=4242,
            command=("optiq", "serve"),
            _child=MagicMock(),
        )
        self.fake_process._child.poll.return_value = None

    def _fake_spawner(self, command: tuple[str, ...], log_path: Path) -> ManagedProcess:
        self.spawn_calls.append((command, log_path))
        return self.fake_process

    def _port_free(self, port: int) -> bool:
        self.port_free_calls.append(port)
        return True

    def _controller(self, **overrides: object) -> HarnessOptiQController:
        defaults: dict[str, object] = {
            "free_memory": lambda: 50.0,
            "port_free": self._port_free,
            "lab_closed": lambda: True,
            "spawner": self._fake_spawner,
            "stop_runner": lambda cmd: self.stop_runner_calls.append(cmd),
            "wait_port_free": lambda port, timeout: self.wait_port_free_calls.append(
                (port, timeout)
            ),
        }
        defaults.update(overrides)
        return HarnessOptiQController(**defaults)

    def _optiq_pin(self) -> ServerPin:
        return ServerPin(
            kind="optiq",
            port=8080,
            start_command=("optiq", "serve"),
            stop_command=("optiq", "stop"),
        )

    def test_construction_without_controller_requires_probe_callbacks(self) -> None:
        with self.assertRaises(HarnessLifecycleError) as ctx:
            HarnessOptiQController()
        self.assertEqual(ctx.exception.code, "missing_probes")

    def test_injected_controller_uses_controller_port_free_for_stop_probes(self) -> None:
        port_free_calls: list[int] = []

        def port_free(port: int) -> bool:
            port_free_calls.append(port)
            return True

        lifecycle = LifecycleController(
            free_memory=lambda: 50.0,
            port_free=port_free,
            lab_closed=lambda: True,
            spawner=self._fake_spawner,
            stop_runner=lambda cmd: self.stop_runner_calls.append(cmd),
            wait_port_free=lambda port, timeout: self.wait_port_free_calls.append(
                (port, timeout)
            ),
        )
        controller = HarnessOptiQController(controller=lifecycle)
        controller.ensure_started(self._optiq_pin())
        port_free_calls.clear()
        controller.ensure_stopped()
        self.assertEqual(port_free_calls, [8080, 8080])

    def test_start_then_stop_records_at_least_two_lifecycle_actions(self) -> None:
        controller = self._controller()
        controller.ensure_started(self._optiq_pin())
        controller.ensure_stopped()
        self.assertGreaterEqual(controller.lifecycle_actions, 2)
        self.assertEqual(len(self.spawn_calls), 1)
        self.assertEqual(self.stop_runner_calls, [("optiq", "stop")])
        self.assertEqual(self.wait_port_free_calls, [(8080, 30.0)])

    def test_foreign_busy_optiq_fails_closed_without_spawn(self) -> None:
        controller = self._controller(port_free=lambda port: False)
        with self.assertRaises(HarnessLifecycleError) as ctx:
            controller.ensure_started(self._optiq_pin())
        self.assertEqual(ctx.exception.code, "port_busy")
        self.assertEqual(controller.lifecycle_actions, 0)
        self.assertEqual(self.spawn_calls, [])

    def test_double_stop_is_safe_noop(self) -> None:
        controller = self._controller()
        controller.ensure_started(self._optiq_pin())
        controller.ensure_stopped()
        actions_after_first_stop = controller.lifecycle_actions
        controller.ensure_stopped()
        self.assertEqual(controller.lifecycle_actions, actions_after_first_stop)
        self.assertEqual(len(self.stop_runner_calls), 1)
        self.assertEqual(len(self.wait_port_free_calls), 1)

    def test_ensure_stopped_verifies_port_free_twice(self) -> None:
        controller = self._controller()
        controller.ensure_started(self._optiq_pin())
        self.port_free_calls.clear()
        controller.ensure_stopped()
        self.assertEqual(self.port_free_calls, [8080, 8080])

    def test_optiq_server_pin_from_profile_builds_start_command(self) -> None:
        profile = RuntimeProfile(
            profile_id="gemma-4-12b-optiq-4bit",
            revision="4",
            runtime_executable=Path("/tools/optiq"),
            runtime_version="0.4.2",
            coordinator_model_id="coord",
            package_versions={"mlx-optiq": "0.4.2"},
            model_repository="mlx-community/gemma",
            model_revision="abc",
            model_snapshot=Path("/model"),
            artifact_hashes={"config.json": "hash"},
            serve_arguments=("serve", "--model", "/model", "--port", "8080"),
            direct_base_url="http://127.0.0.1:8080/v1",
            routed_base_url="http://127.0.0.1:1337/v1",
            direct_model_identities=("/model:no-think",),
            osaurus_provider_id="Optiq",
            routed_model_id="optiq//model:no-think",
            rejected_local_model_ids=(),
            service_ownership="harness",
            provider_activation="verify_routed_id_only",
        )
        pin = optiq_server_pin_from_profile(profile)
        self.assertEqual(pin.kind, "optiq")
        self.assertEqual(pin.port, 8080)
        self.assertEqual(
            pin.start_command,
            ("/tools/optiq", "serve", "--model", "/model", "--port", "8080"),
        )
        self.assertEqual(pin.stop_command, ("/tools/optiq", "stop"))

    def test_capture_matches_and_assert_stopped_expose_operator_compatible_identity(self) -> None:
        listening = False

        def port_free(port: int) -> bool:
            self.port_free_calls.append(port)
            return not listening

        controller = self._controller(port_free=port_free)
        pin = self._optiq_pin()
        controller._server_pin = pin
        identity = controller.capture()
        self.assertEqual(identity.pid, self.fake_process.pid)
        self.assertEqual(identity.process_group_id, self.fake_process.process_group_id)
        listening = True
        self.assertTrue(controller.matches(identity))
        listening = False
        controller.assert_stopped(identity)
        self.assertGreaterEqual(controller.lifecycle_actions, 2)
        self.assertFalse(controller.matches(identity))

    def test_matches_false_when_process_dead_and_port_busy(self) -> None:
        listening = False

        def port_free(port: int) -> bool:
            return not listening

        controller = self._controller(port_free=port_free)
        controller._server_pin = self._optiq_pin()
        identity = controller.capture()
        listening = True
        self.fake_process._child.poll.return_value = 0
        self.assertFalse(controller.matches(identity))

    def test_matches_false_when_not_owned_and_port_busy(self) -> None:
        listening = False

        def port_free(port: int) -> bool:
            return not listening

        controller = self._controller(port_free=port_free)
        controller._server_pin = self._optiq_pin()
        identity = controller.capture()
        listening = True
        controller._controller._owned = False
        self.assertFalse(controller.matches(identity))

    def test_assert_stopped_not_owned_port_busy_skips_stop_runner(self) -> None:
        port_busy = False

        def port_free(port: int) -> bool:
            return not port_busy

        controller = self._controller(port_free=port_free)
        controller.ensure_started(self._optiq_pin())
        identity = ProcessOwnership(
            self.fake_process.pid,
            self.fake_process.pid,
            self.fake_process.process_group_id,
            "harness-owned",
            "deadbeef" * 8,
        )
        controller._identity = identity
        controller._controller._owned = False
        port_busy = True
        with self.assertRaises(StageTwoError):
            controller.assert_stopped(identity)
        self.assertEqual(self.stop_runner_calls, [])

    def test_ensure_stopped_dead_process_port_free_skips_stop_runner(self) -> None:
        controller = self._controller()
        controller.ensure_started(self._optiq_pin())
        self.fake_process._child.poll.return_value = 0
        controller.ensure_stopped()
        self.assertEqual(self.stop_runner_calls, [])


if __name__ == "__main__":
    unittest.main()
