"""Workspace root resolution.

Non-live: temporary directories and environment reads only.
"""

from __future__ import annotations

import os
import unittest
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

from local_model_runtime_evaluation.workspace import (
    LMRE_WORKSPACE_ENV,
    WORKSPACE_MARKER,
    WorkspaceError,
    is_workspace,
    reset_workspace_root_cache,
    workspace_root,
)


@contextmanager
def _resolution_context(cwd: Path, **environment: str):
    """Resolve with a known cwd and environment, leaving no cached state."""
    reset_workspace_root_cache()
    original = Path.cwd()
    try:
        os.chdir(cwd)
        with mock.patch.dict(os.environ, environment, clear=False):
            if LMRE_WORKSPACE_ENV not in environment:
                os.environ.pop(LMRE_WORKSPACE_ENV, None)
            yield
    finally:
        os.chdir(original)
        reset_workspace_root_cache()


def _make_workspace(root: Path, *, marker: bool = True) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    if marker:
        (root / WORKSPACE_MARKER).write_text("", encoding="utf-8")
    else:
        (root / "config" / "managed-runs").mkdir(parents=True)
    return root


class IsWorkspaceTests(unittest.TestCase):
    def test_marker_file_identifies_a_workspace(self) -> None:
        with TemporaryDirectory() as tmp:
            self.assertTrue(is_workspace(_make_workspace(Path(tmp) / "ws")))

    def test_recipe_tree_identifies_a_checkout(self) -> None:
        with TemporaryDirectory() as tmp:
            root = _make_workspace(Path(tmp) / "ws", marker=False)
            self.assertTrue(is_workspace(root))

    def test_unrelated_directory_is_not_a_workspace(self) -> None:
        with TemporaryDirectory() as tmp:
            self.assertFalse(is_workspace(Path(tmp)))


class ResolutionOrderTests(unittest.TestCase):
    def test_environment_wins_over_current_directory(self) -> None:
        with TemporaryDirectory() as tmp:
            chosen = _make_workspace(Path(tmp) / "chosen")
            ignored = _make_workspace(Path(tmp) / "ignored")
            with _resolution_context(ignored, **{LMRE_WORKSPACE_ENV: str(chosen)}):
                self.assertEqual(workspace_root(), chosen.resolve())

    def test_nearest_ancestor_is_chosen(self) -> None:
        with TemporaryDirectory() as tmp:
            outer = _make_workspace(Path(tmp) / "outer")
            inner = _make_workspace(outer / "nested" / "inner")
            deep = inner / "a" / "b"
            deep.mkdir(parents=True)
            with _resolution_context(deep):
                self.assertEqual(workspace_root(), inner.resolve())

    def test_falls_back_to_package_parent_outside_any_workspace(self) -> None:
        # The fallback is what keeps a source checkout resolving as before,
        # and what keeps an installed copy importable rather than crashing.
        with TemporaryDirectory() as tmp, _resolution_context(Path(tmp)):
            expected = Path(__file__).resolve().parents[1]
            self.assertEqual(workspace_root(), expected)

    def test_absent_configuration_never_raises(self) -> None:
        # The import-purity allowlist depends on this property.
        with TemporaryDirectory() as tmp, _resolution_context(Path(tmp)):
            self.assertTrue(workspace_root().is_absolute())


class MisconfigurationTests(unittest.TestCase):
    def test_environment_pointing_at_a_non_directory_is_a_hard_error(self) -> None:
        # Failing loudly matters: silently substituting another root would let a
        # run record evidence against configuration the operator did not choose.
        with TemporaryDirectory() as tmp:
            missing = Path(tmp) / "not-there"
            with _resolution_context(
                Path(tmp), **{LMRE_WORKSPACE_ENV: str(missing)}
            ), self.assertRaises(WorkspaceError):
                workspace_root()

    def test_environment_pointing_at_a_file_is_a_hard_error(self) -> None:
        with TemporaryDirectory() as tmp:
            not_a_dir = Path(tmp) / "file.txt"
            not_a_dir.write_text("", encoding="utf-8")
            with _resolution_context(
                Path(tmp), **{LMRE_WORKSPACE_ENV: str(not_a_dir)}
            ), self.assertRaises(WorkspaceError):
                workspace_root()


class CachingTests(unittest.TestCase):
    def test_resolution_is_stable_within_a_process(self) -> None:
        with TemporaryDirectory() as tmp:
            first = _make_workspace(Path(tmp) / "first")
            second = _make_workspace(Path(tmp) / "second")
            with _resolution_context(first):
                resolved = workspace_root()
                os.chdir(second)
                self.assertEqual(
                    workspace_root(),
                    resolved,
                    "derived path constants would disagree if this drifted",
                )


if __name__ == "__main__":
    unittest.main()
