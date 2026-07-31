"""Fixed OptiQ managed-runtime adapter."""

from __future__ import annotations

from pathlib import Path

from ..matrix_config import Cell
from ..process_inspection import ProcessIdentity
from .base import (
    LoopbackRuntimeAdapter,
    RuntimeAdapterError,
    RuntimeRequirement,
)


class OptiqAdapter(LoopbackRuntimeAdapter):
    runtime = "optiq"
    port = 8080

    def validate_start_command(self, cell: Cell) -> None:
        expected = (
            "optiq",
            "serve",
            "--model",
            cell.artifact_path,
            "--host",
            "127.0.0.1",
            "--port",
            "8080",
            "--no-anthropic",
            "--no-responses",
            "--no-auth",
        )
        if cell.start_command != expected:
            raise RuntimeAdapterError("OptiQ start command is not fixed")
        if cell.stop_command:
            raise RuntimeAdapterError("OptiQ stop command must be empty")

    def identity_matches(
        self,
        identity: ProcessIdentity,
        requirement: RuntimeRequirement,
    ) -> bool:
        if not super().identity_matches(identity, requirement):
            return False
        argv = identity.argv
        identity_text = " ".join(
            (Path(identity.executable).name.lower(), *(
                part.lower() for part in argv
            ))
        )
        try:
            return (
                "optiq" in identity_text
                and "serve" in argv
                and argv[argv.index("--model") + 1]
                == requirement.artifact_path
                and argv[argv.index("--host") + 1] == "127.0.0.1"
                and argv[argv.index("--port") + 1] == "8080"
            )
        except (ValueError, IndexError):
            return False
