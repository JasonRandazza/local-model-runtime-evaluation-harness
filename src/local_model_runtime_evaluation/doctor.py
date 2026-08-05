"""Read-only offline diagnostic engine for the LMRE managed CLI.

`run_diagnostics` inspects static local state only: machine profile JSON,
matrix/preference/RAG/overhead config files, adopted operator policy, and
`PATH` lookups via an injected `which`. It never opens a socket, spawns a
subprocess, binds a port, inspects a process, or touches a credential store,
and it writes nothing. Every fact that would require live contact with a
model runtime, provider, or credential store (endpoint reachability, provider
inventory, process identity, credentials, memory headroom, model load
behavior) is reported as ``NOT_CHECKED_LIVE`` and never inferred from static
state.

`render_text` is a pure projection of the result dict returned by
`run_diagnostics`; it performs no I/O and no recomputation.
"""

from __future__ import annotations

import os
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Callable

from .matrix_config import (
    REPOSITORY_ROOT,
    Campaign,
    MatrixError,
    MatrixSuite,
    load_family,
)
from .operator_policy import PolicyError, load_adopted_policy
from .preference_config import (
    PreferenceError,
    PreferenceSuite,
    load_family_cell_recipes,
)
from .rag_config import RagCorpus, RagError, RagSuite, load_rag_family_cell_recipes
from .artifact_profile import ArtifactProfileError, ArtifactRoots, load_artifact_roots
from .run_identity import RunIdentityError, _load_recipe, _native_recipes


DOCTOR_SCHEMA_VERSION = "1.0.0"
STATUS_OFFLINE_READY = "OFFLINE_READY"
STATUS_ACTION_REQUIRED = "ACTION_REQUIRED"
STATUS_WARNING = "WARNING"
STATUS_NOT_CHECKED_LIVE = "NOT_CHECKED_LIVE"

# Fixed, deterministic check order/content per the offline doctor design.
COMMAND_NAMES = ("osaurus", "omlx", "optiq")
BIN_WRAPPERS = (
    "lmre",
    "lmre-approach3",
    "lmre-discover",
    "lmre-matrix",
    "lmre-overhead",
    "lmre-preference",
    "lmre-rag",
)
REQUIRED_DOCS = (
    "README.md",
    "docs/managed-runs.md",
    "docs/status.md",
    "docs/architecture.md",
)
LIVE_FACTS_SUMMARY = (
    "endpoint reachability, provider inventory, process identity, credentials, "
    "memory headroom, and model load behavior were not checked"
)

# Loader errors doctor.py is expected to convert into findings. None of these
# loaders ever perform network, process, or filesystem-mutating calls.
_LOADER_ERRORS = (
    MatrixError,
    PreferenceError,
    RagError,
    RunIdentityError,
    ArtifactProfileError,
    OSError,
    ValueError,
    KeyError,
    TypeError,
    # json.loads raises RecursionError on pathologically nested documents;
    # one corrupt file must degrade to one finding, not abort the diagnostic.
    RecursionError,
)


def _finding(
    check: str,
    status: str,
    summary: str,
    *,
    detail: str | None = None,
    remediation: str | None = None,
    doc: str | None = None,
) -> dict:
    return {
        "check": check,
        "status": status,
        "summary": summary,
        "detail": detail,
        "remediation": remediation,
        "doc": doc,
    }


def _try(callable_, *args, **kwargs):
    """Call a validator and turn any expected failure into an error string."""
    try:
        return callable_(*args, **kwargs), None
    except _LOADER_ERRORS as error:
        return None, str(error)


def _harness_section(root: Path) -> dict:
    findings = []
    version_ok = sys.version_info >= (3, 11)
    version_text = ".".join(str(part) for part in sys.version_info[:3])
    findings.append(_finding(
        "harness.python_version",
        STATUS_OFFLINE_READY if version_ok else STATUS_ACTION_REQUIRED,
        f"running Python {version_text}" if version_ok
        else f"Python {version_text} is below the 3.11 floor",
        remediation=None if version_ok
        else "Upgrade the Python interpreter to 3.11 or later.",
    ))

    missing_bins = [
        name for name in BIN_WRAPPERS
        if not (
            (root / "bin" / name).is_file()
            and os.access(root / "bin" / name, os.X_OK)
        )
    ]
    findings.append(_finding(
        "harness.bin_wrappers",
        STATUS_ACTION_REQUIRED if missing_bins else STATUS_OFFLINE_READY,
        "some bin/ command wrappers are missing or not executable" if missing_bins
        else "all bin/ command wrappers are present and executable",
        detail=", ".join(missing_bins) or None,
        remediation=None if not missing_bins
        else "Restore the missing bin/ wrappers from version control and mark them executable.",
    ))

    missing_docs = [name for name in REQUIRED_DOCS if not (root / name).is_file()]
    findings.append(_finding(
        "harness.docs",
        STATUS_ACTION_REQUIRED if missing_docs else STATUS_OFFLINE_READY,
        "some core operator docs are missing" if missing_docs
        else "core operator docs are present",
        detail=", ".join(missing_docs) or None,
        remediation=None if not missing_docs
        else "Restore the missing operator docs from version control.",
    ))
    return {"section": "harness", "findings": findings}


