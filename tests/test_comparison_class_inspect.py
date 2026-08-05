from __future__ import annotations

import ast
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from local_model_runtime_evaluation.comparison_class import ComparisonClassError
from local_model_runtime_evaluation.comparison_class_inspect import (
    LIVE_STATUS_NOT_CHECKED,
    STATUS_ACTION_REQUIRED,
    STATUS_BASELINE_ONLY,
    STATUS_DECLARED_EXPANSION_READY,
    STATUS_REVIEWED_CANDIDATES_AVAILABLE,
    inspect_comparison_class,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
INSPECT_SOURCE = (
    REPOSITORY_ROOT
    / "src"
    / "local_model_runtime_evaluation"
    / "comparison_class_inspect.py"
)
FORBIDDEN_MODULES = {
    "credentials",
    "http",
    "managed_run",
    "managed_run_cli",
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


class ComparisonClassInspectTests(unittest.TestCase):
    def _fixture(
        self,
        root: Path,
        *,
        selected_extra: bool,
        create_extra_artifact: bool = True,
    ) -> tuple[Path, Path]:
        config = root / "config"
        families = config / "matrix" / "families"
        cells = config / "matrix" / "cells"
        classes = config / "comparison-classes"
        suites = root / "suites"
        artifacts = root / "artifacts"
        for directory in (families, cells, classes, suites, artifacts):
            directory.mkdir(parents=True)

        quants = {
            "base_osaurus": "osaurus",
            "base_omlx": "omlx",
            "base_optiq": "optiq",
            "extra_osaurus": "osaurus",
        }
        (families / "fixture-family.json").write_text(
            json.dumps(
                {
                    "family_id": "fixture-family",
                    "quants": {
                        quant: {
                            "native_server": server,
                            "artifact_path": f"{{LMRE_ROOT:local_models}}/{quant}",
                            "model_ids": [quant, "{artifact_path}"],
                            **(
                                {"role": "osaurus_native"}
                                if server == "osaurus"
                                else {}
                            ),
                        }
                        for quant, server in quants.items()
                    },
                }
            ),
            encoding="utf-8",
        )

        def write_cell(quant: str, server: str) -> str:
            cell_id = f"{quant}__{server}"
            port = {"osaurus": 1337, "omlx": 8100, "optiq": 8080}[server]
            (cells / f"{cell_id}.json").write_text(
                json.dumps(
                    {
                        "cell_id": cell_id,
                        "quant": quant,
                        "server": server,
                        "base_url": f"http://127.0.0.1:{port}/v1",
                        "model_id": quant,
                        "artifact_path": f"{{LMRE_ROOT:local_models}}/{quant}",
                        "start_command": ["fixture-server"],
                        "stop_command": [],
                        "health_path": "/models",
                        "notes": "fixture",
                    }
                ),
                encoding="utf-8",
            )
            return cell_id

        baseline = [
            write_cell("base_osaurus", "osaurus"),
            write_cell("base_omlx", "omlx"),
            write_cell("base_optiq", "optiq"),
        ]
        extra = write_cell("extra_osaurus", "osaurus")
        (config / "matrix" / "fixture-family-campaign.json").write_text(
            json.dumps(
                {
                    "campaign_id": "fixture-native",
                    "family_id": "fixture-family",
                    "suite_path": "suites/fixture.json",
                    "results_root": "results/matrix",
                    "memory_floor_percent": 20,
                    "ready_timeout_seconds": 180,
                    "request_timeout_seconds": 120,
                    "on_cell_failure": "continue",
                    "ports": {"osaurus": 1337, "omlx": 8100, "optiq": 8080},
                    "cells": [
                        f"config/matrix/cells/{cell_id}.json"
                        for cell_id in baseline
                    ],
                }
            ),
            encoding="utf-8",
        )
        (suites / "fixture.json").write_text("{}", encoding="utf-8")
        (classes / "fixture-class-v1.json").write_text(
            json.dumps(
                {
                    "schema_version": "1.0.0",
                    "comparison_class_id": "fixture-class-v1",
                    "revision": "1",
                    "family_id": "fixture-family",
                    "baseline_campaign_path": (
                        "config/matrix/fixture-family-campaign.json"
                    ),
                    "extra_cell_ids": [extra] if selected_extra else [],
                    "estimated_minutes": 180,
                    "notes": "fixture",
                }
            ),
            encoding="utf-8",
        )
        for quant in quants:
            if quant != "extra_osaurus" or create_extra_artifact:
                (artifacts / quant).mkdir()
        profile = root / "machine-profile.json"
        profile.write_text(
            json.dumps(
                {
                    "schema_version": "1.0.0",
                    "artifact_roots": {
                        "huggingface_hub": str(artifacts),
                        "local_models": str(artifacts),
                    },
                }
            ),
            encoding="utf-8",
        )
        return profile, classes

    def _inspect(
        self,
        root: Path,
        profile: Path,
        classes: Path,
    ) -> dict:
        return inspect_comparison_class(
            "fixture-class-v1",
            machine_profile_path=profile,
            comparison_classes_root=classes,
            repository_root=root,
            families_root=root / "config" / "matrix" / "families",
            cells_root=root / "config" / "matrix" / "cells",
        )

    def test_baseline_class_reports_reviewed_candidate(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            profile, classes = self._fixture(root, selected_extra=False)
            result = self._inspect(root, profile, classes)
        self.assertEqual(result["status"], STATUS_REVIEWED_CANDIDATES_AVAILABLE)
        self.assertEqual(result["class_shape"], STATUS_BASELINE_ONLY)
        self.assertEqual(
            result["reviewed_candidates"][0]["cell_id"],
            "extra_osaurus__osaurus",
        )
        self.assertEqual(result["live_status"], LIVE_STATUS_NOT_CHECKED)

    def test_declared_expansion_is_offline_ready(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            profile, classes = self._fixture(root, selected_extra=True)
            result = self._inspect(root, profile, classes)
        self.assertEqual(result["status"], STATUS_DECLARED_EXPANSION_READY)
        self.assertTrue(result["ready_for_expansion_plan"])
        self.assertEqual(result["extra_cell_ids"], ["extra_osaurus__osaurus"])
        self.assertTrue(
            all(
                item["status"] == "PRESENT"
                for item in result["selected_artifacts"]
            )
        )

    def test_missing_selected_artifact_requires_action(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            profile, classes = self._fixture(
                root,
                selected_extra=True,
                create_extra_artifact=False,
            )
            result = self._inspect(root, profile, classes)
        self.assertEqual(result["status"], STATUS_ACTION_REQUIRED)
        self.assertFalse(result["ready_for_expansion_plan"])
        extra = next(
            item for item in result["selected_artifacts"]
            if item["role"] == "extra"
        )
        self.assertEqual(extra["status"], "MISSING")

    def test_static_imports_exclude_live_modules(self) -> None:
        tree = ast.parse(INSPECT_SOURCE.read_text(encoding="utf-8"))
        found: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.split(".")[0] in FORBIDDEN_MODULES:
                        found.add(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom) and node.module:
                for part in node.module.split("."):
                    if part in FORBIDDEN_MODULES:
                        found.add(part)
        self.assertEqual(found, set())

    def test_fresh_import_does_not_pull_live_modules(self) -> None:
        script = (
            "import sys\n"
            "import local_model_runtime_evaluation.comparison_class_inspect\n"
            "forbidden = " + repr(sorted(FORBIDDEN_MODULES)) + "\n"
            "hits = sorted(\n"
            "    name for name in sys.modules\n"
            "    if any(name == 'local_model_runtime_evaluation.' + item "
            "for item in forbidden)\n"
            ")\n"
            "print(hits)\n"
        )
        env = dict(os.environ)
        env["PYTHONPATH"] = str(REPOSITORY_ROOT / "src")
        completed = subprocess.run(
            [sys.executable, "-c", script],
            cwd=str(REPOSITORY_ROOT),
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(completed.stdout.strip(), "[]")

    def test_path_shaped_class_id_is_rejected_before_file_access(self) -> None:
        with self.assertRaises(ComparisonClassError):
            inspect_comparison_class("../outside")


if __name__ == "__main__":
    unittest.main()
