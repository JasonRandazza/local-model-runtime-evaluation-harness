from __future__ import annotations

import json
import shutil
import socket
import subprocess
import unittest
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from local_model_runtime_evaluation.evidence_bundle import EvidenceBundle
from local_model_runtime_evaluation.managed_run import execute_managed_run
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
        for name in ("qwen_mxfp4__osaurus", "ornith_oq4__omlx"):
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
            (self.local_models / "Qwen3.6-35B-A3B-MXFP4-MTP").mkdir(
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
                    "cell_id": "qwen_mxfp4__osaurus",
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
                ("qwen_mxfp4__osaurus", "ornith_oq4__omlx"),
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
                        "cell_id": "qwen_mxfp4__osaurus",
                    },
                    {
                        "family_id": "qwen36-35b-a3b",
                        "cell_id": "qwen_mxfp4__osaurus",
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
                        "cell_id": "qwen_mxfp4__osaurus",
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

            shutil.rmtree(fixture.local_models / "Qwen3.6-35B-A3B-MXFP4-MTP")
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

    def test_live_execution_refuses_before_using_runtime_dependencies(self) -> None:
        with TemporaryDirectory() as tmp:
            fixture = OpenMixFixture(Path(tmp)).create()
            plan = fixture.plan()
            with self.assertRaisesRegex(RuntimeError, "not implemented"):
                execute_managed_run(  # type: ignore[arg-type]
                    plan,
                    None,
                    None,
                    None,
                    None,
                    machine_profile_path=fixture.profile,
                )

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