def _commands_section(which: Callable[[str], str | None]) -> tuple[dict, dict[str, str]]:
    findings = []
    status_by_name: dict[str, str] = {}
    for name in COMMAND_NAMES:
        path = which(name)
        status = STATUS_OFFLINE_READY if path else STATUS_ACTION_REQUIRED
        status_by_name[name] = status
        findings.append(_finding(
            f"commands.{name}",
            status,
            f"{name} found on PATH at {path}" if path
            else f"{name} was not found on PATH",
            detail=path,
            remediation=None if path
            else f"Install {name} or add it to PATH; see docs/managed-runs.md.",
            doc=None if path else "docs/managed-runs.md",
        ))
    return {"section": "commands", "findings": findings}, status_by_name


def _machine_profile_section(
    machine_profile_path: Path,
) -> tuple[dict, ArtifactRoots | None]:
    roots, error = _try(load_artifact_roots, machine_profile_path)
    if roots is not None:
        finding = _finding(
            "machine_profile.roots",
            STATUS_OFFLINE_READY,
            "machine profile is valid",
            detail=(
                f"huggingface_hub={roots.huggingface_hub} "
                f"local_models={roots.local_models}"
            ),
        )
    else:
        finding = _finding(
            "machine_profile.roots",
            STATUS_ACTION_REQUIRED,
            "machine profile is invalid",
            detail=error,
            remediation=(
                "Copy the example machine profile and edit the artifact roots "
                "for this machine; see docs/managed-runs.md."
            ),
            doc="docs/managed-runs.md",
        )
    return {"section": "machine_profile", "findings": [finding]}, roots


def _diagnose_recipes(root: Path) -> dict[str, str | None]:
    recipes_dir = root / "config" / "managed-runs"
    if not recipes_dir.is_dir():
        return {}
    results: dict[str, str | None] = {}
    for path in sorted(recipes_dir.glob("*.json")):
        _, error = _try(_load_recipe, path)
        results[path.stem] = error
    return results


def _discover_family_ids(root: Path) -> list[str]:
    families_dir = root / "config" / "matrix" / "families"
    if not families_dir.is_dir():
        return []
    return sorted(path.stem for path in families_dir.glob("*.json"))


def _diagnose_family(root: Path, family_id: str) -> dict:
    diag: dict[str, object] = {
        "family": None,
        "family_error": None,
        "campaign": None,
        "campaign_error": None,
        "suite_error": None,
        "preference_error": None,
        "rag_error": None,
        "native_triple_error": None,
    }

    families_root = root / "config" / "matrix" / "families"
    family, error = _try(load_family, family_id, families_root=families_root)
    diag["family"], diag["family_error"] = family, error
    if family is None:
        return diag

    # NOTE: Campaign.load hardcodes matrix_config.REPOSITORY_ROOT for its
    # internal load_family(family_id) call and for resolving any *relative*
    # suite_path/results_root/cell paths listed in the campaign JSON itself.
    # A non-default repository_root only fully drives this check when it
    # equals the real repository root; against a synthetic tree this check
    # legitimately reports whatever the real repo's config says for this
    # family_id (or "family file is missing" if it has none). This is a
    # verified limitation of matrix_config.py, not reimplemented here.
    campaign_path = root / "config" / "matrix" / f"{family_id}-campaign.json"
    campaign, error = _try(Campaign.load, campaign_path)
    diag["campaign"], diag["campaign_error"] = campaign, error
    if campaign is None:
        return diag

    _, diag["suite_error"] = _try(MatrixSuite.load, campaign.suite_path)

    preference_path = root / "config" / "preference" / "family-cells.json"
    recipes, error = _try(load_family_cell_recipes, preference_path)
    if error is None and family_id not in (recipes or {}):
        error = "preference family recipe is missing"
    if error is None:
        _, error = _try(
            PreferenceSuite.load, root / "suites" / "multi-family-preference-v1.json",
        )
    diag["preference_error"] = error

    rag_path = root / "config" / "rag" / "family-cells.json"
    recipes, error = _try(load_rag_family_cell_recipes, rag_path)
    if error is None and family_id not in (recipes or {}):
        error = "rag family recipe is missing"
    if error is None:
        _, error = _try(
            RagSuite.load, root / "suites" / "multi-family-rag-oracle-v1.json",
        )
    if error is None:
        _, error = _try(RagCorpus.load, root / "corpora" / "rag-oracle-v1")
    diag["rag_error"] = error

    # Reuse run_identity's own native-triple cross-check rather than
    # reimplementing the preference/RAG/campaign/overhead-pair agreement rule.
    _, diag["native_triple_error"] = _try(_native_recipes, family_id, campaign)
    return diag


