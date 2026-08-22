"""Resolve a managed plan's lineup: which cells run together, in what order.

A lineup is declared in exactly one of four ways -- native baseline, comparison
class, binding, or open mix -- which differ in provenance and authority but not
in what they produce. This module owns the knowledge of which plan field
combinations are legal for each kind, so callers never re-derive it.

See CONTEXT.md for the vocabulary and docs/adr/0001-native-diagonal.md for why
a lineup may extend a family's baseline but never replace or reorder it.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path

from .artifact_profile import ArtifactRoots
from .comparison_class import ComparisonClass
from .matrix_config import (
    EXPECTED_CAMPAIGN_PORTS,
    REPOSITORY_ROOT,
    Campaign,
    Cell,
    MatrixError,
)
from .managed_run_types import ManagedRunPlan, ManagedStep
from .open_mix import OpenMix, load_open_mix
from .overhead_config import OverheadPair


KIND_BASELINE = "baseline"
KIND_COMPARISON_CLASS = "comparison_class"
KIND_BINDING = "binding"
KIND_OPEN_MIX = "open_mix"


def lineup_kind(plan: ManagedRunPlan) -> str:
    """Name the lineup kind from the plan alone, without touching the disk."""

    if plan.comparison_scope == "open_mix":
        return KIND_OPEN_MIX
    if plan.binding_id is not None:
        return KIND_BINDING
    if plan.comparison_class_id is not None:
        return KIND_COMPARISON_CLASS
    return KIND_BASELINE


@dataclass(frozen=True)
class OpenMixRuntimeContext:
    definition: OpenMix
    campaign: Campaign
    cells: tuple[Cell, ...]
    family_ids_by_cell: dict[str, str]
    family_ids_by_pair: dict[str, str]
    collection_identity: dict[str, object]


def repo_path(value: str) -> Path:
    return REPOSITORY_ROOT / value


def _open_mix_context(
    plan: ManagedRunPlan,
    artifact_roots: ArtifactRoots,
) -> OpenMixRuntimeContext:
    if (
        plan.comparison_scope != "open_mix"
        or plan.open_mix_id is None
        or plan.open_mix_revision is None
        or plan.open_mix_path is None
        or plan.suite_contract_id is None
        or plan.suite_contract_revision is None
        or plan.suite_contract_path is None
    ):
        raise RuntimeError("managed open-mix identity is incomplete")
    definition = load_open_mix(plan.open_mix_id)
    expected_members = tuple(
        (member.family_id, member.cell_id) for member in definition.members
    )
    if (
        definition.path != repo_path(plan.open_mix_path).resolve()
        or definition.revision != plan.open_mix_revision
        or expected_members != plan.open_mix_members
        or definition.cell_ids != plan.cell_ids
        or definition.suite_contract.suite_contract_id != plan.suite_contract_id
        or definition.suite_contract.revision != plan.suite_contract_revision
        or definition.suite_contract.path
        != repo_path(plan.suite_contract_path).resolve()
    ):
        raise RuntimeError("managed open-mix definition does not match plan")

    bound_inputs = dict(plan.input_hashes)
    campaigns: dict[str, Campaign] = {}
    for family_id in dict.fromkeys(definition.family_ids):
        relative = f"config/matrix/{family_id}-campaign.json"
        if relative not in bound_inputs:
            raise RuntimeError("managed open-mix family campaign is not bound")
        campaign = Campaign.load(repo_path(relative))
        if campaign.family_id != family_id:
            raise RuntimeError("managed open-mix family campaign mismatch")
        campaigns[family_id] = campaign

    cells: list[Cell] = []
    family_ids_by_cell: dict[str, str] = {}
    for member in definition.members:
        family = member.family.resolve(artifact_roots)
        cell = member.cell.resolve(artifact_roots)
        cell.validate_for_family(family)
        cells.append(cell)
        family_ids_by_cell[cell.cell_id] = member.family_id

    pair_families: dict[str, str] = {}
    pair_ids_by_cell: dict[str, str] = {}
    for pair_id in plan.pair_ids:
        pair = OverheadPair.load(repo_path(plan.pairs_root) / f"{pair_id}.json")
        matches = {
            family_ids_by_cell[cell_id]
            for cell_id in (pair.direct_cell_id, pair.backend_cell_id)
            if cell_id in family_ids_by_cell
        }
        if (
            pair.direct_cell_id not in family_ids_by_cell
            or pair.backend_cell_id not in family_ids_by_cell
            or len(matches) != 1
        ):
            raise RuntimeError("managed open-mix overhead pair is invalid")
        pair_families[pair_id] = next(iter(matches))
        pair_ids_by_cell[pair.direct_cell_id] = pair_id

    suite_path = repo_path(plan.suite_path(ManagedStep.MATRIX)).resolve()
    if suite_path != definition.suite_contract.matrix_suite_path:
        raise RuntimeError("managed open-mix matrix suite mismatch")
    if any(item.suite_path != suite_path for item in campaigns.values()):
        raise RuntimeError("managed open-mix family campaign suite mismatch")
    campaign = Campaign(
        campaign_id=f"{definition.open_mix_id}--open-mix",
        family_id=definition.open_mix_id,
        family=definition.members[0].family.resolve(artifact_roots),
        suite_path=suite_path,
        results_root=Path("."),
        memory_floor_percent=plan.memory_floor_percent,
        ready_timeout_seconds=max(
            item.ready_timeout_seconds for item in campaigns.values()
        ),
        request_timeout_seconds=max(
            item.request_timeout_seconds for item in campaigns.values()
        ),
        on_cell_failure="continue",
        ports=dict(EXPECTED_CAMPAIGN_PORTS),
        cell_paths=tuple(member.cell_path for member in definition.members),
        cells=tuple(cells),
    )
    identity: dict[str, object] = {
        "comparison_scope": "open_mix",
        "open_mix_id": definition.open_mix_id,
        "open_mix_revision": definition.revision,
        "suite_contract_id": definition.suite_contract.suite_contract_id,
        "suite_contract_revision": definition.suite_contract.revision,
        "members": [
            {"family_id": family_id, "cell_id": cell_id}
            for family_id, cell_id in expected_members
        ],
        "overhead_coverage": [
            (
                {
                    "family_id": family_id,
                    "cell_id": cell_id,
                    "status": "PLANNED",
                    "pair_id": pair_ids_by_cell[cell_id],
                }
                if cell_id in pair_ids_by_cell
                else {
                    "family_id": family_id,
                    "cell_id": cell_id,
                    "status": "N/A",
                    "reason": "no reviewed direct-versus-Osaurus pair",
                }
            )
            for family_id, cell_id in expected_members
        ],
    }
    return OpenMixRuntimeContext(
        definition=definition,
        campaign=campaign,
        cells=tuple(cells),
        family_ids_by_cell=family_ids_by_cell,
        family_ids_by_pair=pair_families,
        collection_identity=identity,
    )


def _campaign_for_plan(
    plan: ManagedRunPlan,
    artifact_roots: ArtifactRoots,
) -> Campaign:
    if plan.comparison_scope == "open_mix":
        return _open_mix_context(plan, artifact_roots).campaign
    baseline = Campaign.load(repo_path(plan.campaign_path))
    baseline_ids = tuple(cell.cell_id for cell in baseline.cells)
    if baseline_ids != plan.baseline_cell_ids:
        raise RuntimeError("managed plan baseline campaign mismatch")
    if plan.binding_id is not None:
        if (
            plan.comparison_class_id is not None
            or plan.comparison_class_path is not None
            or plan.binding_revision is None
            or plan.binding_hash is None
            or plan.binding_proposal_hash is None
        ):
            raise RuntimeError("managed plan binding metadata is invalid")
        cell_paths = tuple(
            repo_path(plan.cells_root) / f"{cell_id}.json" for cell_id in plan.cell_ids
        )
        try:
            cells = tuple(
                Cell.load(
                    path,
                    family=baseline.family,
                    require_native_server=True,
                )
                for path in cell_paths
            )
        except (MatrixError, OSError, ValueError, KeyError, TypeError) as error:
            raise RuntimeError("managed plan binding cells are invalid") from error
        if tuple(cell.cell_id for cell in cells) != plan.cell_ids:
            raise RuntimeError("managed plan binding cell order is invalid")
        return replace(
            baseline,
            campaign_id=f"{baseline.campaign_id}--{plan.binding_id}",
            cell_paths=cell_paths,
            cells=cells,
        ).resolve(artifact_roots)
    if plan.comparison_class_id is None:
        if (
            plan.comparison_class_path is not None
            or plan.binding_revision is not None
            or plan.binding_hash is not None
            or plan.binding_proposal_hash is not None
            or plan.cell_ids != baseline_ids
        ):
            raise RuntimeError("managed plan native baseline is invalid")
        return baseline.resolve(artifact_roots)
    if plan.comparison_class_path is None:
        raise RuntimeError("managed plan comparison class path is missing")
    definition = ComparisonClass.load(repo_path(plan.comparison_class_path))
    if (
        definition.comparison_class_id != plan.comparison_class_id
        or definition.family_id != plan.family_id
        or definition.baseline_campaign_path != repo_path(plan.campaign_path).resolve()
        or definition.baseline_cell_ids != plan.baseline_cell_ids
        or definition.cell_ids != plan.cell_ids
    ):
        raise RuntimeError("managed plan comparison class mismatch")
    return definition.materialize_campaign().resolve(artifact_roots)


@dataclass(frozen=True)
class Lineup:
    """One resolved lineup: its kind, its campaign, and open-mix context if any.

    `open_mix` is None for every same-family kind. Collectors treat that None as
    "no per-family qualification needed", so it is load-bearing, not laziness.
    """

    kind: str
    campaign: Campaign
    open_mix: OpenMixRuntimeContext | None


def resolve_lineup(
    plan: ManagedRunPlan,
    artifact_roots: ArtifactRoots,
) -> Lineup:
    """Validate a plan's lineup identity against its checked-in definition."""

    kind = lineup_kind(plan)
    if kind == KIND_OPEN_MIX:
        context = _open_mix_context(plan, artifact_roots)
        return Lineup(kind=kind, campaign=context.campaign, open_mix=context)
    return Lineup(
        kind=kind,
        campaign=_campaign_for_plan(plan, artifact_roots),
        open_mix=None,
    )
