from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from .models import Operation
from .runner import StageZeroRunner
from .stage_one_factory import build_stage_one_engine
from .stage_two_factory import build_stage_two_engine


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="lmre-stage0")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("inventory")
    for operation in Operation:
        if operation is Operation.INVENTORY:
            continue
        command = subparsers.add_parser(operation.value)
        command.add_argument("run_id")
    validate = subparsers.add_parser("validate-bundle")
    validate.add_argument("run_id")
    worker = subparsers.add_parser("_stage1-worker", help=argparse.SUPPRESS)
    worker.add_argument("run_id")
    stage_two_worker = subparsers.add_parser("_stage2-worker", help=argparse.SUPPRESS)
    stage_two_worker.add_argument("run_id")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    runner = StageZeroRunner(
        REPOSITORY_ROOT,
        stage_one_engine_factory=lambda manifest, output: build_stage_one_engine(
            REPOSITORY_ROOT, manifest, output
        ),
        stage_two_engine_factory=lambda manifest, output: build_stage_two_engine(
            REPOSITORY_ROOT, manifest, output
        ),
    )
    tool = arguments.command
    try:
        if tool == "_stage1-worker":
            result = runner.execute_stage_one_worker(arguments.run_id)
        elif tool == "_stage2-worker":
            result = runner.execute_stage_two_worker(arguments.run_id)
        elif tool == "validate-bundle":
            result = runner.validate_bundle(arguments.run_id)
        else:
            operation = Operation(tool)
            result = runner.dispatch(operation, getattr(arguments, "run_id", None))
        envelope = {"ok": True, "tool": tool, "result": result}
        exit_code = 0
    except Exception as error:
        envelope = {
            "ok": False,
            "tool": tool,
            "error": {
                "kind": getattr(error, "code", error.__class__.__name__),
                "message": str(error),
            },
        }
        exit_code = 1
    print(json.dumps(envelope, sort_keys=True))
    return exit_code
