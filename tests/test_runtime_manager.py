from __future__ import annotations

import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import MagicMock

from local_model_runtime_evaluation.managed_run_types import Ownership
from local_model_runtime_evaluation.operator_policy import (
    OperatorPolicy,
    PolicyRequest,
)
from local_model_runtime_evaluation.process_inspection import ProcessIdentity
from local_model_runtime_evaluation.runtime_adapters.base import (
    RuntimeContext,
    RuntimeLease,
    RuntimeObservation,
    RuntimeRequirement,
)
from local_model_runtime_evaluation.runtime_manager import (
    RuntimeManager,
    RuntimeManagerError,
)


def _policy(**overrides: object) -> OperatorPolicy:
    body: dict[str, object] = {
        "schema_version": "1.0.0",
        "policy_id": "local-managed-v1",
        "authorization_mode": "standing_local",
        "loopback_only": True,
        "allowed_runtimes": ["osaurus", "omlx", "optiq"],
        "allow_inference": True,
        "allow_start": True,
        "allow_exact_reclaim": True,
        "reclaim_grace_seconds": 60,
        "allow_terminate_after_interrupt": True,
        "allow_force_kill": False,
        "allow_provider_edits": False,
        "max_parallel_models": 1,
        "memory_floor_percent": 20,
        "max_run_minutes": 90,
        "max_requests_per_run": 250,
        "expires_at": None,
    }
    body.update(overrides)
    return OperatorPolicy.from_dict(body)


def _policy_request() -> PolicyRequest:
    return PolicyRequest(
        runtimes=frozenset({"omlx"}),
        endpoints=("http://127.0.0.1:8100/v1",),
        inference=True,
        start=True,
        exact_reclaim=True,
        parallel_models=1,
        memory_floor_percent=20,
        estimated_minutes=30,
        request_count=20,
    )


def _requirement() -> RuntimeRequirement:
    return RuntimeRequirement(
        runtime="omlx",
        cell_id="oq4__omlx",
        base_url="http://127.0.0.1:8100/v1",
        port=8100,
        model_id="model-a",
        artifact_path="/Users/test/model-a",
        start_command=("omlx", "serve"),
        stop_command=(),
    )


def _identity(
    *,
    pid: int = 321,
    started_at: str = "Thu Jul 30 18:00:00 2026",
) -> ProcessIdentity:
    return ProcessIdentity(
        pid=pid,
        ppid=100,
        executable="/usr/local/bin/omlx-server",
        argv=("omlx-server", "--port", "8100"),
        started_at=started_at,
        listener_host="127.0.0.1",
        listener_port=8100,
    )


def _observation(
    identity: ProcessIdentity,
    *,
    compatible: bool,
) -> RuntimeObservation:
    return RuntimeObservation(
        identity=identity,
        inventory=("model-a",) if compatible else ("other-model",),
        compatible=compatible,
        reason="compatible" if compatible else "required_model_missing",
    )


def _absent() -> RuntimeObservation:
    return RuntimeObservation(
        identity=None,
        inventory=(),
        compatible=False,
        reason="listener_absent",
    )


class FakeAdapter:
    runtime = "omlx"

    def __init__(
        self,
        observations: list[RuntimeObservation],
        *,
        started_identity: ProcessIdentity | None = None,
        process_alive: list[bool] | None = None,
    ) -> None:
        self.observations = list(observations)
        self.started_identity = started_identity or _identity(pid=900)
        self.interrupted: list[ProcessIdentity] = []
        self.terminated: list[ProcessIdentity] = []
        self.released: list[RuntimeLease] = []
        self.started = 0
        self.process_alive = list(process_alive or [])
        self.process_checks: list[ProcessIdentity] = []

    def inspect(
        self,
        requirement: RuntimeRequirement,
        context: RuntimeContext,
    ) -> RuntimeObservation:
        if not self.observations:
            raise AssertionError("unexpected inspect")
        return self.observations.pop(0)

    def attach(
        self,
        requirement: RuntimeRequirement,
        observation: RuntimeObservation,
    ) -> RuntimeLease:
        assert observation.identity is not None
        return RuntimeLease.create(
            requirement,
            Ownership.ATTACHED,
            observation.identity,
            process=None,
        )

    def start(
        self,
        requirement: RuntimeRequirement,
        context: RuntimeContext,
    ) -> RuntimeLease:
        self.started += 1
        return RuntimeLease.create(
            requirement,
            Ownership.OWNED,
            self.started_identity,
            process=MagicMock(),
        )

    def interrupt(self, identity: ProcessIdentity) -> None:
        self.interrupted.append(identity)

    def terminate(self, identity: ProcessIdentity) -> None:
        self.terminated.append(identity)

    def release(
        self,
        lease: RuntimeLease,
        context: RuntimeContext,
    ) -> None:
        self.released.append(lease)

    def process_is_alive(self, identity: ProcessIdentity) -> bool:
        self.process_checks.append(identity)
        if not self.process_alive:
            return False
        return self.process_alive.pop(0)


