"""Run naming, immutable plan construction, and plan hashing."""

from __future__ import annotations

import hashlib
import json
import re
import secrets
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .artifact_profile import DEFAULT_MACHINE_PROFILE_PATH, load_artifact_roots
from .comparison_class import (
    DEFAULT_COMPARISON_CLASSES_ROOT,
    ComparisonClassError,
    load_comparison_class,
)
from .managed_run_types import (
    MANAGED_PLAN_SCHEMA_VERSION,
    ManagedRunPlan,
    ManagedStep,
    RunIdentity,
)
from .matrix_config import (
    REPOSITORY_ROOT,
    Campaign,
    MatrixError,
    MatrixSuite,
)
from .overhead_config import (
    DEFAULT_PAIRS_ROOT,
    OverheadError,
    OverheadPair,
    load_family_pair_recipes,
)
from .preference_config import (
    PreferenceError,
    PreferenceSuite,
    load_family_cell_recipes,
)
from .rag_config import (
    RagError,
    RagSuite,
    load_rag_family_cell_recipes,
)


RECIPE_FIELDS = frozenset({
    "schema_version",
    "recipe_id",
    "steps",
    "matrix_mode",
    "estimated_minutes",
    "memory_floor_percent",
})
EXPECTED_STEP_ORDER = (
    ManagedStep.PREFLIGHT,
    ManagedStep.MATRIX,
    ManagedStep.PREFERENCE,
    ManagedStep.RAG_ORACLE,
    ManagedStep.RAG_KEYWORD,
    ManagedStep.OVERHEAD,
    ManagedStep.SEAL,
)
SAFE_RUN_NAME = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
SAFE_ENTROPY = re.compile(r"[0-9a-f]{6}")
SAFE_RUN_ID = re.compile(r"run-\d{8}-\d{6}-[0-9a-f]{6}")
DEFAULT_PREFERENCE_SUITE = (
    REPOSITORY_ROOT / "suites" / "multi-family-preference-v1.json"
)
DEFAULT_RAG_SUITE = (
    REPOSITORY_ROOT / "suites" / "multi-family-rag-oracle-v1.json"
)
DEFAULT_RAG_CORPUS = REPOSITORY_ROOT / "corpora" / "rag-oracle-v1"
DEFAULT_CELLS_ROOT = REPOSITORY_ROOT / "config" / "matrix" / "cells"
MACHINE_PROFILE_INPUT = ".lmre/machine-profile.json"


class RunIdentityError(RuntimeError):
    code = "run_identity_invalid"

    def __init__(
        self,
        message: str,
        *,
        code: str = "run_identity_invalid",
    ) -> None:
        super().__init__(message)
        self.code = code


def _utc_now(now: datetime | None) -> datetime:
    current = datetime.now(timezone.utc) if now is None else now
    if current.tzinfo is None or current.utcoffset() != timezone.utc.utcoffset(current):
        raise RunIdentityError("run time must use UTC")
    return current.astimezone(timezone.utc)


def sanitize_run_name(value: str) -> str:
    if not isinstance(value, str):
        raise RunIdentityError("run name must be a string")
    normalized = re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-")
    if (
        not normalized
        or len(normalized) > 80
        or not SAFE_RUN_NAME.fullmatch(normalized)
    ):
        raise RunIdentityError("run name is invalid")
    return normalized


def allocate_run_identity(
    results_root: Path,
    *,
    run_name: str,
    comparison_id: str | None,
    parent_run_id: str | None,
    now: datetime | None = None,
    entropy: str | None = None,
) -> RunIdentity:
    current = _utc_now(now)
    resolved_entropy = secrets.token_hex(3) if entropy is None else entropy
    if not SAFE_ENTROPY.fullmatch(resolved_entropy):
        raise RunIdentityError("run entropy must be six lowercase hex characters")
    resolved_name = sanitize_run_name(run_name)
    resolved_comparison = sanitize_run_name(
        resolved_name if comparison_id is None else comparison_id
    )
    if parent_run_id is not None and not SAFE_RUN_ID.fullmatch(parent_run_id):
        raise RunIdentityError("parent_run_id is invalid")
    run_id = f"run-{current:%Y%m%d-%H%M%S}-{resolved_entropy}"
    if (results_root / run_id).exists():
        raise RunIdentityError(
            f"run id already exists: {run_id}",
            code="run_id_collision",
        )
    return RunIdentity(
        run_name=resolved_name,
        run_id=run_id,
        attempt=1,
        comparison_id=resolved_comparison,
        parent_run_id=parent_run_id,
    )


