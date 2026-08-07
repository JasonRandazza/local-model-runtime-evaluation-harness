# Run Console

`lmre ui` is a functional, server-rendered operator surface for existing
immutable managed plans. It is deliberately a thin layer over the managed CLI
and evidence bundle rather than a second orchestration engine.

## Start the Console

```bash
./bin/lmre ui
```

The address is fixed to `http://127.0.0.1:8765`. There is no host, port,
endpoint, command, plan-path, or provider override. Starting the server reads
local plan/evidence state only and emits `live_authority: false`.

## What It Can Do

- list existing immutable plans and their honest current state;
- show bound plan facts, stage progress, and recorded runtime ownership;
- link sealed, checksum-verified evidence to the existing report view;
- start a `PENDING` plan through the existing managed `run` command;
- offer overhead-only resume only when the evidence contract permits it;
- request cancellation of the one exact console-owned child.

It cannot adopt policy, create or modify a plan, edit providers, reconnect
Osaurus, select arbitrary paths or endpoints, serve files, or reinterpret
child exit status as evidence truth.

## Live-Action Gate

A start or resume form is rendered only when persisted evidence permits that
action and no console-owned child is active. The operator must:

1. enter the complete displayed SHA-256 plan hash;
2. acknowledge live local inference and the documented reclaim behavior;
3. submit a fresh action grant bound to the exact action, run, and plan hash.

The grant expires after ten minutes, is consumed on its first submission, and
is invalidated when a newer page issues the same action grant. A changed plan,
wrong hash, replay, expired page, missing acknowledgement, or second active
child fails closed.

This UI gate does not replace repository authority rules: live execution still
requires an explicit user request in the current session and an adopted policy
that authorizes the exact immutable plan.

## Local Web Boundary

- fixed loopback bind and exact Host/Origin checks;
- strict same-origin CSRF cookie and form token;
- no JavaScript and no arbitrary file routes;
- HTML escaping for every evidence value;
- restrictive CSP, frame denial, no-store, and MIME-sniffing protections;
- one child with a fixed Python module and fixed `run` or `resume` arguments.

The Cancel action sends `SIGINT` only to the exact child. On console shutdown,
an unresponsive child may receive bounded `SIGTERM` after the grace period.
There is no force-kill fallback and no broad process matching.

## Operator Notes

Start from an idle machine when practical. Osaurus provider reconnection
remains manual, especially after oMLX restarts and before overhead-only resume.
Closing the page does not cancel an active managed command; use Cancel or stop
the console with `Ctrl+C` and let exact cleanup finish.

The implementation contract is preserved in
[the MVP specification](superpowers/specs/2026-08-06-run-orchestration-ui-mvp.md).
