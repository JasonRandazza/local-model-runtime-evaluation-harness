"""Durable harness service_lifecycle_actions across CLI processes."""

from __future__ import annotations

import json
from pathlib import Path


class ServiceLifecycleLedger:
    def __init__(self, path: Path) -> None:
        self.path = path

    def read(self) -> int:
        if not self.path.is_file():
            return 0
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return 0
        if not isinstance(payload, dict):
            return 0
        value = payload.get("service_lifecycle_actions")
        return value if isinstance(value, int) and value >= 0 else 0

    def add(self, delta: int) -> int:
        if delta < 0:
            raise ValueError("lifecycle action delta must be non-negative")
        if delta == 0:
            return self.read()
        total = self.read() + delta
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_text(
            json.dumps({"service_lifecycle_actions": total}, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        temporary.replace(self.path)
        return total
