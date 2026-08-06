"""Fail-closed orchestration for managed local evaluation runs."""

from __future__ import annotations

import json
import os
import re
import shutil
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Callable

from .artifact_profile import (
    DEFAULT_MACHINE_PROFILE_PATH,
    ArtifactRoots,
    load_artifact_roots,
)
from .comparison_class import ComparisonClass
from .credentials import (
    OSAURUS_KEYCHAIN_SERVICE,
    KeychainCredentialProvider,
)
from .evidence_bundle import EvidenceBundle, resume_is_allowed
from .matrix_config import (
    REPOSITORY_ROOT,
    Campaign,
    Cell,
    MatrixError,
    MatrixSuite,
    load_family,
)
from .matrix_runner import run_campaign
from .matrix_servers import ServerHandle
from .managed_run_types import (
    ManagedRunPlan,
    ManagedStep,
    RunSummaryState,
    StepState,
)
from .operator_policy import AdoptedPolicy, authorize
from .overhead_config import OverheadPair
from .overhead_runner import run_overhead
from .preference_collect import run_collect as run_preference_collect
from .preference_config import PreferenceSuite
from .preference_judge import DEFAULT_JUDGE_CELL, run_judge
from .preference_review import run_review
from .preference_tally import run_tally
from .rag_collect import run_collect as run_rag_collect
from .rag_config import RagCorpus, RagSuite
from .rag_score import score_run
from .resources import HostResourceProbe
from .run_identity import verify_plan_hash, verify_plan_inputs
from .runtime_manager import RuntimeManager
from .transport import LoopbackTransport


BuildServer = Callable[..., object]
CollectorHook = Callable[[ManagedRunPlan, Path, BuildServer], Path]


@dataclass(frozen=True)
class ManagedCollectorHooks:
    preflight: Callable[[ManagedRunPlan], dict[str, object]]
    matrix: CollectorHook
    preference: CollectorHook
    rag_oracle: CollectorHook
    rag_keyword: CollectorHook
    routed_models: Callable[[ManagedRunPlan], tuple[str, ...]]
    overhead: CollectorHook


def _repo_path(value: str) -> Path:
    return REPOSITORY_ROOT / value


def _campaign_for_plan(
    plan: ManagedRunPlan,
    artifact_roots: ArtifactRoots,
) -> Campaign:
    if plan.comparison_scope == "open_mix":
        raise RuntimeError("open-mix live campaign materialization is not implemented")
    baseline = Campaign.load(_repo_path(plan.campaign_path))
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
            _repo_path(plan.cells_root) / f"{cell_id}.json" for cell_id in plan.cell_ids
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
    definition = ComparisonClass.load(_repo_path(plan.comparison_class_path))
    if (
        definition.comparison_class_id != plan.comparison_class_id
        or definition.family_id != plan.family_id
        or definition.baseline_campaign_path != _repo_path(plan.campaign_path).resolve()
        or definition.baseline_cell_ids != plan.baseline_cell_ids
        or definition.cell_ids != plan.cell_ids
    ):
        raise RuntimeError("managed plan comparison class mismatch")
    return definition.materialize_campaign().resolve(artifact_roots)


