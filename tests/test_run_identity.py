from __future__ import annotations

import dataclasses
import json
import unittest
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from local_model_runtime_evaluation.managed_run_types import (
    COMPARISON_CLASS_PLAN_SCHEMA_VERSION,
    LEGACY_MANAGED_PLAN_SCHEMA_VERSION,
    ManagedRunPlan,
    ManagedStep,
    RunSummaryState,
    StepState,
)
from local_model_runtime_evaluation.free_bind import adopt_binding, propose_binding
from local_model_runtime_evaluation.artifact_profile import load_artifact_roots
from local_model_runtime_evaluation.lineup import _campaign_for_plan
from local_model_runtime_evaluation.run_identity import (
    MACHINE_PROFILE_INPUT,
    RunIdentityError,
    _canonical_plan_hash,
    _scaled_estimated_minutes,
    allocate_run_identity,
    build_plan,
    sanitize_run_name,
    verify_plan_inputs,
    verify_plan_hash,
)
from tests.artifact_profile_fixtures import write_machine_profile


ROOT = Path(__file__).resolve().parents[1]
RECIPE = ROOT / "config" / "managed-runs" / "complete-native-quality-v1.json"


def _adopt_test_binding(
    root: Path,
    profile: Path,
    *,
    binding_id: str,
    cell_ids: tuple[str, ...],
) -> Path:
    profile_body = json.loads(profile.read_text(encoding="utf-8"))
    roots = profile_body["artifact_roots"]
    for base, suffix in (
        (roots["local_models"], "gemma-4-12B-it-qat-JANG_4M"),
        (
            roots["huggingface_hub"],
            "avneetsb/gemma-4-12B-it-qat-oQ4-fp16",
        ),
        (
            roots["huggingface_hub"],
            "mlx-community/gemma-4-12B-it-qat-OptiQ-4bit",
        ),
    ):
        (Path(base) / suffix).mkdir(parents=True, exist_ok=True)
    state_dir = root / ".lmre"
    propose_binding(
        binding_id=binding_id,
        revision="1",
        family_id="gemma-4-12b-qat",
        cell_ids=cell_ids,
        notes="test binding",
        state_dir=state_dir,
        machine_profile_path=profile,
        now=_fixed_time(),
    )
    adopt_binding(
        binding_id,
        state_dir=state_dir,
        machine_profile_path=profile,
        now=_fixed_time(),
    )
    return state_dir


def _fixed_time() -> datetime:
    return datetime(2026, 7, 30, 18, 0, tzinfo=timezone.utc)


