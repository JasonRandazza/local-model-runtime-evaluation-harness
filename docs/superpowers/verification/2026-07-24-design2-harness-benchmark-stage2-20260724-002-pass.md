# Design 2 Gate D — stage2-20260724-002 PASS

**Date:** 2026-07-24  
**Decision:** **ACCEPT PASS**  
**Authorized by:** Jason (`stage2-20260724-002`)

## Contract

| Field | Value |
|---|---|
| Schema | `3.6.0` |
| Mode | `harness_route_benchmark` |
| Comparison | `gemma-optiq-042-harness-route-benchmark` |
| Profile | `gemma-4-12b-optiq-4bit` revision `5` |
| Suite | `gemma-optiq-042-harness-route-benchmark-v1` revision `1` |
| Provider activation | `verify_routed_id_only_no_tap` |
| Manifest | `manifests/stage-2-optiq-harness-benchmark-20260724-002.json` |
| Bundle | `/Users/jrazz/.osaurus/container/output/benchmark-runs/stage2-20260724-002` |

## Results

| Check | Result |
|---|---|
| POSTs | **72/72** |
| Measured / warm-ups | 60 / 12 |
| `inference_path_acceptance` | **PASS** |
| `behavioral_contract_acceptance` | **PASS** |
| `artifact_validation` | **PASS** |
| `checksum_validation` | **PASS** |
| `operator_shutdown_verified` | **PASS** |
| `service_lifecycle_actions` | **2** |
| OptiQ `:8080` after cleanup | free |
| Reconnect tap | not required |

Route overhead (routed − direct median total): short-chat ≈ **+0.068s**;
structured-tool-json ≈ **+0.016s**.

## Comparability

Prior Design 2 PASS: `stage2-20260723-008`. Operator `042` benchmark reference:
`stage2-20260723-007`. Smoke re-evidence: `stage2-20260724-001`.

## Status

Run ID **consumed**. Design 2 harness route benchmark (`3.6.0` / r5) re-evidenced
by `stage2-20260724-002`. Do not reuse `008` or `stage2-20260724-002`.
