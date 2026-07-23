# Slice 1c — Reconnect-Tap Elimination (Wait-and-Verify) Design

**Status:** Design accepted in conversation (Jason, 2026-07-23). Fake-only /
docs first. Does **not** authorize live manifests, usable run IDs, POSTs,
provider edits, plugin rebuild, or a custom Osaurus↔OptiQ bridge.

**Depends on:** Sealed harness-unattended smoke `stage2-20260723-003` (schema
`3.5.0` / profile revision `4`); Slice 1b pin-confirm PASS (`mlx-optiq 0.4.2`).

**Blocks:** Harness-unattended route benchmark design
(`docs/superpowers/specs/2026-07-23-harness-unattended-route-benchmark-design.md`).

## Goal

Remove the documented **≤1 operator reconnect tap** from harness-unattended
lanes by proving routed inventory with a **bounded wait-and-verify** after
harness-owned OptiQ start — fail closed if the required routed ID never
appears. No provider edits; no custom reconnect API (Osaurus/OptiQ are in
rapid development; a home-grown bridge is out of scope).

## Approach (locked)

**Wait-and-verify.** After `HarnessOptiQController.capture()` starts OptiQ,
poll routed `GET /v1/models` for a bounded window (reuse today’s ~300s
inventory-wait pattern). If the profile-pinned `routed_model_id` appears,
continue with `reconnect_tap_used: false` always. On timeout → fail closed.
Rename misleading `provider_reconnect_tap_*` events to inventory-wait events
(no “tap” language).

Rejected alternatives: inventing an Osaurus reconnect API; keeping ≤1 tap on
new harness work; provider file edits.

## Locked policy / profile

| Field | Value |
|---|---|
| Profile | `gemma-4-12b-optiq-4bit` revision **`5`** |
| `service_ownership` | `harness` |
| `provider_activation` | `verify_routed_id_only_no_tap` (exact enum) |
| Provider edit | Forbidden (unchanged) |
| Operator tap | **Forbidden** on r5 harness lanes |

Revision `4` / schema `3.5.0` / sealed `003` remain historical evidence with
the old `verify_routed_id_only` (≤1 tap documented) policy. Do not rewrite
that sealed cohort.

Update
`docs/superpowers/notes/2026-07-22-slice-1c-provider-reconnect-note.md` with a
supersession section pointing at r5 / no-tap (keep historical body).

## Engine / policy changes (Gate A)

- Teach profile loader + `StageTwoInferenceEngine` (and any shared activation
  validator) the new activation enum; reject unknown / edit-style modes.
- Inventory wait: fail closed on timeout; never instruct or accept an operator
  reconnect tap for `verify_routed_id_only_no_tap`.
- Rename wait events away from `provider_reconnect_tap_*`.
- Fake-only unit tests for: success within window; timeout fail-closed; r4
  historical path still loadable; r5 rejects tap-style activation if any
  residual code path remains.

## Live proof (separately gated after Gate A)

Read-only readiness (no POSTs): harness start OptiQ → inventory wait →
required routed ID present → harness stop; record
`reconnect_tap_used: false`. This proof (or equivalent Gate B note) is the
preferred gate before authorizing harness-unattended **benchmark** live
cohorts. A full smoke re-run on r5 is optional, not required for Design 1.

## Explicitly out of scope

- Custom Osaurus↔OptiQ reconnect bridge or provider config writes
- Plugin `0.3.0` rebuild
- Mutating sealed `003` / r4 / operator lanes
- Schema `3.6.0` benchmark implementation (separate design)
- Ornith/Qwen, preference/RAG, personal-selection Phase B

## Success criteria (Gate A)

1. Profile revision `5` loads with `verify_routed_id_only_no_tap`.
2. Policy/factory reject wrong activation / revision pairings for harness.
3. Inventory wait fail-closed tests pass; no tap events in the r5 path.
4. Reconnect note supersession landed; fake-only suite green; no live contact.

## Follow-on

Harness-unattended route benchmark (`3.6.0`) — separate design; Gate A of that
lane is blocked until **this** Gate A is accepted.
