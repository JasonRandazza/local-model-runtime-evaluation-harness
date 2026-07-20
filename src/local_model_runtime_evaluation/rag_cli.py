"""CLI for Gemma RAG oracle and keyword retrieval."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from .matrix_config import Cell, MatrixError, REPOSITORY_ROOT, load_family
from .rag_collect import run_collect
from .rag_config import (
    RagCorpus,
    RagError,
    RagSelection,
    RagSuite,
    resolve_rag_selection,
)
from .rag_score import score_run

DEFAULT_SUITE = REPOSITORY_ROOT / "suites" / "gemma-rag-oracle-v1.json"
DEFAULT_CORPUS = REPOSITORY_ROOT / "corpora" / "rag-oracle-v1"
DEFAULT_RESULTS = REPOSITORY_ROOT / "results" / "rag"
DEFAULT_CELLS_ROOT = REPOSITORY_ROOT / "config" / "matrix" / "cells"
DEFAULT_TOP_K = 2


def _resolve_repo_path(path: Path) -> Path:
    if path.is_absolute():
        return path
    return (REPOSITORY_ROOT / path).resolve()


def _parse_cell_ids(raw: str | None) -> tuple[str, ...] | None:
    if raw is None:
        return None
    parts = tuple(part.strip() for part in raw.split(",") if part.strip())
    if not parts:
        raise RagError("cells filter is empty")
    return parts


def _selection_from_args(args: argparse.Namespace) -> RagSelection:
    cells = _parse_cell_ids(args.cells)
    return resolve_rag_selection(
        family_id=getattr(args, "family", None),
        cells=cells,
    )


def _load_cells(
    cell_ids: tuple[str, ...],
    cells_root: Path,
    family_id: str,
) -> None:
    family = load_family(family_id)
    for cell_id in cell_ids:
        try:
            Cell.load(cells_root / f"{cell_id}.json", family=family)
        except MatrixError as error:
            raise RagError(str(error)) from error


def _cmd_collect(args: argparse.Namespace) -> int:
    suite_path = _resolve_repo_path(args.suite)
    corpus_root = _resolve_repo_path(args.corpus_root)
    cells_root = _resolve_repo_path(args.cells_root)
    selection = _selection_from_args(args)

    suite = RagSuite.load(suite_path)
    corpus = RagCorpus.load(corpus_root)
    if corpus.corpus_id != suite.corpus_id:
        raise RagError(
            f"corpus id mismatch: suite expects {suite.corpus_id!r}, "
            f"corpus has {corpus.corpus_id!r}"
        )
    _load_cells(selection.cells, cells_root, selection.family_id)

    if args.dry_config:
        print(json.dumps({
            "ok": True,
            "family_id": selection.family_id,
            "cells": list(selection.cells),
            "questions": len(suite.questions),
            "corpus_id": corpus.corpus_id,
            "mode": args.mode,
            "top_k": args.top_k,
        }, sort_keys=True))
        return 0

    results_root = _resolve_repo_path(args.results_dir)
    run_dir = run_collect(
        selection.cells,
        suite_path,
        corpus_root,
        cells_root,
        results_root,
        family_id=selection.family_id,
        mode=args.mode,
        top_k=args.top_k,
    )
    print(json.dumps({"ok": True, "run_dir": str(run_dir)}, sort_keys=True))
    return 0


def _cmd_score(args: argparse.Namespace) -> int:
    run_dir = _resolve_repo_path(args.run)
    if not run_dir.is_dir():
        raise RagError(f"run directory not found: {run_dir}")
    suite = RagSuite.load(_resolve_repo_path(args.suite))
    score_run(run_dir, suite)
    print(json.dumps({"ok": True, "run_dir": str(run_dir)}, sort_keys=True))
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="lmre-rag",
        description="Gemma RAG oracle and keyword retrieval: collect answers and score.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    collect = subparsers.add_parser("collect", help="Collect answers from matrix cells")
    collect.add_argument(
        "--family",
        help=(
            "Matrix family id (default: family_id in config/rag/defaults.json, "
            "currently gemma-4-12b-qat; e.g. ornith-35b)"
        ),
    )
    collect.add_argument(
        "--cells",
        help=(
            "Comma-separated cell ids (default: selected family's four-cell recipe "
            "from config/rag/family-cells.json)"
        ),
    )
    collect.add_argument(
        "--suite",
        type=Path,
        default=DEFAULT_SUITE,
        help="RAG suite JSON",
    )
    collect.add_argument(
        "--corpus-root",
        type=Path,
        default=DEFAULT_CORPUS,
        help="RAG corpus directory",
    )
    collect.add_argument(
        "--results-dir",
        type=Path,
        default=DEFAULT_RESULTS,
        help="Directory for RAG run outputs",
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
        help="Validate suite, corpus, and cell configs without network or server start",
    )
    collect.add_argument(
        "--mode",
        choices=("oracle", "keyword"),
        default="oracle",
        help="Collect mode: oracle gold injection (default) or keyword retrieval",
    )
    collect.add_argument(
        "--top-k",
        type=int,
        default=DEFAULT_TOP_K,
        help="Keyword retrieval top-k (default: 2; ignored in oracle mode)",
    )

    score = subparsers.add_parser("score", help="Score answers and write report")
    score.add_argument("--run", type=Path, required=True, help="Collect run directory")
    score.add_argument(
        "--suite",
        type=Path,
        default=DEFAULT_SUITE,
        help="RAG suite JSON",
    )

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "collect":
            return _cmd_collect(args)
        if args.command == "score":
            return _cmd_score(args)
        raise RagError(f"unknown command {args.command!r}")
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
