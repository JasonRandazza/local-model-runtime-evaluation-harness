from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from local_model_runtime_evaluation.discovery_types import (
    DiscoveryError,
    load_proposal,
    verify_proposal_hash,
    write_execution,
)
from local_model_runtime_evaluation.preference_config import load_family_cell_recipes

RunPreference = Callable[[str, tuple[str, ...], str], Path]
RunRag = Callable[[str, tuple[str, ...]], Path]


@dataclass(frozen=True)
class DiscoverySuiteHooks:
    run_preference: RunPreference
    run_rag_oracle: RunRag
    run_rag_keyword: RunRag


def default_suite_hooks(
    *,
    preference_suite: Path,
    rag_suite: Path,
    rag_corpus: Path,
    cells_root: Path,
    preference_results: Path,
    rag_results: Path,
) -> DiscoverySuiteHooks:
    def run_preference(
        family_id: str,
        cell_ids: tuple[str, ...],
        judge_cell_id: str,
    ) -> Path:
        from local_model_runtime_evaluation.preference_collect import run_collect
        from local_model_runtime_evaluation.preference_config import PreferenceSuite
        from local_model_runtime_evaluation.preference_judge import run_judge
        from local_model_runtime_evaluation.preference_review import run_review
        from local_model_runtime_evaluation.preference_tally import run_tally

        run_dir = run_collect(
            cell_ids,
            preference_suite,
            cells_root,
            preference_results,
            family_id=family_id,
        )
        suite = PreferenceSuite.load(preference_suite)
        run_review(run_dir, seed=0, cell_ids=cell_ids, suite=suite)
        run_judge(
            run_dir,
            judge_cell_id=judge_cell_id,
            cells_root=cells_root,
            suite=suite,
            family_id=family_id,
        )
        run_tally(run_dir)
        return run_dir

    def run_rag(mode: str) -> RunRag:
        def _inner(family_id: str, cell_ids: tuple[str, ...]) -> Path:
            from local_model_runtime_evaluation.rag_collect import run_collect
            from local_model_runtime_evaluation.rag_config import RagSuite
            from local_model_runtime_evaluation.rag_score import score_run

            run_dir = run_collect(
                cell_ids,
                rag_suite,
                rag_corpus,
                cells_root,
                rag_results,
                family_id=family_id,
                mode=mode,
            )
            score_run(run_dir, RagSuite.load(rag_suite))
            return run_dir

        return _inner

    return DiscoverySuiteHooks(
        run_preference=run_preference,
        run_rag_oracle=run_rag("oracle"),
        run_rag_keyword=run_rag("keyword"),
    )


def _resolve_cell_ids(
    family_id: str,
    preference_recipes: dict[str, tuple[str, ...]] | None,
) -> tuple[str, ...]:
    recipes = preference_recipes if preference_recipes is not None else load_family_cell_recipes()
    if family_id not in recipes:
        raise DiscoveryError(f"no preference recipe for family {family_id!r}")
    return recipes[family_id]


def execute_proposal(
    *,
    results_root: Path,
    proposal_id: str,
    family_id: str,
    hooks: DiscoverySuiteHooks,
    preference_recipes: dict[str, tuple[str, ...]] | None = None,
) -> dict[str, object]:
    proposal = load_proposal(results_root, proposal_id)
    verify_proposal_hash(proposal)

    executable_families = proposal.get("executable_families")
    if not isinstance(executable_families, list) or family_id not in executable_families:
        raise DiscoveryError(f"family {family_id!r} is not executable")

    cell_ids = _resolve_cell_ids(family_id, preference_recipes)
    judge_cell_id = cell_ids[0]

    steps: list[dict[str, object]] = []
    step_hooks: tuple[tuple[str, Callable[[], Path]], ...] = (
        ("preference", lambda: hooks.run_preference(family_id, cell_ids, judge_cell_id)),
        ("rag_oracle", lambda: hooks.run_rag_oracle(family_id, cell_ids)),
        ("rag_keyword", lambda: hooks.run_rag_keyword(family_id, cell_ids)),
    )

    for step_name, run_step in step_hooks:
        try:
            run_dir = run_step()
        except Exception as error:
            steps.append({
                "step": step_name,
                "status": "FAIL",
                "error": str(error),
            })
            execution = {
                "proposal_id": proposal_id,
                "family_id": family_id,
                "ok": False,
                "steps": steps,
            }
            write_execution(results_root / proposal_id, execution)
            return execution

        steps.append({
            "step": step_name,
            "status": "PASS",
            "run_dir": str(run_dir),
        })

    execution = {
        "proposal_id": proposal_id,
        "family_id": family_id,
        "ok": True,
        "steps": steps,
    }
    write_execution(results_root / proposal_id, execution)
    return execution
