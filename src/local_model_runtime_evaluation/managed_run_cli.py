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

from .artifact_profile import DEFAULT_MACHINE_PROFILE_PATH
from .comparison_class_inspect import inspect_comparison_class
from .evidence_bundle import EvidenceBundle
from .free_bind import (
    adopt_binding,
    propose_binding,
    show_binding_proposal,
    validate_binding_proposal,
)
from .managed_run import (
    default_collector_hooks,
    execute_managed_run,
    resume_managed_run,
)
from .managed_run_types import RunSummaryState
from .open_mix_inspect import inspect_open_mix
from .operator_policy import (
    AdoptedPolicy,
    adopt_policy,
    authorize,
    load_adopted_policy,
)
from .process_inspection import ProcessInspector
from .doctor import render_text, run_diagnostics
from .results_browser_html import write_browser
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
            "terminate_after_interrupt": (policy.allow_terminate_after_interrupt),
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
    *,
    state_dir: Path,
) -> RuntimeManager:
    inspector = ProcessInspector()
    transport = LoopbackTransport(set(plan.endpoints))
    log_dir = bundle.run_dir / "runtime-logs"
    state = bundle.state
    catalog_attempt = state.attempt + 1 if state.sealed else state.attempt
    catalog_root = (
        bundle.run_dir / "runtime-catalogs" / f"attempt-{catalog_attempt:03d}"
    )
    omlx_base_root = (
        state_dir
        / "runtime-state"
        / plan.identity.run_id
        / f"attempt-{catalog_attempt:03d}"
        / "omlx"
    )
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
        omlx_base_root=omlx_base_root,
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


def _command_plan(
    args: argparse.Namespace,
    machine_profile_path: Path,
) -> dict[str, object]:
    adopted = load_adopted_policy(args.state_dir)
    plan = build_plan(
        args.recipe,
        family_id=args.family,
        run_name=args.name,
        comparison_id=args.comparison,
        parent_run_id=args.parent,
        results_root=args.results_dir,
        comparison_class_id=args.comparison_class,
        binding_id=args.binding,
        open_mix_id=args.open_mix,
        binding_state_dir=args.state_dir,
        machine_profile_path=machine_profile_path,
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
        "binding_id": plan.binding_id,
        "comparison_class_id": plan.comparison_class_id,
        "comparison_scope": plan.comparison_scope,
        "open_mix_id": plan.open_mix_id,
        "ok": True,
        "plan_hash": plan.plan_hash,
        "request_count": plan.request_count,
        "run_id": plan.identity.run_id,
        "run_name": plan.identity.run_name,
        "status": RunSummaryState.PENDING.value,
    }


def _command_run(
    args: argparse.Namespace,
    machine_profile_path: Path,
) -> dict[str, object]:
    adopted = load_adopted_policy(args.state_dir)
    bundle = EvidenceBundle.load(_run_dir(args.results_dir, args.run_id))
    if bundle.plan.comparison_scope == "open_mix":
        raise RuntimeError(
            "open-mix live execution is not implemented; review the non-live plan only"
        )
    with _active_run_lock(args.state_dir, args.run_id):
        state = bundle.state
        if state.sealed or state.summary_state is not RunSummaryState.PENDING:
            raise RuntimeError("managed run is not an unstarted plan")
        manager = _build_runtime_manager(
            bundle.plan,
            adopted,
            bundle,
            state_dir=args.state_dir,
        )
        hooks = default_collector_hooks(
            bundle.plan,
            manager,
            bundle,
            machine_profile_path=machine_profile_path,
        )
        return execute_managed_run(
            bundle.plan,
            adopted,
            bundle,
            manager,
            hooks,
            machine_profile_path=machine_profile_path,
        )


