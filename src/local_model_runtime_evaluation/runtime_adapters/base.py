"""Shared runtime lifecycle contracts and loopback adapter behavior."""

from __future__ import annotations

import hashlib
import os
import signal
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Protocol

from ..credentials import Credential
from ..managed_run_types import Ownership
from ..matrix_config import Cell
from ..matrix_lifecycle import ManagedProcess, run_stop_command, spawn_pinned
from ..operator_policy import OperatorPolicy, PolicyRequest
from ..process_inspection import (
    ProcessIdentity,
    ProcessInspectionError,
    ProcessInspector,
)


class RuntimeAdapterError(RuntimeError):
    code = "runtime_adapter_failed"


class TransportProtocol(Protocol):
    def list_models(
        self,
        base_url: str,
        credential: object | None,
    ) -> tuple[str, ...]:
        raise NotImplementedError


LifecycleSink = Callable[[str, str, dict[str, object]], None]
Spawner = Callable[[tuple[str, ...], Path], ManagedProcess]
NoticeSink = Callable[[str], None]
Sleep = Callable[[float], None]
Signaler = Callable[[int, signal.Signals], None]
StopRunner = Callable[[tuple[str, ...]], None]


def _no_lifecycle(
    runtime: str,
    action: str,
    payload: dict[str, object],
) -> None:
    del runtime, action, payload


@dataclass(frozen=True)
class RuntimeContext:
    log_dir: Path
    credential: Credential | None
    transport: TransportProtocol
    policy: OperatorPolicy | None
    policy_request: PolicyRequest | None
    notice: NoticeSink
    sleep: Sleep
    lifecycle_sink: LifecycleSink
    interrupt_checks: int
    terminate_checks: int
    ready_checks: int
    poll_seconds: float
    catalog_root: Path | None = None
    omlx_base_root: Path | None = None

    @classmethod
    def for_test(
        cls,
        *,
        log_dir: Path,
        credential: Credential | None,
        transport: TransportProtocol,
        policy: OperatorPolicy | None = None,
        policy_request: PolicyRequest | None = None,
        notice: NoticeSink | None = None,
        sleep: Sleep | None = None,
        lifecycle_sink: LifecycleSink | None = None,
        interrupt_checks: int = 1,
        terminate_checks: int = 1,
        ready_checks: int = 1,
        poll_seconds: float = 0.25,
        catalog_root: Path | None = None,
        omlx_base_root: Path | None = None,
    ) -> RuntimeContext:
        return cls(
            log_dir=log_dir,
            credential=credential,
            transport=transport,
            policy=policy,
            policy_request=policy_request,
            notice=(lambda message: None) if notice is None else notice,
            sleep=(lambda seconds: None) if sleep is None else sleep,
            lifecycle_sink=(
                _no_lifecycle if lifecycle_sink is None else lifecycle_sink
            ),
            interrupt_checks=interrupt_checks,
            terminate_checks=terminate_checks,
            ready_checks=ready_checks,
            poll_seconds=poll_seconds,
            catalog_root=catalog_root,
            omlx_base_root=omlx_base_root,
        )


@dataclass(frozen=True)
class RuntimeRequirement:
    runtime: str
    cell_id: str
    base_url: str
    port: int
    model_id: str
    artifact_path: str
    start_command: tuple[str, ...]
    stop_command: tuple[str, ...]


@dataclass(frozen=True)
class RuntimeObservation:
    identity: ProcessIdentity | None
    inventory: tuple[str, ...]
    compatible: bool
    reason: str


@dataclass(frozen=True)
class RuntimeLease:
    requirement: RuntimeRequirement
    ownership: Ownership
    identity: ProcessIdentity | None
    process: ManagedProcess | None
    lease_id: str

    @classmethod
    def create(
        cls,
        requirement: RuntimeRequirement,
        ownership: Ownership,
        identity: ProcessIdentity | None,
        *,
        process: ManagedProcess | None,
    ) -> RuntimeLease:
        pid = (
            identity.pid
            if identity is not None
            else process.pid
            if process is not None
            else 0
        )
        started_at = "" if identity is None else identity.started_at
        digest = hashlib.sha256(
            (
                f"{requirement.runtime}\0{requirement.cell_id}\0{pid}\0{started_at}"
            ).encode("utf-8")
        ).hexdigest()[:12]
        return cls(
            requirement=requirement,
            ownership=ownership,
            identity=identity,
            process=process,
            lease_id=f"{requirement.runtime}-{pid}-{digest}",
        )


class RuntimeAdapter(Protocol):
    runtime: str

    def requirement_from_cell(self, cell: Cell) -> RuntimeRequirement:
        raise NotImplementedError

    def inspect(
        self,
        requirement: RuntimeRequirement,
        context: RuntimeContext,
    ) -> RuntimeObservation:
        raise NotImplementedError

    def attach(
        self,
        requirement: RuntimeRequirement,
        observation: RuntimeObservation,
    ) -> RuntimeLease:
        raise NotImplementedError

    def start(
        self,
        requirement: RuntimeRequirement,
        context: RuntimeContext,
    ) -> RuntimeLease:
        raise NotImplementedError

    def interrupt(self, identity: ProcessIdentity) -> None:
        raise NotImplementedError

    def terminate(self, identity: ProcessIdentity) -> None:
        raise NotImplementedError

    def release(
        self,
        lease: RuntimeLease,
        context: RuntimeContext,
    ) -> None:
        raise NotImplementedError

    def process_is_alive(self, identity: ProcessIdentity) -> bool:
        raise NotImplementedError


