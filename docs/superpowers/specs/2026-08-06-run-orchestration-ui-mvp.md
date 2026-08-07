# Run-Orchestration UI MVP

**Status:** Approved implementation contract for the first functional run UI
slice (2026-08-06).
**Visual reference:** `docs/ui/run-console-functional-concept.png`.

## Goal

Add a small local operator console over **existing immutable managed plans**.
It must make plan state, live authority, execution progress, blocked resume,
and sealed evidence understandable without weakening any CLI, policy,
lifecycle, or evidence rule.

This is an expert local tool, not a setup wizard or cloud console. Functional
clarity outranks visual novelty.

## Product Boundary

The command `lmre ui` starts one standard-library HTTP server on fixed
loopback address `127.0.0.1:8765`. Starting the server grants no inference or
policy authority. It does not contact a runtime until the operator submits a
fresh, valid live-action form for an exact existing plan.

The MVP supports:

- listing recognized managed plans beneath the configured results root;
- selecting a plan and reading its immutable identity, state, step progress,
  policy snapshot identity, and lifecycle summary;
- starting an unsealed `PENDING` plan after a single-use authority gate;
- requesting exact cooperative cancellation of the console-owned child;
- resuming only a sealed run that the evidence contract already declares
  resumable;
- opening the existing fail-closed run-detail presentation;
- refreshing state from the evidence bundle at any time.

The UI does not create plans or comparison declarations and does not adopt or
replace policy. Those remain deliberate CLI workflows for this slice.

## Architecture

The UI has three narrow layers:

| Layer | Responsibility |
| --- | --- |
| Console view model | Load vetted run IDs through existing bundle/browser APIs; derive only display and action eligibility. |
| Console HTML | Render escaped, semantic, server-side HTML. No evidence I/O and no JavaScript. |
| Loopback server | Fixed routes, Host/Origin/CSRF checks, single-use live-action grants, and one fixed child CLI process. |

The server starts the existing managed CLI with a fixed argument vector for
`run` or `resume`; it never accepts a command, executable, endpoint, model, or
path from a form. The child remains the only execution writer and continues to
use the existing active-run lock, plan/input verification, policy snapshot,
runtime manager, cleanup, and sealing paths.

The server's in-memory process record is presentation state only. After a UI
restart, the console rebuilds truth from the evidence bundle and active-run
lock. It never rewrites a run based on remembered UI state.

## Routes

| Method | Route | Behavior |
| --- | --- | --- |
| `GET` | `/` | List plans and select the newest recognized plan. |
| `GET` | `/runs/<safe-run-id>` | Render one plan console. |
| `GET` | `/runs/<safe-run-id>/report` | Render the existing fail-closed run detail. |
| `POST` | `/runs/<safe-run-id>/start` | Consume an exact-plan live grant and start the fixed `run` child. |
| `POST` | `/runs/<safe-run-id>/resume` | Consume an exact-plan live grant and start the fixed `resume` child. |
| `POST` | `/runs/<safe-run-id>/cancel` | Send `SIGINT` only to the exact active console-owned child. |

Every successful mutation uses `303 See Other` back to the known run route.
There are no user-controlled redirects or generic file-serving routes.

## Live Authority Gate

`start` and `resume` require all of the following in one current form:

1. a recognized safe run ID;
2. current action eligibility from the evidence state;
3. the full displayed immutable plan hash typed exactly;
4. an explicit acknowledgement that this action performs local inference and
   may reclaim an incompatible process after the policy-defined 60-second
   notice;
5. a same-session CSRF token;
6. a single-use action nonce bound to action, run ID, and plan hash;
7. no active console child and no competing managed-run lock.

The nonce expires after ten minutes and is consumed before child creation.
Any mismatch, expiry, replay, or changed plan fails closed and grants nothing.
Authority is never remembered after the action.

## Cancellation

Cancellation is available only while the exact console-owned child is alive.
The Cancel action sends `SIGINT` to that PID and does not escalate. The
existing managed execution path catches the
interrupt, records `STOPPED`, attempts exact runtime cleanup, and seals when
cleanup succeeds. The UI reports `Cancellation requested` until evidence
reaches a terminal state.

Closing a browser tab does not cancel a run. Stopping the UI from its terminal
requests `SIGINT` for an active child and waits for the child cleanup path. If
that exact child does not exit within the bounded grace period, shutdown may
send `SIGTERM` to the same PID and wait once more. It never uses `SIGKILL`,
force kill, or broad process matching.

## Security and Privacy

- Bind only `127.0.0.1`; never wildcard or remote interfaces.
- Require the exact loopback `Host` and same-origin `Origin` or `Referer` on
  every POST to mitigate DNS rebinding and cross-site form attacks.
- Use one random session CSRF token and `SameSite=Strict`, `HttpOnly` cookie.
- Set a restrictive Content Security Policy, `frame-ancestors 'none'`,
  `form-action 'self'`, `X-Content-Type-Options: nosniff`, and no-store cache
  headers.
- Escape every displayed value. Do not render raw response bodies, arbitrary
  HTML, terminal control sequences, credentials, or generic filesystem data.
- Expose no provider, credential, model-weight, endpoint, command, policy, or
  path editor.

## UI and Accessibility

The visual reference defines a restrained true-white, slate-text, blue-action
system with a fixed plan rail and open table-oriented detail area. The code
implementation uses system fonts and no raster asset at runtime.

- Status always appears as text; color is supplementary.
- Keyboard focus is visible and source order follows visual order.
- Forms have explicit labels, field descriptions, and error summaries.
- The action acknowledgement is unchecked by default.
- No consent is time-pressured even though its unused nonce expires.
- At narrow widths the plan rail stacks above detail without horizontal page
  overflow; wide evidence tables may scroll within their own region.
- Motion is limited to the browser's native interactions and respects reduced
  motion automatically because the page has no scripted animation.

## Explicit Non-Goals

- policy adoption or replacement;
- plan, binding, comparison-class, or open-mix creation;
- provider creation, editing, or reconnection;
- credentials, Keychain, endpoints, commands, paths, or model-weight controls;
- automatic discovery, downloads, cache cleanup, or service polling;
- multiple simultaneous runs or distributed orchestration;
- arbitrary process management or force kill;
- raw model-response viewing, evidence editing, or derived scientific claims;
- remote hosting, authentication, TLS, telemetry, or external assets;
- replacing the CLI or changing sealed evidence semantics.

## Verification Contract

Tests use temporary bundles and injected fake child processes only. They must
prove rendering and escaping, safe-ID routing, Host/Origin/CSRF enforcement,
single-use exact-hash grants, no GET mutations, action eligibility, one-child
exclusion, exact-child `SIGINT`, error sanitization, report fail-closed reuse,
and zero runtime/credential/process contact in default test construction.

The retained Python suite and all dry-config commands must pass. A manual UI
check may use existing evidence read-only, but this slice performs no live run.
