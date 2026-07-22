# Stack-Review Gate A Queue Design

**Status:** Approved in conversation by Jason on 2026-07-21. This document
authorizes **implementation planning only**. It does **not** authorize Gate B,
a live manifest, a usable run ID, OptiQ/oMLX/Osaurus upgrades on disk, provider
edits, OptiQ Lab, plugin rebuild/reinstall, or live inference.

**Context:** Stage 2B-1 cohort `stage2-20260721-005` and Stage 2B-2 cohort
`stage2-20260721-006` sealed PASS under operator-owned `mlx-optiq 0.3.3` and
Gemma profile revision `2`. Those IDs are consumed historical evidence and
rollback. Upstream oMLX `0.5.2` and OptiQ `0.3.3`→`0.4.2` release notes are
captured in implication notes (planning only).

## Goal

Freeze an ordered Gate A queue so the harness can (1) own multi-server lifecycle
without Jason sitting in Ctrl+C loops, (2) retarget Stage 2 OptiQ to `0.4.2` with
a new Gemma profile revision after chat-template sync, and (3) later revisit
thinking-model measurement on oMLX `0.5.2`.

This is a **deployment and continuity** design, not a new preference/RAG/matrix
campaign.

## Artifact shape

- **Thin queue + deep Package 1:** one design locks the queue; Package 1 is fully
  specified in three Gate A slices; Package 2 Gate A is landed (fake-only; live
  pin-confirm and Gate B separately gated).
- Exactly **two** packages in the queue (no parked third comparison matrix item).

## Hard boundaries

- No live Gate B/C/D, run IDs, or authorizing manifests from this document.
- Do not upgrade OptiQ/oMLX binaries or Gemma snapshots on disk until a later,
  separately authorized Gate B+ window.
- Plugin `local.jrazz.model-runtime-evaluation-harness` `0.3.0` unchanged.
- OptiQ Lab must remain closed for any OptiQ-owned port `8080` work.
- Never stop a foreign Osaurus process the harness did not spawn.
- Do not mix sealed `005`/`006` evidence with post–template-sync OptiQ pins.
- Provider *edit* (host/port/path/headers/credentials) remains forbidden.

## Ordered Gate A queue

| Order | Package | Depth | Depends on |
|---|---|---|---|
| 1 | OptiQ pin bump + harness 3-server lifecycle + Stage 2 unattended path | Deep (slices 1a→1b→1c) | — |
| 2 | oMLX `0.5.2` thinking-model measurement revisit | Stub only | Slice 1a (oMLX start/stop) |

## Package 1 — deep design

Package 1 is a **harness lifecycle platform** that Stage 2 consumes, building on
matrix/preference patterns rather than reintroducing early Stage 2 harness
lifecycle without the RAM/ownership lessons already learned.

### Slice 1a — Shared lifecycle controller

**Role:** One harness-owned module that starts and stops **exactly one** pinned
server at a time:

| Server | Port |
|---|---|
| OptiQ | `8080` |
| oMLX | `8100` |
| Osaurus | `1337` |

**Reuse (do not fork a second stack):** patterns from
`src/local_model_runtime_evaluation/matrix_lifecycle.py` and
`src/local_model_runtime_evaluation/matrix_servers.py` (spawn, ready wait,
SIGTERM→SIGKILL, port-free verification, `_owned` guard). Matrix/preference
migration onto this module is allowed later but **not required** in 1a.

**Fail-closed contract:**

- Before start: free memory ≥ configured floor (default **20%**, same as matrix);
  target port free (except observe-only Osaurus when already up and not
  harness-owned); OptiQ Lab closed; no foreign `optiq serve` on `:8080`.
- Start: exact pinned argv/binary/hashes from the active profile (OptiQ `0.4.2`
  arrives in 1b; 1a Gate A tests may use fixtures/fakes).
- Ready: health + inventory identity match (server-specific).
- Stop: only processes the harness spawned (`_owned`); never stop foreign
  Osaurus; verify port free after stop.
- Record **honest** `service_lifecycle_actions` counts (not forced zero).

**Gate A tests (non-live):** fakes only — ownership guards, port busy,
RAM-floor refuse-to-start, Lab-open reject, double-start reject.

**Gate A implementation plan:**
`docs/superpowers/plans/2026-07-21-slice-1a-harness-lifecycle-gate-a.md`

### Slice 1b — OptiQ pin bump (`0.3.3` → `0.4.2`)

**Goal:** New authorizing OptiQ identity after Gemma-4 chat-template sync and
tool-call fixes, without invalidating sealed `005`/`006`.

