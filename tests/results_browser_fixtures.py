"""Synthetic evidence bundle builders for results_browser tests.

Every builder constructs its bundle through the real `EvidenceBundle` /
`ManagedRunPlan` / `build_plan` / `adopt_policy` APIs (mirroring
tests/test_evidence_bundle.py), never by hand-authoring a fake plan shape.
All model names, prompts, and paths are synthetic; nothing here is a real
credential, response, or machine-specific absolute path.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from local_model_runtime_evaluation.evidence_bundle import EvidenceBundle
from local_model_runtime_evaluation.managed_run_types import ManagedStep, StepState
from local_model_runtime_evaluation.operator_policy import adopt_policy
from local_model_runtime_evaluation.run_identity import build_plan
from tests.artifact_profile_fixtures import write_machine_profile


ROOT = Path(__file__).resolve().parents[1]
RECIPE = ROOT / "config" / "managed-runs" / "complete-native-quality-v1.json"
POLICY = ROOT / "config" / "operator-policies" / "local-managed-v1.example.json"
FAMILY_ID = "gemma-4-12b-qat"

_MATRIX_REPORT = """# Matrix screen report

Family: `fake-family-1b`

| Cell | Status | Median total |
|---|---|---|
| fake-cell-a | PASS | 1.23s |
| fake-cell-b | PASS | 1.45s |
"""

_OVERHEAD_REPORT = """# Osaurus routing overhead

