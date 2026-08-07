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
from .managed_run_types import (
    SUPPORTED_MANAGED_PLAN_SCHEMA_VERSIONS,
    ManagedRunPlan,
    ManagedRunState,
    ManagedStep,
)
from .run_identity import SAFE_RUN_ID

SUPPORTED_PLAN_SCHEMA_VERSIONS = SUPPORTED_MANAGED_PLAN_SCHEMA_VERSIONS

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

# The shape sanitize_run_name guarantees at plan build. Re-validated here so
# a tampered or legacy comparison_id can never become an unsafe filename or
# invent a group.
SAFE_COMPARISON_ID = re.compile(r"[a-z0-9][a-z0-9-]{0,79}")

VERDICT_COMPARABLE = "COMPARABLE"
VERDICT_INCOMPARABLE = "INCOMPARABLE"
VERDICT_NOT_APPLICABLE = "N/A"

# Portable immutable plan dimensions, in the fixed order used for mismatch
# reasons. Machine paths (campaign_path, suite_paths, *_root, rag_corpus_path)
# are deliberately absent: input_hashes is the portable content identity.
_COMPARISON_DIMENSIONS = (
    "schema_version",
    "comparison_scope",
    "family_id",
    "recipe_id",
    "comparison_class_id",
    "binding_id",
    "binding_hash",
    "binding_proposal_hash",
    "open_mix_id",
    "open_mix_revision",
    "open_mix_hash",
    "open_mix_members",
    "suite_contract_id",
    "suite_contract_revision",
    "suite_contract_hash",
    "matrix_mode",
    "steps",
    "cell_ids",
    "pair_ids",
    "input_hashes",
)


def _load_json(path: Path) -> dict | None:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        # ValueError covers both JSONDecodeError and UnicodeDecodeError so a
        # single bad byte degrades one row instead of aborting the index.
        return None
    return raw if isinstance(raw, dict) else None