def _context(
    *,
    notices: list[str] | None = None,
    sleeps: list[float] | None = None,
    lifecycle: list[tuple[str, str, dict[str, object]]] | None = None,
    terminate_checks: int = 1,
) -> RuntimeContext:
    notice_list = [] if notices is None else notices
    sleep_list = [] if sleeps is None else sleeps
    lifecycle_list = [] if lifecycle is None else lifecycle
    return RuntimeContext.for_test(
        log_dir=Path("/tmp/logs"),
        credential=None,
        transport=MagicMock(),
        policy=_policy(),
        policy_request=_policy_request(),
        notice=notice_list.append,
        sleep=sleep_list.append,
        lifecycle_sink=lambda runtime, action, payload: lifecycle_list.append(
            (runtime, action, payload)
        ),
        interrupt_checks=1,
        terminate_checks=terminate_checks,
    )


class RuntimeManagerTests(unittest.TestCase):
    def test_absent_runtime_is_started_and_owned(self) -> None:
        new = _identity(pid=900)
        adapter = FakeAdapter([_absent(), _observation(new, compatible=True)])
        manager = RuntimeManager({"omlx": adapter})
        lease = manager.prepare(_requirement(), _context())
        self.assertEqual(lease.ownership, Ownership.OWNED)
        self.assertEqual(adapter.started, 1)
        self.assertEqual(lease.identity, new)

    def test_compatible_runtime_is_attached_and_untouched_on_release(self) -> None:
        existing = _identity()
        lifecycle: list[tuple[str, str, dict[str, object]]] = []
        adapter = FakeAdapter([_observation(existing, compatible=True)])
        manager = RuntimeManager({"omlx": adapter})
        context = _context(lifecycle=lifecycle)
        lease = manager.prepare(_requirement(), context)
        self.assertEqual(lease.ownership, Ownership.ATTACHED)
        manager.release(lease, context)
        self.assertEqual(adapter.released, [])
        self.assertEqual(lifecycle[-1][1], "untouched")

    def test_user_shutdown_during_grace_starts_owned_replacement(self) -> None:
        old = _identity()
        new = _identity(pid=900)
        notices: list[str] = []
        sleeps: list[float] = []
        adapter = FakeAdapter(
            [
                _observation(old, compatible=False),
                _absent(),
                _observation(new, compatible=True),
            ]
        )
        manager = RuntimeManager({"omlx": adapter})
        lease = manager.prepare(
            _requirement(),
            _context(notices=notices, sleeps=sleeps),
        )
        self.assertEqual(sleeps[0], 60)
        self.assertIn("PID 321", notices[0])
        self.assertIn("Ctrl+C", notices[0])
        self.assertEqual(adapter.interrupted, [])
        self.assertEqual(lease.ownership, Ownership.OWNED)

    def test_incompatible_process_is_revalidated_and_exactly_reclaimed(self) -> None:
        old = _identity()
        new = _identity(pid=900)
        notices: list[str] = []
        sleeps: list[float] = []
        adapter = FakeAdapter(
            [
                _observation(old, compatible=False),
                _observation(old, compatible=False),
                _absent(),
                _observation(new, compatible=True),
            ]
        )
        manager = RuntimeManager({"omlx": adapter})
        lease = manager.prepare(
            _requirement(),
            _context(notices=notices, sleeps=sleeps),
        )
        self.assertEqual(sleeps[0], 60)
        self.assertEqual(adapter.interrupted, [old])
        self.assertEqual(adapter.terminated, [])
        self.assertEqual(lease.ownership, Ownership.RECLAIMED)

    def test_changed_identity_cancels_reclaim(self) -> None:
        old = _identity()
        changed = _identity(pid=654)
        adapter = FakeAdapter(
            [
                _observation(old, compatible=False),
                _observation(changed, compatible=False),
            ]
        )
        manager = RuntimeManager({"omlx": adapter})
        with self.assertRaises(RuntimeManagerError) as context:
            manager.prepare(_requirement(), _context())
        self.assertEqual(
            context.exception.code,
            "runtime_identity_changed",
        )
        self.assertEqual(adapter.interrupted, [])

    def test_interrupt_then_policy_allowed_terminate(self) -> None:
        old = _identity()
        new = _identity(pid=900)
        adapter = FakeAdapter(
            [
                _observation(old, compatible=False),
                _observation(old, compatible=False),
                _observation(old, compatible=False),
                _absent(),
                _observation(new, compatible=True),
            ]
        )
        manager = RuntimeManager({"omlx": adapter})
        lease = manager.prepare(_requirement(), _context())
        self.assertEqual(adapter.interrupted, [old])
        self.assertEqual(adapter.terminated, [old])
        self.assertEqual(lease.ownership, Ownership.RECLAIMED)

    def test_terminate_denied_fails_without_force(self) -> None:
        old = _identity()
        adapter = FakeAdapter(
            [
                _observation(old, compatible=False),
                _observation(old, compatible=False),
                _observation(old, compatible=False),
            ]
        )
        context = replace(
            _context(),
            policy=_policy(allow_terminate_after_interrupt=False),
        )
        manager = RuntimeManager({"omlx": adapter})
        with self.assertRaises(RuntimeManagerError) as raised:
            manager.prepare(_requirement(), context)
        self.assertEqual(
            raised.exception.code,
            "runtime_reclaim_incomplete",
        )
        self.assertEqual(adapter.terminated, [])

    def test_started_runtime_must_verify_exact_model(self) -> None:
        new = _identity(pid=900)
        adapter = FakeAdapter(
            [
                _absent(),
                _observation(new, compatible=False),
            ]
        )
        manager = RuntimeManager({"omlx": adapter})
        with self.assertRaises(RuntimeManagerError) as context:
            manager.prepare(_requirement(), _context())
        self.assertEqual(
            context.exception.code,
            "runtime_verification_failed",
        )

    def test_owned_release_revalidates_identity(self) -> None:
        new = _identity(pid=900)
        adapter = FakeAdapter(
            [
                _absent(),
                _observation(new, compatible=True),
                _observation(new, compatible=True),
                _absent(),
            ]
        )
        manager = RuntimeManager({"omlx": adapter})
        context = _context()
        lease = manager.prepare(_requirement(), context)
        manager.release(lease, context)
        self.assertEqual(adapter.released, [lease])

    def test_owned_release_waits_for_exact_process_exit_after_listener_closes(
        self,
    ) -> None:
        new = _identity(pid=900)
        sleeps: list[float] = []
        adapter = FakeAdapter(
            [
                _absent(),
                _observation(new, compatible=True),
                _observation(new, compatible=True),
                _absent(),
            ],
            process_alive=[True, False],
        )
        manager = RuntimeManager({"omlx": adapter})
        context = _context(
            sleeps=sleeps,
            terminate_checks=2,
        )
        lease = manager.prepare(_requirement(), context)

        manager.release(lease, context)

        self.assertEqual(adapter.process_checks, [new, new])
        self.assertEqual(sleeps, [context.poll_seconds])

    def test_owned_release_interrupts_exact_process_left_after_listener_closes(
        self,
    ) -> None:
        new = _identity(pid=900)
        lifecycle: list[tuple[str, str, dict[str, object]]] = []
        adapter = FakeAdapter(
            [
                _absent(),
                _observation(new, compatible=True),
                _observation(new, compatible=True),
                _absent(),
            ],
            process_alive=[True, False],
        )
        manager = RuntimeManager({"omlx": adapter})
        context = _context(lifecycle=lifecycle)
        lease = manager.prepare(_requirement(), context)

        manager.release(lease, context)

        self.assertEqual(adapter.interrupted, [new])
        self.assertEqual(adapter.terminated, [])
        self.assertIn("cleanup_interrupt_sent", [item[1] for item in lifecycle])

    def test_owned_release_terminates_exact_process_after_bounded_interrupt(
        self,
    ) -> None:
        new = _identity(pid=900)
        lifecycle: list[tuple[str, str, dict[str, object]]] = []
        adapter = FakeAdapter(
            [
                _absent(),
                _observation(new, compatible=True),
                _observation(new, compatible=True),
                _absent(),
            ],
            process_alive=[True, True, False],
        )
        manager = RuntimeManager({"omlx": adapter})
        context = _context(lifecycle=lifecycle)
        lease = manager.prepare(_requirement(), context)

        manager.release(lease, context)

        self.assertEqual(adapter.interrupted, [new])
        self.assertEqual(adapter.terminated, [new])
        self.assertIn("cleanup_terminate_sent", [item[1] for item in lifecycle])

    def test_owned_release_cleans_verified_process_when_listener_is_already_absent(
        self,
    ) -> None:
        new = _identity(pid=900)
        adapter = FakeAdapter(
            [
                _absent(),
                _observation(new, compatible=True),
                _absent(),
            ],
            process_alive=[True, False],
        )
        manager = RuntimeManager({"omlx": adapter})
        context = _context()
        lease = manager.prepare(_requirement(), context)

        manager.release(lease, context)

        self.assertEqual(adapter.released, [lease])
        self.assertEqual(adapter.interrupted, [new])

    def test_owned_release_rejects_changed_identity(self) -> None:
        new = _identity(pid=900)
        changed = _identity(pid=901)
        adapter = FakeAdapter(
            [
                _absent(),
                _observation(new, compatible=True),
                _observation(changed, compatible=True),
            ]
        )
        manager = RuntimeManager({"omlx": adapter})
        context = _context()
        lease = manager.prepare(_requirement(), context)
        with self.assertRaises(RuntimeManagerError) as raised:
            manager.release(lease, context)
        self.assertEqual(
            raised.exception.code,
            "runtime_identity_changed",
        )
        self.assertEqual(adapter.released, [])


if __name__ == "__main__":
    unittest.main()
