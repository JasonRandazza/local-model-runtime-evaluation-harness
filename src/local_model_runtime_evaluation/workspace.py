"""Resolve the LMRE workspace root.

A workspace holds the operator-owned trees the harness reads and writes:
`config/`, `suites/`, `corpora/`, `results/`, and `.lmre/`. A repository
checkout is itself a workspace, which is why resolution falls back to the
package's own parent: an installed copy has no such tree, and a checkout must
keep resolving exactly as it did before this module existed.

Resolution order, first match wins:

1. `LMRE_WORKSPACE`, when set. Set but not a directory is a hard error --
   silently substituting a different root would let a run record evidence
   against configuration the operator did not choose.
2. The nearest ancestor of the current directory that looks like a workspace,
   meaning it holds a `.lmre-workspace` marker or a `config/managed-runs/`
   tree.
3. The directory two levels above this package, which is the repository root
   in a source checkout.

Resolution happens once per process. These are one-shot CLIs, so the invoking
directory is the right input and caching keeps every module's derived path
constants agreeing with each other.
"""

from __future__ import annotations

import os
from functools import cache
from pathlib import Path

LMRE_WORKSPACE_ENV = "LMRE_WORKSPACE"
WORKSPACE_MARKER = ".lmre-workspace"
_RECIPES_RELATIVE = Path("config") / "managed-runs"

_PACKAGE_PARENT = Path(__file__).resolve().parents[2]


class WorkspaceError(RuntimeError):
    """The requested workspace root cannot be used."""


def is_workspace(path: Path) -> bool:
    """Does `path` look like an LMRE workspace root?"""
    return (path / WORKSPACE_MARKER).is_file() or (path / _RECIPES_RELATIVE).is_dir()


def _from_environment() -> Path | None:
    raw = os.environ.get(LMRE_WORKSPACE_ENV)
    if not raw:
        return None
    candidate = Path(raw).expanduser()
    if not candidate.is_dir():
        raise WorkspaceError(
            f"{LMRE_WORKSPACE_ENV} is not a directory: {raw}"
        )
    return candidate.resolve()


def _from_current_directory() -> Path | None:
    try:
        start = Path.cwd().resolve()
    except OSError:
        return None
    for candidate in (start, *start.parents):
        if is_workspace(candidate):
            return candidate
    return None


@cache
def workspace_root() -> Path:
    """The resolved workspace root for this process."""
    return _from_environment() or _from_current_directory() or _PACKAGE_PARENT


def reset_workspace_root_cache() -> None:
    """Forget the resolved root. For tests that relocate the workspace."""
    workspace_root.cache_clear()


def is_source_checkout(root: Path | None = None) -> bool:
    """Is the running package the one inside `root` as a source checkout?

    True when the imported package lives under the workspace being used, which
    is the case for a repository checkout and for an editable install of it.
    False for an ordinary installed copy, whose package sits in site-packages.
    Callers use this to avoid demanding checkout-only files -- `bin/` wrappers
    and `docs/` -- from an installed operator who correctly does not have them.
    """
    resolved = workspace_root() if root is None else root.resolve()
    return _PACKAGE_PARENT == resolved


# Default operator trees shipped inside the wheel, copied out by `lmre init`.
# Absent in a source checkout, where the canonical trees are at the root.
WORKSPACE_TEMPLATE_DIR = Path(__file__).resolve().parent / "_workspace_template"
WORKSPACE_TEMPLATE_TREES = ("config", "suites", "corpora")


def workspace_template_root() -> Path:
    """Where `lmre init` reads its default trees from.

    Prefers the template shipped in the wheel; falls back to the checkout root,
    so `lmre init` works from a source tree without duplicating these files
    into the package just to satisfy the installed layout.
    """
    if WORKSPACE_TEMPLATE_DIR.is_dir():
        return WORKSPACE_TEMPLATE_DIR
    return _PACKAGE_PARENT