def default_collector_hooks(
    plan: ManagedRunPlan,
    runtime_manager: RuntimeManager,
    bundle: EvidenceBundle,
    *,
    machine_profile_path: Path = DEFAULT_MACHINE_PROFILE_PATH,
) -> ManagedCollectorHooks:
    """Bind the retained collectors to one immutable managed plan."""

    if plan.comparison_scope == "open_mix":
        raise RuntimeError("open-mix live collectors are not implemented")

    artifact_roots = load_artifact_roots(machine_profile_path)
    campaign = _campaign_for_plan(plan, artifact_roots)
    cells_root = _repo_path(plan.cells_root)
    pairs_root = _repo_path(plan.pairs_root)
    preference_path = _repo_path(plan.suite_path(ManagedStep.PREFERENCE))
    rag_path = _repo_path(plan.suite_path(ManagedStep.RAG_ORACLE))
    corpus_root = _repo_path(plan.rag_corpus_path)
    route_handle: ServerHandle | None = None

    def preflight(candidate: ManagedRunPlan) -> dict[str, object]:
        verify_plan_hash(candidate)
        verify_plan_inputs(
            candidate,
            machine_profile_path=machine_profile_path,
        )
        loaded_campaign = _campaign_for_plan(candidate, artifact_roots)
        MatrixSuite.load(_repo_path(candidate.suite_path(ManagedStep.MATRIX)))
        PreferenceSuite.load(_repo_path(candidate.suite_path(ManagedStep.PREFERENCE)))
        rag_suite = RagSuite.load(
            _repo_path(candidate.suite_path(ManagedStep.RAG_ORACLE))
        )
        RagCorpus.load(_repo_path(candidate.rag_corpus_path))
        family_template = load_family(candidate.family_id)
        family = family_template.resolve(artifact_roots)
        missing_artifacts: list[str] = []
        missing_executables: list[str] = []
        for cell_id in candidate.cell_ids:
            cell = Cell.load(
                _repo_path(candidate.cells_root) / f"{cell_id}.json",
                family=family_template,
            ).resolve(artifact_roots)
            cell.validate_for_family(family)
            artifact = Path(cell.artifact_path)
            if not artifact.exists():
                missing_artifacts.append(cell.cell_id)
            executable = cell.start_command[0]
            if (Path(executable).is_absolute() and not Path(executable).is_file()) or (
                not Path(executable).is_absolute() and shutil.which(executable) is None
            ):
                missing_executables.append(executable)
        for pair_id in candidate.pair_ids:
            pair_template = OverheadPair.load(
                _repo_path(candidate.pairs_root) / f"{pair_id}.json"
            )
            backend = Cell.load(
                _repo_path(candidate.cells_root)
                / f"{pair_template.backend_cell_id}.json",
                family=family_template,
            ).resolve(artifact_roots)
            pair_template.resolve(backend.artifact_path)
        if missing_artifacts:
            raise RuntimeError(
                "managed artifacts are missing for cells: "
                + ", ".join(missing_artifacts)
            )
        if missing_executables:
            raise RuntimeError(
                "managed runtime executables are missing: "
                + ", ".join(sorted(set(missing_executables)))
            )
        free_memory = HostResourceProbe().free_memory_percent()
        if free_memory < candidate.memory_floor_percent:
            raise RuntimeError("free memory is below the managed run floor")
        return {
            "campaign_id": loaded_campaign.campaign_id,
            "cell_count": len(candidate.cell_ids),
            "binding_id": candidate.binding_id,
            "comparison_class_id": candidate.comparison_class_id,
            "free_memory_percent": free_memory,
            "rag_suite_id": rag_suite.suite_id,
            "request_count": candidate.request_count,
        }

    def matrix(
        candidate: ManagedRunPlan,
        output_root: Path,
        build_server: BuildServer,
    ) -> Path:
        return run_campaign(
            campaign,
            candidate.matrix_mode,
            output_root,
            cell_filter=candidate.cell_ids,
            build_server=build_server,
            lifecycle_managed=True,
        )

    def preference(
        candidate: ManagedRunPlan,
        output_root: Path,
        build_server: BuildServer,
    ) -> Path:
        suite = PreferenceSuite.load(preference_path)
        run_dir = run_preference_collect(
            candidate.cell_ids,
            preference_path,
            cells_root,
            output_root,
            family_id=candidate.family_id,
            artifact_roots=artifact_roots,
            build_server=build_server,
            memory_floor_percent=candidate.memory_floor_percent,
        )
        run_review(
            run_dir,
            seed=0,
            cell_ids=candidate.cell_ids,
            suite=suite,
        )
        judge_cell = (
            DEFAULT_JUDGE_CELL
            if DEFAULT_JUDGE_CELL in candidate.cell_ids
            else candidate.cell_ids[0]
        )
        run_judge(
            run_dir,
            judge_cell_id=judge_cell,
            cells_root=cells_root,
            suite=suite,
            family_id=candidate.family_id,
            artifact_roots=artifact_roots,
            build_server=build_server,
        )
        return run_tally(run_dir)

    def rag(
        mode: str,
        candidate: ManagedRunPlan,
        output_root: Path,
        build_server: BuildServer,
    ) -> Path:
        suite = RagSuite.load(rag_path)
        run_dir = run_rag_collect(
            candidate.cell_ids,
            rag_path,
            corpus_root,
            cells_root,
            output_root,
            family_id=candidate.family_id,
            artifact_roots=artifact_roots,
            build_server=build_server,
            memory_floor_percent=candidate.memory_floor_percent,
            mode=mode,
        )
        return score_run(run_dir, suite)

    def routed_models(candidate: ManagedRunPlan) -> tuple[str, ...]:
        nonlocal route_handle
        base_url = "http://127.0.0.1:1337/v1"
        credential = KeychainCredentialProvider(service=OSAURUS_KEYCHAIN_SERVICE).get()
        transport = LoopbackTransport(set(candidate.endpoints))
        if route_handle is None:
            family_template = load_family(candidate.family_id)
            family = family_template.resolve(artifact_roots)
            osaurus_cell: Cell | None = None
            for cell_id in candidate.cell_ids:
                cell = Cell.load(
                    _repo_path(candidate.cells_root) / f"{cell_id}.json",
                    family=family_template,
                ).resolve(artifact_roots)
                cell.validate_for_family(family)
                if cell.server == "osaurus":
                    osaurus_cell = cell
                    break
            if osaurus_cell is None:
                raise RuntimeError(
                    "managed route check requires one Osaurus native cell"
                )
            route_handle = runtime_manager.build_server(
                osaurus_cell,
                transport,
                bundle.run_dir / "runtime-logs",
                credential,
            )
            route_handle.start()
            route_handle.wait_ready(osaurus_cell.model_id, 180.0)
        return transport.list_models(
            base_url,
            credential,
        )

    def overhead(
        candidate: ManagedRunPlan,
        output_root: Path,
        build_server: BuildServer,
    ) -> Path:
        return run_overhead(
            candidate.pair_ids,
            pairs_root,
            cells_root,
            _repo_path(candidate.suite_path(ManagedStep.OVERHEAD)),
            output_root,
            family_id=candidate.family_id,
            artifact_roots=artifact_roots,
            mode=candidate.matrix_mode,
            build_server=build_server,
            memory_floor_percent=candidate.memory_floor_percent,
            lifecycle_managed=True,
        )

    return ManagedCollectorHooks(
        preflight=preflight,
        matrix=matrix,
        preference=preference,
        rag_oracle=lambda candidate, root, build: rag("oracle", candidate, root, build),
        rag_keyword=lambda candidate, root, build: rag(
            "keyword", candidate, root, build
        ),
        routed_models=routed_models,
        overhead=overhead,
    )


