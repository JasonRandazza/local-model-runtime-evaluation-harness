from __future__ import annotations

import re
import os
import signal
import subprocess
from pathlib import Path


STAGE_ONE_RUN_ID = re.compile(r"^stage1-[0-9]{8}-[0-9]{3}$")
STAGE_TWO_RUN_ID = re.compile(r"^stage2-[0-9]{8}-[0-9]{3}$")


class WorkerLauncher:
    """Starts only the fixed harness worker; no shell or user-selected executable."""

    def __init__(self, executable: Path) -> None:
        self.executable = executable

    def command(self, run_id: str) -> list[str]:
        if STAGE_ONE_RUN_ID.fullmatch(run_id):
            worker = "_stage1-worker"
        elif STAGE_TWO_RUN_ID.fullmatch(run_id):
            worker = "_stage2-worker"
        else:
            raise ValueError("invalid worker run ID")
        return [str(self.executable), worker, run_id]

    def launch(self, run_id: str, log_path: Path) -> int:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        handle = log_path.open("ab")
        process = subprocess.Popen(
            self.command(run_id), stdin=subprocess.DEVNULL, stdout=handle, stderr=handle,
            start_new_session=True, close_fds=True,
        )
        handle.close()
        return process.pid

    def matches_process_command(self, command: str, run_id: str) -> bool:
        try:
            expected = " ".join(self.command(run_id))
        except ValueError:
            return False
        return expected in command

    def cancel(self, pid: int, run_id: str) -> None:
        if pid <= 1:
            raise ValueError("invalid worker PID")
        result = subprocess.run(
            ["/bin/ps", "-p", str(pid), "-o", "command="], capture_output=True,
            text=True, check=False, timeout=5,
        )
        if result.returncode != 0 or not self.matches_process_command(result.stdout.strip(), run_id):
            raise ValueError("worker process identity does not match the approved run")
        os.kill(pid, signal.SIGTERM)
