# Operator 007 vs Harness 008 Route Benchmark Comparison

**Date:** 2026-07-23  
**Decision:** observational comparison only (both cohorts sealed **PASS**;
manager-accepted). Does not authorize new run IDs or mutate either bundle.

| Axis | Operator `007` | Harness `008` |
|---|---|---|
| Schema / mode | `3.4.0` / `operator_route_benchmark` | `3.6.0` / `harness_route_benchmark` |
| Profile revision | `3` | `5` |
| Ownership | operator (`service_lifecycle_actions: 0`) | harness (`service_lifecycle_actions: 2`) |
| Provider activation | operator reconnect / Ctrl+C lane | `verify_routed_id_only_no_tap` |
| Suite shape | 72 POSTs (12 warm / 60 measured) | identical |
| Path / behavioral | PASS / PASS | PASS / PASS |
| Checksum | PASS | PASS |

## Route overhead (routed − direct median total)

| Workload | Operator `007` | Harness `008` |
|---|---|---|
| short-chat | **−0.062 s** | **−0.064 s** |
| structured-tool-json | **−0.044 s** | **−0.022 s** |

Both lanes show **near-zero / slightly negative** routed−direct deltas (routed
not observably slower than direct on median total). Absolute medians differ
across cohorts (host load / residency), so compare **deltas and acceptance**,
not absolute wall times, when judging Osaurus route overhead.

## Qualification (both cohorts)

- TTFT: `QUALIFIED_INCREMENTAL_DELIVERY` on direct and routed for both workloads
- Decode TPS: `SUPPRESSED_AMBIGUOUS_TOKEN_ACCOUNTING` (same suppression both lanes)

## Lifecycle contrast (Purpose C)

| | `007` | `008` |
|---|---|---|
| OptiQ start/stop | operator foreground launcher | harness `LifecycleController` |
| `service_lifecycle_actions` | `0` | `2` |
| Cleanup proof | operator Ctrl+C + port free | harness process-group stop + port free twice |

## Verdict

Acceptance and overhead **shape** are comparable. Ownership axis is first-class
on `008` (`lifecycle_actions > 0`) and correctly zero on `007`. Together they
form the Gemma OptiQ `0.4.2` route frame for matrix / preference / RAG /
overhead follow-ons.
