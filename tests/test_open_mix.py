from __future__ import annotations

import json
import shutil
import socket
import subprocess
import unittest
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch

from local_model_runtime_evaluation.artifact_profile import load_artifact_roots
from local_model_runtime_evaluation.evidence_bundle import EvidenceBundle
from local_model_runtime_evaluation.managed_run import (
    ManagedCollectorHooks,
    _open_mix_context,
    _required_routes,
    default_collector_hooks,
    execute_managed_run,
    resume_managed_run,
)
from local_model_runtime_evaluation.managed_run_types import (
    OPEN_MIX_PLAN_SCHEMA_VERSION,
    ManagedRunPlan,
    RunSummaryState,
    StepState,
)
from local_model_runtime_evaluation.open_mix import OpenMixError, load_open_mix
from local_model_runtime_evaluation.open_mix_inspect import inspect_open_mix
from local_model_runtime_evaluation.operator_policy import adopt_policy
from local_model_runtime_evaluation.results_browser import (
    build_comparisons,
    build_index,
    build_run_view,
)
from local_model_runtime_evaluation.run_identity import (
    RunIdentityError,
    build_plan,
    verify_plan_hash,
    verify_plan_inputs,
)
from tests.artifact_profile_fixtures import write_machine_profile


ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / "config" / "operator-policies" / "local-managed-v1.example.json"