_SECRET_VALUE = re.compile(
    r"(?i)(api[_-]?key|authorization|credential|password|secret|token)"
    r"(\s*[:=]\s*)([^\s,;]+)"
)


def _sanitize_message(error: BaseException) -> str:
    message = str(error)
    return _SECRET_VALUE.sub(
        lambda match: f"{match.group(1)}{match.group(2)}<redacted>",
        message,
    )


def _error_detail(error: BaseException) -> dict[str, object]:
    code = getattr(error, "code", error.__class__.__name__)
    return {
        "error_code": str(code),
        "error_message": _sanitize_message(error),
        "error_type": error.__class__.__name__,
    }


def _required_routes(
    plan: ManagedRunPlan,
    artifact_roots: ArtifactRoots,
) -> tuple[str, ...]:
    root = Path(plan.pairs_root)
    if not root.is_absolute():
        root = REPOSITORY_ROOT / root
    family_template = load_family(plan.family_id)
    routes: list[str] = []
    for pair_id in plan.pair_ids:
        pair = OverheadPair.load(root / f"{pair_id}.json")
        backend = Cell.load(
            _repo_path(plan.cells_root) / f"{pair.backend_cell_id}.json",
            family=family_template,
        ).resolve(artifact_roots)
        routes.append(pair.resolve(backend.artifact_path).routed_model_id)
    return tuple(routes)


