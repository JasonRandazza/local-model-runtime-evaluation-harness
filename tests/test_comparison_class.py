from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from local_model_runtime_evaluation.comparison_class import (
    ComparisonClass,
    ComparisonClassError,
    load_comparison_class,
)


class ComparisonClassTests(unittest.TestCase):
    def test_checked_in_native_baseline_loads(self) -> None:
        definition = load_comparison_class("gemma-native-baseline-v1")
        self.assertEqual(definition.family_id, "gemma-4-12b-qat")
        self.assertEqual(definition.extra_cell_ids, ())
        self.assertEqual(definition.cell_ids, definition.baseline_cell_ids)

    def _write_fixture(self, root: Path, *, extra_cell_id: str) -> Path:
        families = root / "config" / "matrix" / "families"
        cells = root / "config" / "matrix" / "cells"
        families.mkdir(parents=True)
        cells.mkdir(parents=True)
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
                            "artifact_path": f"/tmp/{quant}",
                            "model_ids": [quant],
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
                        "artifact_path": f"/tmp/{quant}",
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
        write_cell("extra_osaurus", "osaurus")
        campaign = root / "config" / "matrix" / "fixture-family-campaign.json"
        campaign.write_text(
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
        class_path = root / "fixture-class-v1.json"
        class_path.write_text(
            json.dumps(
                {
                    "schema_version": "1.0.0",
                    "comparison_class_id": "fixture-class-v1",
                    "revision": "1",
                    "family_id": "fixture-family",
                    "baseline_campaign_path": (
                        "config/matrix/fixture-family-campaign.json"
                    ),
                    "extra_cell_ids": [extra_cell_id],
                    "estimated_minutes": 180,
                    "notes": "fixture",
                }
            ),
            encoding="utf-8",
        )
        return class_path

    def test_extra_native_cell_is_appended_after_baseline(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = self._write_fixture(
                root,
                extra_cell_id="extra_osaurus__osaurus",
            )
            definition = ComparisonClass.load(
                path,
                repository_root=root,
                families_root=root / "config" / "matrix" / "families",
                cells_root=root / "config" / "matrix" / "cells",
            )
        self.assertEqual(len(definition.baseline_cell_ids), 3)
        self.assertEqual(definition.cell_ids[-1], "extra_osaurus__osaurus")
        self.assertEqual(len(definition.materialize_campaign().cells), 4)

    def test_baseline_cell_cannot_be_redeclared_as_extra(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = self._write_fixture(
                root,
                extra_cell_id="base_osaurus__osaurus",
            )
            with self.assertRaises(ComparisonClassError):
                ComparisonClass.load(
                    path,
                    repository_root=root,
                    families_root=root / "config" / "matrix" / "families",
                    cells_root=root / "config" / "matrix" / "cells",
                )

    def test_path_shaped_extra_cell_id_is_rejected(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = self._write_fixture(
                root,
                extra_cell_id="../extra_osaurus__osaurus",
            )
            with self.assertRaises(ComparisonClassError):
                ComparisonClass.load(
                    path,
                    repository_root=root,
                    families_root=root / "config" / "matrix" / "families",
                    cells_root=root / "config" / "matrix" / "cells",
                )

    def test_symlinked_baseline_campaign_is_rejected(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = self._write_fixture(
                root,
                extra_cell_id="extra_osaurus__osaurus",
            )
            campaign = root / "config" / "matrix" / "fixture-family-campaign.json"
            target = root / "fixture-family-campaign-target.json"
            campaign.rename(target)
            campaign.symlink_to(target)
            with self.assertRaises(ComparisonClassError):
                ComparisonClass.load(
                    path,
                    repository_root=root,
                    families_root=root / "config" / "matrix" / "families",
                    cells_root=root / "config" / "matrix" / "cells",
                )


if __name__ == "__main__":
    unittest.main()
