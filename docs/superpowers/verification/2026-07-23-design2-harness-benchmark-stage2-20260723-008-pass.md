# Design 2 Gate D — stage2-20260723-008 PASS

**Date:** 2026-07-23  
**Decision:** **ACCEPT PASS**  
**Authorized by:** Jason (current session — Gate B → C/D continuous)

## Contract

| Field | Value |
|---|---|
| Schema | `3.6.0` |
| Mode | `harness_route_benchmark` |
| Comparison | `gemma-optiq-042-harness-route-benchmark` |
| Profile | `gemma-4-12b-optiq-4bit` revision `5` |
| Suite | `gemma-optiq-042-harness-route-benchmark-v1` revision `1` |
| Provider activation | `verify_routed_id_only_no_tap` |
| Manifest | `manifests/stage-2-optiq-harness-benchmark-008.json` |
| Bundle | `/Users/jrazz/.osaurus/container/output/benchmark-runs/stage2-20260723-008` |

## Results

| Check | Result |
|---|---|
| POSTs | **72/72** |
| Measured / warm-ups | 60 / 12 |
| `inference_path_acceptance` | **PASS** |
| `behavioral_contract_acceptance` | **PASS** |
| `artifact_validation` | **PASS** |
| `checksum_validation` | **PASS** |
| `service_lifecycle_actions` | **2** (harness start + stop) |
| OptiQ `:8080` after cleanup | free |
| `reconnect_tap_used` | false (Gate B + preflight) |

Comparability reference (do not mutate): operator `042` benchmark
`stage2-20260723-007`. Ownership reference: harness smoke
`stage2-20260723-003` (r4 historical).

## Status

Run ID **consumed**. Design 2 Gate B–D for schema `3.6.0` / profile revision
`5` is evidenced by `008`.