def _canonical_plan_hash(plan: ManagedRunPlan) -> str:
    encoded = json.dumps(
        plan.to_dict(include_hash=False),
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as source:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as error:
        raise RunIdentityError(
            f"managed plan input is unreadable: {path}"
        ) from error
    return digest.hexdigest()


def _hash_inputs(paths: set[Path]) -> tuple[tuple[str, str], ...]:
    return tuple(
        sorted(
            (_repo_relative(path), _sha256(path))
            for path in paths
        )
    )


def verify_plan_hash(plan: ManagedRunPlan) -> None:
    if not plan.plan_hash or plan.plan_hash != _canonical_plan_hash(plan):
        raise RunIdentityError(
            "managed run plan hash mismatch",
            code="plan_hash_mismatch",
        )


def verify_plan_inputs(
    plan: ManagedRunPlan,
    *,
    repository_root: Path = REPOSITORY_ROOT,
    machine_profile_path: Path | None = None,
) -> None:
    for relative, expected in plan.input_hashes:
        if relative == MACHINE_PROFILE_INPUT:
            path = machine_profile_path or repository_root / MACHINE_PROFILE_INPUT
        else:
            path = repository_root / relative
        if not path.is_file() or _sha256(path) != expected:
            raise RunIdentityError(
                f"managed plan input changed: {relative}",
                code="plan_input_changed",
            )


def _repo_relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPOSITORY_ROOT.resolve()).as_posix()
    except ValueError as error:
        raise RunIdentityError(
            f"managed plan path is outside repository: {path}"
        ) from error


def _load_recipe(path: Path) -> dict[str, object]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise RunIdentityError("managed recipe JSON is invalid") from error
    if not isinstance(data, dict) or set(data) != RECIPE_FIELDS:
        raise RunIdentityError("managed recipe fields are invalid")
    if data["schema_version"] != "1.0.0":
        raise RunIdentityError("managed recipe schema_version is invalid")
    recipe_id = data["recipe_id"]
    if not isinstance(recipe_id, str) or not SAFE_RUN_NAME.fullmatch(recipe_id):
        raise RunIdentityError("managed recipe_id is invalid")
    raw_steps = data["steps"]
    if not isinstance(raw_steps, list):
        raise RunIdentityError("managed recipe steps are invalid")
    try:
        steps = tuple(ManagedStep(value) for value in raw_steps)
    except (TypeError, ValueError) as error:
        raise RunIdentityError("managed recipe step is invalid") from error
    if steps != EXPECTED_STEP_ORDER:
        raise RunIdentityError("managed recipe step order is invalid")
    if data["matrix_mode"] != "screen":
        raise RunIdentityError("managed recipe matrix_mode is invalid")
    for field in ("estimated_minutes", "memory_floor_percent"):
        if type(data[field]) is not int or int(data[field]) <= 0:
            raise RunIdentityError(f"managed recipe {field} is invalid")
    if int(data["memory_floor_percent"]) > 100:
        raise RunIdentityError("managed recipe memory_floor_percent is invalid")
    return data


def _campaign_for_family(family_id: str) -> tuple[Path, Campaign]:
    path = REPOSITORY_ROOT / "config" / "matrix" / f"{family_id}-campaign.json"
    if not path.is_file():
        raise RunIdentityError(f"managed family is unknown: {family_id}")
    try:
        campaign = Campaign.load(path)
    except (MatrixError, OSError, ValueError, KeyError, TypeError) as error:
        raise RunIdentityError("managed campaign is invalid") from error
    if campaign.family_id != family_id:
        raise RunIdentityError("managed campaign family mismatch")
    return path, campaign