def _run_relative(bundle: EvidenceBundle, output: Path) -> str:
    resolved_root = bundle.run_dir.resolve()
    resolved_output = output.resolve()
    if not resolved_output.is_relative_to(resolved_root):
        raise ValueError("collector output escaped the managed evidence bundle")
    return resolved_output.relative_to(resolved_root).as_posix()


def _stop_pending(bundle: EvidenceBundle) -> None:
    for record in bundle.state.steps:
        if record.state is StepState.PENDING and record.step is not ManagedStep.SEAL:
            bundle.transition_step(record.step, StepState.STOPPED)


def _summary(
    plan: ManagedRunPlan,
    status: RunSummaryState,
    *,
    attempt: int | None = None,
    error: BaseException | None = None,
    missing_routes: tuple[str, ...] = (),
) -> dict[str, object]:
    body: dict[str, object] = {
        "attempt": plan.identity.attempt if attempt is None else attempt,
        "comparison_id": plan.identity.comparison_id,
        "binding_id": plan.binding_id,
        "comparison_class_id": plan.comparison_class_id,
        "run_id": plan.identity.run_id,
        "run_name": plan.identity.run_name,
        "status": status.value,
    }
    if error is not None:
        body["error"] = _error_detail(error)
    if missing_routes:
        body["completed_native_steps_valid"] = True
        body["missing_routed_model_ids"] = list(missing_routes)
    return body


def _seal_after_cleanup(
    bundle: EvidenceBundle,
    runtime_manager: RuntimeManager,
    summary: dict[str, object],
) -> bool:
    try:
        runtime_manager.release_all()
    except Exception:
        return False
    bundle.mark_cleanup_complete()
    seal_record = next(
        record for record in bundle.state.steps if record.step is ManagedStep.SEAL
    )
    if seal_record.state is StepState.PENDING:
        bundle.transition_step(ManagedStep.SEAL, StepState.RUNNING)
        bundle.transition_step(ManagedStep.SEAL, StepState.PASS)
    bundle.write_summary(summary)
    bundle.seal()
    return True


