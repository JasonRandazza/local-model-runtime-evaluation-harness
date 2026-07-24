# Stage 2 Harness-Unattended Gate A: Gemma OptiQ 0.4.2 Smoke

## Current Decision

`GATE_A_PASSED`. Gate B `READY_FOR_MANIFEST_AUTHORIZATION` (2026-07-23). Gate C/D
live smoke sealed **PASS** on unused run `stage2-20260723-003` (8/8 POSTs;
schema `3.5.0` / profile revision `4`). Re-evidence **PASS** on
`stage2-20260724-001` (8/8; `service_lifecycle_actions: 2`; no reconnect tap) —
`docs/superpowers/verification/2026-07-24-slice-1c-stage2-20260724-001-pass.md`.
Prior same-day IDs `001`/`002` (2026-07-23) cleaned STOPPED (reconnect / Ornith
residency). See
`docs/superpowers/verification/2026-07-23-slice-1c-stage2-20260723-003-pass.md`.
Do not reuse `001`–`003` (2026-07-23) or `stage2-20260724-001`.

**Follow-on Design 1:** reconnect-tap elimination Gate A landed; live
inventory-wait proof **PASS** (revision `5`, `verify_routed_id_only_no_tap`,
`reconnect_tap_used: false`) —
`docs/superpowers/verification/2026-07-23-slice-1c-inventory-wait-r5-proof.md`.

**Follow-on Design 2 (harness route benchmark):** Gate A–D **closed** for this
window. Cohort `stage2-20260723-008` sealed **PASS** (72/72; schema `3.6.0` /
profile revision `5`; `service_lifecycle_actions: 2`). See
`docs/superpowers/verification/2026-07-23-design2-harness-benchmark-stage2-20260723-008-pass.md`
and Gate B
`docs/superpowers/verification/2026-07-23-design2-harness-benchmark-gate-b.md`.
Do not reuse `008`. A *new* Design 2 cohort needs Jason's separate unused-ID
authorization.

**Prerequisite slices:** Slice 1a (`harness_lifecycle.py`) and Slice 1b
(revision `3` / `0.4.2` pin constants). Live pin-confirm on disk remains
operator-owned and separately gated.

**Rollback:** Operator-owned schemas `3.3.0` / `3.4.0`, profile revision `2`,
sealed cohorts `stage2-20260721-005` / `006`, and Stage 2A revision `3` remain
unchanged evidence and rollback baselines.

Provider policy:
`docs/superpowers/notes/2026-07-22-slice-1c-provider-reconnect-note.md`.

## Fixed Contract (authorizing shape after separate Gate C authorization)

| Item | Required value |
|---|---|
| Manifest schema | `3.5.0` |
| Mode | `harness_inference_probe` |
| Comparison class | `gemma-optiq-042-harness-route-smoke` |
| Runtime profile | `gemma-4-12b-optiq-4bit` revision `4` |
| Suite | `gemma-optiq-042-harness-route-smoke-v1` revision `1` |
| Service ownership | `harness` |
| Provider activation | `verify_routed_id_only` (no provider edits) |
| Direct route | `http://127.0.0.1:8080/v1` |
| Routed route | `http://127.0.0.1:1337/v1` |
| Route order | counterbalanced within each workload |
| Request timeout | 120 seconds |
| Memory stop level | `warning` |
| Maximum in-flight requests | `1` |
| Total request limit | `8` |
| Expected routed ID | `optiq//Users/jrazz/.cache/huggingface/hub/mlx-community/gemma-4-12B-it-qat-OptiQ-4bit:no-think` |
| Plugin | `local.jrazz.model-runtime-evaluation-harness` `0.3.0` (unchanged) |

Acceptance decisions match Stage 2B-1 smoke: `inference_path_acceptance` and
`behavioral_contract_acceptance`. Evidence reports honest
`service_lifecycle_actions > 0`. Cleanup uses harness-owned stop proof (port
`8080` free twice) — **not** operator `Ctrl+C`.

Operator schemas `3.3.0` / `3.4.0` must not start a harness-unattended run.

## Gate Boundaries

| Gate | Scope | Status |
|---|---|---|
| **A** | Code, tests, schemas, suite, docs | **Passed** (implementation closed; not live) |
| **B** | Live read-only readiness; harness starts OptiQ; verify routed ID | **READY_FOR_MANIFEST_AUTHORIZATION** (2026-07-23; evidence `docs/superpowers/verification/2026-07-23-slice-1c-harness-unattended-gate-b.md`) |
| **C** | Jason authorizes one unused run ID + short-lived `3.5.0` manifest | **Closed** — live ID `stage2-20260723-003` (manifest `manifests/stage-2-optiq-harness-route-003.json`); `001`/`002` STOPPED |
| **D** | Eight POSTs, harness cleanup, manager review | **PASS** — `stage2-20260723-003` sealed (8/8; checksum PASS) |

Gate A is non-authorizing. It does not create a usable run ID or live manifest,
install a Coordinator prompt, upgrade OptiQ on disk, edit a provider, or grant
inference authority.

Design authority: `docs/superpowers/specs/2026-07-21-stack-review-gate-a-queue-design.md`
(Slice 1c). Implementation plan:
`docs/superpowers/plans/2026-07-22-slice-1c-harness-unattended-gate-a.md`.
