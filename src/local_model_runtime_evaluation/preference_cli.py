"""CLI for Gemma preference quality POC."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from .matrix_config import REPOSITORY_ROOT, Cell
from .preference_collect import run_collect
from .preference_config import DEFAULT_PREFERENCE_CELLS, PreferenceError, PreferenceSuite
from .preference_judge import DEFAULT_JUDGE_CELL, load_pairs, run_judge
from .preference_review import run_review
from .preference_tally import run_tally

DEFAULT_SUITE = REPOSITORY_ROOT / "suites" / "gemma-preference-v1.json"
DEFAULT_RESULTS = REPOSITORY_ROOT / "results" / "preference"
DEFAULT_CELLS_ROOT = REPOSITORY_ROOT / "config" / "matrix" / "cells"
DEFAULT_REVIEW_SEED = 0


def _resolve_repo_path(path: Path) -> Path:
    if path.is_absolute():
        return path
    return (REPOSITORY_ROOT / path).resolve()


def _parse_cell_ids(raw: str | None) -> tuple[str, ...]:
    if raw is None:
        return DEFAULT_PREFERENCE_CELLS
    parts = tuple(part.strip() for part in raw.split(",") if part.strip())
    if not parts:
        raise PreferenceError("cells filter is empty")
    return parts


def _load_run_metadata(run_dir: Path) -> tuple[tuple[str, ...], str | None]:
    raw_path = run_dir / "raw.json"
    if not raw_path.is_file():
        return DEFAULT_PREFERENCE_CELLS, None
    payload = json.loads(raw_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        return DEFAULT_PREFERENCE_CELLS, None
    cell_ids_raw = payload.get("cell_ids")
    if isinstance(cell_ids_raw, list) and all(isinstance(item, str) for item in cell_ids_raw):
        cell_ids = tuple(cell_ids_raw)
    else:
        cell_ids = DEFAULT_PREFERENCE_CELLS
    suite_id = payload.get("suite_id")
    suite_id_str = suite_id if isinstance(suite_id, str) else None
    return cell_ids, suite_id_str


def _cmd_collect(args: argparse.Namespace) -> int:
    suite_path = _resolve_repo_path(args.suite)
    cells_root = _resolve_repo_path(args.cells_root)
    cell_ids = _parse_cell_ids(args.cells)

    suite = PreferenceSuite.load(suite_path)
    for cell_id in cell_ids:
        Cell.load(cells_root / f"{cell_id}.json")

    if args.dry_config:
        print(json.dumps({
            "ok": True,
            "suite_id": suite.suite_id,
            "cells": list(cell_ids),
            "prompts": len(suite.prompts),
        }, sort_keys=True))
        return 0

    results_root = _resolve_repo_path(args.results_dir)
    run_dir = run_collect(
        cell_ids,
        suite_path,
        cells_root,
        results_root,
    )
    print(json.dumps({"ok": True, "run_dir": str(run_dir)}, sort_keys=True))
    return 0


def _cmd_review(args: argparse.Namespace) -> int:
    run_dir = _resolve_repo_path(args.run)
    if not run_dir.is_dir():
        raise PreferenceError(f"run directory not found: {run_dir}")
    cell_ids, _ = _load_run_metadata(run_dir)
    suite = PreferenceSuite.load(_resolve_repo_path(args.suite))
    run_review(run_dir, seed=args.seed, cell_ids=cell_ids, suite=suite)
    print(json.dumps({"ok": True, "run_dir": str(run_dir)}, sort_keys=True))
    return 0


def _cmd_tally(args: argparse.Namespace) -> int:
    run_dir = _resolve_repo_path(args.run)
    if not run_dir.is_dir():
        raise PreferenceError(f"run directory not found: {run_dir}")
    run_tally(run_dir)
    print(json.dumps({"ok": True, "run_dir": str(run_dir)}, sort_keys=True))
    return 0


def _cmd_judge(args: argparse.Namespace) -> int:
    run_dir = _resolve_repo_path(args.run)
    if not run_dir.is_dir():
        raise PreferenceError(f"run directory not found: {run_dir}")

    judge_cell_id = args.judge_cell
    cells_root = _resolve_repo_path(args.cells_root)
    suite_path = _resolve_repo_path(args.suite)

    suite = PreferenceSuite.load(suite_path)
    Cell.load(cells_root / f"{judge_cell_id}.json")

    answers_dir = run_dir / "answers"
    if not answers_dir.is_dir():
        raise PreferenceError(f"missing answers directory: {answers_dir}")
    pairs = load_pairs(run_dir)
    pair_count = len(pairs)

    if args.dry_config:
        print(json.dumps({
            "ok": True,
            "judge_cell": judge_cell_id,
            "run_dir": str(run_dir),
            "pairs": pair_count,
        }, sort_keys=True))
        return 0

    run_judge(
        run_dir,
        judge_cell_id=judge_cell_id,
        cells_root=cells_root,
        suite=suite,
    )
    print(json.dumps({"ok": True, "run_dir": str(run_dir)}, sort_keys=True))
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="lmre-preference",
        description="Gemma preference quality POC: collect, review, judge, and tally.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    collect = subparsers.add_parser("collect", help="Collect answers from matrix cells")
    collect.add_argument(
        "--cells",
        help="Comma-separated cell ids (default: three screen PASS cells)",
    )
    collect.add_argument(
        "--suite",
        type=Path,
        default=DEFAULT_SUITE,
        help="Preference suite JSON",
    )
    collect.add_argument(
        "--results-dir",
        type=Path,
        default=DEFAULT_RESULTS,
        help="Directory for preference run outputs",
    )
    collect.add_argument(
        "--cells-root",
        type=Path,
        default=DEFAULT_CELLS_ROOT,
        help="Matrix cell JSON directory",
    )
    collect.add_argument(
        "--dry-config",
        action="store_true",
        help="Validate suite and cell configs without network or server start",
    )

    review = subparsers.add_parser("review", help="Build blind pairwise review pack")
    review.add_argument("--run", type=Path, required=True, help="Collect run directory")
    review.add_argument(
        "--seed",
        type=int,
        default=DEFAULT_REVIEW_SEED,
        help="Shuffle seed for A/B assignment (default: 0)",
    )
    review.add_argument(
        "--suite",
        type=Path,
        default=DEFAULT_SUITE,
        help="Preference suite JSON",
    )

    judge = subparsers.add_parser("judge", help="Run local judge cell on blind pairs")
    judge.add_argument("--run", type=Path, required=True, help="Review run directory")
    judge.add_argument(
        "--judge-cell",
        default=DEFAULT_JUDGE_CELL,
        help=f"Matrix cell id for the judge (default: {DEFAULT_JUDGE_CELL})",
    )
    judge.add_argument(
        "--suite",
        type=Path,
        default=DEFAULT_SUITE,
        help="Preference suite JSON",
    )
    judge.add_argument(
        "--cells-root",
        type=Path,
        default=DEFAULT_CELLS_ROOT,
        help="Matrix cell JSON directory",
    )
    judge.add_argument(
        "--dry-config",
        action="store_true",
        help="Validate judge cell and run dir without network or server start",
    )

    tally = subparsers.add_parser("tally", help="Score judgments and write report")
    tally.add_argument("--run", type=Path, required=True, help="Review run directory")

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "collect":
            return _cmd_collect(args)
        if args.command == "review":
            return _cmd_review(args)
        if args.command == "judge":
            return _cmd_judge(args)
        if args.command == "tally":
            return _cmd_tally(args)
        raise PreferenceError(f"unknown command {args.command!r}")
    except Exception as error:
        print(json.dumps({
            "ok": False,
            "error": {
                "kind": getattr(error, "code", error.__class__.__name__),
                "message": str(error),
            },
        }, sort_keys=True))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
