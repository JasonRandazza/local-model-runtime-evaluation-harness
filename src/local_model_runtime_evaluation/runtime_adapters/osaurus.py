"""Fixed Osaurus managed-runtime adapter."""

from __future__ import annotations

from pathlib import Path

from ..matrix_config import Cell
from ..process_inspection import ProcessIdentity
from .base import (
    LoopbackRuntimeAdapter,
    RuntimeAdapterError,
    RuntimeRequirement,
)


OSAURUS_COMMAND = ("osaurus", "serve", "--port", "1337", "--yes")


class OsaurusAdapter(LoopbackRuntimeAdapter):
    runtime = "osaurus"
    port = 1337

    def validate_start_command(self, cell: Cell) -> None:
        if cell.start_command != OSAURUS_COMMAND:
            raise RuntimeAdapterError("Osaurus start command is not fixed")
        if cell.stop_command not in {(), ("osaurus", "stop")}:
            raise RuntimeAdapterError("Osaurus stop command is not fixed")

    def identity_matches(
        self,
        identity: ProcessIdentity,
        requirement: RuntimeRequirement,
    ) -> bool:
        if not super().identity_matches(identity, requirement):
            return False
        identity_text = " ".join(
            (
                Path(identity.executable).name.lower(),
                *(part.lower() for part in identity.argv),
            )
        )
        return "osaurus" in identity_text