def _command_resume(
    args: argparse.Namespace,
    machine_profile_path: Path,
) -> dict[str, object]:
    adopted = load_adopted_policy(args.state_dir)
    run_dir = _run_dir(args.results_dir, args.run_id)
    with _active_run_lock(args.state_dir, args.run_id):
        bundle = EvidenceBundle.load(run_dir)
        bundle.verify()
        if bundle.plan.comparison_scope == "open_mix":
            raise RuntimeError(
                "open-mix live resume is not implemented; review the non-live plan only"
            )
        manager = _build_runtime_manager(
            bundle.plan,
            adopted,
            bundle,
            state_dir=args.state_dir,
        )
        hooks = default_collector_hooks(
            bundle.plan,
            manager,
            bundle,
            machine_profile_path=machine_profile_path,
        )
        return resume_managed_run(
            run_dir,
            adopted,
            manager,
            hooks,
            machine_profile_path=machine_profile_path,
        )


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


def _command_browse(args: argparse.Namespace) -> dict[str, object]:
    result = write_browser(args.results_root, args.output)
    return {
        "ok": True,
        "index": result["index"],
        "runs": result["runs"],
        "results_root": str(args.results_root),
        "output": str(args.output),
        "comparison_index": result["comparison_index"],
        "comparisons": result["comparisons"],
        "unattributed_exclusions": result["unattributed_exclusions"],
    }


def _command_doctor(
    args: argparse.Namespace, machine_profile_path: Path
) -> dict[str, object] | None:
    result = run_diagnostics(
        machine_profile_path=machine_profile_path,
        state_root=args.state_dir,
    )
    if args.format == "text":
        # Text mode prints the checklist projection alone; the JSON envelope
        # is the default managed-CLI convention.
        print(render_text(result))
        return None
    return {"ok": True, "diagnostic": result}


def _command_comparison_class(
    args: argparse.Namespace,
    machine_profile_path: Path,
) -> dict[str, object]:
    return {
        "ok": True,
        "inspection": inspect_comparison_class(
            args.comparison_class_id,
            machine_profile_path=machine_profile_path,
        ),
    }


def _command_open_mix(
    args: argparse.Namespace,
    machine_profile_path: Path,
) -> dict[str, object]:
    return {
        "ok": True,
        "inspection": inspect_open_mix(
            args.open_mix_id,
            machine_profile_path=machine_profile_path,
        ),
    }