**Pin contract:**

- Executable: `mlx-optiq` / `optiq` **`0.4.2`** (exact path, version, and hash in
  profile).
- New Gemma runtime profile revision: `gemma-4-12b-optiq-4bit` revision **`3`**.
  Revision `2` remains historical evidence only.
- Re-resolve snapshot path, artifact hashes, argv array, and **exact routed
  inventory ID** after Google chat-template sync (may still be path-based
  `:no-think`, but must be measured later — not assumed from revision `2`).
- Comparison evidence must stay distinct: do not silently reuse sealed
  `gemma-optiq-operator-route-smoke` / `gemma-optiq-operator-route-benchmark`
  evidence under the new pin. New live authorization (later) needs a new
  comparison class and/or suite revision — named in the Gate A implementation
  plan, not invented here as live authority.

**Gate A / non-live verification:** profile loader tests, hash/argv fail-closed
tests, factory rejects mixing revision `2` manifests with `0.4.2` lifecycle,
documented pin-confirm checklist (live identity probe separately gated).

**Rollback:** Stage 2B-1/`005`, Stage 2B-2/`006`, and operator-owned `0.3.3`
launchers (`bin/lmre-stage2-operator-serve-gemma`) remain the accepted baseline.

**Gate A implementation plan:**
`docs/superpowers/plans/2026-07-21-slice-1b-optiq-042-pin-gate-a.md`

**Pin-confirm checklist (operator-owned, separately gated):**
`docs/superpowers/notes/2026-07-21-slice-1b-optiq-042-pin-confirm-checklist.md`

### Slice 1c — Stage 2 unattended path

**Goal:** Stage 2 smoke/benchmark cohorts without Jason starting/stopping OptiQ.
Harness uses Slice 1a lifecycle + Slice 1b pin.

```mermaid
sequenceDiagram
  participant Coord as Coordinator
  participant Harness as Stage2Engine
  participant Life as LifecycleController
  participant OptiQ as OptiQ_8080
  participant Osa as Osaurus_1337

  Coord->>Harness: preflight
  Harness->>Life: ensure OptiQ started
  Life->>OptiQ: spawn_ready
  Harness->>Life: ensure Osaurus ready
  Note over Harness,Osa: Provider edit forbidden; verify routed identity after OptiQ is up
  Coord->>Harness: run_scenario
  Harness->>OptiQ: serial POSTs direct and routed
  Harness->>Life: stop harness-owned OptiQ
  Life->>OptiQ: stop_port_free
  Coord->>Harness: cleanup
```

**Policy change for the new lane:**

- New Stage 2 mode/schema and/or profile flag where `service_lifecycle_actions`
  may be **greater than zero**.
- Cleanup requires harness-owned stop proof (process absent, port `8080` free),
  **not** manual Ctrl+C.
- Operator-owned `0.3.3` path remains rollback for historical manifests only.

**Provider policy (default locked by this design):**

- Provider *edit* remains forbidden.
- Provider must already be configured to reach OptiQ; harness verifies exact
  routed inventory ID after OptiQ is up.
- If reconnect is required and no safe non-editing API exists, Gate A may
  document **one** remaining operator tap — not full lifecycle ownership.
  Prefer eliminating that tap when a safe reconnect path is proven.

**Depends on:** slices 1a and 1b.

**Gate A status:** landed (implementation and fake-only tests; not live authority).

**Gate A implementation plan:**
`docs/superpowers/plans/2026-07-22-slice-1c-harness-unattended-gate-a.md`

**Provider verify-only / reconnect tap note:**
`docs/superpowers/notes/2026-07-22-slice-1c-provider-reconnect-note.md`

**Gate A operator doc:** `docs/stage-2-harness-unattended-gate-a.md`

## Package 2 — oMLX 0.5.2 thinking-model measurement

**Name:** oMLX `0.5.2` thinking-model measurement revisit.

**Depends on:** Slice 1a (harness can start/stop oMLX).

**Design (expanded from stub):**
`docs/superpowers/specs/2026-07-22-package-2-omlx-thinking-measure-design.md`

**Gate A implementation plan:**
`docs/superpowers/plans/2026-07-22-package-2-omlx-thinking-measure-gate-a.md`

**Pin-confirm checklist:**
`docs/superpowers/notes/2026-07-22-package-2-omlx-052-pin-confirm-checklist.md`

**Pin-confirm evidence (2026-07-22):**
`docs/superpowers/notes/2026-07-22-package-2-omlx-052-pin-confirm-evidence.md`

