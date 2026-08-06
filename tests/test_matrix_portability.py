from __future__ import annotations

import unittest
from pathlib import Path

from local_model_runtime_evaluation.artifact_profile import load_artifact_roots
from local_model_runtime_evaluation.matrix_config import Campaign, Cell, load_family
from local_model_runtime_evaluation.overhead_config import OverheadPair
from tests.artifact_profile_fixtures import temporary_machine_profile


ROOT = Path(__file__).resolve().parents[1]
CELLS = ROOT / "config" / "matrix" / "cells"
PAIRS = ROOT / "config" / "overhead" / "pairs"


class MatrixPortabilityTests(unittest.TestCase):
    def test_resolves_all_family_artifacts_under_approved_roots(self) -> None:
        expected = {
            "gemma-4-12b-qat": {
                "jang_4m": ("local_models", "gemma-4-12B-it-qat-JANG_4M"),
                "oq4_fp16": (
                    "huggingface_hub",
                    "avneetsb/gemma-4-12B-it-qat-oQ4-fp16",
                ),
                "optiq_4bit": (
                    "huggingface_hub",
                    "mlx-community/gemma-4-12B-it-qat-OptiQ-4bit",
                ),
            },
            "ornith-35b": {
                "ornith_jang_4m": ("local_models", "Ornith-1.0-35B-JANG_4M"),
                "ornith_oq4": (
                    "huggingface_hub",
                    "georgeis55/Ornith-1.0-35B-MLX-oQ4",
                ),
                "ornith_optiq_4bit": (
                    "huggingface_hub",
                    "mlx-community/Ornith-1.0-35B-OptiQ-4bit",
                ),
            },
            "qwen36-35b-a3b": {
                "qwen_jangtq4": ("local_models", "Qwen3.6-35B-A3B-JANGTQ4"),
                "qwen_oq4": (
                    "huggingface_hub",
                    "Jundot/Qwen3.6-35B-A3B-oQ4-mtp",
                ),
                "qwen_optiq_4bit": (
                    "huggingface_hub",
                    "mlx-community/Qwen3.6-35B-A3B-OptiQ-4bit",
                ),
            },
        }
        with temporary_machine_profile() as (profile, paths):
            roots = load_artifact_roots(profile)
            for family_id, quants in expected.items():
                family = load_family(family_id).resolve(roots)
                for quant, (root_key, suffix) in quants.items():
                    with self.subTest(family_id=family_id, quant=quant):
                        self.assertEqual(
                            family.quants[quant].artifact_path,
                            str((paths[root_key] / suffix).resolve()),
                        )

    def test_resolved_optiq_cell_binds_path_to_id_and_fixed_command(self) -> None:
        with temporary_machine_profile() as (profile, paths):
            roots = load_artifact_roots(profile)
            family_template = load_family("gemma-4-12b-qat")
            family = family_template.resolve(roots)
            cell = Cell.load(
                CELLS / "optiq_4bit__optiq.json",
                family=family_template,
            ).resolve(roots)
            cell.validate_for_family(family)

        artifact = str(
            (
                paths["huggingface_hub"]
                / "mlx-community"
                / "gemma-4-12B-it-qat-OptiQ-4bit"
            ).resolve()
        )
        self.assertEqual(cell.artifact_path, artifact)
        self.assertEqual(cell.model_id, f"{artifact}:no-think")
        self.assertEqual(cell.start_command[3], artifact)

    def test_campaign_resolution_returns_resolved_family_and_cells(self) -> None:
        with temporary_machine_profile() as (profile, _):
            roots = load_artifact_roots(profile)
            campaign = Campaign.load(
                ROOT / "config" / "matrix" / "gemma-4-12b-qat-campaign.json"
            ).resolve(roots)

        self.assertEqual(len(campaign.cells), 3)
        self.assertTrue(all(Path(cell.artifact_path).is_absolute() for cell in campaign.cells))
        for cell in campaign.cells:
            cell.validate_for_family(campaign.family)

    def test_overhead_pair_resolves_routed_id_from_backend_artifact(self) -> None:
        pair = OverheadPair.load(PAIRS / "optiq_4bit.json")
        resolved = pair.resolve("/synthetic/hub/mlx-community/model-a")

        self.assertEqual(
            resolved.routed_model_id,
            "optiq//synthetic/hub/mlx-community/model-a:no-think",
        )


if __name__ == "__main__":
    unittest.main()
