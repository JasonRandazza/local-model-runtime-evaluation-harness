from __future__ import annotations

import unittest
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from local_model_runtime_evaluation.artifact_profile import load_artifact_roots
from local_model_runtime_evaluation.lineup import (
    KIND_BASELINE,
    KIND_BINDING,
    KIND_COMPARISON_CLASS,
    KIND_OPEN_MIX,
    lineup_kind,
    resolve_lineup,
)
from local_model_runtime_evaluation.run_identity import build_plan
from tests.artifact_profile_fixtures import write_machine_profile


ROOT = Path(__file__).resolve().parents[1]
RECIPE = ROOT / "config/managed-runs/complete-native-quality-v1.json"
FIXED = datetime(2026, 1, 1, tzinfo=timezone.utc)


class LineupTestCase(unittest.TestCase):
    """Every lineup test builds its own machine profile.

    The repo's real profile lives at a gitignored path, so a test that reads
    it passes only on the machine that happens to have one.
    """

    def setUp(self) -> None:
        tmp = TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.profile = write_machine_profile(self.root / "machine")
        self.roots = load_artifact_roots(self.profile)
        self.stage_open_mix_weights()

    def plan(self, **extra):
        return build_plan(
            RECIPE,
            run_name="lineup",
            comparison_id=None,
            parent_run_id=None,
            results_root=self.root / "results",
            now=FIXED,
            entropy="abc123",
            machine_profile_path=self.profile,
            **extra,
        )

    def stage_open_mix_weights(self) -> None:
        """Fake the weight directories the open-mix definition expects."""

        (self.roots.local_models / "Qwen3.6-35B-A3B-JANGTQ4").mkdir(
            parents=True, exist_ok=True
        )
        (self.roots.huggingface_hub / "georgeis55" / "Ornith-1.0-35B-MLX-oQ4").mkdir(
            parents=True, exist_ok=True
        )


class LineupKindTests(LineupTestCase):
    """lineup_kind names the kind from plan fields alone, without disk access."""

    def test_native_baseline(self) -> None:
        plan = self.plan(family_id="gemma-4-12b-qat")
        self.assertEqual(lineup_kind(plan), KIND_BASELINE)

    def test_comparison_class(self) -> None:
        plan = self.plan(
            family_id="gemma-4-12b-qat",
            comparison_class_id="gemma-native-baseline-v1",
        )
        self.assertEqual(lineup_kind(plan), KIND_COMPARISON_CLASS)

    def test_open_mix(self) -> None:
        plan = self.plan(family_id=None, open_mix_id="qwen-ornith-capability-v1")
        self.assertEqual(lineup_kind(plan), KIND_OPEN_MIX)

    def test_binding_outranks_comparison_class(self) -> None:
        # A plan carrying both is invalid, but the kind must still be decided
        # deterministically so resolve_lineup raises one predictable error.
        plan = replace(
            self.plan(family_id="gemma-4-12b-qat"),
            binding_id="some-binding",
            comparison_class_id="gemma-native-baseline-v1",
        )
        self.assertEqual(lineup_kind(plan), KIND_BINDING)

    def test_open_mix_scope_outranks_every_family_field(self) -> None:
        plan = replace(
            self.plan(family_id="gemma-4-12b-qat"),
            comparison_scope="open_mix",
            binding_id="some-binding",
        )
        self.assertEqual(lineup_kind(plan), KIND_OPEN_MIX)


class ResolveLineupTests(LineupTestCase):
    def test_baseline_resolves_without_open_mix_context(self) -> None:
        lineup = resolve_lineup(self.plan(family_id="gemma-4-12b-qat"), self.roots)
        self.assertEqual(lineup.kind, KIND_BASELINE)
        self.assertIsNone(lineup.open_mix)
        self.assertEqual(lineup.campaign.family_id, "gemma-4-12b-qat")

    def test_open_mix_carries_family_qualification(self) -> None:
        plan = self.plan(family_id=None, open_mix_id="qwen-ornith-capability-v1")
        lineup = resolve_lineup(plan, self.roots)
        self.assertEqual(lineup.kind, KIND_OPEN_MIX)
        self.assertIsNotNone(lineup.open_mix)
        # every cell is attributed to the family it actually came from
        self.assertEqual(
            set(lineup.open_mix.family_ids_by_cell.values()),
            {"qwen36-35b-a3b", "ornith-35b"},
        )
        self.assertEqual(lineup.campaign.cells, lineup.open_mix.cells)

    def test_plan_definition_mismatch_is_rejected(self) -> None:
        plan = replace(
            self.plan(family_id=None, open_mix_id="qwen-ornith-capability-v1"),
            open_mix_revision="999",
        )
        with self.assertRaises(RuntimeError):
            resolve_lineup(plan, self.roots)


if __name__ == "__main__":
    unittest.main()