**Gate B development plan:**
`docs/superpowers/plans/2026-07-22-package-2-omlx-thinking-gate-b.md`

**Gate B readiness surface (not live):**
`docs/package-2-omlx-thinking-gate-b.md`

**Gate C sealed PASS:**
`docs/superpowers/verification/2026-07-22-package-2-gate-c-omlx-thinking-20260722-004.md`

**Gate D design / plan / status (manager review; not auto-accepted):**
`docs/superpowers/specs/2026-07-22-package-2-omlx-thinking-gate-d-design.md`,
`docs/superpowers/plans/2026-07-22-package-2-omlx-thinking-gate-d.md`,
`docs/package-2-omlx-thinking-gate-d.md`

**Implications note:**
`docs/superpowers/notes/2026-07-21-omlx-0.5.2-implications.md`

**Intent:** Measure thinking models without false preflight failure (oMLX
`0.5.2`/`0.5.3` token-budget / external-bench fixes + harness-side classification).

**Gate A status:** landed (implementation and fake-only tests; not live authority).
**Gate B status:** landed readiness surface.
**Gate C status:** sealed PASS `omlx-thinking-20260722-004`.
**Gate D status:** **Passed** (Jason ACCEPT 2026-07-22 on sealed `004`).
**Follow-ons:** D2 Gate A ready (`docs/package-2-omlx-thinking-d2.md`); D3 external-bench (deferred).

**Non-goals:** OptiQ retarget, same-artifact OptiQ↔oMLX
matrix campaign, preference/RAG expansion.

## Package 1 success criteria

- Harness can serially own OptiQ / oMLX / Osaurus start-stop under the RAM floor
  without Jason holding Ctrl+C for OptiQ.
- OptiQ `0.4.2` + Gemma profile revision `3` is specified fail-closed; `005` and
  `006` remain rollback on `0.3.3` / revision `2`.
- Stage 2 unattended path is specified; provider edit remains forbidden.
- This document creates no live authority.

## Explicit out of scope

- Live Gate B/C/D, manifests, run IDs, inference.
- Upgrading binaries/snapshots on disk.
- Plugin `0.3.0` rebuild or reinstall.
- OptiQ Lab as a substitute for pinned `optiq serve`.
- Killing foreign Osaurus.
- Mixing pre- and post–template-sync Gemma evidence in one comparison class.
- Live Package 2 Gate B / thinking-measure POSTs (pin-confirm and Gate B remain
  separately gated).
- Expanding preference/matrix/overhead campaigns in Package 1 (reuse patterns
  only).

## Related evidence and notes

| Item | Location |
|---|---|
| Stage 2B-1 PASS `005` | Sealed under `mlx-optiq 0.3.3` / Gemma rev `2` |
| Stage 2B-2 PASS `006` | Sealed under same pin; manager-reviewed |
| oMLX `0.5.2` implications | Vault: `oMLX 0.5.2 Release Implications - 2026-07-21` |
| OptiQ `0.3.3`→`0.4.2` implications | `docs/superpowers/notes/2026-07-21-mlx-optiq-0.3.3-to-0.4.2-implications.md` |
| Matrix lifecycle base | `matrix_lifecycle.py`, `matrix_servers.py` |
| Stage 2B-2 design (historical operator-owned) | `docs/superpowers/specs/2026-07-21-stage-2b2-gemma-route-benchmark-design.md` |

## Implementation planning order (after this spec is accepted)

1. Gate A implementation plan for **slice 1a** (shared lifecycle).
2. Gate A implementation plan for **slice 1b** (OptiQ `0.4.2` pin).
3. Gate A implementation plan for **slice 1c** (Stage 2 unattended wiring).
4. Separate design + plan for **Package 2** (oMLX thinking measure).

Do not start live authorization for any slice until its Gate A is implemented,
reviewed, and Jason separately authorizes Gate B+.

## Spec self-review (2026-07-21)

- No TBD/TODO/FIXME placeholders.
- Queue length and slice order match brainstorm locks (exactly two packages;
  1a→1b→1c; Package 2 Gate A landed).
- Boundaries consistent: planning-only; `005`/`006` rollback; plugin `0.3.0`
  unchanged; Lab closed; no foreign Osaurus stop; provider edit forbidden.
- Deliberate tension with current Stage 2 operator-owned lifecycle is stated as
  a **new lane** with historical rollback — not a silent rewrite of sealed runs.
- Soft deferrals left to Gate A plans (exact schema/mode names; comparison class
  strings for post-sync evidence; optional single reconnect tap) are named as
  plan-time decisions, not live authority.
