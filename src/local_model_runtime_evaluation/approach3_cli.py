"""CLI for Approach 3 free-form recipes."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

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
from local_model_runtime_evaluation.preference_collect import run_collect

DEFAULT_PREFERENCE_SUITE = REPOSITORY_ROOT / "suites" / "multi-family-preference-v1.json"
DEFAULT_PREFERENCE_RESULTS = REPOSITORY_ROOT / "results" / "preference"

_COMMANDS = frozenset({"dry-config", "show", "list", "collect-preference"})


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
    cells = load_recipe_cells(recipe, cells_root=cells_root)
    run_dir = run_collect(
        tuple(cell.cell_id for cell in cells),
        suite_path,
        cells_root,
        results_root,
        family_id=recipe.family_id,
    )
    return {
        "ok": True,
        "status": "COLLECT_FINISHED",
        "live_collect": "EXECUTED_UNSEALED",
        "recipe_id": recipe.recipe_id,
        "family_id": recipe.family_id,
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
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "list":
            payload = _cmd_list(root=args.approach3_root)
        elif args.command == "dry-config":
            payload = dry_config(
                args.recipe,
                approach3_root=args.approach3_root,
                cells_root=args.cells_root,
            )
        elif args.command == "show":
            payload = _cmd_show(args.recipe, root=args.approach3_root)
        elif args.command == "collect-preference":
            payload = _cmd_collect_preference(
                args.recipe,
                root=args.approach3_root,
                cells_root=args.cells_root,
                suite_path=args.suite,
                results_root=args.results_root,
                confirm_live=args.i_understand_live,
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
