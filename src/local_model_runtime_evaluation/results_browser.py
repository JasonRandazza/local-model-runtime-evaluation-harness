"""Read-only evidence interpretation boundary for sealed managed run bundles.

This module discovers evidence bundles beneath a results root, classifies
their health, and builds plain-dict view models for an index page and a
per-run detail page. It never writes evidence, never contacts a runtime or
network, and never emits HTML — rendering is a separate concern. All
checksum, state, and schema semantics are delegated to `EvidenceBundle` and
`ManagedRunPlan`; nothing here re-implements or re-derives them.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from .evidence_bundle import EvidenceBundle, EvidenceError
from .managed_run_types import MANAGED_PLAN_SCHEMA_VERSION, ManagedRunPlan, ManagedRunState
from .run_identity import SAFE_RUN_ID


SUPPORTED_PLAN_SCHEMA_VERSION = MANAGED_PLAN_SCHEMA_VERSION

HEALTH_SEALED_VERIFIED = "SEALED_VERIFIED"
HEALTH_SEALED_CORRUPT = "SEALED_CORRUPT"
HEALTH_UNSEALED = "UNSEALED"
HEALTH_UNSUPPORTED_SCHEMA = "UNSUPPORTED_SCHEMA"
HEALTH_UNREADABLE = "UNREADABLE"
HEALTH_UNRECOGNIZED = "UNRECOGNIZED"

_DEGRADED_HEALTHS = frozenset(
    {HEALTH_UNRECOGNIZED, HEALTH_UNREADABLE, HEALTH_UNSUPPORTED_SCHEMA}
)

_POLICY_ALLOWLIST = (
    "policy_id",
    "schema_version",
    "authorization_mode",
    "loopback_only",
    "allowed_runtimes",
    "allow_inference",
    "allow_start",
    "allow_exact_reclaim",
    "reclaim_grace_seconds",
    "allow_terminate_after_interrupt",
    "allow_force_kill",
    "allow_provider_edits",
    "max_parallel_models",
    "memory_floor_percent",
    "max_run_minutes",
    "max_requests_per_run",
    "expires_at",
)

_ATTEMPT_FILENAME = re.compile(r"attempt-(\d+)\.json")
_REPORT_SUFFIXES = (".md", ".json")


def _load_json(path: Path) -> dict | None:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return raw if isinstance(raw, dict) else None


def classify_bundle(run_dir: Path) -> tuple[str, str]:
    """Return (health, detail). detail is '' for healthy, else 'code: message'."""
    if not run_dir.is_dir() or not SAFE_RUN_ID.fullmatch(run_dir.name):
        return (
            HEALTH_UNRECOGNIZED,
            "unrecognized_run_dir: name does not match the safe run-id pattern",
        )
    plan_path = run_dir / "plan.json"
    if not plan_path.is_file():
        return HEALTH_UNREADABLE, "evidence_file_missing: managed run plan is missing"
    raw_plan = _load_json(plan_path)
    if raw_plan is None:
        return HEALTH_UNREADABLE, "evidence_plan_invalid: managed run plan is invalid"
    schema_version = raw_plan.get("schema_version")
    if schema_version != SUPPORTED_PLAN_SCHEMA_VERSION:
        return (
            HEALTH_UNSUPPORTED_SCHEMA,
            "plan_schema_unsupported: expected "
            f"{SUPPORTED_PLAN_SCHEMA_VERSION}, found {schema_version!r}",
        )
    try:
        bundle = EvidenceBundle.load(run_dir)
        state = bundle.state
    except EvidenceError as error:
        return HEALTH_UNREADABLE, f"{error.code}: {error}"
    if not state.sealed:
        return HEALTH_UNSEALED, ""
    try:
        bundle.verify()
    except EvidenceError as error:
        return HEALTH_SEALED_CORRUPT, f"{error.code}: {error}"
    return HEALTH_SEALED_VERIFIED, ""


def _index_entry(run_dir: Path) -> dict:
    health, detail = classify_bundle(run_dir)
    entry: dict = {
        "run_dir_name": run_dir.name,
        "health": health,
        "health_detail": detail,
        "run_name": None,
        "run_id": None,
        "comparison_id": None,
        "family_id": None,
        "recipe_id": None,
        "attempt": None,
        "run_status": None,
        "created_at": None,
    }
    if health == HEALTH_UNRECOGNIZED:
        return entry
    try:
        bundle = EvidenceBundle.load(run_dir)
    except EvidenceError:
        return entry
    plan = bundle.plan
    entry.update(
        run_name=plan.identity.run_name,
        run_id=plan.identity.run_id,
        comparison_id=plan.identity.comparison_id,
        family_id=plan.family_id,
        recipe_id=plan.recipe_id,
        created_at=plan.created_at,
    )
    try:
        state = bundle.state
        entry["attempt"] = state.attempt
        entry["run_status"] = state.summary_state.value
    except EvidenceError:
        pass
    return entry


def build_index(results_root: Path) -> dict:
    """{"results_root", "missing_root", "entries": [...]}. Never raises."""
    if not results_root.is_dir():
        return {
            "results_root": str(results_root),
            "missing_root": True,
            "entries": [],
        }
    entries = [_index_entry(child) for child in results_root.iterdir()]
    # Two stable sorts: tiebreak first (run_dir_name desc), then the primary
    # key (created_at desc, with the None -> "" proxy sorting last).
    entries.sort(key=lambda entry: entry["run_dir_name"], reverse=True)
    entries.sort(key=lambda entry: entry["created_at"] or "", reverse=True)
    return {
        "results_root": str(results_root),
        "missing_root": False,
        "entries": entries,
    }


def _identity_dict(plan: ManagedRunPlan) -> dict:
    return {
        "run_name": plan.identity.run_name,
        "run_id": plan.identity.run_id,
        "comparison_id": plan.identity.comparison_id,
        "parent_run_id": plan.identity.parent_run_id,
        "attempt": plan.identity.attempt,
        "family_id": plan.family_id,
        "recipe_id": plan.recipe_id,
        "matrix_mode": plan.matrix_mode,
        "schema_version": plan.schema_version,
        "plan_hash": plan.plan_hash,
        "created_at": plan.created_at,
        "request_count": plan.request_count,
        "estimated_minutes": plan.estimated_minutes,
        "runtimes": sorted(plan.runtimes),
        "endpoints": list(plan.endpoints),
        "cell_ids": list(plan.cell_ids),
        "pair_ids": list(plan.pair_ids),
    }


def _read_policy(run_dir: Path) -> dict | None:
    raw = _load_json(run_dir / "policy-snapshot.json")
    if raw is None:
        return None
    policy = raw.get("policy")
    if not isinstance(policy, dict):
        return None
    view = {key: policy[key] for key in _POLICY_ALLOWLIST if key in policy}
    # Adoption identity lives beside the policy body in the snapshot.
    for key in ("policy_hash", "adopted_at"):
        if isinstance(raw.get(key), str):
            view[key] = raw[key]
    return view


def _read_summary(run_dir: Path) -> dict | None:
    return _load_json(run_dir / "summary.json")


def _steps_list(run_dir: Path, state: ManagedRunState) -> list:
    steps = []
    for record in state.steps:
        has_output_dir = False
        report_files: list[str] = []
        if record.output_path:
            output_dir = run_dir / record.output_path
            if output_dir.is_dir():
                has_output_dir = True
                report_files = sorted(
                    path.name
                    for path in output_dir.iterdir()
                    if path.is_file() and path.suffix in _REPORT_SUFFIXES
                )
        steps.append(
            {
                "step": record.step.value,
                "state": record.state.value,
                "attempt": record.attempt,
                "output_path": record.output_path,
                "has_output_dir": has_output_dir,
                "report_files": report_files,
            }
        )
    return steps


def _attempts_list(run_dir: Path) -> list:
    attempts_dir = run_dir / "attempts"
    if not attempts_dir.is_dir():
        return []
    results = []
    for path in sorted(attempts_dir.glob("attempt-*.json")):
        match = _ATTEMPT_FILENAME.fullmatch(path.name)
        if match is None:
            continue
        number = int(match.group(1))
        raw = _load_json(path)
        state_raw = raw.get("state") if raw is not None else None
        summary_raw = raw.get("summary") if raw is not None else None
        step_records = state_raw.get("steps") if isinstance(state_raw, dict) else None
        if (
            raw is None
            or not isinstance(summary_raw, dict)
            or not isinstance(step_records, list)
        ):
            results.append({"attempt": number, "error": "attempt snapshot is invalid"})
            continue
        try:
            steps = [
                {"step": s["step"], "state": s["state"], "attempt": s["attempt"]}
                for s in step_records
            ]
        except (KeyError, TypeError):
            results.append({"attempt": number, "error": "attempt snapshot step is invalid"})
            continue
        results.append(
            {
                "attempt": number,
                "status": summary_raw.get("status"),
                "steps": steps,
                "has_checksums": isinstance(raw.get("checksums_sha256"), str),
            }
        )
    return results


def _lifecycle_summary(run_dir: Path) -> dict:
    path = run_dir / "lifecycle.jsonl"
    leases: dict[str, dict] = {}
    unparsed = 0
    if path.is_file():
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                unparsed += 1
                continue
            if not isinstance(entry, dict):
                unparsed += 1
                continue
            action = entry.get("action")
            payload = entry.get("payload")
            runtime = entry.get("runtime")
            if (
                not isinstance(action, str)
                or not isinstance(payload, dict)
                or not isinstance(runtime, str)
            ):
                unparsed += 1
                continue
            if action not in ("lease_acquired", "released", "untouched"):
                # Valid journal entry that carries no lease ownership data
                # (initial_observation, start_requested, ...). Not a parse
                # failure; leases alone drive the ownership summary.
                continue
            lease_id = payload.get("lease_id")
            if not isinstance(lease_id, str) or not lease_id:
                unparsed += 1
                continue
            if action == "lease_acquired":
                ownership = payload.get("ownership")
                if not isinstance(ownership, str):
                    unparsed += 1
                    continue
                lease = leases.setdefault(
                    lease_id,
                    {
                        "runtime": runtime,
                        "lease_id": lease_id,
                        "ownership": ownership,
                        "terminal_action": "unresolved",
                    },
                )
                lease["runtime"] = runtime
                lease["ownership"] = ownership
            else:
                lease = leases.setdefault(
                    lease_id,
                    {
                        "runtime": runtime,
                        "lease_id": lease_id,
                        "ownership": "unresolved",
                        "terminal_action": "unresolved",
                    },
                )
                lease["terminal_action"] = action
    return {
        "leases": sorted(leases.values(), key=lambda lease: lease["lease_id"]),
        "unparsed_lines": unparsed,
    }


def _step_reports(run_dir: Path, state: ManagedRunState) -> dict:
    reports: dict[str, str] = {}
    for record in state.steps:
        if not record.output_path:
            continue
        report_path = run_dir / record.output_path / "report.md"
        if report_path.is_file():
            try:
                reports[record.step.value] = report_path.read_text(encoding="utf-8")
            except OSError:
                continue
    return reports


def build_run_view(run_dir: Path) -> dict:
    """Build the full per-run view model. Never raises; fails closed."""
    health, detail = classify_bundle(run_dir)
    view: dict = {
        "run_dir_name": run_dir.name,
        "health": health,
        "health_detail": detail,
        "identity": None,
        "policy": None,
        "summary": None,
        "steps": None,
        "attempts": [],
        "lifecycle": {"leases": [], "unparsed_lines": 0},
        "step_reports": {},
    }
    if health in _DEGRADED_HEALTHS:
        return view

    try:
        bundle = EvidenceBundle.load(run_dir)
    except EvidenceError:
        return view

    view["identity"] = _identity_dict(bundle.plan)
    view["policy"] = _read_policy(run_dir)
    view["summary"] = _read_summary(run_dir)

    state: ManagedRunState | None
    try:
        state = bundle.state
    except EvidenceError:
        state = None
    if state is not None:
        view["steps"] = _steps_list(run_dir, state)

    view["attempts"] = _attempts_list(run_dir)
    view["lifecycle"] = _lifecycle_summary(run_dir)

    if health == HEALTH_SEALED_VERIFIED and state is not None:
        view["step_reports"] = _step_reports(run_dir, state)

    return view
