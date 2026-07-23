# Package 2 Gate B: oMLX Thinking Measure Readiness

## Current Decision

`GATE_B_READY` historically meant implementation + read-only check only.
**Supersession (2026-07-23):** Package 2 Gate C/D and D2/D3/D4 live cohorts for
this window are sealed PASSED — see `docs/package-2-omlx-thinking-gate-d.md`.
A *new* thinking live cohort still needs Jason's separate current-session
authorization. This page remains the Gate B contract reference.

**Prerequisite:** Package 2 Gate A (`ThinkingMeasureRunner`, pin, suite,
qualification helpers) and Slice 1a `LifecycleController`.

**Rollback:** Stage 2 OptiQ operator/harness lanes unchanged; sealed `005`/`006`
evidence on `mlx-optiq 0.3.3` / Gemma revision `2`.

## Fixed Contract (authorizing shape after separate live authorization)

| Item | Required value |
|---|---|
| Pin | `omlx-0.5.3-thinking` revision `2` |
| oMLX version | `0.5.3` (exact) |
| Comparison class | `omlx-thinking-measure-v1` |
| Suite | `omlx-thinking-smoke-v1` revision `1` |
| Base URL | `http://127.0.0.1:8100/v1` |
| Ownership mode | `dedicated_serve` |
| Model id | `Qwen3.6-35B-A3B-OptiQ-4bit` |
| Model dir | `/Users/jrazz/.cache/huggingface/hub/mlx-community/Qwen3.6-35B-A3B-OptiQ-4bit` |
| Auth | `matrix_local` (`Authorization: Bearer lmre-matrix-local`) |
| Port | `8100` (must be free before harness-owned dedicated serve) |
| Plugin | `local.jrazz.model-runtime-evaluation-harness` `0.3.0` (unchanged) |

**Out of scope for comparison:** `ThinkingCap-Qwen3.6-27B-OptiQ-4bit` — OptiQ-specific
variation; not comparable to the other Qwen models under test (Jason, 2026-07-22).

**Foreign pool:** Do not reclaim Jason's observed multi-model `:8100` pool with
`omlX stop` without explicit in-session approval. Gate B may observe a busy port
(diagnostic only); `READY_FOR_LIVE_AUTHORIZATION` for `dedicated_serve` requires
port `8100` free.

## Gate Boundaries

| Gate | Scope | Status |
|---|---|---|
| **A** | Pin, runner, suite, qualification, fake-only tests | **Passed** (not live) |
| **B** | Read-only identity + auth + lifecycle mode check | **Ready** (implementation closed; not live) |
| **C** | Jason authorizes one unused run ID + short-lived smoke | **Passed** — sealed `omlx-thinking-20260722-004` |
| **D** | Manager review of sealed Gate C smoke | **Passed** — ACCEPT on `004` |

Gate B is non-authorizing. It does not create a usable run ID or live manifest,
issue thinking POSTs, start or stop oMLX, or reclaim a foreign `:8100` pool.

**Gate C sealed evidence:**
`docs/superpowers/verification/2026-07-22-package-2-gate-c-omlx-thinking-20260722-004.md`
(consumed IDs `001`–`003` are historical FAIL / FAIL_CLEANUP only).

**Gate D:** **Passed** (ACCEPT 2026-07-22) — see
`docs/package-2-omlx-thinking-gate-d.md` and
`docs/superpowers/verification/2026-07-22-package-2-gate-d-manager-review-004.md`.
Follow-ons: **D2** / **D3** / **D4** live PASSED for this window
(`omlx-thinking-measure-20260722-001`, `omlx-thinking-bench-20260723-001`,
`omlx-thinking-measure-20260722-004`).

## Readiness CLI

```sh
./bin/lmre-omlx-thinking-gate-b-check
```

Optional flags:

- `--pin-path` — override pin JSON (default: `config/omlx-pins/omlx-0.5.3-thinking-r2.json`)
- `--observe-busy-port` / `--no-observe-busy-port` — when port `8100` is busy, probe
  `GET /health` and authenticated `GET /v1/models` without reclaim (default: observe on)

The CLI emits JSON on stdout. Exit code `0` only when `decision` is
`READY_FOR_LIVE_AUTHORIZATION`. It never POSTs, never creates run IDs, and
reports `http_post_attempts: 0`, `inference_request_attempts: 0`, and
`service_lifecycle_actions: 0`.

When `~/.omlx/model_settings.json` (and optional `model_profiles.json`) is
readable, the report includes an `omlx_profile_observe` diagnostic block
(`enable_thinking`, `active_profile_name`, `profile_enable_thinking`). This
block does **not** affect the `decision` or exit code — request pinning is
enforced by the pin JSON and transport, not by oMLX UI profile state.

## Decision codes

| Code | Meaning |
|---|---|
| `READY_FOR_LIVE_AUTHORIZATION` | Pin, version, and dedicated-serve preconditions satisfied; port `8100` free |
| `pin_invalid` | Pin JSON fails fail-closed loader or mismatches locked constants |
| `version_mismatch` | Disk `omlX --version` ≠ `0.5.3` |
| `port_busy` | Port `8100` occupied and `--no-observe-busy-port` (no diagnostic probe) |
| `port_busy_foreign_pool` | Port busy; health and inventory probe succeeded but port not free (dedicated serve blocked) |
| `health_unavailable` | Port busy; `/health` not `ok`/`healthy` |
| `model_missing` | Port busy; authenticated inventory lacks exact `model_id` |
| `version_probe_failed` | `omlX --version` failed or unreadable |
| `STOPPED` | Unexpected error during check |

For `dedicated_serve`, only `port_8100_free: true` yields
`READY_FOR_LIVE_AUTHORIZATION`. Observe mode helps diagnose a foreign pool but
does not authorize live work while the port remains busy.

## Operator sequence (after Jason authorizes live Gate C+)

1. Ensure port `8100` is free (stop foreign pool only with explicit approval).
2. Run read-only Gate B: `./bin/lmre-omlx-thinking-gate-b-check`.
3. Confirm `decision: READY_FOR_LIVE_AUTHORIZATION`.
4. Jason authorizes one exact unused run ID in the current session.
5. Issue thinking smoke via `ThinkingMeasureRunner` + Slice 1a lifecycle (honest
   `service_lifecycle_actions > 0`).

## Related documents

| Item | Location |
|---|---|
| Design | `docs/superpowers/specs/2026-07-22-package-2-omlx-thinking-measure-design.md` |
| Gate A plan | `docs/superpowers/plans/2026-07-22-package-2-omlx-thinking-measure-gate-a.md` |
| Gate B plan | `docs/superpowers/plans/2026-07-22-package-2-omlx-thinking-gate-b.md` |
| Pin-confirm checklist | `docs/superpowers/notes/2026-07-22-package-2-omlx-052-pin-confirm-checklist.md` |
| Pin-confirm evidence | `docs/superpowers/notes/2026-07-22-package-2-omlx-052-pin-confirm-evidence.md` |
| Queue design | `docs/superpowers/specs/2026-07-21-stack-review-gate-a-queue-design.md` |
| Gate D status | `docs/package-2-omlx-thinking-gate-d.md` |
| Gate D design | `docs/superpowers/specs/2026-07-22-package-2-omlx-thinking-gate-d-design.md` |
| Gate D checklist | `docs/superpowers/notes/2026-07-22-package-2-gate-d-manager-review-checklist.md` |
| Gate D ACCEPT | `docs/superpowers/verification/2026-07-22-package-2-gate-d-manager-review-004.md` |
