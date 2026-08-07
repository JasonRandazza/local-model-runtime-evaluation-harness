"""Workspace scaffolding.

Non-live: temporary directories and file copies only. No runtime, provider,
credential, policy, or model is touched.
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

from local_model_runtime_evaluation import workspace_init
from local_model_runtime_evaluation.workspace import (
    WORKSPACE_MARKER,
    WORKSPACE_TEMPLATE_TREES,
    is_workspace,
)
from local_model_runtime_evaluation.workspace_init import (
    WorkspaceInitError,
    initialize_workspace,
)


def _fake_template(root: Path) -> Path:
    """A minimal stand-in for the shipped template trees."""
    for name in WORKSPACE_TEMPLATE_TREES:
        tree = root / name
        (tree / "nested").mkdir(parents=True)
        (tree / f"{name}.json").write_text(json.dumps({"name": name}), encoding="utf-8")
        (tree / "nested" / "deep.json").write_text("{}", encoding="utf-8")
    return root


class InitializeWorkspaceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.template = _fake_template(self.root / "template")
        patcher = mock.patch.object(
            workspace_init, "workspace_template_root", return_value=self.template
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_creates_a_resolvable_workspace(self) -> None:
        target = self.root / "ws"
        result = initialize_workspace(target)
        self.assertEqual(result["status"], "WORKSPACE_READY")
        self.assertIs(result["live_authority"], False)
        self.assertTrue(is_workspace(target))
        self.assertTrue((target / WORKSPACE_MARKER).is_file())

    def test_copies_every_template_tree_including_nested_files(self) -> None:
        target = self.root / "ws"
        result = initialize_workspace(target)
        for name in WORKSPACE_TEMPLATE_TREES:
            self.assertTrue((target / name / f"{name}.json").is_file(), name)
            self.assertTrue((target / name / "nested" / "deep.json").is_file(), name)
            self.assertEqual(result["copied_file_counts"][name], 2)

    def test_creates_empty_result_and_state_directories(self) -> None:
        target = self.root / "ws"
        initialize_workspace(target)
        self.assertTrue((target / "results" / "runs").is_dir())
        self.assertTrue((target / ".lmre").is_dir())

    def test_reports_next_steps_without_claiming_authority(self) -> None:
        result = initialize_workspace(self.root / "ws")
        joined = " ".join(result["next_steps"]).lower()
        self.assertIn("machine-profile", joined)
        self.assertIn("doctor", joined)
        # Scaffolding must not imply a policy was adopted for the operator.
        self.assertIn("adopt", joined)

    def test_existing_tree_is_refused_without_force(self) -> None:
        target = self.root / "ws"
        initialize_workspace(target)
        marker = target / "config" / "operator-edit.json"
        marker.write_text("{}", encoding="utf-8")
        with self.assertRaises(WorkspaceInitError) as context:
            initialize_workspace(target)
        self.assertIn("--force", str(context.exception))
        # The operator's own file survives a refused run.
        self.assertTrue(marker.is_file())

    def test_force_replaces_the_tree_without_merging(self) -> None:
        # Merging would leave a workspace mixing template revisions while still
        # reading as valid configuration.
        target = self.root / "ws"
        initialize_workspace(target)
        stale = target / "config" / "stale.json"
        stale.write_text("{}", encoding="utf-8")
        initialize_workspace(target, force=True)
        self.assertFalse(stale.exists())
        self.assertTrue((target / "config" / "config.json").is_file())

    def test_target_that_is_a_file_is_refused(self) -> None:
        target = self.root / "afile"
        target.write_text("", encoding="utf-8")
        with self.assertRaises(WorkspaceInitError):
            initialize_workspace(target)

    def test_incomplete_template_is_refused(self) -> None:
        empty = self.root / "empty-template"
        empty.mkdir()
        with mock.patch.object(
            workspace_init, "workspace_template_root", return_value=empty
        ), self.assertRaises(WorkspaceInitError) as context:
            initialize_workspace(self.root / "ws")
        self.assertIn("incomplete", str(context.exception))

    def test_writes_nothing_outside_the_target(self) -> None:
        # Directories leading to the target are legitimately created; nothing
        # else outside it may be written.
        target = self.root / "outer" / "inner" / "ws"
        allowed_ancestors = set(target.parents)

        def snapshot() -> set[Path]:
            return {
                path
                for path in self.root.rglob("*")
                if self.template not in path.parents and path != self.template
            }

        before = snapshot()
        initialize_workspace(target)
        for path in snapshot() - before:
            self.assertTrue(
                path == target or target in path.parents or path in allowed_ancestors,
                f"wrote outside the target: {path}",
            )


class InitCommandTests(unittest.TestCase):
    def test_parser_defaults_to_current_directory(self) -> None:
        from local_model_runtime_evaluation.managed_run_cli import build_parser

        args = build_parser().parse_args(["init"])
        self.assertEqual(args.command, "init")
        self.assertEqual(args.target, Path("."))
        self.assertFalse(args.force)

    def test_parser_accepts_target_and_force(self) -> None:
        from local_model_runtime_evaluation.managed_run_cli import build_parser

        args = build_parser().parse_args(["init", "/tmp/ws", "--force"])
        self.assertEqual(args.target, Path("/tmp/ws"))
        self.assertTrue(args.force)

    def test_parser_rejects_unknown_options(self) -> None:
        from local_model_runtime_evaluation.managed_run_cli import build_parser

        with self.assertRaises(SystemExit):
            build_parser().parse_args(["init", "--download-models"])


class ShippedTemplateTests(unittest.TestCase):
    def test_checkout_falls_back_to_repository_trees(self) -> None:
        # In a source checkout the packaged template is absent; init must still
        # work from the canonical trees rather than duplicating them into the
        # package to satisfy the installed layout.
        from local_model_runtime_evaluation.workspace import workspace_template_root

        root = workspace_template_root()
        for name in WORKSPACE_TEMPLATE_TREES:
            self.assertTrue((root / name).is_dir(), f"{name} missing under {root}")


if __name__ == "__main__":
    unittest.main()
