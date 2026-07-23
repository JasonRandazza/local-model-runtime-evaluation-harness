# Operator-Owned Gemma OptiQ 0.4.2 Route Lanes — Gate A Design

**Status:** Design locked for overnight Gate A (Jason, 2026-07-23 — overnight
build authorization). Fake-only / docs first. Does **not** authorize Gate B,
live manifests, usable run IDs, POSTs, provider edits, or plugin rebuild.

**Depends on:** Slice 1b pin-confirm PASS (`0.4.2` on disk; profile revision
`3` constants verified); Slice 1c harness lane sealed PASS on
`stage2-20260723-003` (separate ownership). Sealed operator evidence `005` /
`006` remain bound to profile revision `2` / `0.3.3`.

## Goal

Open distinct **operator-owned** comparison classes for Gemma OptiQ on
`mlx-optiq 0.4.2` so live smoke/benchmark can be authorized later without
mutating sealed `gemma-optiq-operator-route-*` / revision `2` contracts.

## Locked names

| Field | Smoke | Benchmark |
|---|---|---|
| Comparison class | `gemma-optiq-042-operator-route-smoke` | `gemma-optiq-042-operator-route-benchmark` |
| Schema | `3.3.0` | `3.4.0` |
| Mode | `operator_inference_probe` | `operator_route_benchmark` |
| Profile | `gemma-4-12b-optiq-4bit` revision **`3`** | same |
| Suite | `gemma-optiq-042-operator-route-smoke-v1` rev `1` | `gemma-optiq-042-operator-route-benchmark-v1` rev `1` |
| Ownership | `operator` / `service_lifecycle_actions: 0` | same |
| Provider activation | `operator_reconnect_required` | same |
| Launcher | `bin/lmre-stage2-operator-serve-gemma-042` (r3 argv; not the `0.3.3` rollback launcher) | same |

Routes / limits / request counts match the existing revision-`2` smoke (8) and
benchmark (72) suites. Clone suite JSON with new `suite_id` values; keep
workload shapes identical.

## Fail-closed pairing

| Manifest comparison | Allowed profile revision |
|---|---|
| `gemma-optiq-operator-route-smoke` / `-benchmark` | **`2` only** (sealed `005`/`006`) |
| `gemma-optiq-042-operator-route-smoke` / `-benchmark` | **`3` only** |

Reject r3 with historical comparison classes and r2 with `042` comparison
classes.

## Engine / factory

Reuse `StageTwoInferenceEngine` / `StageTwoBenchmarkEngine` and
`OperatorOptiQController`. Extend contract validation / policy allowlists /
manifest schema oneOf branches so the new comparison + suite + revision `3`
tuples are accepted. Do **not** change harness schema `3.5.0`.

## Artifact requirements

Reuse existing Stage 2 inference / benchmark required-file sets (no Stage 2A
`process-ownership.json` / `redacted-log.md`).

## Explicitly out of scope (Gate A)

- Live Gate B readiness, manifests, run IDs, POSTs
- Harness-unattended changes
- Plugin rebuild
- Editing Osaurus providers
- Mutating sealed `005`/`006` or revision-`2` shared parser constants used by
  those cohorts

## Success criteria

1. Fixtures load for both new comparison classes with profile revision `3`.
2. Policy + factory reject wrong revision/comparison pairings.
3. Suites clone existing shapes under new suite IDs.
4. Operator launcher for r3 argv exists and is documented; rollback launcher
   unchanged.
5. Fake-only unit tests pass; no live contact.

## Follow-on (separately gated)

Gate B readiness → Jason authorizes unused run IDs → short-lived manifests →
operator OptiQ lifecycle + reconnect → smoke then (later) benchmark.