def _native_recipes(
    family_id: str,
    campaign: Campaign,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    try:
        preference = load_family_cell_recipes()
        rag = load_rag_family_cell_recipes()
        pairs = load_family_pair_recipes()
    except (PreferenceError, RagError, OverheadError, OSError) as error:
        raise RunIdentityError("managed family recipe is invalid") from error
    if family_id not in preference or family_id not in rag or family_id not in pairs:
        raise RunIdentityError("managed family recipe is missing")
    cell_ids = tuple(path.stem for path in campaign.cell_paths)
    if preference[family_id] != cell_ids or rag[family_id] != cell_ids:
        raise RunIdentityError(
            "preference, RAG, and campaign native triples must agree"
        )
    pair_ids = pairs[family_id]
    for pair_id in pair_ids:
        try:
            pair = OverheadPair.load(DEFAULT_PAIRS_ROOT / f"{pair_id}.json")
        except (OverheadError, OSError) as error:
            raise RunIdentityError("managed overhead pair is invalid") from error
        if (
            pair.direct_cell_id not in cell_ids
            or pair.backend_cell_id not in cell_ids
        ):
            raise RunIdentityError("managed overhead pair is outside native triple")
    return cell_ids, pair_ids


def _request_count(
    *,
    cell_count: int,
    pair_count: int,
    matrix_suite: MatrixSuite,
    preference_suite: PreferenceSuite,
    rag_suite: RagSuite,
) -> int:
    matrix_requests = cell_count * len(matrix_suite.workloads)
    preference_collect_requests = cell_count * len(preference_suite.prompts)
    preference_judge_requests = (
        cell_count * (cell_count - 1) // 2
    ) * len(preference_suite.prompts)
    rag_requests = 2 * cell_count * len(rag_suite.questions)
    overhead_requests = 2 * pair_count * len(matrix_suite.workloads)
    return (
        matrix_requests
        + preference_collect_requests
        + preference_judge_requests
        + rag_requests
        + overhead_requests
    )


def _scaled_estimated_minutes(
    baseline_minutes: int,
    baseline_requests: int,
    selected_requests: int,
) -> int:
    return (
        baseline_minutes * selected_requests + baseline_requests - 1
    ) // baseline_requests


def build_plan(
    recipe_path: Path,
    *,
    family_id: str,
    run_name: str | None,
    comparison_id: str | None,
    parent_run_id: str | None,
    results_root: Path,
    comparison_class_id: str | None = None,
    now: datetime | None = None,
    entropy: str | None = None,
    machine_profile_path: Path = DEFAULT_MACHINE_PROFILE_PATH,
    comparison_classes_root: Path = DEFAULT_COMPARISON_CLASSES_ROOT,
) -> ManagedRunPlan:
    current = _utc_now(now)
    load_artifact_roots(machine_profile_path)
    recipe = _load_recipe(recipe_path)
    campaign_path, campaign = _campaign_for_family(family_id)
    baseline_cell_ids, pair_ids = _native_recipes(family_id, campaign)
    comparison_class = None
    if comparison_class_id is not None:
        try:
            comparison_class = load_comparison_class(
                comparison_class_id,
                root=comparison_classes_root,
            )
        except ComparisonClassError as error:
            raise RunIdentityError(
                str(error),
                code=error.code,
            ) from error
        if comparison_class.family_id != family_id:
            raise RunIdentityError("managed comparison class family mismatch")
        if comparison_class.baseline_campaign_path != campaign_path.resolve():
            raise RunIdentityError("managed comparison class campaign mismatch")
        if comparison_class.baseline_cell_ids != baseline_cell_ids:
            raise RunIdentityError("managed comparison class baseline mismatch")
        cell_ids = comparison_class.cell_ids
    else:
        cell_ids = baseline_cell_ids
    try:
        matrix_suite = MatrixSuite.load(campaign.suite_path)
        preference_suite = PreferenceSuite.load(DEFAULT_PREFERENCE_SUITE)
        rag_suite = RagSuite.load(DEFAULT_RAG_SUITE)
    except (MatrixError, PreferenceError, RagError, OSError) as error:
        raise RunIdentityError("managed suite is invalid") from error
    if campaign.memory_floor_percent != int(recipe["memory_floor_percent"]):
        raise RunIdentityError("recipe and campaign memory floors must agree")
    baseline_request_count = _request_count(
        cell_count=len(baseline_cell_ids),
        pair_count=len(pair_ids),
        matrix_suite=matrix_suite,
        preference_suite=preference_suite,
        rag_suite=rag_suite,
    )
    request_count = _request_count(
        cell_count=len(cell_ids),
        pair_count=len(pair_ids),
        matrix_suite=matrix_suite,
        preference_suite=preference_suite,
        rag_suite=rag_suite,
    )
    baseline_minutes = int(recipe["estimated_minutes"])
    estimated_minutes = baseline_minutes
    if comparison_class is not None:
        minimum_minutes = _scaled_estimated_minutes(
            baseline_minutes,
            baseline_request_count,
            request_count,
        )
        if comparison_class.estimated_minutes < minimum_minutes:
            raise RunIdentityError(
                "managed comparison class estimated_minutes is below "
                "the request-scaled minimum"
            )
        estimated_minutes = comparison_class.estimated_minutes
    input_paths = {
        recipe_path,
        campaign_path,
        campaign.suite_path,
        DEFAULT_PREFERENCE_SUITE,
        DEFAULT_RAG_SUITE,
        REPOSITORY_ROOT
        / "config"
        / "matrix"
        / "families"
        / f"{family_id}.json",
        REPOSITORY_ROOT / "config" / "preference" / "family-cells.json",
        REPOSITORY_ROOT / "config" / "rag" / "family-cells.json",
        REPOSITORY_ROOT / "config" / "overhead" / "family-pairs.json",
        *campaign.cell_paths,
        *(
            DEFAULT_PAIRS_ROOT / f"{pair_id}.json"
            for pair_id in pair_ids
        ),
        *(
            path
            for path in DEFAULT_RAG_CORPUS.rglob("*")
            if path.is_file()
        ),
    }
    if comparison_class is not None:
        input_paths.add(comparison_class.path)
        input_paths.update(comparison_class.cell_paths)

    recipe_id = str(recipe["recipe_id"])
    resolved_name = (
        (
            f"{family_id}-{comparison_class.comparison_class_id}"
            if comparison_class is not None
            else f"{family_id}-{recipe_id.removesuffix('-v1')}"
        )
        if run_name is None
        else run_name
    )
    identity = allocate_run_identity(
        results_root,
        run_name=resolved_name,
        comparison_id=comparison_id,
        parent_run_id=parent_run_id,
        now=current,
        entropy=entropy,
    )
    steps = tuple(ManagedStep(value) for value in recipe["steps"])  # type: ignore[arg-type]
    endpoints = (
        "http://127.0.0.1:1337/v1",
        "http://127.0.0.1:8100/v1",
        "http://127.0.0.1:8080/v1",
    )
    plan = ManagedRunPlan(
        schema_version=MANAGED_PLAN_SCHEMA_VERSION,
        identity=identity,
        recipe_id=recipe_id,
        family_id=family_id,
        comparison_class_id=(
            comparison_class.comparison_class_id
            if comparison_class is not None
            else None
        ),
        comparison_class_path=(
            _repo_relative(comparison_class.path)
            if comparison_class is not None
            else None
        ),
        baseline_cell_ids=baseline_cell_ids,
        steps=steps,
        cell_ids=cell_ids,
        pair_ids=pair_ids,
        matrix_mode=str(recipe["matrix_mode"]),
        campaign_path=_repo_relative(campaign_path),
        suite_paths=(
            (ManagedStep.MATRIX.value, _repo_relative(campaign.suite_path)),
            (
                ManagedStep.PREFERENCE.value,
                _repo_relative(DEFAULT_PREFERENCE_SUITE),
            ),
            (ManagedStep.RAG_ORACLE.value, _repo_relative(DEFAULT_RAG_SUITE)),
            (ManagedStep.RAG_KEYWORD.value, _repo_relative(DEFAULT_RAG_SUITE)),
            (ManagedStep.OVERHEAD.value, _repo_relative(campaign.suite_path)),
        ),
        rag_corpus_path=_repo_relative(DEFAULT_RAG_CORPUS),
        cells_root=_repo_relative(DEFAULT_CELLS_ROOT),
        pairs_root=_repo_relative(DEFAULT_PAIRS_ROOT),
        input_hashes=tuple(sorted((
            *_hash_inputs(input_paths),
            (MACHINE_PROFILE_INPUT, _sha256(machine_profile_path)),
        ))),
        endpoints=endpoints,
        runtimes=frozenset({"osaurus", "omlx", "optiq"}),
        request_count=request_count,
        estimated_minutes=estimated_minutes,
        memory_floor_percent=int(recipe["memory_floor_percent"]),
        max_parallel_models=1,
        created_at=current.isoformat(),
        plan_hash="",
    )
    resolved = replace(plan, plan_hash=_canonical_plan_hash(plan))
    verify_plan_inputs(
        resolved,
        machine_profile_path=machine_profile_path,
    )
    verify_plan_hash(resolved)
    return resolved
