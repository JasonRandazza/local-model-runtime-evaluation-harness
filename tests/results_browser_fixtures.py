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

_PREFERENCE_REPORT = """# Preference tally

Family: `fake-family-1b`

Latency was not used for preference scoring.
"""

_RAG_ORACLE_REPORT = """# RAG oracle score

Family: `fake-family-1b`

Mode: `oracle`

Latency was not used for RAG scoring.
"""

_RAG_KEYWORD_REPORT = """# RAG keyword score

Family: `fake-family-1b`

Mode: `keyword`

Latency was not used for RAG scoring.
"""


def _make_bundle(
    root: Path,
    *,
    run_name: str,
    entropy: str,
    now: datetime,
    comparison_id: str | None = None,
    family_id: str = FAMILY_ID,
) -> EvidenceBundle:
    results_root = root / "results"
    state_root = root / ".lmre"
    adopted = adopt_policy(POLICY, state_root, now=now)
    plan = build_plan(
        RECIPE,
        family_id=family_id,
        run_name=run_name,
        comparison_id=comparison_id,
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
    raw: dict,
    filename: str = "raw.json",
) -> str:
    output_dir = bundle.step_attempt_dir(step, attempt)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "report.md").write_text(report_md, encoding="utf-8")
    (output_dir / filename).write_text(json.dumps(raw), encoding="utf-8")
    return output_dir.relative_to(bundle.run_dir).as_posix()


def _matrix_raw(bundle: EvidenceBundle) -> dict:
    return {
        "schema_version": "matrix-campaign-1.0.0",
        "cells": [
            {
                "cell_id": cell_id,
                "family_id": bundle.plan.family_id,
                "status": "PASS",
                "na_reason": None,
                "summary": {
                    "median_total_seconds": 1.25 + index,
                    "median_ttft_seconds": 0.2 + index,
                    "success_count": 9,
                    "contract_pass_count": 9,
                    "measured_count": 9,
                },
            }
            for index, cell_id in enumerate(bundle.plan.cell_ids)
        ],
    }


def _overhead_raw(bundle: EvidenceBundle) -> dict:
    return {
        "schema_version": "overhead-run-1.0.0",
        "pairs": [
            {
                "pair_id": pair_id,
                "family_id": bundle.plan.family_id,
                "direct": {
                    "status": "PASS",
                    "summary": {
                        "median_total_seconds": 2.0 + index,
                        "median_ttft_seconds": 0.4 + index,
                    },
                },
                "routed": {
                    "status": "PASS",
                    "summary": {
                        "median_total_seconds": 2.3 + index,
                        "median_ttft_seconds": 0.6 + index,
                    },
                },
            }
            for index, pair_id in enumerate(bundle.plan.pair_ids)
        ],
    }


def _preference_raw(bundle: EvidenceBundle) -> dict:
    total_judgments = len(bundle.plan.cell_ids) + 4
    cells = {}
    for index, cell_id in enumerate(bundle.plan.cell_ids):
        wins = index + 1
        losses = total_judgments - wins
        ties = 0
        rows = wins + losses
        win_rate = round(wins / rows, 3) if rows else None
        cells[cell_id] = {
            "wins": wins,
            "losses": losses,
            "ties": ties,
            "win_rate": win_rate,
        }
    return {
        "schema_version": "preference-campaign-1.0.0",
        "run_id": bundle.plan.identity.run_id,
        "suite_id": None,
        "cells": cells,
    }


