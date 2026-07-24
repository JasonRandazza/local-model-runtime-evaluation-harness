"""CLI for discovery MVP: propose, show, execute, and dry-config."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

from local_model_runtime_evaluation.discovery_execute import (
    DiscoverySuiteHooks,
    default_suite_hooks,
    execute_proposal,
)
from local_model_runtime_evaluation.discovery_match import (
    build_proposal,
    native_base_url,
    require_agreeing_recipes,
)
from local_model_runtime_evaluation.discovery_types import (
    DEFAULT_DISCOVERY_RESULTS_ROOT,
    DiscoveryError,
    allocate_proposal_id,
    load_proposal,
    verify_proposal_hash,
    write_proposal,
)
from local_model_runtime_evaluation.matrix_config import (
    REPOSITORY_ROOT,
    Cell,
    load_family,
)
from local_model_runtime_evaluation.preference_config import load_family_cell_recipes
from local_model_runtime_evaluation.rag_config import load_rag_family_cell_recipes
from local_model_runtime_evaluation.transport import LoopbackTransport

DEFAULT_PREFERENCE_SUITE = REPOSITORY_ROOT / "suites" / "multi-family-preference-v1.json"
DEFAULT_RAG_SUITE = REPOSITORY_ROOT / "suites" / "multi-family-rag-oracle-v1.json"
DEFAULT_RAG_CORPUS = REPOSITORY_ROOT / "corpora" / "rag-oracle-v1"
DEFAULT_CELLS_ROOT = REPOSITORY_ROOT / "config" / "matrix" / "cells"
DEFAULT_PREFERENCE_RESULTS = REPOSITORY_ROOT / "results" / "preference"
DEFAULT_RAG_RESULTS = REPOSITORY_ROOT / "results" / "rag"

_COMMANDS = frozenset({"propose", "show", "execute", "dry-config"})


def _resolve_repo_path(path: Path) -> Path:
    if path.is_absolute():
        return path
    return (REPOSITORY_ROOT / path).resolve()


def _default_transport() -> LoopbackTransport:
    base_urls = {native_base_url(server) for server in ("osaurus", "omlx", "optiq")}
    return LoopbackTransport(base_urls)


def _cmd_dry_config(
    *,
    cells_root: Path | None = None,
    preference_recipes: dict[str, tuple[str, ...]] | None = None,
    rag_recipes: dict[str, tuple[str, ...]] | None = None,
) -> dict[str, object]:
    cells_root = cells_root or DEFAULT_CELLS_ROOT
    preference = (
        preference_recipes
        if preference_recipes is not None
        else load_family_cell_recipes()
    )
    rag = (
        rag_recipes
        if rag_recipes is not None
        else load_rag_family_cell_recipes()
    )
    agreed = require_agreeing_recipes(
        preference_recipes=preference,
        rag_recipes=rag,
    )
    cells: dict[str, list[str]] = {}
    for family_id, cell_ids in sorted(agreed.items()):
        family = load_family(family_id)
        for cell_id in cell_ids:
            Cell.load(cells_root / f"{cell_id}.json", family=family)
        cells[family_id] = list(cell_ids)
    return {
        "ok": True,
        "families": sorted(agreed.keys()),
        "cells": cells,
    }


def _cmd_propose(
    *,
    results_root: Path,
    transport: object,
    cells_root: Path | None = None,
    path_exists: Callable[[str], bool] | None = None,
    preference_recipes: dict[str, tuple[str, ...]] | None = None,
    rag_recipes: dict[str, tuple[str, ...]] | None = None,
) -> dict[str, object]:
    cells_root = cells_root or DEFAULT_CELLS_ROOT
    preference = (
        preference_recipes
        if preference_recipes is not None
        else load_family_cell_recipes()
    )
    rag = (
        rag_recipes
        if rag_recipes is not None
        else load_rag_family_cell_recipes()
    )
    proposal_id = allocate_proposal_id(results_root)
    created_at = datetime.now(timezone.utc).isoformat()
    proposal = build_proposal(
        proposal_id=proposal_id,
        created_at=created_at,
        preference_recipes=preference,
        rag_recipes=rag,
        cells_root=cells_root,
        transport=transport,
        path_exists=path_exists,
    )
    path = write_proposal(results_root, proposal)
    return {
        "ok": True,
        "proposal_id": proposal_id,
        "executable_families": proposal["executable_families"],
        "path": str(path),
    }


def _cmd_show(
    *,
    results_root: Path,
    proposal_id: str,
) -> dict[str, object]:
    proposal = load_proposal(results_root, proposal_id)
    verify_proposal_hash(proposal)
    return proposal


def _cmd_execute(
    *,
    results_root: Path,
    proposal_id: str,
    family_id: str,
    hooks: DiscoverySuiteHooks,
    preference_recipes: dict[str, tuple[str, ...]] | None = None,
) -> dict[str, object]:
    return execute_proposal(
        results_root=results_root,
        proposal_id=proposal_id,
        family_id=family_id,
        hooks=hooks,
        preference_recipes=preference_recipes,
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="lmre-discover",
        description=(
            "Discovery MVP: observe local stack readiness, write proposals, "
            "and execute preference+RAG suites for one ready family."
        ),
    )
    subparsers = parser.add_subparsers(dest="command")

    propose = subparsers.add_parser("propose", help="Observe stack and write a proposal")
    propose.add_argument(
        "--results-dir",
        type=Path,
        default=DEFAULT_DISCOVERY_RESULTS_ROOT,
        help="Directory for discovery proposal outputs",
    )
    propose.add_argument(
        "--cells-root",
        type=Path,
        default=DEFAULT_CELLS_ROOT,
        help="Matrix cell JSON directory",
    )

    dry = subparsers.add_parser(
        "dry-config",
        help="Validate discovery config and cell wiring without network",
    )
    dry.add_argument(
        "--cells-root",
        type=Path,
        default=DEFAULT_CELLS_ROOT,
        help="Matrix cell JSON directory",
    )

    show = subparsers.add_parser("show", help="Load and print a stored proposal")
    show.add_argument("proposal_id", help="Discovery proposal id")
    show.add_argument(
        "--results-dir",
        type=Path,
        default=DEFAULT_DISCOVERY_RESULTS_ROOT,
        help="Directory for discovery proposal outputs",
    )

    execute = subparsers.add_parser(
        "execute",
        help="Run preference and RAG suites for one executable family",
    )
    execute.add_argument("proposal_id", help="Discovery proposal id")
    execute.add_argument("--family", required=True, help="Executable family id")
    execute.add_argument(
        "--results-dir",
        type=Path,
        default=DEFAULT_DISCOVERY_RESULTS_ROOT,
        help="Directory for discovery proposal outputs",
    )
    execute.add_argument(
        "--cells-root",
        type=Path,
        default=DEFAULT_CELLS_ROOT,
        help="Matrix cell JSON directory",
    )
    execute.add_argument(
        "--preference-suite",
        type=Path,
        default=DEFAULT_PREFERENCE_SUITE,
        help="Preference suite JSON",
    )
    execute.add_argument(
        "--rag-suite",
        type=Path,
        default=DEFAULT_RAG_SUITE,
        help="RAG suite JSON",
    )
    execute.add_argument(
        "--rag-corpus",
        type=Path,
        default=DEFAULT_RAG_CORPUS,
        help="RAG corpus directory",
    )
    execute.add_argument(
        "--preference-results-dir",
        type=Path,
        default=DEFAULT_PREFERENCE_RESULTS,
        help="Directory for preference run outputs",
    )
    execute.add_argument(
        "--rag-results-dir",
        type=Path,
        default=DEFAULT_RAG_RESULTS,
        help="Directory for RAG run outputs",
    )

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    raw_argv = list(sys.argv[1:] if argv is None else argv)
    if not raw_argv or raw_argv[0] not in _COMMANDS:
        raw_argv = ["propose", *raw_argv]

    args = _parser().parse_args(raw_argv)
    try:
        if args.command == "dry-config":
            payload = _cmd_dry_config(
                cells_root=_resolve_repo_path(args.cells_root),
            )
        elif args.command == "propose":
            payload = _cmd_propose(
                results_root=_resolve_repo_path(args.results_dir),
                transport=_default_transport(),
                cells_root=_resolve_repo_path(args.cells_root),
            )
        elif args.command == "show":
            payload = _cmd_show(
                results_root=_resolve_repo_path(args.results_dir),
                proposal_id=args.proposal_id,
            )
        elif args.command == "execute":
            hooks = default_suite_hooks(
                preference_suite=_resolve_repo_path(args.preference_suite),
                rag_suite=_resolve_repo_path(args.rag_suite),
                rag_corpus=_resolve_repo_path(args.rag_corpus),
                cells_root=_resolve_repo_path(args.cells_root),
                preference_results=_resolve_repo_path(args.preference_results_dir),
                rag_results=_resolve_repo_path(args.rag_results_dir),
            )
            payload = _cmd_execute(
                results_root=_resolve_repo_path(args.results_dir),
                proposal_id=args.proposal_id,
                family_id=args.family,
                hooks=hooks,
            )
        else:
            raise DiscoveryError(f"unknown command {args.command!r}")

        print(json.dumps(payload, sort_keys=True))
        return 0
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
