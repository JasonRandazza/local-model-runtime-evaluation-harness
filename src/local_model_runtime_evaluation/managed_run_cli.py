"""JSON-only operator CLI for managed local evaluation runs."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import json
import os
import platform
import re
import sys
import time
from pathlib import Path
from typing import Sequence

from .evidence_bundle import EvidenceBundle
from .managed_run import (
    default_collector_hooks,
    execute_managed_run,
    resume_managed_run,
)
from .managed_run_types import RunSummaryState
from .operator_policy import (
    AdoptedPolicy,
    adopt_policy,
    authorize,
    load_adopted_policy,
)
from .process_inspection import ProcessInspector
from .run_identity import build_plan
from .runtime_adapters import (
    OmlxAdapter,
    OptiqAdapter,
    OsaurusAdapter,
    RuntimeContext,
)
from .runtime_manager import RuntimeManager
from .transport import LoopbackTransport


DEFAULT_STATE_DIR = Path(".lmre")
DEFAULT_RESULTS_DIR = Path("results/runs")
ACTIVE_RUN_LOCK = "active-run.lock"
_SECRET_VALUE = re.compile(
    r"(?i)(api[_-]?key|authorization|credential|password|secret|token)"
    r"(\s*[:=]\s*)([^\s,;]+)"
)


def _sanitize_error(message: str) -> str:
    return _SECRET_VALUE.sub(
        lambda match: f"{match.group(1)}{match.group(2)}<redacted>",
        message,
    )


def _emit(body: dict[str, object]) -> None:
    print(json.dumps(body, sort_keys=True))


def _policy_payload(adopted: AdoptedPolicy) -> dict[str, object]:
    policy = adopted.policy
    return {
        "adopted_at": adopted.adopted_at,
        "exclusions": {
            "force_kill": True,
            "provider_edits": True,
            "remote_endpoints": True,
        },
        "inference_authority": policy.allow_inference,
        "lifecycle_authority": {
            "exact_reclaim": policy.allow_exact_reclaim,
            "start": policy.allow_start,
            "terminate_after_interrupt": (
                policy.allow_terminate_after_interrupt
            ),
        },
        "ok": True,
        "policy_hash": adopted.policy_hash,
        "policy_id": policy.policy_id,
        "reclaim_grace_seconds": policy.reclaim_grace_seconds,
    }


def _run_dir(results_dir: Path, run_id: str) -> Path:
    return results_dir / run_id


@contextmanager
def _active_run_lock(state_dir: Path, run_id: str):
    state_dir.mkdir(parents=True, exist_ok=True)
    path = state_dir / ACTIVE_RUN_LOCK
    try:
        descriptor = os.open(
            path,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL,
            0o600,
        )
    except FileExistsError as error:
        raise RuntimeError(
            "another active managed run or resume holds the local run lock"
        ) from error
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(
                {
                    "pid": os.getpid(),
                    "run_id": run_id,
                },
                stream,
                sort_keys=True,
            )
            stream.write("\n")
        yield
    finally:
        path.unlink(missing_ok=True)


def _build_runtime_manager(
    plan,
    adopted: AdoptedPolicy,
    bundle: EvidenceBundle,
) -> RuntimeManager:
    inspector = ProcessInspector()
    transport = LoopbackTransport(set(plan.endpoints))
    log_dir = bundle.run_dir / "runtime-logs"
    catalog_root = bundle.run_dir / "runtime-catalogs"
    context = RuntimeContext(
        log_dir=log_dir,
        credential=None,
        transport=transport,
        policy=adopted.policy,
        policy_request=plan.policy_request(),
        notice=lambda message: print(message, file=sys.stderr),
        sleep=time.sleep,
        lifecycle_sink=bundle.append_lifecycle,
        interrupt_checks=20,
        terminate_checks=20,
        ready_checks=720,
        poll_seconds=0.25,
        catalog_root=catalog_root,
    )
    return RuntimeManager(
        {
            "osaurus": OsaurusAdapter(inspector=inspector),
            "omlx": OmlxAdapter(inspector=inspector),
            "optiq": OptiqAdapter(inspector=inspector),
        },
        context_template=context,
    )


def _command_policy(args: argparse.Namespace) -> dict[str, object]:
    if args.policy_command == "show":
        return _policy_payload(load_adopted_policy(args.state_dir))
    adopted = adopt_policy(args.source, args.state_dir)
    return _policy_payload(adopted)


def _command_plan(args: argparse.Namespace) -> dict[str, object]:
    adopted = load_adopted_policy(args.state_dir)
    plan = build_plan(
        args.recipe,
        family_id=args.family,
        run_name=args.name,
        comparison_id=args.comparison,
        parent_run_id=args.parent,
        results_root=args.results_dir,
    )
    authorize(adopted.policy, plan.policy_request())
    EvidenceBundle.create(
        args.results_dir,
        plan,
        adopted,
        {
            "platform": platform.platform(),
            "python": platform.python_version(),
        },
    )
    return {
        "comparison_id": plan.identity.comparison_id,
        "ok": True,
        "plan_hash": plan.plan_hash,
        "request_count": plan.request_count,
        "run_id": plan.identity.run_id,
        "run_name": plan.identity.run_name,
        "status": RunSummaryState.PENDING.value,
    }


def _command_run(args: argparse.Namespace) -> dict[str, object]:
    adopted = load_adopted_policy(args.state_dir)
    bundle = EvidenceBundle.load(_run_dir(args.results_dir, args.run_id))
    with _active_run_lock(args.state_dir, args.run_id):
        state = bundle.state
        if state.sealed or state.summary_state is not RunSummaryState.PENDING:
            raise RuntimeError("managed run is not an unstarted plan")
        manager = _build_runtime_manager(bundle.plan, adopted, bundle)
        hooks = default_collector_hooks(bundle.plan, manager, bundle)
        return execute_managed_run(
            bundle.plan,
            adopted,
            bundle,
            manager,
            hooks,
        )


def _command_resume(args: argparse.Namespace) -> dict[str, object]:
    adopted = load_adopted_policy(args.state_dir)
    run_dir = _run_dir(args.results_dir, args.run_id)
    with _active_run_lock(args.state_dir, args.run_id):
        bundle = EvidenceBundle.load(run_dir)
        bundle.verify()
        manager = _build_runtime_manager(bundle.plan, adopted, bundle)
        hooks = default_collector_hooks(bundle.plan, manager, bundle)
        return resume_managed_run(run_dir, adopted, manager, hooks)


def _command_status(args: argparse.Namespace) -> dict[str, object]:
    bundle = EvidenceBundle.load(_run_dir(args.results_dir, args.run_id))
    state = bundle.state.to_dict()
    state["ok"] = True
    return state


def _command_report(args: argparse.Namespace) -> dict[str, object]:
    bundle = EvidenceBundle.load(_run_dir(args.results_dir, args.run_id))
    bundle.verify()
    path = bundle.run_dir / "summary.json"
    body = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(body, dict):
        raise RuntimeError("managed run summary is invalid")
    body["ok"] = True
    return body


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="lmre",
        description=(
            "Plan and execute policy-governed local model evaluations. "
            "Provider reconnect remains owned by the operator in the "
            "Osaurus UI."
        ),
    )
    parser.add_argument(
        "--state-dir",
        type=Path,
        default=DEFAULT_STATE_DIR,
    )
    parser.add_argument(
        "--results-dir",
        type=Path,
        default=DEFAULT_RESULTS_DIR,
    )
    commands = parser.add_subparsers(dest="command", required=True)

    policy = commands.add_parser(
        "policy",
        help="Show or explicitly adopt standing local authority",
    )
    policy_commands = policy.add_subparsers(
        dest="policy_command",
        required=True,
    )
    policy_commands.add_parser("show", help="Show adopted policy")
    adopt = policy_commands.add_parser(
        "adopt",
        help="Explicitly adopt one reviewed policy file",
    )
    adopt.add_argument("--from", dest="source", type=Path, required=True)

    plan = commands.add_parser("plan", help="Create a non-live immutable plan")
    plan.add_argument("--family", required=True)
    plan.add_argument("--recipe", type=Path, required=True)
    plan.add_argument("--name")
    plan.add_argument("--comparison")
    plan.add_argument("--parent")

    run = commands.add_parser("run", help="Execute one previously saved plan")
    run.add_argument("run_id")
    resume = commands.add_parser(
        "resume",
        help=(
            "After reconnecting the existing provider in the Osaurus UI, "
            "resume only the blocked overhead step"
        ),
        description=(
            "Provider reconnect is operator-owned. Reconnect the existing "
            "provider in the Osaurus UI, then resume only the blocked "
            "overhead step."
        ),
    )
    resume.add_argument("run_id")
    status = commands.add_parser("status", help="Read managed run state")
    status.add_argument("run_id")
    report = commands.add_parser(
        "report",
        help="Verify and read a sealed run summary",
    )
    report.add_argument("run_id")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "policy":
            body = _command_policy(args)
        elif args.command == "plan":
            body = _command_plan(args)
        elif args.command == "run":
            body = _command_run(args)
        elif args.command == "resume":
            body = _command_resume(args)
        elif args.command == "status":
            body = _command_status(args)
        else:
            body = _command_report(args)
        _emit(body)
        return 0
    except Exception as error:
        _emit(
            {
                "error": {
                    "kind": str(
                        getattr(error, "code", error.__class__.__name__)
                    ),
                    "message": _sanitize_error(str(error)),
                },
                "ok": False,
            }
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