def execute_managed_run(
    plan: ManagedRunPlan,
    adopted_policy: AdoptedPolicy,
    bundle: EvidenceBundle,
    runtime_manager: RuntimeManager,
    hooks: ManagedCollectorHooks,
    *,
    machine_profile_path: Path = DEFAULT_MACHINE_PROFILE_PATH,
) -> dict[str, object]:
    """Execute an immutable managed plan and seal all terminal evidence."""

    if plan.comparison_scope == "open_mix":
        raise RuntimeError("open-mix live execution is not implemented")

    current: ManagedStep | None = None
    terminal = RunSummaryState.FAIL
    failure: BaseException | None = None
    missing_routes: tuple[str, ...] = ()
    try:
        verify_plan_hash(plan)
        verify_plan_inputs(plan, machine_profile_path=machine_profile_path)
        artifact_roots = load_artifact_roots(machine_profile_path)
        if bundle.plan.plan_hash != plan.plan_hash:
            raise ValueError("evidence bundle plan does not match execution plan")
        _verify_policy_snapshot(bundle, adopted_policy)
        authorize(adopted_policy.policy, plan.policy_request())
        bundle.append_event(
            "policy_authorized",
            {
                "policy_hash": adopted_policy.policy_hash,
                "policy_id": adopted_policy.policy.policy_id,
            },
        )

        for step, hook in (
            (ManagedStep.PREFLIGHT, hooks.preflight),
            (ManagedStep.MATRIX, hooks.matrix),
            (ManagedStep.PREFERENCE, hooks.preference),
            (ManagedStep.RAG_ORACLE, hooks.rag_oracle),
            (ManagedStep.RAG_KEYWORD, hooks.rag_keyword),
        ):
            current = step
            bundle.transition_step(step, StepState.RUNNING)
            if step is ManagedStep.PREFLIGHT:
                detail = hook(plan)
                bundle.transition_step(step, StepState.PASS, detail=detail)
                continue
            output_root = bundle.step_attempt_dir(
                step,
                bundle.state.attempt,
            )
            output_root.mkdir(parents=True, exist_ok=False)
            output = hook(plan, output_root, runtime_manager.build_server)
            bundle.transition_step(
                step,
                StepState.PASS,
                output_path=_run_relative(bundle, output),
            )

        current = ManagedStep.OVERHEAD
        bundle.transition_step(current, StepState.RUNNING)
        routed = frozenset(hooks.routed_models(plan))
        missing_routes = tuple(
            route
            for route in _required_routes(plan, artifact_roots)
            if route not in routed
        )
        if missing_routes:
            bundle.transition_step(
                current,
                StepState.BLOCKED_PROVIDER_RECONNECT,
                detail={
                    "missing_routed_model_ids": list(missing_routes),
                    "operator_action": (
                        "Reconnect the existing provider in the Osaurus UI, "
                        "then run lmre resume <run-id>."
                    ),
                },
            )
            terminal = RunSummaryState.PARTIAL_BLOCKED
        else:
            output_root = bundle.step_attempt_dir(
                current,
                bundle.state.attempt,
            )
            output_root.mkdir(parents=True, exist_ok=False)
            output = hooks.overhead(
                plan,
                output_root,
                runtime_manager.build_server,
            )
            bundle.transition_step(
                current,
                StepState.PASS,
                output_path=_run_relative(bundle, output),
            )
            terminal = RunSummaryState.PASS
    except KeyboardInterrupt as error:
        terminal = RunSummaryState.STOPPED
        failure = error
        if current is not None:
            record = next(item for item in bundle.state.steps if item.step is current)
            if record.state is StepState.RUNNING:
                bundle.transition_step(
                    current,
                    StepState.STOPPED,
                    detail=_error_detail(error),
                )
    except Exception as error:
        terminal = RunSummaryState.FAIL
        failure = error
        if current is not None:
            record = next(item for item in bundle.state.steps if item.step is current)
            if record.state is StepState.RUNNING:
                bundle.transition_step(
                    current,
                    StepState.FAIL,
                    detail=_error_detail(error),
                )

    _stop_pending(bundle)
    summary = _summary(
        plan,
        terminal,
        error=failure,
        missing_routes=missing_routes,
    )
    if not _seal_after_cleanup(bundle, runtime_manager, summary):
        cleanup_error = RuntimeError("managed runtime cleanup failed")
        return _summary(plan, RunSummaryState.FAIL, error=cleanup_error)
    return summary


def _verify_policy_snapshot(
    bundle: EvidenceBundle,
    adopted_policy: AdoptedPolicy,
) -> None:
    snapshot_path = bundle.run_dir / "policy-snapshot.json"
    try:
        snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError("managed policy snapshot is invalid") from error
    if (
        not isinstance(snapshot, dict)
        or snapshot.get("policy_hash") != adopted_policy.policy_hash
        or snapshot.get("policy") != adopted_policy.policy.to_dict()
        or snapshot.get("adopted_at") != adopted_policy.adopted_at
    ):
        raise RuntimeError(
            "current adopted policy does not match the run policy snapshot"
        )


