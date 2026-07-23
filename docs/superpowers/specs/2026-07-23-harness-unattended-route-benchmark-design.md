# Harness-Unattended Gemma OptiQ 0.4.2 Route Benchmark Design

**Status:** Design accepted in conversation (Jason, 2026-07-23). Fake-only /
docs first. Does **not** authorize live manifests, usable run IDs, POSTs,
provider edits, or plugin rebuild.

**Depends on:**  
1. Reconnect-tap elimination Gate A accepted —
   `docs/superpowers/specs/2026-07-23-slice-1c-reconnect-tap-elimination-design.md`
   (profile revision `5`, `verify_routed_id_only_no_tap`).  
2. Preferred before live: Design 1 live inventory-wait proof without tap.  
3. Sealed operator `042` benchmark `stage2-20260723-007` (comparability
   reference; do not mutate).  
4. Sealed harness smoke `stage2-20260723-003` (ownership reference; r4
   historical).

## Goal

Ship a harness-owned **72-POST route benchmark** that is:

1. **Comparable** to operator OptiQ `0.4.2` benchmark `007` (same workload
   shapes, warm/measured counts, routes, limits, observational
   `route_overhead_*`), and  
2. **First-class on harness lifecycle** (`service_lifecycle_actions > 0`,
   harness start/stop proof — not operator Ctrl+C).

Purpose class **C** from brainstorming: both axes are acceptance goals.

## Locked names

| Field | Value |
|---|---|
| Schema | `3.6.0` |
| Mode | `harness_route_benchmark` |
| Comparison class | `gemma-optiq-042-harness-route-benchmark` |
| Profile | `gemma-4-12b-optiq-4bit` revision **`5`** |
| Suite | `gemma-optiq-042-harness-route-benchmark-v1` revision `1` |
| Ownership | `harness` |
| Provider activation | `verify_routed_id_only_no_tap` |
| Plugin | `0.3.0` (unchanged) |
| Direct / routed | `http://127.0.0.1:8080/v1` / `http://127.0.0.1:1337/v1` |
| Total POSTs | `72` (12 excluded warm-ups, 60 measured) |
| Limits | 120s / request; memory `warning`; max in-flight `1` |

Clone suite JSON from
`suites/gemma-optiq-042-operator-route-benchmark-v1.json` with the new
`suite_id`; keep workload prompts, `max_tokens`, and contracts identical.

## Fail-closed pairing

| Comparison | Profile revision | Schema / mode |
|---|---|---|
| `gemma-optiq-042-harness-route-smoke` | `4` only | `3.5.0` / `harness_inference_probe` |
| `gemma-optiq-042-harness-route-benchmark` | `5` only | `3.6.0` / `harness_route_benchmark` |
| `gemma-optiq-042-operator-route-*` | `3` only | `3.3.0` / `3.4.0` |

Reject cross-wiring (r5 + operator comparison; `3.6.0` + r4; r5 + smoke
comparison; etc.).

## Engine / factory

- Add factory branch `(3.6.0, harness_route_benchmark)`.
- Reuse **`StageTwoBenchmarkEngine`** with **`HarnessOptiQController`** (mirror
  how `3.5.0` smoke reuses inference engine + harness controller).
- Extend contract validation, policy allowlists, manifest schema `oneOf`, and
  artifact required-file sets for the new tuple.
- Do **not** mutate operator `3.4.0` / profile r2 / r3 shared parser constants
  used by sealed cohorts.
- Waiter: harness modes must **not** report `OPERATOR_SHUTDOWN_REQUIRED`
  (same as `harness_inference_probe`).

## Acceptance

| Axis | Rule |
|---|---|
| `inference_path_acceptance` | Same semantics as Stage 2B-2 / operator `042` bench |
| `behavioral_contract_acceptance` | Same |
| `route_overhead_summary` / deltas | Observational; parity shape with `007` |
| Lifecycle | Fail-closed: `service_lifecycle_actions > 0`; harness stop verified (port `8080` free twice) |
| Inventory | No operator tap; wait-and-verify per Design 1 |

## Explicitly out of scope (Gate A)

- Live Gate B–D, manifests, run IDs, POSTs
- Provider edits; custom Osaurus↔OptiQ bridge
- Plugin rebuild
- Re-opening sealed `003` / `007` / operator r2 / r3 contracts
- Ornith/Qwen, preference/RAG, personal-selection Phase B
- Implementing Design 1 inside this plan (prerequisite must land first)

## Success criteria (Gate A)

1. Fixtures load for `3.6.0` / harness benchmark / profile r5 / cloned suite.
2. Policy + factory reject wrong pairings.
3. Fake engine path uses harness controller; lifecycle actions counted.
4. Waiter skips operator Ctrl+C for the new mode.
5. Fake-only unit tests pass; no live contact.

## Gate boundaries (after Gate A)

| Gate | Scope |
|---|---|
| **A** | Code, tests, schemas, suite, docs (this design) |
| **B** | Live readiness; harness start; inventory wait; no POSTs |
| **C** | Jason authorizes one unused ID + short-lived `3.6.0` manifest |
| **D** | 72 POSTs, harness cleanup, manager review |

## Follow-on (program)

After sealed PASS: Gemma matrix → preference/RAG/overhead on Gemma PASS cells;
later Ornith/Qwen multi-family; personal-selection Phase B remains paused until
the Gemma frame is built.