class RunIdentityTests(unittest.TestCase):
    def test_expansion_estimate_scales_up_with_request_count(self) -> None:
        self.assertEqual(_scaled_estimated_minutes(90, 93, 93), 90)
        self.assertEqual(_scaled_estimated_minutes(90, 93, 132), 128)

    def test_name_and_id_are_separate_and_collision_safe(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = allocate_run_identity(
                root,
                run_name=" Qwen Native / Baseline ",
                comparison_id=None,
                parent_run_id=None,
                now=_fixed_time(),
                entropy="a1b2c3",
            )
            second = allocate_run_identity(
                root,
                run_name=" Qwen Native / Baseline ",
                comparison_id=None,
                parent_run_id=None,
                now=_fixed_time(),
                entropy="d4e5f6",
            )
            self.assertEqual(first.run_name, "qwen-native-baseline")
            self.assertEqual(first.comparison_id, "qwen-native-baseline")
            self.assertEqual(first.attempt, 1)
            self.assertNotEqual(first.run_id, second.run_id)

    def test_existing_run_id_is_rejected(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "run-20260730-180000-a1b2c3").mkdir()
            with self.assertRaises(RunIdentityError) as context:
                allocate_run_identity(
                    root,
                    run_name="baseline",
                    comparison_id=None,
                    parent_run_id=None,
                    now=_fixed_time(),
                    entropy="a1b2c3",
                )
            self.assertEqual(context.exception.code, "run_id_collision")

    def test_invalid_names_entropy_and_parent_are_rejected(self) -> None:
        for value in ("", "---", "a" * 81):
            with self.subTest(value=value):
                with self.assertRaises(RunIdentityError):
                    sanitize_run_name(value)
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaises(RunIdentityError):
                allocate_run_identity(
                    root,
                    run_name="baseline",
                    comparison_id=None,
                    parent_run_id=None,
                    now=_fixed_time(),
                    entropy="NOTHEX",
                )
            with self.assertRaises(RunIdentityError):
                allocate_run_identity(
                    root,
                    run_name="baseline",
                    comparison_id=None,
                    parent_run_id="../prior",
                    now=_fixed_time(),
                    entropy="a1b2c3",
                )

    def test_complete_recipe_has_fixed_order_and_bounded_requests(self) -> None:
        with TemporaryDirectory() as tmp:
            profile = write_machine_profile(Path(tmp) / "machine")
            plan = build_plan(
                RECIPE,
                family_id="gemma-4-12b-qat",
                run_name="gemma managed baseline",
                comparison_id=None,
                parent_run_id=None,
                results_root=Path(tmp),
                now=_fixed_time(),
                entropy="a1b2c3",
                machine_profile_path=profile,
            )
            verify_plan_inputs(plan, machine_profile_path=profile)
        self.assertEqual(
            plan.steps,
            (
                ManagedStep.PREFLIGHT,
                ManagedStep.MATRIX,
                ManagedStep.PREFERENCE,
                ManagedStep.RAG_ORACLE,
                ManagedStep.RAG_KEYWORD,
                ManagedStep.OVERHEAD,
                ManagedStep.SEAL,
            ),
        )
        self.assertEqual(
            plan.cell_ids,
            (
                "jang_4m__osaurus",
                "oq4_fp16__omlx",
                "optiq_4bit__optiq",
            ),
        )
        self.assertEqual(plan.pair_ids, ("oq4_fp16", "optiq_4bit"))
        self.assertEqual(plan.request_count, 93)
        self.assertLessEqual(plan.request_count, 250)
        self.assertEqual(plan.memory_floor_percent, 20)
        self.assertEqual(plan.estimated_minutes, 90)
        self.assertTrue(plan.input_hashes)
        verify_plan_hash(plan)
        self.assertIn(MACHINE_PROFILE_INPUT, dict(plan.input_hashes))

    def test_generated_name_and_lineage_are_persisted(self) -> None:
        with TemporaryDirectory() as tmp:
            profile = write_machine_profile(Path(tmp) / "machine")
            plan = build_plan(
                RECIPE,
                family_id="ornith-35b",
                run_name=None,
                comparison_id="Ornith July Baselines",
                parent_run_id="run-20260729-180000-abcdef",
                results_root=Path(tmp),
                now=_fixed_time(),
                entropy="a1b2c3",
                machine_profile_path=profile,
            )
        self.assertEqual(
            plan.identity.run_name,
            "ornith-35b-complete-native-quality",
        )
        self.assertEqual(
            plan.identity.comparison_id,
            "ornith-july-baselines",
        )
        self.assertEqual(
            plan.identity.parent_run_id,
            "run-20260729-180000-abcdef",
        )

    def test_declared_comparison_class_is_bound_into_plan(self) -> None:
        with TemporaryDirectory() as tmp:
            profile = write_machine_profile(Path(tmp) / "machine")
            plan = build_plan(
                RECIPE,
                family_id="gemma-4-12b-qat",
                run_name=None,
                comparison_id=None,
                parent_run_id=None,
                results_root=Path(tmp),
                comparison_class_id="gemma-native-baseline-v1",
                now=_fixed_time(),
                entropy="a1b2c3",
                machine_profile_path=profile,
            )
        self.assertEqual(plan.comparison_class_id, "gemma-native-baseline-v1")
        self.assertEqual(plan.baseline_cell_ids, plan.cell_ids)
        self.assertIn(
            "config/comparison-classes/gemma-native-baseline-v1.json",
            dict(plan.input_hashes),
        )
        self.assertEqual(
            plan.identity.run_name,
            "gemma-4-12b-qat-gemma-native-baseline-v1",
        )

    def test_adopted_free_binding_is_bound_into_plan(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            profile = write_machine_profile(root / "machine")
            state_dir = _adopt_test_binding(
                root,
                profile,
                binding_id="gemma-free-bind-v1",
                cell_ids=(
                    "jang_4m__osaurus",
                    "oq4_fp16__omlx",
                    "optiq_4bit__optiq",
                ),
            )
            plan = build_plan(
                RECIPE,
                family_id="gemma-4-12b-qat",
                run_name=None,
                comparison_id=None,
                parent_run_id=None,
                results_root=root / "results",
                binding_id="gemma-free-bind-v1",
                binding_state_dir=state_dir,
                now=_fixed_time(),
                entropy="a1b2c3",
                machine_profile_path=profile,
            )
            materialized = _campaign_for_plan(
                plan,
                load_artifact_roots(profile),
            )
        self.assertEqual(plan.schema_version, "1.2.0")
        self.assertEqual(plan.binding_id, "gemma-free-bind-v1")
        self.assertEqual(plan.binding_revision, "1")
        self.assertIsNotNone(plan.binding_hash)
        self.assertIsNotNone(plan.binding_proposal_hash)
        self.assertIsNone(plan.comparison_class_id)
        self.assertEqual(plan.request_count, 93)
        self.assertEqual(plan.estimated_minutes, 90)
        self.assertEqual(plan.runtimes, frozenset({"osaurus", "omlx", "optiq"}))
        self.assertEqual(
            ManagedRunPlan.from_dict(plan.to_dict()).to_dict(),
            plan.to_dict(),
        )
        self.assertEqual(
            tuple(cell.cell_id for cell in materialized.cells),
            plan.cell_ids,
        )

    def test_two_cell_binding_filters_runtime_and_overhead_scope(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            profile = write_machine_profile(root / "machine")
            state_dir = _adopt_test_binding(
                root,
                profile,
                binding_id="gemma-two-cell-v1",
                cell_ids=("jang_4m__osaurus", "oq4_fp16__omlx"),
            )
            plan = build_plan(
                RECIPE,
                family_id="gemma-4-12b-qat",
                run_name=None,
                comparison_id=None,
                parent_run_id=None,
                results_root=root / "results",
                binding_id="gemma-two-cell-v1",
                binding_state_dir=state_dir,
                now=_fixed_time(),
                entropy="a1b2c3",
                machine_profile_path=profile,
            )
        self.assertEqual(
            plan.cell_ids,
            ("jang_4m__osaurus", "oq4_fp16__omlx"),
        )
        self.assertEqual(plan.pair_ids, ("oq4_fp16",))
        self.assertEqual(plan.runtimes, frozenset({"osaurus", "omlx"}))
        self.assertEqual(
            plan.endpoints,
            (
                "http://127.0.0.1:1337/v1",
                "http://127.0.0.1:8100/v1",
            ),
        )
        self.assertEqual(plan.request_count, 54)
        self.assertEqual(plan.estimated_minutes, 53)

    def test_plan_rejects_competing_class_and_binding(self) -> None:
        with TemporaryDirectory() as tmp:
            profile = write_machine_profile(Path(tmp) / "machine")
            with self.assertRaises(RunIdentityError):
                build_plan(
                    RECIPE,
                    family_id="gemma-4-12b-qat",
                    run_name=None,
                    comparison_id=None,
                    parent_run_id=None,
                    results_root=Path(tmp) / "results",
                    comparison_class_id="gemma-native-baseline-v1",
                    binding_id="gemma-free-bind-v1",
                    machine_profile_path=profile,
                )

    def test_legacy_plan_shape_remains_hash_verifiable(self) -> None:
        with TemporaryDirectory() as tmp:
            profile = write_machine_profile(Path(tmp) / "machine")
            current = build_plan(
                RECIPE,
                family_id="gemma-4-12b-qat",
                run_name=None,
                comparison_id=None,
                parent_run_id=None,
                results_root=Path(tmp),
                now=_fixed_time(),
                entropy="a1b2c3",
                machine_profile_path=profile,
            )
        legacy = dataclasses.replace(
            current,
            schema_version=LEGACY_MANAGED_PLAN_SCHEMA_VERSION,
            comparison_class_id=None,
            comparison_class_path=None,
            baseline_cell_ids=current.cell_ids,
            plan_hash="",
        )
        legacy = dataclasses.replace(
            legacy,
            plan_hash=_canonical_plan_hash(legacy),
        )
        payload = legacy.to_dict()
        self.assertNotIn("comparison_class_id", payload)
        loaded = ManagedRunPlan.from_dict(payload)
        verify_plan_hash(loaded)
        self.assertEqual(loaded.baseline_cell_ids, loaded.cell_ids)

    def test_comparison_class_plan_v1_1_remains_hash_verifiable(self) -> None:
        with TemporaryDirectory() as tmp:
            profile = write_machine_profile(Path(tmp) / "machine")
            current = build_plan(
                RECIPE,
                family_id="gemma-4-12b-qat",
                run_name=None,
                comparison_id=None,
                parent_run_id=None,
                results_root=Path(tmp),
                comparison_class_id="gemma-native-baseline-v1",
                now=_fixed_time(),
                entropy="a1b2c3",
                machine_profile_path=profile,
            )
        prior = dataclasses.replace(
            current,
            schema_version=COMPARISON_CLASS_PLAN_SCHEMA_VERSION,
            plan_hash="",
        )
        prior = dataclasses.replace(
            prior,
            plan_hash=_canonical_plan_hash(prior),
        )
        payload = prior.to_dict()
        self.assertNotIn("binding_id", payload)
        loaded = ManagedRunPlan.from_dict(payload)
        verify_plan_hash(loaded)
        self.assertEqual(loaded.comparison_class_id, "gemma-native-baseline-v1")

    def test_all_retained_families_build_valid_plans(self) -> None:
        families = (
            "gemma-4-12b-qat",
            "ornith-35b",
            "qwen36-35b-a3b",
        )
        with TemporaryDirectory() as tmp:
            profile = write_machine_profile(Path(tmp) / "machine")
            for index, family_id in enumerate(families):
                with self.subTest(family_id=family_id):
                    plan = build_plan(
                        RECIPE,
                        family_id=family_id,
                        run_name=None,
                        comparison_id=None,
                        parent_run_id=None,
                        results_root=Path(tmp),
                        now=_fixed_time(),
                        entropy=f"{index + 1:06x}",
                        machine_profile_path=profile,
                    )
                    self.assertEqual(len(plan.cell_ids), 3)
                    self.assertEqual(len(plan.pair_ids), 2)
                    self.assertEqual(plan.request_count, 93)
                    verify_plan_hash(plan)

    def test_unknown_family_is_rejected(self) -> None:
        with TemporaryDirectory() as tmp:
            profile = write_machine_profile(Path(tmp) / "machine")
            with self.assertRaises(RunIdentityError):
                build_plan(
                    RECIPE,
                    family_id="unknown-family",
                    run_name=None,
                    comparison_id=None,
                    parent_run_id=None,
                    results_root=Path(tmp),
                    now=_fixed_time(),
                    entropy="a1b2c3",
                    machine_profile_path=profile,
                )

    def test_changed_plan_content_fails_hash_verification(self) -> None:
        with TemporaryDirectory() as tmp:
            profile = write_machine_profile(Path(tmp) / "machine")
            plan = build_plan(
                RECIPE,
                family_id="gemma-4-12b-qat",
                run_name=None,
                comparison_id=None,
                parent_run_id=None,
                results_root=Path(tmp),
                now=_fixed_time(),
                entropy="a1b2c3",
                machine_profile_path=profile,
            )
        changed = dataclasses.replace(plan, request_count=plan.request_count + 1)
        with self.assertRaises(RunIdentityError) as context:
            verify_plan_hash(changed)
        self.assertEqual(context.exception.code, "plan_hash_mismatch")

    def test_changed_planned_input_fails_verification(self) -> None:
        with TemporaryDirectory() as tmp:
            profile = write_machine_profile(Path(tmp) / "machine")
            plan = build_plan(
                RECIPE,
                family_id="gemma-4-12b-qat",
                run_name=None,
                comparison_id=None,
                parent_run_id=None,
                results_root=Path(tmp),
                now=_fixed_time(),
                entropy="a1b2c3",
                machine_profile_path=profile,
            )
            hashes = dict(plan.input_hashes)
            self.assertNotEqual(hashes[MACHINE_PROFILE_INPUT], "0" * 64)
            hashes[MACHINE_PROFILE_INPUT] = "0" * 64
            changed = dataclasses.replace(
                plan,
                input_hashes=tuple(sorted(hashes.items())),
            )

            with self.assertRaises(RunIdentityError) as context:
                verify_plan_inputs(changed, machine_profile_path=profile)

        self.assertEqual(context.exception.code, "plan_input_changed")

    def test_legacy_plan_without_machine_profile_hash_remains_verifiable(self) -> None:
        with TemporaryDirectory() as tmp:
            profile = write_machine_profile(Path(tmp) / "machine")
            plan = build_plan(
                RECIPE,
                family_id="gemma-4-12b-qat",
                run_name=None,
                comparison_id=None,
                parent_run_id=None,
                results_root=Path(tmp),
                now=_fixed_time(),
                entropy="a1b2c3",
                machine_profile_path=profile,
            )
            legacy = dataclasses.replace(
                plan,
                input_hashes=tuple(
                    item
                    for item in plan.input_hashes
                    if item[0] != MACHINE_PROFILE_INPUT
                ),
            )
            verify_plan_inputs(legacy, machine_profile_path=Path("/missing"))

    def test_shared_state_values_match_evidence_contract(self) -> None:
        self.assertEqual(
            StepState.BLOCKED_PROVIDER_RECONNECT.value, "BLOCKED_PROVIDER_RECONNECT"
        )
        self.assertEqual(RunSummaryState.PARTIAL_BLOCKED.value, "PARTIAL_BLOCKED")


if __name__ == "__main__":
    unittest.main()
