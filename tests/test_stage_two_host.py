from __future__ import annotations

import json
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace

from local_model_runtime_evaluation.stage_two import ModelDescriptor, StageTwoError
from local_model_runtime_evaluation.stage_two_host import (
    HostValidator, MacProcessBackend, OperatorOptiQController, OptiQLifecycleController, ProcessSnapshot,
    StageTwoReadOnlyTransport,
)
from local_model_runtime_evaluation.stage_two_profiles import RuntimeProfileRegistry


class FakeProcessBackend:
    def __init__(self) -> None:
        self.free = True
        self.processes: tuple[ProcessSnapshot, ...] = ()
        self.current = ProcessSnapshot(4242, 4000, 4242, "start-token", ("fixed", "command"))
        self.signals: list[tuple[int, bool]] = []
        self.lifecycle_calls: list[str] = []
        self.listener_pids: tuple[int, ...] = ()
        self.free_observations: list[bool] = []
        self.port_checks = 0
        self.exited = False

    def port_is_free(self) -> bool:
        self.port_checks += 1
        if self.free_observations:
            return self.free_observations.pop(0)
        return self.free

    def listener_process_ids(self) -> tuple[int, ...]:
        return self.listener_pids

    def optiq_processes(self) -> tuple[ProcessSnapshot, ...]:
        return self.processes

    def spawn(self, command: tuple[str, ...], log_path: Path) -> ProcessSnapshot:
        self.lifecycle_calls.append("spawn")
        self.current = ProcessSnapshot(4242, 4000, 4242, "start-token", command)
        self.free = False
        return self.current

    def describe(self, pid: int) -> ProcessSnapshot | None:
        return None if self.exited else self.current

    def terminate_group(self, process_group_id: int, force: bool) -> None:
        self.lifecycle_calls.append("terminate_group")
        self.signals.append((process_group_id, force))
        self.exited = True
        self.free = True

    def wait_exit(self, pid: int, timeout_seconds: int) -> bool:
        self.lifecycle_calls.append("wait_exit")
        return self.exited


