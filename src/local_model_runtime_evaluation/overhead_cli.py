"""CLI for Osaurus routing overhead measurement."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Sequence

from .matrix_config import REPOSITORY_ROOT, Cell, MatrixSuite, load_family
from .overhead_config import (
    DEFAULT_PAIRS_ROOT,
    OverheadError,
    OverheadPair,
    OverheadSelection,
    make_routed_measure_cell,
    resolve_overhead_selection,
)
from .overhead_report import write_report
from .overhead_runner import run_overhead

DEFAULT_SUITE = REPOSITORY_ROOT / "suites" / "gemma-matrix-v1.json"
DEFAULT_RESULTS = REPOSITORY_ROOT / "results" / "overhead"
DEFAULT_CELLS_ROOT = REPOSITORY_ROOT / "config" / "matrix" / "cells"
DEFAULT_MODE = "screen"


def _resolve_repo_path(path: Path) -> Path:
    if path.is_absolute():
        return path
    return (REPOSITORY_ROOT / path).resolve()


def _parse_pair_ids(raw: str | None) -> tuple[str, ...] | None:
    if raw is None:
        return None
    parts = tuple(part.strip() for part in raw.split(",") if part.strip())
    if not parts:
        raise OverheadError("pairs filter is empty")
    return parts


def _selection_from_args(args: argparse.Namespace) -> OverheadSelection:
    pairs = _parse_pair_ids(args.pairs)
    return resolve_overhead_selection(
        family_id=getattr(args, "family", None),
        pairs=pairs,
    )


def _dry_config_payload(
    selection: OverheadSelection,
    pairs_root: Path,
    cells_root: Path,
    suite_path: Path,
) -> dict[str, Any]:
    suite = MatrixSuite.load(suite_path)
    family = load_family(selection.family_id)
    pairs: list[dict[str, str]] = []
    for pair_id in selection.pairs:
        pair = OverheadPair.load(pairs_root / f"{pair_id}.json")
        Cell.load(cells_root / f"{pair.direct_cell_id}.json", family=family)
        backend = Cell.load(cells_root / f"{pair.backend_cell_id}.json", family=family)
        routed = make_routed_measure_cell(backend, pair, family=family)
        pairs.append({
            "pair_id": pair.pair_id,
            "direct_cell_id": pair.direct_cell_id,
            "routed_cell_id": routed.cell_id,
            "routed_model_id": pair.routed_model_id,
            "routed_base_url": pair.routed_base_url,
        })
    return {
        "ok": True,
        "family_id": selection.family_id,
        "pairs": pairs,
        "suite_id": suite.suite_id,
        "mode": DEFAULT_MODE,
    }


def _cmd_run(args: argparse.Namespace) -> int:
    pairs_root = _resolve_repo_path(args.pairs_root)
    cells_root = _resolve_repo_path(args.cells_root)
    suite_path = _resolve_repo_path(args.suite)
    selection = _selection_from_args(args)

    if args.dry_config:
        print(json.dumps(
            _dry_config_payload(selection, pairs_root, cells_root, suite_path),
            sort_keys=True,
        ))
        return 0

    results_root = _resolve_repo_path(args.results_dir)
    run_dir = run_overhead(
        selection.pairs,
        pairs_root,
        cells_root,
        suite_path,
        results_root,
        family_id=selection.family_id,
        mode=DEFAULT_MODE,
    )
    print(json.dumps({"ok": True, "run_dir": str(run_dir)}, sort_keys=True))
    return 0


def _cmd_report(args: argparse.Namespace) -> int:
    run_dir = _resolve_repo_path(args.run)
    if not run_dir.is_dir():
        raise OverheadError(f"run directory not found: {run_dir}")
    write_report(run_dir)
    print(json.dumps({"ok": True, "run_dir": str(run_dir)}, sort_keys=True))
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="lmre-overhead",
        description="Measure Osaurus routing tax: direct native vs routed via :1337.",
    )
    parser.add_argument(
        "--dry-config",
        action="store_true",
        help="Validate pair, cell, and suite configs without network or server start",
    )

    subparsers = parser.add_subparsers(dest="command")

    run = subparsers.add_parser("run", help="Run direct and routed overhead legs")
    run.add_argument(
        "--family",
        help=(
            "Matrix family id (default: family_id in config/overhead/defaults.json, "
            "currently gemma-4-12b-qat; e.g. ornith-35b)"
        ),
    )
    run.add_argument(
        "--pairs",
        help="Comma-separated pair ids (default: family recipe in family-pairs.json)",
    )
    run.add_argument(
        "--pairs-root",
        type=Path,
        default=DEFAULT_PAIRS_ROOT,
        help="Overhead pair JSON directory",
    )
    run.add_argument(
        "--cells-root",
        type=Path,
        default=DEFAULT_CELLS_ROOT,
        help="Matrix cell JSON directory",
    )
    run.add_argument(
        "--suite",
        type=Path,
        default=DEFAULT_SUITE,
        help="Matrix suite JSON",
    )
    run.add_argument(
        "--results-dir",
        type=Path,
        default=DEFAULT_RESULTS,
        help="Directory for overhead run outputs",
    )
    run.add_argument(
        "--dry-config",
        action="store_true",
        help="Validate pair, cell, and suite configs without network or server start",
    )

    report = subparsers.add_parser("report", help="Regenerate report.md from raw.json")
    report.add_argument("--run", type=Path, required=True, help="Overhead run directory")

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    dry_config = getattr(args, "dry_config", False)
    try:
        if args.command is None:
            if dry_config:
                return _cmd_run(argparse.Namespace(
                    family=None,
                    pairs=None,
                    pairs_root=DEFAULT_PAIRS_ROOT,
                    cells_root=DEFAULT_CELLS_ROOT,
                    suite=DEFAULT_SUITE,
                    results_dir=DEFAULT_RESULTS,
                    dry_config=True,
                ))
            raise OverheadError("command is required (run or report)")
        if args.command == "run":
            return _cmd_run(args)
        if args.command == "report":
            return _cmd_report(args)
        raise OverheadError(f"unknown command {args.command!r}")
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