def _configuration_section(
    family_diags: dict[str, dict], recipe_errors: dict[str, str | None],
) -> dict:
    findings = []
    # An empty tree must fail closed: with no recipes or families discovered
    # there would otherwise be no findings here at all, and a gutted install
    # could aggregate to OFFLINE_READY on harness checks alone.
    if not recipe_errors:
        findings.append(_finding(
            "configuration.recipes",
            STATUS_ACTION_REQUIRED,
            "no managed recipes found under config/managed-runs",
            remediation="Restore the managed recipe files from version control.",
            doc="docs/managed-runs.md",
        ))
    if not family_diags:
        findings.append(_finding(
            "configuration.families",
            STATUS_ACTION_REQUIRED,
            "no active families found under config/matrix/families",
            remediation="Restore the family configuration files from version control.",
            doc="docs/matrix.md",
        ))
    for recipe_id in sorted(recipe_errors):
        error = recipe_errors[recipe_id]
        findings.append(_finding(
            f"configuration.recipe.{recipe_id}",
            STATUS_ACTION_REQUIRED if error else STATUS_OFFLINE_READY,
            "managed recipe is invalid" if error else "managed recipe is valid",
            detail=error,
            remediation=None if not error
            else f"Fix config/managed-runs/{recipe_id}.json; see docs/managed-runs.md.",
            doc=None if not error else "docs/managed-runs.md",
        ))

    for family_id in sorted(family_diags):
        diag = family_diags[family_id]
        labels = (
            ("family", diag["family_error"]),
            ("campaign", diag["campaign_error"]),
            ("suite", diag["suite_error"]),
            ("preference", diag["preference_error"]),
            ("rag", diag["rag_error"]),
            ("native_triple", diag["native_triple_error"]),
        )
        problems = [f"{label}: {error}" for label, error in labels if error]
        findings.append(_finding(
            f"configuration.family.{family_id}",
            STATUS_ACTION_REQUIRED if problems else STATUS_OFFLINE_READY,
            f"family configuration has {len(problems)} issue(s)" if problems
            else "family configuration is valid",
            detail="; ".join(problems) or None,
            remediation=None if not problems
            else "Fix the listed configuration file(s) for this family; see docs/matrix.md.",
            doc=None if not problems else "docs/matrix.md",
        ))
    return {"section": "configuration", "findings": findings}


def _artifact_path_status(path: Path) -> tuple[str, str, str | None]:
    if path.is_symlink() and not path.exists():
        return (
            STATUS_ACTION_REQUIRED,
            f"artifact path is a broken symlink: {path}",
            "Repoint or remove the broken symlink so it resolves to the real model artifact.",
        )
    if not path.exists():
        return (
            STATUS_ACTION_REQUIRED,
            f"artifact path is missing: {path}",
            "Place the model artifact at this path or correct the machine profile root.",
        )
    if not path.is_dir():
        return (
            STATUS_ACTION_REQUIRED,
            f"artifact path has the wrong kind (expected a directory): {path}",
            "Replace the artifact file with the expected model directory, or correct the machine profile root.",
        )
    if not os.access(path, os.R_OK):
        return (
            STATUS_ACTION_REQUIRED,
            f"artifact path is unreadable: {path}",
            "Fix filesystem permissions so this path is readable by the current user.",
        )
    return (STATUS_OFFLINE_READY, f"artifact path is present: {path}", None)