class StageTwoHostTest(unittest.TestCase):
    def setUp(self) -> None:
        root = Path(__file__).parents[1]
        self.profile = RuntimeProfileRegistry(root / "config" / "runtime-profiles").get(
            "vibethinker-3b-optiq-4bit", "2"
        )

    def test_model_inventory_is_sanitized_to_bounded_descriptors(self) -> None:
        transport = StageTwoReadOnlyTransport({"http://127.0.0.1:8080/v1"}, 10)
        transport._request = lambda _base_url, _path: {  # type: ignore[method-assign]
            "data": [{
                "id": "mlx-community/VibeThinker-3B-OptiQ-4bit",
                "owned_by": "Optiq",
                "root": "mlx-community/VibeThinker-3B-OptiQ-4bit",
                "ignored": "discard-me",
            }]
        }
        self.assertEqual(transport.list_models("http://127.0.0.1:8080/v1"), (
            ModelDescriptor(
                "mlx-community/VibeThinker-3B-OptiQ-4bit",
                "Optiq",
                "mlx-community/VibeThinker-3B-OptiQ-4bit",
            ),
        ))
        self.assertNotIn("discard-me", repr(transport.list_models("http://127.0.0.1:8080/v1")))

    def test_model_inventory_rejects_malformed_descriptors(self) -> None:
        invalid_payloads = (
            {"data": [{}]},
            {"data": [{"id": ""}]},
            {"data": [{"id": "valid", "owned_by": 7}]},
            {"data": [{"id": "valid", "root": []}]},
            {"data": {}},
        )
        for payload in invalid_payloads:
            with self.subTest(payload=payload):
                transport = StageTwoReadOnlyTransport({"http://127.0.0.1:8080/v1"}, 10)
                transport._request = lambda _base_url, _path, value=payload: value  # type: ignore[method-assign]
                with self.assertRaisesRegex(StageTwoError, "model inventory payload"):
                    transport.list_models("http://127.0.0.1:8080/v1")

    def test_read_only_transport_rejects_non_inventory_paths_before_network(self) -> None:
        transport = StageTwoReadOnlyTransport({"http://127.0.0.1:8080/v1"}, 10)
        with self.assertRaises(StageTwoError) as raised:
            transport._request(
                "http://127.0.0.1:8080/v1", "/v1/chat/completions"
            )
        self.assertEqual(raised.exception.code, "endpoint_forbidden")

    def test_host_validator_uses_structured_config_and_never_returns_header_values(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            provider_path = Path(temp) / "remote.json"
            provider_path.write_text(json.dumps({"providers": [{
                "name": "Optiq", "host": "127.0.0.1", "port": 8080,
                "basePath": "/v1", "providerProtocol": "http", "providerType": "openai",
                "enabled": True, "customHeaders": {}, "secretHeaderKeys": [],
            }]}))

            commands: list[list[str]] = []

            def run(command: list[str]):
                commands.append(command)
                return SimpleNamespace(
                    returncode=0,
                    stdout=json.dumps(dict(self.profile.package_versions)),
                )

            validation = HostValidator(
                self.profile, provider_path, command_runner=run,
                hash_file=lambda path: self.profile.artifact_hashes[path.name],
            ).validate()
            self.assertEqual(validation.provider_identity, {
                "provider_id": "Optiq", "enabled": True, "endpoint": "127.0.0.1:8080",
                "custom_header_count": 0, "secret_header_key_count": 0,
            })
            self.assertNotIn("customHeaders", json.dumps(validation.provider_identity))
            self.assertFalse(any("--version" in command for command in commands))

    def test_controller_refuses_lab_or_unowned_service(self) -> None:
        command = (str(self.profile.runtime_executable), *self.profile.serve_arguments)
        backend = FakeProcessBackend()
        backend.processes = (ProcessSnapshot(12, 1, 12, "old", ("optiq", "lab")),)
        controller = OptiQLifecycleController(command, backend, lambda: {"status": "ok"})
        with self.assertRaisesRegex(StageTwoError, "OptiQ Lab or service"):
            controller.assert_available()

        backend.processes = ()
        controller.assert_available()
        ownership = controller.start(command, Path("/tmp/redacted.log"))
        backend.current = ProcessSnapshot(ownership.pid, 9999, ownership.process_group_id, "changed", command)
        self.assertFalse(controller.is_owned(ownership))
        with self.assertRaisesRegex(StageTwoError, "identity changed"):
            controller.stop(ownership, 30)
        self.assertEqual(backend.signals, [])

    def test_controller_stops_only_matching_owned_process_group(self) -> None:
        command = (str(self.profile.runtime_executable), *self.profile.serve_arguments)
        backend = FakeProcessBackend()
        controller = OptiQLifecycleController(command, backend, lambda: {"status": "ok"})
        ownership = controller.start(command, Path("/tmp/redacted.log"))
        self.assertEqual(controller.wait_ready(ownership, 1, threading.Event()), {"status": "ok"})
        controller.stop(ownership, 30)
        self.assertEqual(backend.signals, [(ownership.process_group_id, False)])
        self.assertTrue(controller.port_is_free())

    def test_operator_controller_captures_exact_foreground_service_with_interpreter_prefix(self) -> None:
        command = (str(self.profile.runtime_executable), *self.profile.serve_arguments)
        backend = FakeProcessBackend()
        backend.free = False
        backend.current = ProcessSnapshot(
            4242, 4000, 4242, "start-token",
            ("/Users/jrazz/Dev/tools/mlx-optiq/.venv/bin/python", *command),
        )
        backend.processes = (backend.current,)
        backend.listener_pids = (4242,)
        controller = OperatorOptiQController(command, backend, lambda: {
            "status": "ok",
            "model_loaded": True,
            "model": str(self.profile.model_snapshot),
            "model_path": str(self.profile.model_snapshot),
            "active_requests": 0,
            "foreground_active": 0,
        })

        identity = controller.capture()

        self.assertEqual(identity.pid, 4242)
        self.assertTrue(controller.matches(identity))
        self.assertEqual(backend.signals, [])
        self.assertEqual(backend.lifecycle_calls, [])

    def test_operator_controller_rejects_lab_command_health_and_listener_drift(self) -> None:
        command = (str(self.profile.runtime_executable), *self.profile.serve_arguments)
        cases = (
            (
                "lab",
                (ProcessSnapshot(4242, 4000, 4242, "start-token", ("optiq", "lab")),),
                (4242,),
                {"status": "ok"},
            ),
            (
                "command drift",
                (ProcessSnapshot(4242, 4000, 4242, "start-token", (*command, "--extra")),),
                (4242,),
                {"status": "ok"},
            ),
            (
                "loaded model",
                (ProcessSnapshot(4242, 4000, 4242, "start-token", command),),
                (4242,),
                {"status": "ok", "model_loaded": True, "current_model": "wrong/model"},
            ),
            (
                "resident model",
                (ProcessSnapshot(4242, 4000, 4242, "start-token", command),),
                (4242,),
                {"status": "ok", "resident_models": ["wrong/model"]},
            ),
            (
                "listener mismatch",
                (ProcessSnapshot(4242, 4000, 4242, "start-token", command),),
                (9999,),
                {"status": "ok"},
            ),
        )
        for name, processes, listener_pids, health in cases:
            with self.subTest(name=name):
                backend = FakeProcessBackend()
                backend.free = False
                backend.current = processes[0]
                backend.processes = processes
                backend.listener_pids = listener_pids
                controller = OperatorOptiQController(command, backend, lambda value=health: value)

                with self.assertRaises(StageTwoError):
                    controller.capture()
                self.assertEqual(backend.signals, [])
                self.assertEqual(backend.lifecycle_calls, [])

    def test_operator_controller_detects_identity_replacement(self) -> None:
        command = (str(self.profile.runtime_executable), *self.profile.serve_arguments)
        backend = FakeProcessBackend()
        backend.free = False
        backend.current = ProcessSnapshot(4242, 4000, 4242, "start-token", command)
        backend.processes = (backend.current,)
        backend.listener_pids = (4242,)
        controller = OperatorOptiQController(command, backend, lambda: {"status": "ok"})
        identity = controller.capture()
        backend.current = ProcessSnapshot(4242, 9999, 4242, "replacement-token", command)

        self.assertFalse(controller.matches(identity))
        self.assertEqual(backend.signals, [])
        self.assertEqual(backend.lifecycle_calls, [])

    def test_operator_controller_detects_an_additional_optiq_process(self) -> None:
        command = (str(self.profile.runtime_executable), *self.profile.serve_arguments)
        backend = FakeProcessBackend()
        backend.free = False
        backend.current = ProcessSnapshot(4242, 4000, 4242, "start-token", command)
        backend.processes = (backend.current,)
        backend.listener_pids = (4242,)
        controller = OperatorOptiQController(command, backend, lambda: {"status": "ok"})
        identity = controller.capture()
        backend.processes = (
            backend.current,
            ProcessSnapshot(5252, 5000, 5252, "other", ("optiq", "lab")),
        )

        self.assertFalse(controller.matches(identity))

    def test_operator_controller_requires_two_free_port_observations_to_confirm_shutdown(self) -> None:
        command = (str(self.profile.runtime_executable), *self.profile.serve_arguments)
        backend = FakeProcessBackend()
        backend.free = False
        backend.current = ProcessSnapshot(4242, 4000, 4242, "start-token", command)
        backend.processes = (backend.current,)
        backend.listener_pids = (4242,)
        controller = OperatorOptiQController(command, backend, lambda: {"status": "ok"})
        identity = controller.capture()
        backend.exited = True
        backend.processes = ()
        backend.free_observations = [True, True]
        port_checks_before_shutdown = backend.port_checks

        controller.assert_stopped(identity)

        self.assertEqual(backend.port_checks - port_checks_before_shutdown, 2)
        self.assertEqual(backend.signals, [])
        self.assertEqual(backend.lifecycle_calls, [])

    def test_operator_shutdown_rejects_any_remaining_optiq_process(self) -> None:
        command = (str(self.profile.runtime_executable), *self.profile.serve_arguments)
        backend = FakeProcessBackend()
        backend.free = False
        backend.current = ProcessSnapshot(4242, 4000, 4242, "start-token", command)
        backend.processes = (backend.current,)
        backend.listener_pids = (4242,)
        controller = OperatorOptiQController(command, backend, lambda: {"status": "ok"})
        identity = controller.capture()
        backend.exited = True
        backend.processes = (
            ProcessSnapshot(5252, 5000, 5252, "replacement", command),
        )
        backend.free_observations = [True, True]

        with self.assertRaisesRegex(StageTwoError, "OptiQ process"):
            controller.assert_stopped(identity)

    def test_production_backend_reaps_harness_child_handle(self) -> None:
        class Child:
            def __init__(self) -> None:
                self.timeout = None

            def wait(self, timeout):
                self.timeout = timeout
                return 0

            def poll(self):
                return 0

        backend = MacProcessBackend()
        child = Child()
        backend._children[77] = child
        self.assertTrue(backend.wait_exit(77, 30))
        self.assertEqual(child.timeout, 30)
        self.assertNotIn(77, backend._children)


if __name__ == "__main__":
    unittest.main()
