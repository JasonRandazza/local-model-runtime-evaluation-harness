from __future__ import annotations

import os
from pathlib import Path


class LockError(RuntimeError):
    pass


class RunLock:
    def __init__(self, output_root: Path) -> None:
        self.path = output_root / ".active-run.lock"

    def owner(self) -> str | None:
        if not self.path.exists():
            return None
        value = self.path.read_text(encoding="utf-8").strip()
        return value or None

    def acquire(self, run_id: str) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            descriptor = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            owner = self.path.read_text(encoding="utf-8").strip()
            if owner == run_id:
                return
            raise LockError(f"another run owns the lock: {owner}")
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(f"{run_id}\n")

    def assert_owner(self, run_id: str) -> None:
        owner = self.owner()
        if owner is None:
            raise LockError("active run lock is missing")
        if owner != run_id:
            raise LockError(f"run {run_id} does not own the lock")

    def release(self, run_id: str) -> None:
        self.assert_owner(run_id)
        self.path.unlink()
