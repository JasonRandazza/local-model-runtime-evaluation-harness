"""CLI for Approach 3 free-form recipes."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from local_model_runtime_evaluation.artifact_profile import (
    DEFAULT_MACHINE_PROFILE_PATH,
    ArtifactRoots,
    load_artifact_roots,
)
from local_model_runtime_evaluation.approach3 import (
    DEFAULT_APPROACH3_ROOT,
    DEFAULT_CELLS_ROOT,
    Approach3Error,
    FreeFormRecipe,
    dry_config,
    list_recipes,
    load_recipe_cells,
    resolve_recipe_path,
)
from local_model_runtime_evaluation.matrix_config import REPOSITORY_ROOT
from local_model_runtime_evaluation.overhead_config import (
    DEFAULT_PAIRS_ROOT,
    OverheadPair,
    resolve_overhead_selection,
)
from local_model_runtime_evaluation.overhead_runner import run_overhead
from local_model_runtime_evaluation.preference_collect import run_collect
from local_model_runtime_evaluation.rag_collect import run_collect as run_rag_collect

DEFAULT_PREFERENCE_SUITE = REPOSITORY_ROOT / "suites" / "multi-family-preference-v1.json"
DEFAULT_PREFERENCE_RESULTS = REPOSITORY_ROOT / "results" / "preference"
DEFAULT_RAG_SUITE = REPOSITORY_ROOT / "suites" / "multi-family-rag-oracle-v1.json"
DEFAULT_RAG_CORPUS = REPOSITORY_ROOT / "corpora" / "rag-oracle-v1"
DEFAULT_RAG_RESULTS = REPOSITORY_ROOT / "results" / "rag"
DEFAULT_OVERHEAD_SUITE = REPOSITORY_ROOT / "suites" / "gemma-matrix-v1.json"
DEFAULT_OVERHEAD_RESULTS = REPOSITORY_ROOT / "results" / "overhead"


def _print(payload: dict[str, object]) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True))


def _cmd_list(*, root: Path) -> dict[str, object]:
    paths = list_recipes(root=root)
    return {
        "ok": True,
        "recipes": [path.stem for path in paths],
        "paths": [str(path) for path in paths],
    }


def _cmd_show(recipe_ref: str, *, root: Path) -> dict[str, object]:
    path = resolve_recipe_path(recipe_ref, root=root)
    recipe = FreeFormRecipe.load(path)
    return {
        "ok": True,
        "recipe_id": recipe.recipe_id,
        "revision": recipe.revision,
        "family_id": recipe.family_id,
        "require_native_server": recipe.require_native_server,
        "cell_ids": list(recipe.cell_ids),
        "suites": list(recipe.suites),
        "notes": recipe.notes,
        "path": str(recipe.path),
        "live_collect": "UNTESTED",
    }


def _cmd_collect_preference(
    recipe_ref: str,
    *,
    root: Path,
    cells_root: Path,
    suite_path: Path,
    results_root: Path,
    confirm_live: bool,
    artifact_roots: ArtifactRoots,
) -> dict[str, object]:
    if not confirm_live:
        raise Approach3Error(
            "refusing live collect without --i-understand-live "
            "(Approach 3 live collect is UNTESTED)",
            code="live_not_confirmed",
        )
    path = resolve_recipe_path(recipe_ref, root=root)
    recipe = FreeFormRecipe.load(path)
    if "preference" not in recipe.suites:
        raise Approach3Error(
            "recipe does not list preference suite",
            code="suite_unsupported",
        )
    cells = load_recipe_cells(
        recipe,
        cells_root=cells_root,
        artifact_roots=artifact_roots,
    )
    run_dir = run_collect(
        tuple(cell.cell_id for cell in cells),
        suite_path,
        cells_root,
        results_root,
        family_id=recipe.family_id,
        artifact_roots=artifact_roots,
        require_native_server=recipe.require_native_server,
    )
    return {
        "ok": True,
        "status": "COLLECT_FINISHED",
        "live_collect": "EXECUTED_UNSEALED",
        "recipe_id": recipe.recipe_id,
        "family_id": recipe.family_id,
        "run_dir": str(run_dir),
    }


def _cmd_collect_rag(
    recipe_ref: str,
    *,
    root: Path,
    cells_root: Path,
    suite_path: Path,
    corpus_root: Path,
    results_root: Path,
    mode: str,
    confirm_live: bool,
    artifact_roots: ArtifactRoots,
) -> dict[str, object]:
    if not confirm_live:
        raise Approach3Error(
            "refusing live collect without --i-understand-live "
            "(Approach 3 live collect is UNTESTED)",
            code="live_not_confirmed",
        )
    path = resolve_recipe_path(recipe_ref, root=root)
    recipe = FreeFormRecipe.load(path)
    if "rag" not in recipe.suites:
        raise Approach3Error(
            "recipe does not list rag suite",
            code="suite_unsupported",
        )
    if mode not in {"oracle", "keyword"}:
        raise Approach3Error(
            "rag mode must be oracle or keyword",
            code="rag_mode_invalid",
        )
    cells = load_recipe_cells(
        recipe,
        cells_root=cells_root,
        artifact_roots=artifact_roots,
    )
    run_dir = run_rag_collect(
        tuple(cell.cell_id for cell in cells),
        suite_path,
        corpus_root,
        cells_root,
        results_root,
        family_id=recipe.family_id,
        artifact_roots=artifact_roots,
        mode=mode,
        require_native_server=recipe.require_native_server,
    )
    return {
        "ok": True,
        "status": "COLLECT_FINISHED",
        "live_collect": "EXECUTED_UNSEALED",
        "recipe_id": recipe.recipe_id,
        "family_id": recipe.family_id,
        "mode": mode,
        "run_dir": str(run_dir),
    }


def _pair_ids_for_recipe(
    recipe: FreeFormRecipe,
    *,
    pairs_root: Path = DEFAULT_PAIRS_ROOT,
) -> tuple[str, ...]:
    """Select family overhead pairs that touch recipe cells; else all family pairs."""
    selection = resolve_overhead_selection(family_id=recipe.family_id, pairs=None)
    cell_set = set(recipe.cell_ids)
    matched: list[str] = []
    for pair_id in selection.pairs:
        pair = OverheadPair.load(pairs_root / f"{pair_id}.json")
        if pair.direct_cell_id in cell_set or pair.backend_cell_id in cell_set:
            matched.append(pair_id)
    if matched:
        return tuple(matched)
    return selection.pairs


def _cmd_collect_overhead(
    recipe_ref: str,
    *,
    root: Path,
    cells_root: Path,
    pairs_root: Path,
    suite_path: Path,
    results_root: Path,
    confirm_live: bool,
    artifact_roots: ArtifactRoots,
) -> dict[str, object]:
    if not confirm_live:
        raise Approach3Error(
            "refusing live collect without --i-understand-live "
            "(Approach 3 live collect is UNTESTED)",
            code="live_not_confirmed",
        )
    path = resolve_recipe_path(recipe_ref, root=root)
    recipe = FreeFormRecipe.load(path)
    if "overhead" not in recipe.suites:
        raise Approach3Error(
            "recipe does not list overhead suite",
            code="suite_unsupported",
        )
    # Validate cells load under recipe rules before measuring.
    load_recipe_cells(
        recipe,
        cells_root=cells_root,
        artifact_roots=artifact_roots,
    )
    pair_ids = _pair_ids_for_recipe(recipe, pairs_root=pairs_root)
    run_dir = run_overhead(
        pair_ids,
        pairs_root,
        cells_root,
        suite_path,
        results_root,
        family_id=recipe.family_id,
        artifact_roots=artifact_roots,
    )
    return {
        "ok": True,
        "status": "COLLECT_FINISHED",
        "live_collect": "EXECUTED_UNSEALED",
        "recipe_id": recipe.recipe_id,
        "family_id": recipe.family_id,
        "pair_ids": list(pair_ids),
        "run_dir": str(run_dir),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="lmre-approach3")
    parser.add_argument(
        "--approach3-root",
        type=Path,
        default=DEFAULT_APPROACH3_ROOT,
    )
    parser.add_argument(
        "--cells-root",
        type=Path,
        default=DEFAULT_CELLS_ROOT,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("list")

    dry = sub.add_parser("dry-config")
    dry.add_argument("recipe")

    show = sub.add_parser("show")
    show.add_argument("recipe")

    collect = sub.add_parser("collect-preference")
    collect.add_argument("recipe")
    collect.add_argument(
        "--suite",
        type=Path,
        default=DEFAULT_PREFERENCE_SUITE,
    )
    collect.add_argument(
        "--results-root",
        type=Path,
        default=DEFAULT_PREFERENCE_RESULTS,
    )
    collect.add_argument(
        "--i-understand-live",
        action="store_true",
        help="Required for live preference collect (UNTESTED seal)",
    )

    rag = sub.add_parser("collect-rag")
    rag.add_argument("recipe")
    rag.add_argument(
        "--mode",
        choices=("oracle", "keyword"),
        required=True,
    )
    rag.add_argument(
        "--suite",
        type=Path,
        default=DEFAULT_RAG_SUITE,
    )
    rag.add_argument(
        "--corpus-root",
        type=Path,
        default=DEFAULT_RAG_CORPUS,
    )
    rag.add_argument(
        "--results-root",
        type=Path,
        default=DEFAULT_RAG_RESULTS,
    )
    rag.add_argument(
        "--i-understand-live",
        action="store_true",
        help="Required for live RAG collect (UNTESTED seal)",
    )

    overhead = sub.add_parser("collect-overhead")
    overhead.add_argument("recipe")
    overhead.add_argument(
        "--suite",
        type=Path,
        default=DEFAULT_OVERHEAD_SUITE,
    )
    overhead.add_argument(
        "--pairs-root",
        type=Path,
        default=DEFAULT_PAIRS_ROOT,
    )
    overhead.add_argument(
        "--results-root",
        type=Path,
        default=DEFAULT_OVERHEAD_RESULTS,
    )
    overhead.add_argument(
        "--i-understand-live",
        action="store_true",
        help="Required for live overhead collect (UNTESTED seal)",
    )
    return parser


def main(
    argv: Sequence[str] | None = None,
    *,
    artifact_roots: ArtifactRoots | None = None,
) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as error:
        code = error.code
        return int(code) if isinstance(code, int) else 1
    try:
        if args.command == "list":
            payload = _cmd_list(root=args.approach3_root)
        elif args.command == "dry-config":
            roots = artifact_roots or load_artifact_roots(DEFAULT_MACHINE_PROFILE_PATH)
            payload = dry_config(
                args.recipe,
                approach3_root=args.approach3_root,
                cells_root=args.cells_root,
                artifact_roots=roots,
            )
        elif args.command == "show":
            payload = _cmd_show(args.recipe, root=args.approach3_root)
        elif args.command == "collect-preference":
            if not args.i_understand_live:
                raise Approach3Error(
                    "refusing live collect without --i-understand-live "
                    "(Approach 3 live collect is UNTESTED)",
                    code="live_not_confirmed",
                )
            roots = artifact_roots or load_artifact_roots(DEFAULT_MACHINE_PROFILE_PATH)
            payload = _cmd_collect_preference(
                args.recipe,
                root=args.approach3_root,
                cells_root=args.cells_root,
                suite_path=args.suite,
                results_root=args.results_root,
                confirm_live=args.i_understand_live,
                artifact_roots=roots,
            )
        elif args.command == "collect-rag":
            if not args.i_understand_live:
                raise Approach3Error(
                    "refusing live collect without --i-understand-live "
                    "(Approach 3 live collect is UNTESTED)",
                    code="live_not_confirmed",
                )
            roots = artifact_roots or load_artifact_roots(DEFAULT_MACHINE_PROFILE_PATH)
            payload = _cmd_collect_rag(
                args.recipe,
                root=args.approach3_root,
                cells_root=args.cells_root,
                suite_path=args.suite,
                corpus_root=args.corpus_root,
                results_root=args.results_root,
                mode=args.mode,
                confirm_live=args.i_understand_live,
                artifact_roots=roots,
            )
        elif args.command == "collect-overhead":
            if not args.i_understand_live:
                raise Approach3Error(
                    "refusing live collect without --i-understand-live "
                    "(Approach 3 live collect is UNTESTED)",
                    code="live_not_confirmed",
                )
            roots = artifact_roots or load_artifact_roots(DEFAULT_MACHINE_PROFILE_PATH)
            payload = _cmd_collect_overhead(
                args.recipe,
                root=args.approach3_root,
                cells_root=args.cells_root,
                pairs_root=args.pairs_root,
                suite_path=args.suite,
                results_root=args.results_root,
                confirm_live=args.i_understand_live,
                artifact_roots=roots,
            )
        else:
            raise Approach3Error(f"unknown command: {args.command}", code="unknown_command")
        _print(payload)
        return 0
    except Approach3Error as error:
        _print({"ok": False, "error": {"kind": error.code, "message": str(error)}})
        return 1
    except Exception as error:  # pragma: no cover - unexpected
        _print(
            {
                "ok": False,
                "error": {
                    "kind": getattr(error, "code", error.__class__.__name__),
                    "message": str(error),
                },
            }
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
