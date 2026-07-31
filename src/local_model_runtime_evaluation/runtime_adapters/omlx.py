"""Fixed oMLX managed-runtime adapter."""

from __future__ import annotations

from pathlib import Path

from ..credentials import Credential
from ..managed_run_types import Ownership
from ..matrix_config import Cell
from ..omlx_catalog import (
    OMLX_CATALOG_TOKEN,
    CatalogEntry,
    OmlxCatalogError,
    TemporaryOmlxCatalog,
)
from ..process_inspection import ProcessIdentity
from .base import (
    LoopbackRuntimeAdapter,
    RuntimeAdapterError,
    RuntimeContext,
    RuntimeLease,
    RuntimeRequirement,
    Spawner,
    Signaler,
)
from ..process_inspection import ProcessInspector


MATRIX_OMLX_API_KEY = "lmre-matrix-local"


class OmlxAdapter(LoopbackRuntimeAdapter):
    runtime = "omlx"
    port = 8100

    def __init__(
        self,
        *,
        inspector: ProcessInspector,
        spawner: Spawner | None = None,
        signaler: Signaler | None = None,
    ) -> None:
        super().__init__(
            inspector=inspector,
            spawner=spawner,
            signaler=signaler,
        )
        self._catalogs: dict[int, TemporaryOmlxCatalog] = {}

    def validate_start_command(self, cell: Cell) -> None:
        command = cell.start_command
        if (
            len(command) < 8
            or command[0].lower() != "omlx"
            or command[1] != "serve"
            or "--model-dir" not in command
            or "--host" not in command
            or "--port" not in command
        ):
            raise RuntimeAdapterError("oMLX start command is not fixed")
        if command[command.index("--host") + 1] != "127.0.0.1":
            raise RuntimeAdapterError("oMLX host must be fixed loopback")
        if command[command.index("--port") + 1] != "8100":
            raise RuntimeAdapterError("oMLX port must be fixed")
        if cell.stop_command:
            raise RuntimeAdapterError("oMLX stop command must be empty")

    def identity_matches(
        self,
        identity: ProcessIdentity,
        requirement: RuntimeRequirement,
    ) -> bool:
        if not super().identity_matches(identity, requirement):
            return False
        lowered = tuple(part.lower() for part in identity.argv)
        if lowered and Path(lowered[0]).name == "omlx-server":
            return True
        identity_text = " ".join(
            (Path(identity.executable).name.lower(), *lowered)
        )
        return (
            "omlx" in identity_text
            and "--port" in lowered
            and lowered[lowered.index("--port") + 1] == "8100"
        )

    def start_command(
        self,
        requirement: RuntimeRequirement,
        context: RuntimeContext,
    ) -> tuple[str, ...]:
        if "--api-key" in requirement.start_command:
            raise RuntimeAdapterError(
                "oMLX credential must not be stored in cell config"
            )
        credential = (
            Credential(MATRIX_OMLX_API_KEY)
            if context.credential is None
            else context.credential
        )
        command = requirement.start_command
        if OMLX_CATALOG_TOKEN in command:
            if context.catalog_root is None:
                raise RuntimeAdapterError(
                    "oMLX managed catalog root is missing"
                )
            command = tuple(
                str(context.catalog_root)
                if part == OMLX_CATALOG_TOKEN
                else part
                for part in command
            )
        return command + (
            "--api-key",
            credential.api_key(),
        )

    def start(
        self,
        requirement: RuntimeRequirement,
        context: RuntimeContext,
    ) -> RuntimeLease:
        if context.catalog_root is None:
            raise RuntimeAdapterError("oMLX managed catalog root is missing")
        catalog: TemporaryOmlxCatalog | None = None
        try:
            catalog = TemporaryOmlxCatalog.create(
                context.catalog_root,
                (
                    CatalogEntry(
                        requirement.model_id,
                        Path(requirement.artifact_path),
                    ),
                ),
            )
            command = catalog.command(requirement.start_command)
            credential = (
                Credential(MATRIX_OMLX_API_KEY)
                if context.credential is None
                else context.credential
            )
            command = command + ("--api-key", credential.api_key())
            process = self._spawner(
                command,
                context.log_dir / f"{requirement.cell_id}.log",
            )
        except Exception as error:
            if catalog is not None:
                try:
                    catalog.cleanup()
                except OmlxCatalogError:
                    pass
            raise RuntimeAdapterError(str(error)) from error
        self._catalogs[process.pid] = catalog
        return RuntimeLease.create(
            requirement,
            ownership=Ownership.OWNED,
            identity=None,
            process=process,
        )

    def release(
        self,
        lease: RuntimeLease,
        context: RuntimeContext,
    ) -> None:
        if lease.process is None:
            raise RuntimeAdapterError(
                "owned oMLX lease has no managed process"
            )
        catalog = self._catalogs.get(lease.process.pid)
        if catalog is None:
            raise RuntimeAdapterError("owned oMLX catalog is missing")
        super().release(lease, context)
        try:
            catalog.cleanup()
        except OmlxCatalogError as error:
            raise RuntimeAdapterError(str(error)) from error
        del self._catalogs[lease.process.pid]