def resume_managed_run(
    run_dir: Path,
    adopted_policy: AdoptedPolicy,
    runtime_manager: RuntimeManager,
    hooks: ManagedCollectorHooks,
    *,
    machine_profile_path: Path = DEFAULT_MACHINE_PROFILE_PATH,
) -> dict[str, object]:
    """Resume only overhead after an operator reconnects an existing provider."""

    lock_path = run_dir / ".resume.lock"
    try:
        descriptor = os.open(
            lock_path,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL,
            0o600,
        )
    except FileExistsError as error:
        raise RuntimeError("managed run already has an active resume writer") from error
    os.close(descriptor)
    try:
        bundle = EvidenceBundle.load(run_dir)
        bundle.verify()
        if bundle.plan.comparison_scope == "open_mix":
            raise RuntimeError("open-mix live resume is not implemented")
        state = bundle.state
        if not resume_is_allowed(state):
            raise RuntimeError("only a sealed overhead-only retry may resume")
        verify_plan_hash(bundle.plan)
        verify_plan_inputs(
            bundle.plan,
            machine_profile_path=machine_profile_path,
        )
        artifact_roots = load_artifact_roots(machine_profile_path)
        _verify_policy_snapshot(bundle, adopted_policy)
        authorize(adopted_policy.policy, bundle.plan.policy_request())

        attempt = bundle.begin_attempt()
        bundle.append_event(
            "policy_authorized",
            {
                "policy_hash": adopted_policy.policy_hash,
                "policy_id": adopted_policy.policy.policy_id,
            },
        )
        try:
            routed = frozenset(hooks.routed_models(bundle.plan))
        except BaseException as error:
            bundle.transition_step(ManagedStep.OVERHEAD, StepState.RUNNING)
            terminal_state = (
                StepState.STOPPED
                if isinstance(error, KeyboardInterrupt)
                else StepState.FAIL
            )
            terminal_summary = (
                RunSummaryState.STOPPED
                if isinstance(error, KeyboardInterrupt)
                else RunSummaryState.FAIL
            )
            bundle.transition_step(
                ManagedStep.OVERHEAD,
                terminal_state,
                detail=_error_detail(error),
            )
            summary = _summary(
                bundle.plan,
                terminal_summary,
                attempt=attempt,
                error=error,
            )
            if not _seal_after_cleanup(bundle, runtime_manager, summary):
                raise RuntimeError("managed runtime cleanup failed") from error
            raise
        missing = tuple(
            route
            for route in _required_routes(bundle.plan, artifact_roots)
            if route not in routed
        )
        if missing:
            error = RuntimeError(
                "required routed models are still missing: " + ", ".join(missing)
            )
            bundle.transition_step(ManagedStep.OVERHEAD, StepState.RUNNING)
            bundle.transition_step(
                ManagedStep.OVERHEAD,
                StepState.BLOCKED_PROVIDER_RECONNECT,
                detail={
                    "missing_routed_model_ids": list(missing),
                    "operator_action": (
                        "Reconnect the existing provider in the Osaurus UI, "
                        "then run lmre resume <run-id>."
                    ),
                },
            )
            summary = _summary(
                bundle.plan,
                RunSummaryState.PARTIAL_BLOCKED,
                attempt=attempt,
                missing_routes=missing,
            )
            if not _seal_after_cleanup(bundle, runtime_manager, summary):
                raise RuntimeError("managed runtime cleanup failed") from error
            raise error

        bundle.transition_step(ManagedStep.OVERHEAD, StepState.RUNNING)
        output_root = bundle.step_attempt_dir(
            ManagedStep.OVERHEAD,
            attempt,
        )
        output_root.mkdir(parents=True, exist_ok=False)
        try:
            output = hooks.overhead(
                bundle.plan,
                output_root,
                runtime_manager.build_server,
            )
            bundle.transition_step(
                ManagedStep.OVERHEAD,
                StepState.PASS,
                output_path=_run_relative(bundle, output),
            )
            terminal = RunSummaryState.PASS
            failure: BaseException | None = None
        except KeyboardInterrupt as error:
            terminal = RunSummaryState.STOPPED
            failure = error
            bundle.transition_step(
                ManagedStep.OVERHEAD,
                StepState.STOPPED,
                detail=_error_detail(error),
            )
        except Exception as error:
            terminal = RunSummaryState.FAIL
            failure = error
            bundle.transition_step(
                ManagedStep.OVERHEAD,
                StepState.FAIL,
                detail=_error_detail(error),
            )
        summary = _summary(
            bundle.plan,
            terminal,
            attempt=attempt,
            error=failure,
        )
        if not _seal_after_cleanup(bundle, runtime_manager, summary):
            cleanup_error = RuntimeError("managed runtime cleanup failed")
            return _summary(
                bundle.plan,
                RunSummaryState.FAIL,
                attempt=attempt,
                error=cleanup_error,
            )
        return summary
    finally:
        lock_path.unlink(missing_ok=True)