class OpenMixFixture:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.repository = root / "repository"
        self.profile = root / "machine-profile.json"
        self.results = root / "results"
        self.state = root / ".lmre"
        self.mix_id = "qwen-ornith-capability-v1"
        self.mix_path = (
            self.repository / "config" / "open-mixes" / f"{self.mix_id}.json"
        )
        self.contracts_root = (
            self.repository / "config" / "open-mix-suite-contracts"
        )
        self.open_mixes_root = self.repository / "config" / "open-mixes"
        self.families_root = self.repository / "config" / "matrix" / "families"
        self.cells_root = self.repository / "config" / "matrix" / "cells"
        self.local_models = root / "local-models"
        self.huggingface = root / "huggingface"
        self.recipe = (
            self.repository
            / "config"
            / "managed-runs"
            / "complete-native-quality-v1.json"
        )

    def create(self, *, artifacts_ready: bool = True) -> OpenMixFixture:
        for directory in (
            self.open_mixes_root,
            self.contracts_root,
            self.families_root,
            self.cells_root,
            self.repository / "config" / "overhead" / "pairs",
            self.recipe.parent,
            self.repository / "suites",
            self.repository / "corpora",
        ):
            directory.mkdir(parents=True, exist_ok=True)

        for name in ("qwen36-35b-a3b", "ornith-35b"):
            shutil.copy2(
                ROOT / "config" / "matrix" / "families" / f"{name}.json",
                self.families_root / f"{name}.json",
            )
            shutil.copy2(
                ROOT / "config" / "matrix" / f"{name}-campaign.json",
                self.repository / "config" / "matrix" / f"{name}-campaign.json",
            )
        for name in ("qwen_jangtq4__osaurus", "ornith_oq4__omlx"):
            shutil.copy2(
                ROOT / "config" / "matrix" / "cells" / f"{name}.json",
                self.cells_root / f"{name}.json",
            )
        for name in (
            "gemma-matrix-v1.json",
            "multi-family-preference-v1.json",
            "multi-family-rag-oracle-v1.json",
        ):
            shutil.copy2(ROOT / "suites" / name, self.repository / "suites" / name)
        shutil.copytree(
            ROOT / "corpora" / "rag-oracle-v1",
            self.repository / "corpora" / "rag-oracle-v1",
        )
        shutil.copy2(
            ROOT / "config" / "managed-runs" / self.recipe.name,
            self.recipe,
        )
        (self.repository / "config" / "overhead" / "family-pairs.json").write_text(
            json.dumps({"qwen36-35b-a3b": [], "ornith-35b": []}),
            encoding="utf-8",
        )
        shutil.copy2(
            ROOT
            / "config"
            / "open-mix-suite-contracts"
            / "shared-capability-v1.json",
            self.contracts_root / "shared-capability-v1.json",
        )
        self.write_mix()
        self.profile.write_text(
            json.dumps(
                {
                    "schema_version": "1.0.0",
                    "artifact_roots": {
                        "huggingface_hub": str(self.huggingface),
                        "local_models": str(self.local_models),
                    },
                }
            ),
            encoding="utf-8",
        )
        self.local_models.mkdir(parents=True, exist_ok=True)
        self.huggingface.mkdir(parents=True, exist_ok=True)
        if artifacts_ready:
            (self.local_models / "Qwen3.6-35B-A3B-JANGTQ4").mkdir(
                parents=True
            )
            (
                self.huggingface / "georgeis55" / "Ornith-1.0-35B-MLX-oQ4"
            ).mkdir(parents=True)
        return self

    def write_mix(self, **updates: object) -> None:
        body: dict[str, object] = {
            "schema_version": "1.0.0",
            "open_mix_id": self.mix_id,
            "revision": "1",
            "members": [
                {
                    "family_id": "qwen36-35b-a3b",
                    "cell_id": "qwen_jangtq4__osaurus",
                },
                {
                    "family_id": "ornith-35b",
                    "cell_id": "ornith_oq4__omlx",
                },
            ],
            "suite_contract_id": "shared-capability-v1",
            "estimated_minutes": 90,
            "notes": "synthetic test mix",
        }
        body.update(updates)
        self.mix_path.write_text(
            json.dumps(body, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    def load(self):
        return load_open_mix(
            self.mix_id,
            root=self.open_mixes_root,
            repository_root=self.repository,
            families_root=self.families_root,
            cells_root=self.cells_root,
            suite_contracts_root=self.contracts_root,
        )

    def plan(self, *, entropy: str = "a1b2c3") -> ManagedRunPlan:
        return build_plan(
            self.recipe,
            family_id=None,
            open_mix_id=self.mix_id,
            run_name=None,
            comparison_id="heterogeneous-review",
            parent_run_id=None,
            results_root=self.results,
            now=datetime(2026, 8, 5, 12, 0, tzinfo=timezone.utc),
            entropy=entropy,
            machine_profile_path=self.profile,
            repository_root=self.repository,
            open_mixes_root=self.open_mixes_root,
            suite_contracts_root=self.contracts_root,
        )


class OpenMixTests(unittest.TestCase):
    def _actual_plan(self, root: Path) -> tuple[ManagedRunPlan, Path]:
        profile = write_machine_profile(root / "machine")
        payload = json.loads(profile.read_text(encoding="utf-8"))
        local_models = Path(payload["artifact_roots"]["local_models"])
        huggingface = Path(payload["artifact_roots"]["huggingface_hub"])
        (local_models / "Qwen3.6-35B-A3B-JANGTQ4").mkdir()
        (huggingface / "georgeis55" / "Ornith-1.0-35B-MLX-oQ4").mkdir(
            parents=True
        )
        plan = build_plan(
            ROOT / "config/managed-runs/complete-native-quality-v1.json",
            family_id=None,
            open_mix_id="qwen-ornith-capability-v1",
            run_name="open mix test",
            comparison_id="open-mix-test",
            parent_run_id=None,
            results_root=root / "results",
            now=datetime(2026, 8, 5, 12, 0, tzinfo=timezone.utc),
            entropy="b1c2d3",
            machine_profile_path=profile,
        )
        return plan, profile

    def test_runtime_context_binds_campaigns_and_ordered_members(self) -> None:
        with TemporaryDirectory() as tmp:
            plan, profile = self._actual_plan(Path(tmp))
            context = _open_mix_context(plan, load_artifact_roots(profile))
            self.assertEqual(
                tuple(cell.cell_id for cell in context.cells), plan.cell_ids
            )
            self.assertEqual(context.campaign.ready_timeout_seconds, 300)
            self.assertEqual(context.campaign.request_timeout_seconds, 180)
            self.assertEqual(plan.pair_ids, ("ornith_oq4",))
            self.assertEqual(
                context.family_ids_by_pair,
                {"ornith_oq4": "ornith-35b"},
            )
            self.assertEqual(
                context.family_ids_by_cell,
                {
                    "qwen_jangtq4__osaurus": "qwen36-35b-a3b",
                    "ornith_oq4__omlx": "ornith-35b",
                },
            )
            bound = dict(plan.input_hashes)
            self.assertIn(
                "config/matrix/qwen36-35b-a3b-campaign.json", bound
            )
            self.assertIn("config/matrix/ornith-35b-campaign.json", bound)

    def test_default_hooks_forward_member_qualified_collector_context(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan, profile = self._actual_plan(root)
            bundle = type("Bundle", (), {"run_dir": root / "run"})()
            runtime_manager = MagicMock()
            hooks = default_collector_hooks(
                plan,
                runtime_manager,
                bundle,  # type: ignore[arg-type]
                machine_profile_path=profile,
            )
            output = root / "output"
            output.mkdir()
            collector = output / "collector"
            collector.mkdir()
            with patch(
                "local_model_runtime_evaluation.managed_run.run_campaign",
                return_value=collector,
            ) as matrix:
                self.assertEqual(hooks.matrix(plan, output, MagicMock()), collector)
            matrix_kwargs = matrix.call_args.kwargs
            self.assertEqual(
                tuple(cell.cell_id for cell in matrix_kwargs["cells"]),
                plan.cell_ids,
            )
            self.assertEqual(
                matrix_kwargs["collection_identity"]["open_mix_id"],
                plan.open_mix_id,
            )
            self.assertEqual(
                matrix_kwargs["collection_identity"]["overhead_coverage"][0][
                    "status"
                ],
                "N/A",
            )

            with (
                patch(
                    "local_model_runtime_evaluation.managed_run.run_preference_collect",
                    return_value=collector,
                ) as preference,
                patch("local_model_runtime_evaluation.managed_run.run_review"),
                patch(
                    "local_model_runtime_evaluation.managed_run.run_judge"
                ) as judge,
                patch(
                    "local_model_runtime_evaluation.managed_run.run_tally",
                    return_value=collector,
                ),
            ):
                self.assertEqual(
                    hooks.preference(plan, output, MagicMock()), collector
                )
            self.assertIsNone(preference.call_args.kwargs["family_id"])
            self.assertEqual(
                preference.call_args.kwargs["run_label"], plan.open_mix_id
            )
            self.assertEqual(
                judge.call_args.kwargs["family_id"], "qwen36-35b-a3b"
            )

            with (
                patch(
                    "local_model_runtime_evaluation.managed_run.run_rag_collect",
                    return_value=collector,
                ) as rag,
                patch(
                    "local_model_runtime_evaluation.managed_run.score_run",
                    return_value=collector,
                ),
            ):
                self.assertEqual(hooks.rag_oracle(plan, output, MagicMock()), collector)
            self.assertIsNone(rag.call_args.kwargs["family_id"])
            self.assertEqual(
                rag.call_args.kwargs["family_ids_by_cell"],
                {
                    "qwen_jangtq4__osaurus": "qwen36-35b-a3b",
                    "ornith_oq4__omlx": "ornith-35b",
                },
            )

    def test_valid_cross_family_definition_loads(self) -> None:
        with TemporaryDirectory() as tmp:
            fixture = OpenMixFixture(Path(tmp)).create()
            mix = fixture.load()
            self.assertEqual(mix.open_mix_id, fixture.mix_id)
            self.assertEqual(
                mix.family_ids, ("qwen36-35b-a3b", "ornith-35b")
            )
            self.assertEqual(
                mix.cell_ids,
                ("qwen_jangtq4__osaurus", "ornith_oq4__omlx"),
            )
            self.assertEqual(
                mix.suite_contract.suite_contract_id, "shared-capability-v1"
            )

    def test_same_family_and_duplicate_members_fail_closed(self) -> None:
        with TemporaryDirectory() as tmp:
            fixture = OpenMixFixture(Path(tmp)).create()
            fixture.write_mix(
                members=[
                    {
                        "family_id": "qwen36-35b-a3b",
                        "cell_id": "qwen_jangtq4__osaurus",
                    },
                    {
                        "family_id": "qwen36-35b-a3b",
                        "cell_id": "qwen_jangtq4__osaurus",
                    },
                ]
            )
            with self.assertRaises(OpenMixError):
                fixture.load()

    def test_member_family_mismatch_fails_closed(self) -> None:
        with TemporaryDirectory() as tmp:
            fixture = OpenMixFixture(Path(tmp)).create()
            fixture.write_mix(
                members=[
                    {
                        "family_id": "ornith-35b",
                        "cell_id": "qwen_jangtq4__osaurus",
                    },
                    {
                        "family_id": "qwen36-35b-a3b",
                        "cell_id": "ornith_oq4__omlx",
                    },
                ]
            )
            with self.assertRaises(OpenMixError):
                fixture.load()

    def test_symlinked_definition_is_rejected(self) -> None:
        with TemporaryDirectory() as tmp:
            fixture = OpenMixFixture(Path(tmp)).create()
            target = fixture.root / "outside.json"
            fixture.mix_path.replace(target)
            fixture.mix_path.symlink_to(target)
            with self.assertRaises(OpenMixError):
                fixture.load()

    def test_inspection_reports_ready_and_missing_without_live_status(self) -> None:
        with TemporaryDirectory() as tmp:
            fixture = OpenMixFixture(Path(tmp)).create()
            ready = inspect_open_mix(
                fixture.mix_id,
                machine_profile_path=fixture.profile,
                open_mixes_root=fixture.open_mixes_root,
                suite_contracts_root=fixture.contracts_root,
                repository_root=fixture.repository,
                families_root=fixture.families_root,
                cells_root=fixture.cells_root,
            )
            self.assertEqual(ready["status"], "READY_FOR_PLAN")
            self.assertEqual(ready["live_status"], "NOT_CHECKED_LIVE")

            shutil.rmtree(fixture.local_models / "Qwen3.6-35B-A3B-JANGTQ4")
            missing = inspect_open_mix(
                fixture.mix_id,
                machine_profile_path=fixture.profile,
                open_mixes_root=fixture.open_mixes_root,
                suite_contracts_root=fixture.contracts_root,
                repository_root=fixture.repository,
                families_root=fixture.families_root,
                cells_root=fixture.cells_root,
            )
            self.assertEqual(missing["status"], "ACTION_REQUIRED")
            self.assertFalse(missing["ready_for_plan"])

    def test_inspection_tripwire_does_not_touch_network_or_subprocesses(self) -> None:
        with TemporaryDirectory() as tmp:
            fixture = OpenMixFixture(Path(tmp)).create()
            with (
                patch.object(
                    socket,
                    "create_connection",
                    side_effect=AssertionError("inspection must not use network"),
                ),
                patch.object(
                    subprocess,
                    "run",
                    side_effect=AssertionError("inspection must not run commands"),
                ),
                patch.object(
                    subprocess,
                    "Popen",
                    side_effect=AssertionError("inspection must not spawn"),
                ),
            ):
                result = inspect_open_mix(
                    fixture.mix_id,
                    machine_profile_path=fixture.profile,
                    open_mixes_root=fixture.open_mixes_root,
                    suite_contracts_root=fixture.contracts_root,
                    repository_root=fixture.repository,
                    families_root=fixture.families_root,
                    cells_root=fixture.cells_root,
                )
            self.assertEqual(result["status"], "READY_FOR_PLAN")

    def test_plan_records_and_verifies_heterogeneous_identity(self) -> None:
        with TemporaryDirectory() as tmp:
            fixture = OpenMixFixture(Path(tmp)).create()
            plan = fixture.plan()
            self.assertEqual(plan.schema_version, OPEN_MIX_PLAN_SCHEMA_VERSION)
            self.assertEqual(plan.comparison_scope, "open_mix")
            self.assertIsNone(plan.family_id)
            self.assertEqual(plan.open_mix_id, fixture.mix_id)
            self.assertEqual(plan.suite_contract_id, "shared-capability-v1")
            self.assertEqual(plan.baseline_cell_ids, ())
            self.assertEqual(plan.pair_ids, ())
            self.assertEqual(plan.runtimes, frozenset({"osaurus", "omlx"}))
            self.assertEqual(ManagedRunPlan.from_dict(plan.to_dict()), plan)
            verify_plan_hash(plan)
            verify_plan_inputs(
                plan,
                repository_root=fixture.repository,
                machine_profile_path=fixture.profile,
            )

    def test_plan_rejects_missing_artifact_and_mixed_declaration_modes(self) -> None:
        with TemporaryDirectory() as tmp:
            fixture = OpenMixFixture(Path(tmp)).create(artifacts_ready=False)
            with self.assertRaises(RunIdentityError) as missing:
                fixture.plan()
            self.assertEqual(missing.exception.code, "open_mix_artifacts_not_ready")
            with self.assertRaises(RunIdentityError):
                build_plan(
                    fixture.recipe,
                    family_id="qwen36-35b-a3b",
                    open_mix_id=fixture.mix_id,
                    run_name=None,
                    comparison_id=None,
                    parent_run_id=None,
                    results_root=fixture.results,
                    machine_profile_path=fixture.profile,
                    repository_root=fixture.repository,
                    open_mixes_root=fixture.open_mixes_root,
                    suite_contracts_root=fixture.contracts_root,
                )

    def test_plan_tampering_and_input_changes_fail_closed(self) -> None:
        with TemporaryDirectory() as tmp:
            fixture = OpenMixFixture(Path(tmp)).create()
            plan = fixture.plan()
            raw = plan.to_dict()
            raw["open_mix_members"] = list(reversed(raw["open_mix_members"]))
            with self.assertRaises(ValueError):
                ManagedRunPlan.from_dict(raw)
            fixture.mix_path.write_text("{}", encoding="utf-8")
            with self.assertRaises(RunIdentityError):
                verify_plan_inputs(
                    plan,
                    repository_root=fixture.repository,
                    machine_profile_path=fixture.profile,
                )

    def test_execution_seals_pass_with_explicit_overhead_na(self) -> None:
        with TemporaryDirectory() as tmp:
            fixture = OpenMixFixture(Path(tmp)).create()
            plan = fixture.plan()
            adopted = adopt_policy(
                POLICY,
                fixture.state,
                now=datetime(2026, 8, 5, 11, 0, tzinfo=timezone.utc),
            )
            bundle = EvidenceBundle.create(
                fixture.results,
                plan,
                adopted,
                {"platform": "test", "python": "3"},
            )

            def collect(candidate, output_root, build_server):
                del candidate, build_server
                run_dir = output_root / "collector"
                run_dir.mkdir()
                (run_dir / "report.md").write_text("PASS\n", encoding="utf-8")
                return run_dir

            def routed(candidate):
                raise AssertionError(
                    f"route discovery must not run without pairs: {candidate}"
                )

            hooks = ManagedCollectorHooks(
                preflight=lambda candidate: {"open_mix_id": candidate.open_mix_id},
                matrix=collect,
                preference=collect,
                rag_oracle=collect,
                rag_keyword=collect,
                routed_models=routed,
                overhead=collect,
            )

            class Manager:
                build_server = object()

                def release_all(self) -> None:
                    return None

            with patch(
                "local_model_runtime_evaluation.managed_run.verify_plan_inputs"
            ):
                summary = execute_managed_run(
                    plan,
                    adopted,
                    bundle,
                    Manager(),  # type: ignore[arg-type]
                    hooks,
                    machine_profile_path=fixture.profile,
                )
            self.assertEqual(summary["status"], "PASS")
            verified = EvidenceBundle.load(bundle.run_dir)
            verified.verify()
            overhead = next(
                record
                for record in verified.state.steps
                if record.step.value == "overhead"
            )
            self.assertEqual(overhead.state, StepState.NOT_APPLICABLE)

    def test_open_mix_provider_block_resumes_only_overhead(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan, profile = self._actual_plan(root)
            adopted = adopt_policy(
                POLICY,
                root / ".lmre",
                now=datetime(2026, 8, 5, 11, 0, tzinfo=timezone.utc),
            )
            bundle = EvidenceBundle.create(
                root / "results",
                plan,
                adopted,
                {"platform": "test", "python": "3"},
            )

            def collect(candidate, output_root, build_server):
                del candidate, build_server
                run_dir = output_root / "collector"
                run_dir.mkdir()
                (run_dir / "report.md").write_text("PASS\n", encoding="utf-8")
                return run_dir

            class Manager:
                build_server = object()

                def release_all(self) -> None:
                    return None

            blocked_hooks = ManagedCollectorHooks(
                preflight=lambda candidate: {"open_mix_id": candidate.open_mix_id},
                matrix=collect,
                preference=collect,
                rag_oracle=collect,
                rag_keyword=collect,
                routed_models=lambda candidate: (),
                overhead=collect,
            )
            first = execute_managed_run(
                plan,
                adopted,
                bundle,
                Manager(),  # type: ignore[arg-type]
                blocked_hooks,
                machine_profile_path=profile,
            )
            self.assertEqual(first["status"], "PARTIAL_BLOCKED")

            routes = _required_routes(plan, load_artifact_roots(profile))
            resumed_hooks = ManagedCollectorHooks(
                preflight=lambda candidate: {},
                matrix=collect,
                preference=collect,
                rag_oracle=collect,
                rag_keyword=collect,
                routed_models=lambda candidate: routes,
                overhead=collect,
            )
            second = resume_managed_run(
                bundle.run_dir,
                adopted,
                Manager(),  # type: ignore[arg-type]
                resumed_hooks,
                machine_profile_path=profile,
            )
            self.assertEqual(second["status"], "PASS")
            verified = EvidenceBundle.load(bundle.run_dir)
            verified.verify()
            self.assertEqual(verified.state.attempt, 2)
            self.assertEqual(verified.state.summary_state, RunSummaryState.PASS)

    def test_browser_exposes_and_compares_exact_open_mix_dimensions(self) -> None:
        with TemporaryDirectory() as tmp:
            fixture = OpenMixFixture(Path(tmp)).create()
            plan = fixture.plan()
            adopted = adopt_policy(
                POLICY,
                fixture.state,
                now=datetime(2026, 8, 5, 11, 0, tzinfo=timezone.utc),
            )
            bundle = EvidenceBundle.create(
                fixture.results,
                plan,
                adopted,
                {"platform": "test", "python": "3"},
            )
            for step in plan.steps:
                bundle.transition_step(step, StepState.RUNNING)
                bundle.transition_step(step, StepState.PASS)
            bundle.mark_cleanup_complete()
            bundle.write_summary(
                {
                    "run_id": plan.identity.run_id,
                    "status": RunSummaryState.PASS.value,
                }
            )
            bundle.seal()

            entry = build_index(fixture.results)["entries"][0]
            self.assertEqual(entry["open_mix_id"], fixture.mix_id)
            self.assertEqual(entry["suite_contract_id"], "shared-capability-v1")
            identity = build_run_view(bundle.run_dir)["identity"]
            self.assertEqual(identity["comparison_scope"], "open_mix")
            self.assertEqual(len(identity["open_mix_members"]), 2)
            group = build_comparisons(fixture.results)["groups"][0]
            self.assertEqual(group["verdict"], "N/A")


if __name__ == "__main__":
    unittest.main()
