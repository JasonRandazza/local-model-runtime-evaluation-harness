"""Policy-gated runtime ownership and exact reclaim state machine."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Mapping

from .credentials import Credential
from .managed_run_types import Ownership
from .matrix_config import Cell
from .matrix_servers import ServerHandle, TransportProtocol
from .operator_policy import PolicyError, authorize
from .process_inspection import ProcessIdentity
from .runtime_adapters.base import (
    RuntimeAdapter,
    RuntimeAdapterError,
    RuntimeContext,
    RuntimeLease,
    RuntimeObservation,
    RuntimeRequirement,
)


class RuntimeManagerError(RuntimeError):
    code = "runtime_manager_failed"

    def __init__(
        self,
        message: str,
        *,
        code: str = "runtime_manager_failed",
    ) -> None:
        super().__init__(message)
        self.code = code


def _safe_argv(argv: tuple[str, ...]) -> list[str]:
    values = list(argv)
    for index, value in enumerate(values[:-1]):
        if value in {"--api-key", "--access-key", "--authorization"}:
            values[index + 1] = "<redacted>"
    return values


def _identity_payload(identity: ProcessIdentity) -> dict[str, object]:
    return {
        "pid": identity.pid,
        "ppid": identity.ppid,
        "executable": identity.executable,
        "argv": _safe_argv(identity.argv),
        "started_at": identity.started_at,
        "listener_host": identity.listener_host,
        "listener_port": identity.listener_port,
    }


def _same_identity(
    expected: ProcessIdentity,
    actual: ProcessIdentity,
) -> None:
    if expected.fingerprint() != actual.fingerprint():
        raise RuntimeManagerError(
            "runtime identity changed during managed lifecycle",
            code="runtime_identity_changed",
        )


class RuntimeManager:
    def __init__(
        self,
        adapters: Mapping[str, RuntimeAdapter],
        *,
        context_template: RuntimeContext | None = None,
    ) -> None:
        self._adapters = dict(adapters)
        self._context_template = context_template
        self._active: dict[
            str,
            tuple[RuntimeLease, RuntimeContext],
        ] = {}
        self._lease_sequence = 0

    def _activate(
        self,
        lease: RuntimeLease,
        context: RuntimeContext,
    ) -> RuntimeLease:
        self._lease_sequence += 1
        activated = replace(
            lease,
            lease_id=f"{lease.lease_id}-{self._lease_sequence:04d}",
        )
        self._record_lease(activated, context)
        self._active[activated.lease_id] = (activated, context)
        return activated

    def _adapter(self, runtime: str) -> RuntimeAdapter:
        try:
            return self._adapters[runtime]
        except KeyError as error:
            raise RuntimeManagerError(
                f"runtime adapter is unavailable: {runtime}"
            ) from error

    def _record_observation(
        self,
        requirement: RuntimeRequirement,
        observation: RuntimeObservation,
        context: RuntimeContext,
        *,
        action: str,
    ) -> None:
        payload: dict[str, object] = {
            "cell_id": requirement.cell_id,
            "compatible": observation.compatible,
            "inventory": list(observation.inventory),
            "reason": observation.reason,
            "required_model": requirement.model_id,
        }
        if observation.identity is not None:
            payload["identity"] = _identity_payload(observation.identity)
        context.lifecycle_sink(requirement.runtime, action, payload)

    def _record_lease(
        self,
        lease: RuntimeLease,
        context: RuntimeContext,
    ) -> None:
        if lease.identity is None:
            raise RuntimeManagerError(
                "runtime lease has no verified identity",
                code="runtime_verification_failed",
            )
        context.lifecycle_sink(
            lease.requirement.runtime,
            "lease_acquired",
            {
                "identity": _identity_payload(lease.identity),
                "lease_id": lease.lease_id,
                "ownership": lease.ownership.value,
            },
        )

    def _verify_started(
        self,
        adapter: RuntimeAdapter,
        lease: RuntimeLease,
        context: RuntimeContext,
    ) -> RuntimeLease:
        last: RuntimeObservation | None = None
        for index in range(max(1, context.ready_checks)):
            last = adapter.inspect(lease.requirement, context)
            if last.compatible and last.identity is not None:
                verified = replace(lease, identity=last.identity)
                self._record_observation(
                    lease.requirement,
                    last,
                    context,
                    action="start_verified",
                )
                return verified
            if index + 1 < max(1, context.ready_checks):
                context.sleep(context.poll_seconds)
        reason = "unknown" if last is None else last.reason
        raise RuntimeManagerError(
            f"started runtime failed exact verification: {reason}",
            code="runtime_verification_failed",
        )

    def _start_verified(
        self,
        adapter: RuntimeAdapter,
        requirement: RuntimeRequirement,
        context: RuntimeContext,
        *,
        ownership: Ownership,
    ) -> RuntimeLease:
        provisional = adapter.start(requirement, context)
        context.lifecycle_sink(
            requirement.runtime,
            "start_requested",
            {
                "cell_id": requirement.cell_id,
                "ownership": ownership.value,
            },
        )
        try:
            verified = self._verify_started(adapter, provisional, context)
        except Exception:
            try:
                adapter.release(provisional, context)
            except Exception:
                pass
            raise
        verified = replace(verified, ownership=ownership)
        return verified

    def _wait_absent(
        self,
        adapter: RuntimeAdapter,
        requirement: RuntimeRequirement,
        context: RuntimeContext,
        expected: ProcessIdentity,
        *,
        checks: int,
    ) -> bool:
        for index in range(max(1, checks)):
            observation = adapter.inspect(requirement, context)
            if observation.identity is None:
                return True
            _same_identity(expected, observation.identity)
            if index + 1 < max(1, checks):
                context.sleep(context.poll_seconds)
        return False

    def _wait_process_exit(
        self,
        adapter: RuntimeAdapter,
        context: RuntimeContext,
        expected: ProcessIdentity,
        *,
        checks: int,
    ) -> bool:
        for index in range(max(1, checks)):
            if not adapter.process_is_alive(expected):
                return True
            if index + 1 < max(1, checks):
                context.sleep(context.poll_seconds)
        return False

    def _notice(
        self,
        requirement: RuntimeRequirement,
        observation: RuntimeObservation,
        context: RuntimeContext,
    ) -> None:
        if observation.identity is None or context.policy is None:
            raise RuntimeManagerError("incompatible runtime identity is missing")
        observed = (
            ", ".join(observation.inventory)
            if observation.inventory
            else "<inventory unavailable>"
        )
        context.notice(
            (
                f"LMRE found incompatible {requirement.runtime} on "
                f"127.0.0.1:{requirement.port}: PID "
                f"{observation.identity.pid}, observed models {observed}, "
                f"required model {requirement.model_id}. "
                f"Policy {context.policy.policy_id} grants a "
                f"{context.policy.reclaim_grace_seconds}-second grace period. "
                "Shut the runtime down now or press Ctrl+C to cancel this run."
            )
        )

    def prepare(
        self,
        requirement: RuntimeRequirement,
        context: RuntimeContext,
    ) -> RuntimeLease:
        if context.policy is None or context.policy_request is None:
            raise RuntimeManagerError("managed runtime policy context is missing")
        try:
            authorize(context.policy, context.policy_request)
        except PolicyError as error:
            raise RuntimeManagerError(
                str(error),
                code=error.code,
            ) from error
        adapter = self._adapter(requirement.runtime)
        try:
            observation = adapter.inspect(requirement, context)
            self._record_observation(
                requirement,
                observation,
                context,
                action="initial_observation",
            )
            if observation.identity is None:
                return self._activate(
                    self._start_verified(
                        adapter,
                        requirement,
                        context,
                        ownership=Ownership.OWNED,
                    ),
                    context,
                )
            if observation.compatible:
                lease = adapter.attach(requirement, observation)
                return self._activate(lease, context)

            original = observation.identity
            self._notice(requirement, observation, context)
            context.lifecycle_sink(
                requirement.runtime,
                "reclaim_notice",
                {
                    "grace_seconds": context.policy.reclaim_grace_seconds,
                    "identity": _identity_payload(original),
                    "policy_id": context.policy.policy_id,
                },
            )
            context.sleep(context.policy.reclaim_grace_seconds)
            rechecked = adapter.inspect(requirement, context)
            self._record_observation(
                requirement,
                rechecked,
                context,
                action="grace_revalidation",
            )
            if rechecked.identity is None:
                return self._activate(
                    self._start_verified(
                        adapter,
                        requirement,
                        context,
                        ownership=Ownership.OWNED,
                    ),
                    context,
                )
            _same_identity(original, rechecked.identity)

            adapter.interrupt(original)
            context.lifecycle_sink(
                requirement.runtime,
                "interrupt_sent",
                {"identity": _identity_payload(original)},
            )
            stopped = self._wait_absent(
                adapter,
                requirement,
                context,
                original,
                checks=context.interrupt_checks,
            )
            if not stopped:
                if not context.policy.allow_terminate_after_interrupt:
                    raise RuntimeManagerError(
                        "runtime remained after interrupt",
                        code="runtime_reclaim_incomplete",
                    )
                adapter.terminate(original)
                context.lifecycle_sink(
                    requirement.runtime,
                    "terminate_sent",
                    {"identity": _identity_payload(original)},
                )
                stopped = self._wait_absent(
                    adapter,
                    requirement,
                    context,
                    original,
                    checks=context.terminate_checks,
                )
            if not stopped:
                raise RuntimeManagerError(
                    "runtime remained after normal termination",
                    code="runtime_reclaim_incomplete",
                )
            return self._activate(
                self._start_verified(
                    adapter,
                    requirement,
                    context,
                    ownership=Ownership.RECLAIMED,
                ),
                context,
            )
        except RuntimeManagerError:
            raise
        except RuntimeAdapterError as error:
            raise RuntimeManagerError(str(error)) from error

    def release(
        self,
        lease: RuntimeLease,
        context: RuntimeContext,
    ) -> None:
        adapter = self._adapter(lease.requirement.runtime)
        if lease.ownership is Ownership.ATTACHED:
            context.lifecycle_sink(
                lease.requirement.runtime,
                "untouched",
                {"lease_id": lease.lease_id},
            )
            self._active.pop(lease.lease_id, None)
            return
        if lease.identity is None:
            raise RuntimeManagerError(
                "owned runtime lease has no identity",
                code="runtime_verification_failed",
            )
        current = adapter.inspect(lease.requirement, context)
        listener_already_absent = current.identity is None
        if current.identity is not None:
            _same_identity(lease.identity, current.identity)
        try:
            adapter.release(lease, context)
        except RuntimeAdapterError as error:
            raise RuntimeManagerError(
                str(error),
                code="runtime_cleanup_failed",
            ) from error
        if not listener_already_absent and not self._wait_absent(
            adapter,
            lease.requirement,
            context,
            lease.identity,
            checks=context.terminate_checks,
        ):
            raise RuntimeManagerError(
                "owned runtime listener remained after cleanup",
                code="runtime_cleanup_failed",
            )
        process_exited = self._wait_process_exit(
            adapter,
            context,
            lease.identity,
            checks=context.terminate_checks,
        )
        if not process_exited:
            try:
                adapter.interrupt(lease.identity)
            except RuntimeAdapterError as error:
                raise RuntimeManagerError(
                    str(error),
                    code="runtime_cleanup_failed",
                ) from error
            context.lifecycle_sink(
                lease.requirement.runtime,
                "cleanup_interrupt_sent",
                {"identity": _identity_payload(lease.identity)},
            )
            process_exited = self._wait_process_exit(
                adapter,
                context,
                lease.identity,
                checks=context.interrupt_checks,
            )
        if not process_exited:
            if (
                context.policy is None
                or not context.policy.allow_terminate_after_interrupt
            ):
                raise RuntimeManagerError(
                    "owned runtime remained after cleanup interrupt",
                    code="runtime_cleanup_failed",
                )
            try:
                adapter.terminate(lease.identity)
            except RuntimeAdapterError as error:
                raise RuntimeManagerError(
                    str(error),
                    code="runtime_cleanup_failed",
                ) from error
            context.lifecycle_sink(
                lease.requirement.runtime,
                "cleanup_terminate_sent",
                {"identity": _identity_payload(lease.identity)},
            )
            process_exited = self._wait_process_exit(
                adapter,
                context,
                lease.identity,
                checks=context.terminate_checks,
            )
        if not process_exited:
            raise RuntimeManagerError(
                "owned runtime process remained after cleanup",
                code="runtime_cleanup_failed",
            )
        context.lifecycle_sink(
            lease.requirement.runtime,
            "released",
            {
                "lease_id": lease.lease_id,
                "listener_already_absent": listener_already_absent,
            },
        )
        self._active.pop(lease.lease_id, None)

    def release_all(self) -> None:
        errors: list[Exception] = []
        for lease, context in reversed(tuple(self._active.values())):
            try:
                self.release(lease, context)
            except Exception as error:
                errors.append(error)
        if errors:
            first = errors[0]
            raise RuntimeManagerError(
                f"managed runtime cleanup failed: {first}",
                code="runtime_cleanup_failed",
            ) from first

    def build_server(
        self,
        cell: Cell,
        transport: TransportProtocol,
        log_dir: Path,
        credential: Credential | None,
    ) -> ServerHandle:
        if self._context_template is None:
            raise RuntimeManagerError(
                "runtime manager server context is not configured"
            )
        adapter = self._adapter(cell.server)
        requirement = adapter.requirement_from_cell(cell)
        context = replace(
            self._context_template,
            log_dir=log_dir,
            credential=credential,
            transport=transport,
        )
        return ManagedRuntimeServerHandle(
            manager=self,
            adapter=adapter,
            requirement=requirement,
            context=context,
        )


class ManagedRuntimeServerHandle:
    def __init__(
        self,
        *,
        manager: RuntimeManager,
        adapter: RuntimeAdapter,
        requirement: RuntimeRequirement,
        context: RuntimeContext,
    ) -> None:
        self._manager = manager
        self._adapter = adapter
        self._requirement = requirement
        self._context = context
        self._lease: RuntimeLease | None = None

    def start(self) -> None:
        if self._lease is None:
            self._lease = self._manager.prepare(
                self._requirement,
                self._context,
            )

    def wait_ready(self, model_id: str, timeout_seconds: float) -> None:
        if model_id != self._requirement.model_id:
            raise RuntimeManagerError("ready model does not match requirement")
        checks = max(
            1,
            int(timeout_seconds / max(self._context.poll_seconds, 0.01)),
        )
        for index in range(checks):
            observation = self._adapter.inspect(
                self._requirement,
                self._context,
            )
            if observation.compatible:
                return
            if index + 1 < checks:
                self._context.sleep(self._context.poll_seconds)
        raise RuntimeManagerError(
            "managed runtime did not become ready",
            code="runtime_verification_failed",
        )

    def stop(self) -> None:
        if self._lease is not None:
            self._manager.release(self._lease, self._context)
            self._lease = None
