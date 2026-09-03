"""Runtime version capture for provenance.

Records which runtime build a result was produced against, so a sealed
artifact can say what it ran on. The captured version is **written**, never
**read** by ruling, rubric, comparison, or discovery code. It must never
enter ``input_hashes`` or the plan -- anything that changes the plan hash
makes runs before and after read ``INCOMPARABLE``.

Each runtime is captured by shelling out to its CLI. A runtime that is not
installed, times out, exits non-zero, or prints unparseable output yields an
explicit unavailable record with a reason -- it never raises and never
silently omits the runtime. An absent version is visibly absent.
"""

from __future__ import annotations

import json
import subprocess
from typing import Callable, Protocol

RUNTIME_OSAURUS = "osaurus"
RUNTIME_OMLX = "omlx"
RUNTIME_OPTIQ = "optiq"

ALL_RUNTIMES = (RUNTIME_OSAURUS, RUNTIME_OMLX, RUNTIME_OPTIQ)


class CommandResult(Protocol):
    """Result of running a command."""

    returncode: int
    stdout: str
    stderr: str


CommandRunner = Callable[[list[str]], CommandResult]


class _SubprocessResult:
    """Thin wrapper around subprocess.CompletedProcess."""

    def __init__(self, returncode: int, stdout: str, stderr: str) -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def _subprocess_runner(command: list[str]) -> CommandResult:
    """Default command runner using subprocess."""
    proc = subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=30,
    )
    return _SubprocessResult(proc.returncode, proc.stdout, proc.stderr)


def capture_runtime_versions(
    runner: CommandRunner | None = None,
) -> dict[str, object]:
    """Capture runtime versions for provenance.

    Returns a dict mapping runtime name to a small record. Each record carries
    the raw version string and how it was obtained, or an explicit unavailable
    record with a reason. Never raises and never silently omits a runtime.
    """
    if runner is None:
        runner = _subprocess_runner
    return {
        RUNTIME_OSAURUS: _capture_osaurus(runner),
        RUNTIME_OMLX: _capture_omlx(runner),
        RUNTIME_OPTIQ: _capture_optiq(runner),
    }


def _capture_osaurus(runner: CommandRunner) -> dict[str, object]:
    """Capture osaurus version from `doctor --json --redact`."""
    try:
        result = runner([RUNTIME_OSAURUS, "doctor", "--json", "--redact"])
    except Exception as error:
        return _unavailable(f"command failed: {error}")

    if result.returncode != 0:
        return _unavailable(f"exited with code {result.returncode}")

    try:
        data = json.loads(result.stdout)
    except (json.JSONDecodeError, ValueError) as error:
        return _unavailable(f"unparseable JSON output: {error}")

    apps = data.get("apps")
    if not isinstance(apps, list) or not apps:
        return _unavailable("no apps array in doctor output")

    objects = [entry for entry in apps if isinstance(entry, dict)]
    if not objects:
        return _unavailable("apps entry is not an object")

    # `osaurus doctor` reports every installed bundle precisely because
    # duplicates happen. Naming an arbitrary one would make the provenance
    # confidently wrong, so prefer the bundle actually serving and always
    # record how many were seen.
    running = [entry for entry in objects if entry.get("isRunning") is True]
    app = running[0] if running else objects[0]

    version = app.get("version")
    if not isinstance(version, str) or not version.strip():
        return _unavailable("no version in apps entry")

    return {
        "version": version,
        "method": "osaurus doctor --json --redact",
        "available": True,
        "app_bundles_seen": len(objects),
        "selected_running_bundle": bool(running),
    }


def _capture_omlx(runner: CommandRunner) -> dict[str, object]:
    """Capture omlx version from `omlx --version`."""
    try:
        result = runner([RUNTIME_OMLX, "--version"])
    except Exception as error:
        return _unavailable(f"command failed: {error}")

    if result.returncode != 0:
        return _unavailable(f"exited with code {result.returncode}")

    output = result.stdout.strip()
    if not output:
        return _unavailable("empty output")

    return {
        "version": output,
        "method": "omlx --version",
        "available": True,
    }


def _capture_optiq(runner: CommandRunner) -> dict[str, object]:
    """Capture optiq version from `optiq --version`."""
    try:
        result = runner([RUNTIME_OPTIQ, "--version"])
    except Exception as error:
        return _unavailable(f"command failed: {error}")

    if result.returncode != 0:
        return _unavailable(f"exited with code {result.returncode}")

    output = result.stdout.strip()
    if not output:
        return _unavailable("empty output")

    return {
        "version": output,
        "method": "optiq --version",
        "available": True,
    }


def _unavailable(reason: str) -> dict[str, object]:
    """Create an unavailable record with a reason."""
    return {
        "version": None,
        "method": None,
        "available": False,
        "reason": reason,
    }
