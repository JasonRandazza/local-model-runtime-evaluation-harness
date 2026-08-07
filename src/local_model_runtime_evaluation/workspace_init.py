"""Scaffold an LMRE workspace from the shipped default trees.

Non-live and non-authorizing. Copies configuration templates and creates empty
result and state directories. It contacts no runtime, adopts no policy,
downloads no model, and writes nothing outside the target directory.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from .workspace import (
    WORKSPACE_MARKER,
    WORKSPACE_TEMPLATE_TREES,
    workspace_template_root,
)

# Created empty so a fresh workspace has somewhere to put evidence and state.
_EMPTY_DIRECTORIES = ("results/runs", ".lmre")

_MARKER_TEXT = (
    "# LMRE workspace marker.\n"
    "# Presence of this file identifies the directory as a workspace root.\n"
    "# The harness resolves config/, suites/, corpora/, results/, and .lmre/\n"
    "# relative to it.\n"
)


class WorkspaceInitError(RuntimeError):
    """The workspace could not be scaffolded."""


def _copy_tree(source: Path, destination: Path) -> int:
    shutil.copytree(
        source,
        destination,
        ignore=shutil.ignore_patterns("__pycache__", ".DS_Store"),
    )
    return sum(1 for path in destination.rglob("*") if path.is_file())


def initialize_workspace(target: Path, *, force: bool = False) -> dict[str, object]:
    """Create a workspace at `target` and report exactly what was written."""
    template_root = workspace_template_root()
    missing = [
        name
        for name in WORKSPACE_TEMPLATE_TREES
        if not (template_root / name).is_dir()
    ]
    if missing:
        raise WorkspaceInitError(
            "workspace template is incomplete: " + ", ".join(sorted(missing))
        )

    target = target.expanduser()
    if target.exists() and not target.is_dir():
        raise WorkspaceInitError(f"target exists and is not a directory: {target}")

    # Refuse to write into a populated directory unless explicitly forced, and
    # never merge over an existing tree: a half-template workspace would read as
    # valid configuration while silently mixing revisions.
    collisions = [
        name for name in WORKSPACE_TEMPLATE_TREES if (target / name).exists()
    ]
    if collisions and not force:
        raise WorkspaceInitError(
            "refusing to overwrite existing "
            + ", ".join(sorted(collisions))
            + f" in {target}; pass --force to replace them"
        )

    target.mkdir(parents=True, exist_ok=True)
    copied: dict[str, int] = {}
    for name in WORKSPACE_TEMPLATE_TREES:
        destination = target / name
        if destination.exists():
            shutil.rmtree(destination)
        copied[name] = _copy_tree(template_root / name, destination)

    for relative in _EMPTY_DIRECTORIES:
        (target / relative).mkdir(parents=True, exist_ok=True)

    (target / WORKSPACE_MARKER).write_text(_MARKER_TEXT, encoding="utf-8")

    return {
        "live_authority": False,
        "ok": True,
        "status": "WORKSPACE_READY",
        "workspace": str(target.resolve()),
        "copied_file_counts": copied,
        "created_directories": list(_EMPTY_DIRECTORIES),
        "next_steps": [
            (
                "Create .lmre/machine-profile.json with this machine's artifact "
                "roots; see docs/managed-runs.md."
            ),
            "Run 'lmre doctor' to check offline readiness.",
            "Review and adopt an operator policy before any live run.",
        ],
    }