def _artifacts_section(
    roots: ArtifactRoots | None, family_diags: dict[str, dict],
) -> tuple[dict, dict[str, str]]:
    findings = []
    family_status: dict[str, str] = {}
    if roots is None:
        findings.append(_finding(
            "artifacts.profile",
            STATUS_ACTION_REQUIRED,
            "artifact checks skipped because the machine profile is invalid",
            remediation="Fix the machine profile (see the machine_profile section) first.",
            doc="docs/managed-runs.md",
        ))
        return {"section": "artifacts", "findings": findings}, family_status

    for family_id in sorted(family_diags):
        campaign = family_diags[family_id]["campaign"]
        if campaign is None:
            family = family_diags[family_id]["family"]
            if family is not None:
                _, family_error = _try(family.resolve, roots)
                if family_error:
                    findings.append(_finding(
                        f"artifacts.{family_id}",
                        STATUS_ACTION_REQUIRED,
                        "family artifact template resolution failed",
                        detail=family_error,
                        remediation="Fix the artifact_path templates for this family; see docs/matrix.md.",
                        doc="docs/matrix.md",
                    ))
                    family_status[family_id] = STATUS_ACTION_REQUIRED
                    continue
            findings.append(_finding(
                f"artifacts.{family_id}",
                STATUS_ACTION_REQUIRED,
                "artifacts not checked because campaign configuration is invalid",
                detail=family_diags[family_id]["campaign_error"],
            ))
            family_status[family_id] = STATUS_ACTION_REQUIRED
            continue

        # Resolve the complete campaign, not only the family quant entries.
        # Cell.resolve validates every cell's artifact path, model ID, and
        # fixed start/stop command token set through the existing resolver.
        resolved, error = _try(campaign.resolve, roots)
        if resolved is None:
            findings.append(_finding(
                f"artifacts.{family_id}",
                STATUS_ACTION_REQUIRED,
                "family or cell artifact template resolution failed",
                detail=error,
                remediation="Fix the artifact_path, model_id, or command templates for this family; see docs/matrix.md.",
                doc="docs/matrix.md",
            ))
            family_status[family_id] = STATUS_ACTION_REQUIRED
            continue

        family_ok = True
        for cell in sorted(resolved.cells, key=lambda value: value.cell_id):
            path = Path(cell.artifact_path)
            status, summary, remediation = _artifact_path_status(path)
            if status != STATUS_OFFLINE_READY:
                family_ok = False
            findings.append(_finding(
                f"artifacts.{family_id}.{cell.quant}",
                status,
                summary,
                detail=str(path),
                remediation=remediation,
                doc=None if status == STATUS_OFFLINE_READY else "docs/managed-runs.md",
            ))
        family_status[family_id] = STATUS_OFFLINE_READY if family_ok else STATUS_ACTION_REQUIRED

    return {"section": "artifacts", "findings": findings}, family_status


def _policy_section(state_root: Path, now: datetime | None) -> dict:
    try:
        adopted = load_adopted_policy(state_root, now=now)
    except PolicyError as error:
        finding = _finding(
            "policy.adopted",
            STATUS_ACTION_REQUIRED,
            f"adopted operator policy check failed ({error.code})",
            detail=f"{error.code}: {error}",
            remediation=(
                "Review the operator policy manually and adopt it into this state "
                "directory; this command never adopts or repairs a policy."
            ),
            doc="docs/managed-runs.md",
        )
        return {"section": "policy", "findings": [finding]}

    policy = adopted.policy
    finding = _finding(
        "policy.adopted",
        STATUS_OFFLINE_READY,
        f"operator policy {policy.policy_id!r} is adopted and not expired",
        detail=(
            f"policy_id={policy.policy_id} policy_hash={adopted.policy_hash} "
            f"adopted_at={adopted.adopted_at} expires_at={policy.expires_at}"
        ),
    )
    return {"section": "policy", "findings": [finding]}


