"""Shared harness-owned lifecycle controller for pinned OptiQ, oMLX, and Osaurus."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

ServerKind = Literal["optiq", "omlx", "osaurus"]

DEFAULT_MEMORY_FLOOR_PERCENT = 20

PORT_BY_KIND: dict[ServerKind, int] = {
    "optiq": 8080,
    "omlx": 8100,
    "osaurus": 1337,
}


class HarnessLifecycleError(RuntimeError):
    def __init__(self, message: str, *, code: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class ServerPin:
    kind: ServerKind
    port: int
    start_command: tuple[str, ...]
    stop_command: tuple[str, ...] = ()
    ready_model_id: str = ""

    def __post_init__(self) -> None:
        expected = PORT_BY_KIND[self.kind]
        if self.port != expected:
            raise HarnessLifecycleError(
                f"port {self.port} does not match {self.kind} pin {expected}",
                code="port_mismatch",
            )


class LifecycleController:
    def __init__(self) -> None:
        self.lifecycle_actions = 0