def _rag_raw(
    bundle: EvidenceBundle, *, mode: str, recall_offset: float = 0.25
) -> dict:
    prompts = {
        "prompt-1": {"hits": 3, "total": 4},
        "prompt-2": {"hits": 2, "total": 4},
    }
    cells = {}
    for index, cell_id in enumerate(bundle.plan.cell_ids):
        hit_rate = round(0.8 + 0.05 * (index + 1), 3)
        recall = round(recall_offset + 0.05 * (index + 1), 3)
        precision = round(recall_offset + 0.02 * (index + 1), 3)
        cells[cell_id] = {
            "mean_hit_rate": hit_rate,
            "prompts": prompts,
        }
        if mode == "keyword":
            cells[cell_id]["mean_recall"] = recall
            cells[cell_id]["mean_precision"] = precision
    return {
        "schema_version": "rag-campaign-1.0.0",
        "run_id": bundle.plan.identity.run_id,
        "suite_id": None,
        "mode": mode,
        "cells": cells,
    }


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
    comparison_id: str | None = None,
    family_id: str = FAMILY_ID,
    structured_metrics: bool = True,
) -> EvidenceBundle:
    bundle = _make_bundle(
        root,
        run_name=run_name,
        entropy=entropy,
        now=now,
        comparison_id=comparison_id,
        family_id=family_id,
    )
    for step in bundle.plan.steps:
        bundle.transition_step(step, StepState.RUNNING)
        output_path = None
        if step is ManagedStep.MATRIX:
            raw = (
                _matrix_raw(bundle)
                if structured_metrics
                else {"family": "fake-family-1b", "stub": True}
            )
            output_path = _write_output(bundle, step, 1, _MATRIX_REPORT, raw)
        elif step is ManagedStep.OVERHEAD:
            raw = (
                _overhead_raw(bundle)
                if structured_metrics
                else {"family": "fake-family-1b", "stub": True}
            )
            output_path = _write_output(bundle, step, 1, _OVERHEAD_REPORT, raw)
        elif step is ManagedStep.PREFERENCE:
            raw = (
                _preference_raw(bundle)
                if structured_metrics
                else {"family": "fake-family-1b", "stub": True}
            )
            output_path = _write_output(
                bundle, step, 1, _PREFERENCE_REPORT, raw, filename="tally.json"
            )
        elif step is ManagedStep.RAG_ORACLE:
            raw = _rag_raw(bundle, mode="oracle")
            output_path = _write_output(
                bundle, step, 1, _RAG_ORACLE_REPORT, raw, filename="scores.json"
            )
        elif step is ManagedStep.RAG_KEYWORD:
            raw = _rag_raw(bundle, mode="keyword", recall_offset=0.25)
            output_path = _write_output(
                bundle, step, 1, _RAG_KEYWORD_REPORT, raw, filename="scores.json"
            )
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


def make_sealed_pass(
    root: Path,
    *,
    run_name: str = "fixture-sealed-pass",
    entropy: str = "aaaaaa",
    now: datetime | None = None,
    comparison_id: str | None = None,
    family_id: str = FAMILY_ID,
    structured_metrics: bool = True,
) -> Path:
    bundle = _build_full_pass(
        root,
        run_name=run_name,
        entropy=entropy,
        now=now or datetime(2026, 7, 31, 4, 0, tzinfo=timezone.utc),
        comparison_id=comparison_id,
        family_id=family_id,
        structured_metrics=structured_metrics,
    )
    return bundle.run_dir


def make_pending_plan(
    root: Path,
    *,
    run_name: str = "fixture-pending-plan",
    entropy: str = "ababab",
    comparison_id: str | None = None,
) -> Path:
    bundle = _make_bundle(
        root,
        run_name=run_name,
        entropy=entropy,
        now=datetime(2026, 7, 31, 4, 30, tzinfo=timezone.utc),
        comparison_id=comparison_id,
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
            _write_output(bundle, step, 1, _MATRIX_REPORT, _matrix_raw(bundle))
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


def make_unsealed_running(
    root: Path, *, comparison_id: str | None = None
) -> Path:
    bundle = _make_bundle(
        root,
        run_name="fixture-unsealed-running",
        entropy="cccccc",
        now=datetime(2026, 7, 31, 2, 0, tzinfo=timezone.utc),
        comparison_id=comparison_id,
    )
    bundle.transition_step(ManagedStep.PREFLIGHT, StepState.RUNNING)
    bundle.transition_step(ManagedStep.PREFLIGHT, StepState.PASS)
    bundle.transition_step(ManagedStep.MATRIX, StepState.RUNNING)
    return bundle.run_dir


def make_corrupt(root: Path, *, comparison_id: str | None = None) -> Path:
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
        comparison_id=comparison_id,
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