def _command_binding(
    args: argparse.Namespace,
    machine_profile_path: Path,
) -> dict[str, object]:
    common = {
        "state_dir": args.state_dir,
        "machine_profile_path": machine_profile_path,
    }
    if args.binding_command == "propose":
        result = propose_binding(
            binding_id=args.binding_id,
            revision=args.revision,
            family_id=args.family,
            cell_ids=args.cells,
            notes=args.notes,
            **common,
        )
    elif args.binding_command == "show":
        result = show_binding_proposal(args.binding_id, **common)
    elif args.binding_command == "validate":
        result = validate_binding_proposal(args.binding_id, **common)
    else:
        result = adopt_binding(args.binding_id, **common)
    return {"binding": result, "ok": True}


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
    plan.add_argument("--family")
    plan.add_argument("--recipe", type=Path, required=True)
    plan.add_argument("--name")
    plan.add_argument("--comparison")
    declaration = plan.add_mutually_exclusive_group()
    declaration.add_argument(
        "--comparison-class",
        help=("Checked-in controlled-expansion class ID; no arbitrary cell list"),
    )
    declaration.add_argument(
        "--binding",
        help="Explicitly adopted offline binding ID; no arbitrary cell list",
    )
    declaration.add_argument(
        "--open-mix",
        help="Checked-in heterogeneous comparison ID; no arbitrary members",
    )
    plan.add_argument("--parent")

    run = commands.add_parser("run", help="Execute one previously saved plan")
    run.add_argument("run_id")
    resume = commands.add_parser(
        "resume",
        help=(
            "After reconnecting the existing provider in the Osaurus UI, "
            "retry only the blocked or failed overhead step"
        ),
        description=(
            "Provider reconnect is operator-owned. Reconnect the existing "
            "provider in the Osaurus UI, then retry only the blocked or "
            "failed overhead step."
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

    browse = commands.add_parser(
        "browse",
        help="Render a read-only HTML browser over sealed evidence bundles",
    )
    browse.add_argument(
        "--results-root",
        type=Path,
        default=Path("results/runs"),
    )
    browse.add_argument(
        "--output",
        type=Path,
        default=Path("results/browser"),
    )

    doctor = commands.add_parser(
        "doctor",
        help="Report offline static readiness; live facts are never checked",
    )
    doctor.add_argument(
        "--format",
        choices=("json", "text"),
        default="json",
    )
    comparison_class = commands.add_parser(
        "comparison-class",
        help="Inspect checked-in expansion readiness without live contact",
    )
    comparison_class_commands = comparison_class.add_subparsers(
        dest="comparison_class_command",
        required=True,
    )
    inspect = comparison_class_commands.add_parser(
        "inspect",
        help="Inspect one checked-in comparison class and approved artifacts",
    )
    inspect.add_argument("comparison_class_id")

    open_mix = commands.add_parser(
        "open-mix",
        help="Inspect a checked-in heterogeneous comparison without live contact",
    )
    open_mix_commands = open_mix.add_subparsers(
        dest="open_mix_command",
        required=True,
    )
    inspect_mix = open_mix_commands.add_parser(
        "inspect",
        help="Inspect members, shared suites, and static artifact readiness",
    )
    inspect_mix.add_argument("open_mix_id")

    binding = commands.add_parser(
        "binding",
        help="Propose, validate, and explicitly adopt an offline cell binding",
    )
    binding_commands = binding.add_subparsers(
        dest="binding_command",
        required=True,
    )
    propose = binding_commands.add_parser(
        "propose",
        help="Write one immutable local proposal from checked-in cell IDs",
    )
    propose.add_argument("--id", dest="binding_id", required=True)
    propose.add_argument("--revision", default="1")
    propose.add_argument("--family", required=True)
    propose.add_argument(
        "--cell",
        dest="cells",
        action="append",
        required=True,
        help="Checked-in same-family native cell ID; repeat in desired order",
    )
    propose.add_argument("--notes", default="")
    for name, help_text in (
        ("show", "Show a proposal and its current offline validation"),
        ("validate", "Revalidate proposal hashes, cells, and artifacts"),
        ("adopt", "Explicitly adopt a ready declaration without live authority"),
    ):
        command = binding_commands.add_parser(name, help=help_text)
        command.add_argument("binding_id")
    return parser


def main(
    argv: Sequence[str] | None = None,
    *,
    machine_profile_path: Path = DEFAULT_MACHINE_PROFILE_PATH,
) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "policy":
            body = _command_policy(args)
        elif args.command == "plan":
            body = _command_plan(args, machine_profile_path)
        elif args.command == "run":
            body = _command_run(args, machine_profile_path)
        elif args.command == "resume":
            body = _command_resume(args, machine_profile_path)
        elif args.command == "status":
            body = _command_status(args)
        elif args.command == "browse":
            body = _command_browse(args)
        elif args.command == "doctor":
            body = _command_doctor(args, machine_profile_path)
            if body is None:
                return 0
        elif args.command == "comparison-class":
            body = _command_comparison_class(args, machine_profile_path)
        elif args.command == "open-mix":
            body = _command_open_mix(args, machine_profile_path)
        elif args.command == "binding":
            body = _command_binding(args, machine_profile_path)
        else:
            body = _command_report(args)
        _emit(body)
        return 0
    except Exception as error:
        _emit(
            {
                "error": {
                    "kind": str(getattr(error, "code", error.__class__.__name__)),
                    "message": _sanitize_error(str(error)),
                },
                "ok": False,
            }
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