def _families_section(
    family_diags: dict[str, dict],
    recipe_errors: dict[str, str | None],
    commands_status: dict[str, str],
    profile_ok: bool,
    artifacts_status: dict[str, str],
) -> dict:
    findings = []
    for family_id in sorted(family_diags):
        diag = family_diags[family_id]
        family = diag["family"]
        servers = sorted({quant.native_server for quant in family.quants.values()}) if family else []

        for recipe_id in sorted(recipe_errors):
            reasons: list[str] = []
            if not profile_ok:
                reasons.append("machine profile is invalid")
            for label, error in (
                ("family", diag["family_error"]),
                ("campaign", diag["campaign_error"]),
                ("suite", diag["suite_error"]),
                ("preference", diag["preference_error"]),
                ("rag", diag["rag_error"]),
                ("native_triple", diag["native_triple_error"]),
            ):
                if error:
                    reasons.append(f"{label} configuration is invalid")
            if recipe_errors[recipe_id]:
                reasons.append("recipe configuration is invalid")
            if artifacts_status.get(family_id) == STATUS_ACTION_REQUIRED:
                reasons.append("one or more artifact paths are not usable")
            missing_commands = [
                name for name in servers if commands_status.get(name) != STATUS_OFFLINE_READY
            ]
            if missing_commands:
                reasons.append("missing command(s): " + ", ".join(missing_commands))

            status = STATUS_ACTION_REQUIRED if reasons else STATUS_OFFLINE_READY
            summary = (
                "static prerequisite issue(s): " + "; ".join(reasons) if reasons
                else "no static prerequisite issues found for this family and recipe"
            )
            findings.append(_finding(
                f"families.{family_id}.{recipe_id}",
                status,
                summary,
                remediation=None if not reasons
                else "Resolve the listed issues, then re-run the doctor.",
            ))

        findings.append(_finding(
            f"families.{family_id}.live_facts",
            STATUS_NOT_CHECKED_LIVE,
            LIVE_FACTS_SUMMARY,
        ))
    return {"section": "families", "findings": findings}


def _collect_actions(sections: list[dict]) -> list[str]:
    actions: list[str] = []
    seen: set[str] = set()
    for section in sections:
        for finding in section["findings"]:
            if finding["status"] != STATUS_ACTION_REQUIRED:
                continue
            text = finding["remediation"] or finding["summary"]
            if text not in seen:
                seen.add(text)
                actions.append(text)
    return actions


def run_diagnostics(
    *,
    machine_profile_path: Path,
    state_root: Path,
    repository_root: Path | None = None,
    which: Callable[[str], str | None] = shutil.which,
    now: datetime | None = None,
) -> dict:
    root = REPOSITORY_ROOT if repository_root is None else repository_root

    harness = _harness_section(root)
    commands, commands_status = _commands_section(which)
    profile, roots = _machine_profile_section(machine_profile_path)
    profile_ok = roots is not None

    recipe_errors = _diagnose_recipes(root)
    family_diags = {
        family_id: _diagnose_family(root, family_id)
        for family_id in _discover_family_ids(root)
    }

    configuration = _configuration_section(family_diags, recipe_errors)
    artifacts, artifacts_status = _artifacts_section(roots, family_diags)
    policy = _policy_section(state_root, now)
    families = _families_section(
        family_diags, recipe_errors, commands_status, profile_ok, artifacts_status,
    )

    sections = [harness, commands, profile, configuration, artifacts, policy, families]
    overall = (
        STATUS_ACTION_REQUIRED
        if any(
            finding["status"] == STATUS_ACTION_REQUIRED
            for section in sections
            for finding in section["findings"]
        )
        else STATUS_OFFLINE_READY
    )
    return {
        "doctor_schema_version": DOCTOR_SCHEMA_VERSION,
        "overall_readiness": overall,
        "sections": sections,
        "actions": _collect_actions(sections),
    }


def render_text(result: dict) -> str:
    lines = [
        f"LMRE Offline Doctor Report (schema {result['doctor_schema_version']})",
        f"Overall readiness: {result['overall_readiness']}",
        "",
    ]
    for section in result["sections"]:
        lines.append(f"{section['section']}:")
        for finding in section["findings"]:
            lines.append(f"  [{finding['status']}] {finding['check']}: {finding['summary']}")
        lines.append("")

    lines.append("Actions:")
    if result["actions"]:
        for index, action in enumerate(result["actions"], start=1):
            lines.append(f"  {index}. {action}")
    else:
        lines.append("  none")
    lines.append("")

    lines.append(
        "This command is fully offline: it never opened a socket, spawned a "
        "process, or contacted a model runtime, provider, or credential "
        "store. Endpoint reachability, provider inventory, process identity, "
        "credentials, memory headroom, and model load behavior were NOT "
        "checked here and must be verified separately before running a live "
        "evaluation."
    )
    return "\n".join(lines)
