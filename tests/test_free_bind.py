from __future__ import annotations

import ast
import json
import subprocess
import sys
import unittest
from contextlib import redirect_stdout
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from local_model_runtime_evaluation.free_bind import (
    STATUS_ACTION_REQUIRED,
    STATUS_READY,
    STATUS_STALE,
    FreeBindError,
    adopt_binding,
    load_adopted_binding,
    propose_binding,
    show_binding_proposal,
    validate_binding_proposal,
)
from local_model_runtime_evaluation.managed_run_cli import main as managed_main


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "src" / "local_model_runtime_evaluation" / "free_bind.py"
FORBIDDEN_MODULES = {
    "credentials",
    "http",
    "managed_run",
    "matrix_lifecycle",
    "matrix_servers",
    "process_inspection",
    "resources",
    "runtime_adapters",
    "runtime_manager",
    "socket",
    "subprocess",
    "transport",
}


class FreeBindTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.repository = self.root / "repository"
        self.state_dir = self.root / ".lmre"
        self.families = self.repository / "config" / "matrix" / "families"
        self.cells = self.repository / "config" / "matrix" / "cells"
        self.artifacts = self.root / "artifacts"
        for path in (self.families, self.cells, self.artifacts):
            path.mkdir(parents=True)
        self.profile = self.root / "machine-profile.json"
        self.profile.write_text(
            json.dumps(
                {
                    "schema_version": "1.0.0",
                    "artifact_roots": {
                        "huggingface_hub": str(self.artifacts),
                        "local_models": str(self.artifacts),
                    },
                }
            ),
            encoding="utf-8",
        )
        (self.families / "fixture-family.json").write_text(
            json.dumps(
                {
                    "family_id": "fixture-family",
                    "quants": {
                        "alpha": {
                            "native_server": "osaurus",
                            "artifact_path": "{LMRE_ROOT:local_models}/alpha",
                            "model_ids": ["alpha", "{artifact_path}"],
                        },
                        "beta": {
                            "native_server": "omlx",
                            "artifact_path": "{LMRE_ROOT:local_models}/beta",
                            "model_ids": ["beta", "{artifact_path}"],
                        },
                        "gamma": {
                            "native_server": "optiq",
                            "artifact_path": "{LMRE_ROOT:local_models}/gamma",
                            "model_ids": ["gamma", "{artifact_path}"],
                        },
                    },
                }
            ),
            encoding="utf-8",
        )
        self.cell_ids = (
            self._write_cell("alpha", "osaurus"),
            self._write_cell("beta", "omlx"),
            self._write_cell("gamma", "optiq"),
        )
        for quant in ("alpha", "beta", "gamma"):
            (self.artifacts / quant).mkdir()

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _write_cell(self, quant: str, server: str) -> str:
        cell_id = f"{quant}__{server}"
        port = {"osaurus": 1337, "omlx": 8100, "optiq": 8080}[server]
        (self.cells / f"{cell_id}.json").write_text(
            json.dumps(
                {
                    "cell_id": cell_id,
                    "quant": quant,
                    "server": server,
                    "base_url": f"http://127.0.0.1:{port}/v1",
                    "model_id": quant,
                    "artifact_path": f"{{LMRE_ROOT:local_models}}/{quant}",
                    "start_command": ["fixed-runtime-command"],
                    "stop_command": [],
                    "health_path": "/health",
                    "notes": "fixture",
                }
            ),
            encoding="utf-8",
        )
        return cell_id

    def _kwargs(self) -> dict[str, object]:
        return {
            "state_dir": self.state_dir,
            "machine_profile_path": self.profile,
            "repository_root": self.repository,
            "families_root": self.families,
            "cells_root": self.cells,
        }

    def _propose(self) -> dict[str, object]:
        return propose_binding(
            binding_id="fixture-binding-v1",
            revision="1",
            family_id="fixture-family",
            cell_ids=self.cell_ids,
            notes="Reviewed fixture binding.",
            now=datetime(2026, 8, 5, 12, 0, tzinfo=timezone.utc),
            **self._kwargs(),
        )

    def test_proposal_is_immutable_hashed_and_ready(self) -> None:
        result = self._propose()
        self.assertEqual(result["status"], STATUS_READY)
        self.assertTrue(result["ready_for_adoption"])
        self.assertFalse(result["live_authority"])
        self.assertEqual(result["live_status"], "NOT_CHECKED_LIVE")
        self.assertTrue(
            all(item["status"] == "PRESENT" for item in result["artifacts"])
        )
        path = self.state_dir / "bindings" / "proposals" / "fixture-binding-v1.json"
        self.assertTrue(path.is_file())
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)

    def test_show_and_validate_recompute_current_readiness(self) -> None:
        proposed = self._propose()
        shown = show_binding_proposal(
            "fixture-binding-v1",
            **self._kwargs(),
        )
        validated = validate_binding_proposal(
            "fixture-binding-v1",
            **self._kwargs(),
        )
        self.assertEqual(shown["proposal"]["proposal_hash"], proposed["proposal_hash"])
        self.assertIsNone(shown["adoption"])
        self.assertEqual(shown["validation"], validated)

    def test_adoption_requires_ready_proposal_and_grants_no_live_authority(
        self,
    ) -> None:
        self._propose()
        result = adopt_binding(
            "fixture-binding-v1",
            now=datetime(2026, 8, 5, 12, 1, tzinfo=timezone.utc),
            **self._kwargs(),
        )
        self.assertEqual(result["status"], "ADOPTED_OFFLINE")
        self.assertFalse(result["live_authority"])
        record = load_adopted_binding(
            "fixture-binding-v1",
            state_dir=self.state_dir,
        )
        self.assertEqual(record["binding_hash"], result["binding_hash"])
        self.assertFalse(record["live_authority"])
        shown = show_binding_proposal(
            "fixture-binding-v1",
            **self._kwargs(),
        )
        self.assertEqual(shown["adoption"], record)

    def test_missing_artifact_is_action_required_and_blocks_adoption(self) -> None:
        (self.artifacts / "gamma").rmdir()
        result = self._propose()
        self.assertEqual(result["status"], STATUS_ACTION_REQUIRED)
        self.assertFalse(result["ready_for_adoption"])
        with self.assertRaises(FreeBindError) as context:
            adopt_binding("fixture-binding-v1", **self._kwargs())
        self.assertEqual(context.exception.code, "free_bind_not_ready")

    def test_changed_checked_in_cell_makes_proposal_stale(self) -> None:
        self._propose()
        path = self.cells / f"{self.cell_ids[0]}.json"
        body = json.loads(path.read_text(encoding="utf-8"))
        body["notes"] = "changed after proposal"
        path.write_text(json.dumps(body), encoding="utf-8")
        result = validate_binding_proposal(
            "fixture-binding-v1",
            **self._kwargs(),
        )
        self.assertEqual(result["status"], STATUS_STALE)
        self.assertFalse(result["inputs_match"])

    def test_tampered_proposal_hash_fails_closed(self) -> None:
        self._propose()
        path = self.state_dir / "bindings" / "proposals" / "fixture-binding-v1.json"
        body = json.loads(path.read_text(encoding="utf-8"))
        body["notes"] = "tampered"
        path.write_text(json.dumps(body), encoding="utf-8")
        with self.assertRaises(FreeBindError) as context:
            validate_binding_proposal("fixture-binding-v1", **self._kwargs())
        self.assertEqual(context.exception.code, "free_bind_hash_mismatch")

    def test_proposal_never_overwrites_existing_record(self) -> None:
        self._propose()
        with self.assertRaises(FreeBindError) as context:
            self._propose()
        self.assertEqual(context.exception.code, "free_bind_exists")

    def test_duplicate_or_path_shaped_cells_fail_closed(self) -> None:
        with self.assertRaises(FreeBindError):
            propose_binding(
                binding_id="fixture-binding-v1",
                revision="1",
                family_id="fixture-family",
                cell_ids=(self.cell_ids[0], self.cell_ids[0]),
                notes="",
                **self._kwargs(),
            )
        with self.assertRaises(FreeBindError):
            propose_binding(
                binding_id="fixture-binding-v1",
                revision="1",
                family_id="fixture-family",
                cell_ids=("../alpha__osaurus", self.cell_ids[1]),
                notes="",
                **self._kwargs(),
            )

    def test_non_native_cell_is_rejected(self) -> None:
        path = self.cells / "alpha__omlx.json"
        source = json.loads(
            (self.cells / "alpha__osaurus.json").read_text(encoding="utf-8")
        )
        source.update(
            {
                "cell_id": "alpha__omlx",
                "server": "omlx",
                "base_url": "http://127.0.0.1:8100/v1",
            }
        )
        path.write_text(json.dumps(source), encoding="utf-8")
        with self.assertRaises(FreeBindError):
            propose_binding(
                binding_id="fixture-binding-v1",
                revision="1",
                family_id="fixture-family",
                cell_ids=("alpha__omlx", self.cell_ids[1]),
                notes="",
                **self._kwargs(),
            )

    def test_static_imports_exclude_live_modules(self) -> None:
        tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
        found: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                found.update(
                    alias.name.split(".")[0]
                    for alias in node.names
                    if alias.name.split(".")[0] in FORBIDDEN_MODULES
                )
            elif isinstance(node, ast.ImportFrom) and node.module:
                found.update(
                    part for part in node.module.split(".") if part in FORBIDDEN_MODULES
                )
        self.assertEqual(found, set())

    def test_fresh_import_does_not_pull_live_modules(self) -> None:
        script = (
            "import sys\n"
            "import local_model_runtime_evaluation.free_bind\n"
            f"forbidden = {FORBIDDEN_MODULES!r}\n"
            "loaded = {name.split('.')[0] for name in sys.modules}\n"
            "unexpected = sorted(forbidden & loaded)\n"
            "raise SystemExit(','.join(unexpected) if unexpected else 0)\n"
        )
        result = subprocess.run(
            [sys.executable, "-c", script],
            cwd=ROOT,
            env={"PYTHONPATH": str(ROOT / "src")},
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_cli_propose_validate_show_and_adopt_are_non_live(self) -> None:
        argv_base = ["--state-dir", str(self.state_dir)]
        proposal_args = argv_base + [
            "binding",
            "propose",
            "--id",
            "gemma-cli-binding-v1",
            "--family",
            "gemma-4-12b-qat",
            "--cell",
            "jang_4m__osaurus",
            "--cell",
            "oq4_fp16__omlx",
        ]
        # Create the two repository-configured artifacts beneath the fake roots.
        (self.artifacts / "gemma-4-12B-it-qat-JANG_4M").mkdir()
        (self.artifacts / "avneetsb" / "gemma-4-12B-it-qat-oQ4-fp16").mkdir(
            parents=True
        )
        with patch(
            "local_model_runtime_evaluation.managed_run_cli.execute_managed_run",
            side_effect=AssertionError("binding commands must not execute"),
        ):
            outputs = []
            for args in (
                proposal_args,
                argv_base + ["binding", "validate", "gemma-cli-binding-v1"],
                argv_base + ["binding", "show", "gemma-cli-binding-v1"],
                argv_base + ["binding", "adopt", "gemma-cli-binding-v1"],
            ):
                stream = StringIO()
                with redirect_stdout(stream):
                    code = managed_main(args, machine_profile_path=self.profile)
                self.assertEqual(code, 0, stream.getvalue())
                outputs.append(json.loads(stream.getvalue()))
        self.assertEqual(outputs[0]["binding"]["status"], STATUS_READY)
        self.assertEqual(outputs[-1]["binding"]["status"], "ADOPTED_OFFLINE")
        self.assertFalse(outputs[-1]["binding"]["live_authority"])


if __name__ == "__main__":
    unittest.main()