| Pair | Direct median total | Routed median total | Status | est. tokens |
|---|---|---|---|---|
| fake-pair-1 | 1.10s | 1.30s | PASS | est. 128 tokens |
| fake-pair-2 (optiq) | — | — | N/A (optiq pair skipped: port busy) | — |
"""


def _make_bundle(
    root: Path,
    *,
    run_name: str,
    entropy: str,
    now: datetime,
) -> EvidenceBundle:
    results_root = root / "results"
    state_root = root / ".lmre"
    adopted = adopt_policy(POLICY, state_root, now=now)
    plan = build_plan(
        RECIPE,
        family_id=FAMILY_ID,
        run_name=run_name,
        comparison_id=None,
        parent_run_id=None,
        results_root=results_root,
        now=now,
        entropy=entropy,
        machine_profile_path=write_machine_profile(root / "machine-profile"),
    )
    return EvidenceBundle.create(
        results_root,
        plan,
        adopted,
        {"platform": "macOS", "python": "3.11"},
    )


def _write_output(
    bundle: EvidenceBundle,
    step: ManagedStep,
    attempt: int,
    report_md: str,
) -> str:
    output_dir = bundle.step_attempt_dir(step, attempt)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "report.md").write_text(report_md, encoding="utf-8")
    (output_dir / "raw.json").write_text(
        json.dumps({"family": "fake-family-1b", "stub": True}),
        encoding="utf-8",
    )
    return output_dir.relative_to(bundle.run_dir).as_posix()


def _add_lifecycle_pair(bundle: EvidenceBundle) -> None:
    bundle.append_lifecycle(
        "omlx",
        "lease_acquired",
        {"lease_id": "lease-owned", "ownership": "owned"},
    )
    bundle.append_lifecycle(
        "osaurus",
        "lease_acquired",
        {"lease_id": "lease-attached", "ownership": "attached"},
    )
    bundle.append_lifecycle(
        "omlx",
        "released",
        {"lease_id": "lease-owned"},
    )
    bundle.append_lifecycle(
        "osaurus",
        "untouched",
        {"lease_id": "lease-attached"},
    )


def _build_full_pass(
    root: Path,
    *,
    run_name: str,
    entropy: str,
    now: datetime,
) -> EvidenceBundle:
    bundle = _make_bundle(root, run_name=run_name, entropy=entropy, now=now)
    for step in bundle.plan.steps:
        bundle.transition_step(step, StepState.RUNNING)
        output_path = None
        if step is ManagedStep.MATRIX:
            output_path = _write_output(bundle, step, 1, _MATRIX_REPORT)
        elif step is ManagedStep.OVERHEAD:
            output_path = _write_output(bundle, step, 1, _OVERHEAD_REPORT)
        bundle.transition_step(step, StepState.PASS, output_path=output_path)
    _add_lifecycle_pair(bundle)
    bundle.mark_cleanup_complete()
    bundle.write_summary(
        {
            "attempt": 1,
            "comparison_id": bundle.plan.identity.comparison_id,
            "run_id": bundle.plan.identity.run_id,
            "run_name": bundle.plan.identity.run_name,
            "status": "PASS",
            "completed_native_steps_valid": True,
        }
    )
    bundle.seal()
    return bundle


def make_sealed_pass(root: Path) -> Path:
    bundle = _build_full_pass(
        root,
        run_name="fixture-sealed-pass",
        entropy="aaaaaa",
        now=datetime(2026, 7, 31, 4, 0, tzinfo=timezone.utc),
    )
    return bundle.run_dir


def make_partial_blocked_with_attempts(root: Path) -> Path:
    bundle = _make_bundle(
        root,
        run_name="fixture-partial-blocked",
        entropy="bbbbbb",
        now=datetime(2026, 7, 31, 3, 0, tzinfo=timezone.utc),
    )
    for step in bundle.plan.steps:
        if step is ManagedStep.OVERHEAD:
            continue
        bundle.transition_step(step, StepState.RUNNING)
        output_path = (
            _write_output(bundle, step, 1, _MATRIX_REPORT)
            if step is ManagedStep.MATRIX
            else None
        )
        bundle.transition_step(step, StepState.PASS, output_path=output_path)
    bundle.transition_step(ManagedStep.OVERHEAD, StepState.RUNNING)
    bundle.transition_step(
        ManagedStep.OVERHEAD,
        StepState.BLOCKED_PROVIDER_RECONNECT,
        detail={"missing_routed_model_ids": ["omlx/fake-family-1b"]},
    )
    _add_lifecycle_pair(bundle)
    bundle.mark_cleanup_complete()
    bundle.write_summary(
        {
            "attempt": 1,
            "comparison_id": bundle.plan.identity.comparison_id,
            "run_id": bundle.plan.identity.run_id,
            "run_name": bundle.plan.identity.run_name,
            "status": "PARTIAL_BLOCKED",
            "missing_routed_model_ids": ["omlx/fake-family-1b"],
        }
    )
    bundle.seal()

    # Resume through the real begin_attempt flow: attempt 1 becomes the
    # preserved attempts/attempt-001.json snapshot, overhead resets to
    # PENDING under attempt 2, then is blocked again to land at attempt >= 2.
    bundle.begin_attempt()
    bundle.transition_step(ManagedStep.OVERHEAD, StepState.RUNNING)
    bundle.transition_step(
        ManagedStep.OVERHEAD,
        StepState.BLOCKED_PROVIDER_RECONNECT,
        detail={"missing_routed_model_ids": ["omlx/fake-family-1b"]},
    )
    bundle.mark_cleanup_complete()
    bundle.write_summary(
        {
            "attempt": 2,
            "comparison_id": bundle.plan.identity.comparison_id,
            "run_id": bundle.plan.identity.run_id,
            "run_name": bundle.plan.identity.run_name,
            "status": "PARTIAL_BLOCKED",
            "missing_routed_model_ids": ["omlx/fake-family-1b"],
        }
    )
    bundle.seal()
    return bundle.run_dir


def make_unsealed_running(root: Path) -> Path:
    bundle = _make_bundle(
        root,
        run_name="fixture-unsealed-running",
        entropy="cccccc",
        now=datetime(2026, 7, 31, 2, 0, tzinfo=timezone.utc),
    )
    bundle.transition_step(ManagedStep.PREFLIGHT, StepState.RUNNING)
    bundle.transition_step(ManagedStep.PREFLIGHT, StepState.PASS)
    bundle.transition_step(ManagedStep.MATRIX, StepState.RUNNING)
    return bundle.run_dir


def make_corrupt(root: Path) -> Path:
    # ponytail: reuse the shared full-pass builder (own entropy so this can
    # coexist with make_sealed_pass in the same root) rather than
    # duplicating the transition flow, then tamper bytes directly
    # (bypassing the sealed-immutability guard, exactly like
    # test_evidence_bundle.test_seal_then_verify_detects_tampering).
    bundle = _build_full_pass(
        root,
        run_name="fixture-corrupt",
        entropy="dddddd",
        now=datetime(2026, 7, 31, 0, 30, tzinfo=timezone.utc),
    )
    summary_path = bundle.run_dir / "summary.json"
    summary_path.write_text('{"status":"FAIL"}\n', encoding="utf-8")
    return bundle.run_dir


def make_missing_plan(root: Path) -> Path:
    results_root = root / "results"
    run_dir = results_root / "run-20260731-000000-eeeeee"
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def make_unsupported_schema(root: Path) -> Path:
    bundle = _make_bundle(
        root,
        run_name="fixture-unsupported-schema",
        entropy="ffffff",
        now=datetime(2026, 7, 31, 1, 0, tzinfo=timezone.utc),
    )
    plan_path = bundle.run_dir / "plan.json"
    raw = json.loads(plan_path.read_text(encoding="utf-8"))
    raw["schema_version"] = "9.9.9"
    # plan_hash now mismatches the edited content; that is fine because the
    # raw schema_version check in classify_bundle runs before EvidenceBundle
    # .load ever re-verifies the hash.
    plan_path.write_text(json.dumps(raw, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return bundle.run_dir