def classify_bundle(run_dir: Path) -> tuple[str, str]:
    """Return (health, detail). detail is '' for healthy, else 'code: message'."""
    if run_dir.is_symlink():
        # Never follow symlinks: a link named like a run could otherwise
        # publish files from outside the results root.
        return (
            HEALTH_UNRECOGNIZED,
            "unrecognized_run_dir: symlinked entries are not followed",
        )
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
    if schema_version not in SUPPORTED_PLAN_SCHEMA_VERSIONS:
        expected_versions = ", ".join(sorted(SUPPORTED_PLAN_SCHEMA_VERSIONS))
        return (
            HEALTH_UNSUPPORTED_SCHEMA,
            "plan_schema_unsupported: expected one of "
            f"{expected_versions}, found {schema_version!r}",
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
        "comparison_class_id": None,
        "binding_id": None,
        "open_mix_id": None,
        "suite_contract_id": None,
        "attempt": None,
        "run_status": None,
        "created_at": None,
    }
    if health in _DEGRADED_HEALTHS:
        # Mirror build_run_view's fail-closed gate: no identity or status is
        # shown for bundles the browser has refused to vet.
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
        comparison_class_id=plan.comparison_class_id,
        binding_id=plan.binding_id,
        open_mix_id=plan.open_mix_id,
        suite_contract_id=plan.suite_contract_id,
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
        "comparison_scope": plan.comparison_scope,
        "recipe_id": plan.recipe_id,
        "comparison_class_id": plan.comparison_class_id,
        "binding_id": plan.binding_id,
        "binding_revision": plan.binding_revision,
        "binding_hash": plan.binding_hash,
        "binding_proposal_hash": plan.binding_proposal_hash,
        "open_mix_id": plan.open_mix_id,
        "open_mix_revision": plan.open_mix_revision,
        "open_mix_hash": plan.open_mix_hash,
        "open_mix_members": [
            f"{family_id}/{cell_id}"
            for family_id, cell_id in plan.open_mix_members
        ],
        "suite_contract_id": plan.suite_contract_id,
        "suite_contract_revision": plan.suite_contract_revision,
        "suite_contract_hash": plan.suite_contract_hash,
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
            results.append(
                {"attempt": number, "error": "attempt snapshot step is invalid"}
            )
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
    leases: dict[tuple[int, str], dict] = {}
    unparsed = 0
    try:
        text = path.read_text(encoding="utf-8") if path.is_file() else ""
    except (OSError, UnicodeDecodeError):
        return {"leases": [], "unparsed_lines": 1}
    if text:
        for line in text.splitlines():
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
            attempt = entry.get("attempt")
            if type(attempt) is not int or attempt < 1:
                unparsed += 1
                continue
            lease_key = (attempt, lease_id)
            if action == "lease_acquired":
                ownership = payload.get("ownership")
                if not isinstance(ownership, str):
                    unparsed += 1
                    continue
                lease = leases.setdefault(
                    lease_key,
                    {
                        "attempt": attempt,
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
                    lease_key,
                    {
                        "attempt": attempt,
                        "runtime": runtime,
                        "lease_id": lease_id,
                        "ownership": "unresolved",
                        "terminal_action": "unresolved",
                    },
                )
                lease["terminal_action"] = action
    return {
        "leases": sorted(
            leases.values(),
            key=lambda lease: (lease["attempt"], lease["lease_id"]),
        ),
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
            except (OSError, UnicodeDecodeError):
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


def _plan_dimensions(plan: ManagedRunPlan) -> dict:
    return {
        "schema_version": plan.schema_version,
        "comparison_scope": plan.comparison_scope,
        "family_id": plan.family_id,
        "recipe_id": plan.recipe_id,
        "comparison_class_id": plan.comparison_class_id,
        "binding_id": plan.binding_id,
        "binding_hash": plan.binding_hash,
        "binding_proposal_hash": plan.binding_proposal_hash,
        "open_mix_id": plan.open_mix_id,
        "open_mix_revision": plan.open_mix_revision,
        "open_mix_hash": plan.open_mix_hash,
        "open_mix_members": [
            {"family_id": family_id, "cell_id": cell_id}
            for family_id, cell_id in plan.open_mix_members
        ],
        "suite_contract_id": plan.suite_contract_id,
        "suite_contract_revision": plan.suite_contract_revision,
        "suite_contract_hash": plan.suite_contract_hash,
        "matrix_mode": plan.matrix_mode,
        "steps": [step.value for step in plan.steps],
        "cell_ids": list(plan.cell_ids),
        "pair_ids": list(plan.pair_ids),
        "input_hashes": dict(plan.input_hashes),
    }


_EXCLUSION_REASONS = {
    HEALTH_SEALED_CORRUPT: ("excluded: sealed but failed checksum verification"),
    HEALTH_UNSEALED: "excluded: bundle is not sealed",
}

# Fixed reason strings for unattributed_exclusions records. Never
# interpolate health_detail or other bundle-derived text into a reason: a
# degraded bundle's own content must never reach the comparisons view.
_UNATTRIBUTED_REASONS = {
    HEALTH_UNREADABLE: "unreadable_bundle",
    HEALTH_UNSUPPORTED_SCHEMA: "unsupported_schema",
    HEALTH_UNRECOGNIZED: "unrecognized_entry",
}
_MALFORMED_COMPARISON_ID_REASON = "malformed_comparison_id"

_UNATTRIBUTED_PLACEHOLDER = "(unrecognized entry)"

METRICS_AVAILABLE = "AVAILABLE"
METRICS_UNAVAILABLE = "UNAVAILABLE"
METRICS_NOT_APPLICABLE = "N/A"


def _unattributed_record(health: str, raw_run_dir_name: str, reason: str) -> dict:
    display_name = (
        raw_run_dir_name
        if SAFE_RUN_ID.fullmatch(raw_run_dir_name)
        else _UNATTRIBUTED_PLACEHOLDER
    )
    return {"run_dir_name": display_name, "health": health, "reason": reason}


def _step_raw_json(
    run_dir: Path, state: ManagedRunState, step: ManagedStep
) -> dict | None:
    """Read one checksummed collector raw file without leaving the bundle."""
    record = next((item for item in state.steps if item.step is step), None)
    if record is None or not record.output_path:
        return None
    raw_path = run_dir / record.output_path / "raw.json"
    try:
        if raw_path.is_symlink() or not raw_path.resolve().is_relative_to(
            run_dir.resolve()
        ):
            return None
    except OSError:
        return None
    return _load_json(raw_path)


def _summary_values(raw: object) -> dict | None:
    summary = raw.get("summary") if isinstance(raw, dict) else None
    if not isinstance(summary, dict):
        return None
    values = {
        key: summary.get(key)
        for key in (
            "median_total_seconds",
            "median_ttft_seconds",
            "success_count",
            "contract_pass_count",
            "measured_count",
        )
    }
    if any(
        value is not None
        and (isinstance(value, bool) or not isinstance(value, (int, float)))
        for value in values.values()
    ):
        return None
    return values


def _matrix_metric_rows(raw: dict | None, plan: ManagedRunPlan) -> list[dict] | None:
    cells = raw.get("cells") if isinstance(raw, dict) else None
    if not isinstance(cells, list):
        return None
    by_id: dict[str, dict] = {}
    for cell in cells:
        cell_id = cell.get("cell_id") if isinstance(cell, dict) else None
        if not isinstance(cell_id, str) or cell_id in by_id:
            return None
        by_id[cell_id] = cell
    if set(by_id) != set(plan.cell_ids):
        return None
    rows = []
    for cell_id in plan.cell_ids:
        cell = by_id[cell_id]
        family_id = cell.get("family_id")
        status = cell.get("status")
        summary = _summary_values(cell)
        if (
            (family_id is not None and not isinstance(family_id, str))
            or not isinstance(status, str)
            or summary is None
        ):
            return None
        rows.append(
            {
                "cell_id": cell_id,
                "family_id": family_id,
                "status": status,
                **summary,
            }
        )
    return rows


def _overhead_metric_rows(
    raw: dict | None, plan: ManagedRunPlan
) -> list[dict] | None:
    pairs = raw.get("pairs") if isinstance(raw, dict) else None
    if not isinstance(pairs, list):
        return None
    by_id: dict[str, dict] = {}
    for pair in pairs:
        pair_id = pair.get("pair_id") if isinstance(pair, dict) else None
        if not isinstance(pair_id, str) or pair_id in by_id:
            return None
        by_id[pair_id] = pair
    if set(by_id) != set(plan.pair_ids):
        return None
    rows = []
    for pair_id in plan.pair_ids:
        pair = by_id[pair_id]
        direct = pair.get("direct")
        routed = pair.get("routed")
        direct_values = _summary_values(direct)
        routed_values = _summary_values(routed)
        status = pair.get("status")
        na_reason = pair.get("na_reason")
        direct_status = direct.get("status") if isinstance(direct, dict) else None
        routed_status = routed.get("status") if isinstance(routed, dict) else None
        direct_reason = (
            direct.get("na_reason") if isinstance(direct, dict) else None
        )
        routed_reason = (
            routed.get("na_reason") if isinstance(routed, dict) else None
        )
        text_values = (
            status,
            na_reason,
            direct_status,
            routed_status,
            direct_reason,
            routed_reason,
        )
        if (
            any(
                value is not None and not isinstance(value, str)
                for value in text_values
            )
            or direct_values is None
            or routed_values is None
            or direct_status is None
            or routed_status is None
        ):
            return None
        rows.append(
            {
                "pair_id": pair_id,
                "status": status,
                "na_reason": na_reason,
                "direct_status": direct_status,
                "direct_na_reason": direct_reason,
                "direct_median_total_seconds": direct_values[
                    "median_total_seconds"
                ],
                "direct_median_ttft_seconds": direct_values[
                    "median_ttft_seconds"
                ],
                "routed_status": routed_status,
                "routed_na_reason": routed_reason,
                "routed_median_total_seconds": routed_values[
                    "median_total_seconds"
                ],
                "routed_median_ttft_seconds": routed_values[
                    "median_ttft_seconds"
                ],
            }
        )
    return rows


def _comparison_metrics(
    run_dir: Path, plan: ManagedRunPlan, state: ManagedRunState
) -> dict:
    matrix_rows = _matrix_metric_rows(
        _step_raw_json(run_dir, state, ManagedStep.MATRIX), plan
    )
    if plan.pair_ids:
        overhead_rows = _overhead_metric_rows(
            _step_raw_json(run_dir, state, ManagedStep.OVERHEAD), plan
        )
        overhead_status = (
            METRICS_AVAILABLE if overhead_rows is not None else METRICS_UNAVAILABLE
        )
    else:
        overhead_rows = []
        overhead_status = METRICS_NOT_APPLICABLE
    return {
        "matrix_status": (
            METRICS_AVAILABLE if matrix_rows is not None else METRICS_UNAVAILABLE
        ),
        "matrix_rows": matrix_rows or [],
        "overhead_status": overhead_status,
        "overhead_rows": overhead_rows or [],
    }


def _comparison_scan(run_dir: Path) -> tuple:
    """Classify one results-root entry for the comparisons view.

    Returns one of:
      ("group", comparison_id, member, dimensions) -- contributes to a group
      ("unattributed", health, reason) -- no vetted identity; listed
          separately, never assigned to any group
      ("skip",) -- a healthy bundle with no comparison_id at all (a solo
          run); unchanged existing behavior, not an exclusion

    UNREADABLE/UNRECOGNIZED/UNSUPPORTED_SCHEMA bundles have no vetted
    identity, so they cannot be attributed to any group (fail closed); they
    stay visible in the run index as before.
    """
    health, detail = classify_bundle(run_dir)
    if health in _DEGRADED_HEALTHS:
        return ("unattributed", health, _UNATTRIBUTED_REASONS[health])
    try:
        bundle = EvidenceBundle.load(run_dir)
    except EvidenceError:
        # classify_bundle already loaded this bundle successfully; a load
        # failure here means the filesystem changed between calls. Fail
        # closed the same way this branch always has: no group membership.
        return ("skip",)
    plan = bundle.plan
    comparison_id = plan.identity.comparison_id
    if comparison_id is None:
        # A healthy solo run with no comparison_id is not an exclusion --
        # it simply never participates in comparisons.
        return ("skip",)
    if not isinstance(comparison_id, str) or not SAFE_COMPARISON_ID.fullmatch(
        comparison_id
    ):
        return ("unattributed", health, _MALFORMED_COMPARISON_ID_REASON)
    accepted = health == HEALTH_SEALED_VERIFIED
    member: dict = {
        "run_dir_name": run_dir.name,
        "run_id": plan.identity.run_id,
        "run_name": plan.identity.run_name,
        "attempt": plan.identity.attempt,
        "created_at": plan.created_at,
        "run_status": None,
        "health": health,
        "health_detail": detail,
        "accepted": accepted,
        "exclusion_reason": None if accepted else _EXCLUSION_REASONS[health],
        "metrics": None,
    }
    state = None
    try:
        state = bundle.state
        member["run_status"] = state.summary_state.value
    except EvidenceError:
        pass
    if accepted:
        # classify_bundle verified this bundle, so a state read failure here
        # means the filesystem changed between calls. Keep the member but
        # report its metrics as unavailable instead of crashing the build.
        member["metrics"] = (
            _comparison_metrics(run_dir, plan, state)
            if state is not None
            else {
                "matrix_status": METRICS_UNAVAILABLE,
                "matrix_rows": [],
                "overhead_status": METRICS_UNAVAILABLE,
                "overhead_rows": [],
            }
        )
    return (
        "group",
        comparison_id,
        member,
        _plan_dimensions(plan) if accepted else None,
    )


def build_comparisons(results_root: Path) -> dict:
    """{"results_root", "missing_root", "groups": [...]}. Never raises.

    Groups bundles by persisted comparison_id. Only SEALED_VERIFIED members
    are accepted; comparability is judged over accepted members only, on the
    portable plan dimensions in _COMPARISON_DIMENSIONS. Ordering is
    deterministic and independent of filesystem iteration order.
    """
    if not results_root.is_dir():
        return {
            "results_root": str(results_root),
            "missing_root": True,
            "groups": [],
            "unattributed_exclusions": [],
        }
    grouped: dict[str, list[tuple[dict, dict | None]]] = {}
    # (health, raw run_dir.name, reason): sorted with the raw name as
    # tiebreaker so ordering is deterministic regardless of scan order.
    unattributed_raw: list[tuple[str, str, str]] = []
    for child in results_root.iterdir():
        outcome = _comparison_scan(child)
        if outcome[0] == "skip":
            continue
        if outcome[0] == "unattributed":
            _, health, reason = outcome
            unattributed_raw.append((health, child.name, reason))
            continue
        _, comparison_id, member, dimensions = outcome
        grouped.setdefault(comparison_id, []).append((member, dimensions))

    unattributed_raw.sort(key=lambda item: (item[0], item[1]))
    unattributed_exclusions = [
        _unattributed_record(health, raw_name, reason)
        for health, raw_name, reason in unattributed_raw
    ]

    groups = []
    for comparison_id in sorted(grouped):
        pairs = grouped[comparison_id]
        pairs.sort(
            key=lambda pair: (
                pair[0]["created_at"],
                pair[0]["run_id"],
                pair[0]["run_dir_name"],
            )
        )
        members = [member for member, _dims in pairs]
        accepted_dims = [dims for _member, dims in pairs if dims is not None]
        if len(accepted_dims) < 2:
            verdict = VERDICT_NOT_APPLICABLE
            reason = "fewer than two accepted members"
            dimensions = None
        else:
            baseline = accepted_dims[0]
            mismatched = [
                dim
                for dim in _COMPARISON_DIMENSIONS
                if any(dims[dim] != baseline[dim] for dims in accepted_dims[1:])
            ]
            if mismatched:
                verdict = VERDICT_INCOMPARABLE
                reason = "plan_dimension_mismatch: " + ", ".join(mismatched)
                dimensions = None
            else:
                verdict = VERDICT_COMPARABLE
                reason = ""
                dimensions = baseline
        metrics = None
        if verdict == VERDICT_COMPARABLE:
            accepted_members = [member for member in members if member["accepted"]]
            metrics = {
                "availability": [
                    {
                        "run_id": member["run_id"],
                        "matrix": member["metrics"]["matrix_status"],
                        "overhead": member["metrics"]["overhead_status"],
                    }
                    for member in accepted_members
                ],
                "matrix": [
                    {"run_id": member["run_id"], **row}
                    for member in accepted_members
                    for row in member["metrics"]["matrix_rows"]
                ],
                "overhead": [
                    {"run_id": member["run_id"], **row}
                    for member in accepted_members
                    for row in member["metrics"]["overhead_rows"]
                ],
            }
        groups.append(
            {
                "comparison_id": comparison_id,
                "verdict": verdict,
                "verdict_reason": reason,
                "accepted_count": sum(1 for m in members if m["accepted"]),
                "excluded_count": sum(1 for m in members if not m["accepted"]),
                "dimensions": dimensions,
                "metrics": metrics,
                "members": members,
            }
        )
    return {
        "results_root": str(results_root),
        "missing_root": False,
        "groups": groups,
        "unattributed_exclusions": unattributed_exclusions,
    }