class LoopbackRuntimeAdapter:
    runtime = ""
    port = 0

    def __init__(
        self,
        *,
        inspector: ProcessInspector,
        spawner: Spawner | None = None,
        signaler: Signaler | None = None,
        stop_runner: StopRunner | None = None,
    ) -> None:
        self._inspector = inspector
        self._spawner = spawn_pinned if spawner is None else spawner
        self._signaler = os.kill if signaler is None else signaler
        self._stop_runner = run_stop_command if stop_runner is None else stop_runner

    def requirement_from_cell(self, cell: Cell) -> RuntimeRequirement:
        if cell.server != self.runtime:
            raise RuntimeAdapterError(
                f"{self.runtime} adapter cannot run {cell.server} cell"
            )
        expected_url = f"http://127.0.0.1:{self.port}/v1"
        if cell.base_url != expected_url:
            raise RuntimeAdapterError(f"{self.runtime} requires {expected_url}")
        if not Path(cell.artifact_path).is_absolute():
            raise RuntimeAdapterError("model artifact path must be absolute")
        self.validate_start_command(cell)
        return RuntimeRequirement(
            runtime=self.runtime,
            cell_id=cell.cell_id,
            base_url=cell.base_url,
            port=self.port,
            model_id=cell.model_id,
            artifact_path=cell.artifact_path,
            start_command=cell.start_command,
            stop_command=cell.stop_command,
        )

    def validate_start_command(self, cell: Cell) -> None:
        raise NotImplementedError

    def identity_matches(
        self,
        identity: ProcessIdentity,
        requirement: RuntimeRequirement,
    ) -> bool:
        del requirement
        return (
            identity.listener_host == "127.0.0.1"
            and identity.listener_port == self.port
        )

    def inspect(
        self,
        requirement: RuntimeRequirement,
        context: RuntimeContext,
    ) -> RuntimeObservation:
        inspection_error: ProcessInspectionError | None = None
        for attempt in range(3):
            try:
                identity = self._inspector.inspect_listener(
                    "127.0.0.1",
                    self.port,
                )
                break
            except ProcessInspectionError as error:
                inspection_error = error
                if attempt < 2:
                    context.sleep(context.poll_seconds)
        else:
            assert inspection_error is not None
            raise RuntimeAdapterError(str(inspection_error)) from inspection_error
        if identity is None:
            return RuntimeObservation(
                identity=None,
                inventory=(),
                compatible=False,
                reason="listener_absent",
            )
        try:
            inventory = tuple(
                context.transport.list_models(
                    requirement.base_url,
                    context.credential,
                )
            )
        except Exception:
            return RuntimeObservation(
                identity=identity,
                inventory=(),
                compatible=False,
                reason="inventory_unavailable",
            )
        if not self.identity_matches(identity, requirement):
            return RuntimeObservation(
                identity=identity,
                inventory=inventory,
                compatible=False,
                reason="runtime_identity_mismatch",
            )
        if requirement.model_id not in inventory:
            return RuntimeObservation(
                identity=identity,
                inventory=inventory,
                compatible=False,
                reason="required_model_missing",
            )
        return RuntimeObservation(
            identity=identity,
            inventory=inventory,
            compatible=True,
            reason="compatible",
        )

    def process_is_alive(self, identity: ProcessIdentity) -> bool:
        try:
            return self._inspector.process_is_alive(identity)
        except Exception as error:
            raise RuntimeAdapterError(str(error)) from error

    def attach(
        self,
        requirement: RuntimeRequirement,
        observation: RuntimeObservation,
    ) -> RuntimeLease:
        if observation.identity is None or not observation.compatible:
            raise RuntimeAdapterError("cannot attach an incompatible runtime")
        return RuntimeLease.create(
            requirement,
            Ownership.ATTACHED,
            observation.identity,
            process=None,
        )

    def start_command(
        self,
        requirement: RuntimeRequirement,
        context: RuntimeContext,
    ) -> tuple[str, ...]:
        del context
        return requirement.start_command

    def evidence_command(
        self,
        command: tuple[str, ...],
    ) -> tuple[str, ...]:
        redacted = list(command)
        for index, value in enumerate(redacted[:-1]):
            if value in {"--api-key", "--access-key", "--authorization"}:
                redacted[index + 1] = "<redacted>"
        return tuple(redacted)

    def start(
        self,
        requirement: RuntimeRequirement,
        context: RuntimeContext,
    ) -> RuntimeLease:
        command = self.start_command(requirement, context)
        try:
            process = self._spawner(
                command,
                context.log_dir / f"{requirement.cell_id}.log",
            )
        except Exception as error:
            raise RuntimeAdapterError(str(error)) from error
        return RuntimeLease.create(
            requirement,
            Ownership.OWNED,
            None,
            process=process,
        )

    def interrupt(self, identity: ProcessIdentity) -> None:
        try:
            self._signaler(identity.pid, signal.SIGINT)
        except ProcessLookupError:
            return
        except PermissionError as error:
            raise RuntimeAdapterError(
                "permission denied while interrupting exact runtime"
            ) from error

    def terminate(self, identity: ProcessIdentity) -> None:
        try:
            self._signaler(identity.pid, signal.SIGTERM)
        except ProcessLookupError:
            return
        except PermissionError as error:
            raise RuntimeAdapterError(
                "permission denied while terminating exact runtime"
            ) from error

    def release(
        self,
        lease: RuntimeLease,
        context: RuntimeContext,
    ) -> None:
        del context
        if lease.process is None:
            raise RuntimeAdapterError("owned runtime lease has no managed process")
        try:
            if lease.requirement.stop_command:
                self._stop_runner(lease.requirement.stop_command)
            else:
                lease.process.stop()
        except Exception as error:
            raise RuntimeAdapterError(str(error)) from error
