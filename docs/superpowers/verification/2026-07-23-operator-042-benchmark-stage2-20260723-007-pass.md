# Operator OptiQ 0.4.2 Benchmark — stage2-20260723-007 PASS

**Date:** 2026-07-23  
**Decision:** sealed **PASS**

| Field | Value |
|---|---|
| Run ID | `stage2-20260723-007` |
| Schema / mode | `3.4.0` / `operator_route_benchmark` |
| Comparison | `gemma-optiq-042-operator-route-benchmark` |
| Profile | `gemma-4-12b-optiq-4bit` revision `3` |
| Suite | `gemma-optiq-042-operator-route-benchmark-v1` revision `1` |
| Launcher | `bin/lmre-stage2-operator-serve-gemma-042` |
| POSTs | 72/72 (12 excluded warmups; 60 measured) |
| `inference_path_acceptance` | PASS |
| `behavioral_contract_acceptance` | PASS |
| `checksum_validation` | PASS |
| `service_lifecycle_actions` | 0 |
| `model_load_attempts` | 0 |

## Observational route overhead (pin-only)

| Workload | routed − direct median total |
|---|---|
| short-chat | ≈ **−0.062 s** |
| structured-tool-json | ≈ **−0.044 s** |

Decode TPS suppressed (`SUPPRESSED_AMBIGUOUS_TOKEN_ACCOUNTING`); TTFT qualified.

## Stability

Same OptiQ PID (`11449`) stayed healthy through warm-up, all 72 POSTs, and
`awaiting_review`. Prerequisite smoke: `stage2-20260723-006` PASS.
