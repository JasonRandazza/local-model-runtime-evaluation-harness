# Stage 2B-2 Gate A: Gemma OptiQ Route Benchmark

## Current Decision

`GATE_A_PASSED` (Jason, 2026-07-21). Gate A implementation and review are closed:
schema `3.4.0`, the 72-request benchmark suite, measurement module,
`StageTwoBenchmarkEngine`, factory dispatch, policy branch, artifact sealing,
package template pin, and non-authorizing docs/prompt draft are in tree with
deterministic tests green (100 focused Python tests; Swift plugin `0.3.0` 4/4;
no live 2B-2 manifest). This is **not** live-ready. Gate B, Gate C (manifest
authorization), Gate D (72 POSTs), Coordinator prompt installation, and manager
review remain separately gated and still require Jason's current-session
authorization.

**Prerequisite evidence:** Stage 2B-1 cohort `stage2-20260721-005` sealed **PASS**
(schema `3.3.0`, profile `gemma-4-12b-optiq-4bit` revision `2`, suite
`gemma-optiq-route-smoke-v1` revision `1`). That smoke evidence remains accepted;
Stage 2B-2 does not derive benchmark statistics from it.

Stage 2B-2 is a bounded **route benchmark**, not path smoke. It runs seventy-two
serial POSTs (twelve excluded warm-ups, sixty measured observations) to support
sealed medians and direct↔routed deltas for this pin only. It does not authorize
preference winners, RAG quality, matrix cells, or cross-runtime rankings.

Design authority: `docs/superpowers/specs/2026-07-21-stage-2b2-gemma-route-benchmark-design.md`.

## Fixed Contract (authorizing shape after separate Gate C authorization)

| Item | Required value |
|---|---|
| Manifest schema | `3.4.0` |
| Mode | `operator_route_benchmark` |
| Comparison class | `gemma-optiq-operator-route-benchmark` |
| Runtime profile | `gemma-4-12b-optiq-4bit` revision `2` |
| Suite | `gemma-optiq-route-benchmark-v1` revision `1` |
| Operator launcher | `bin/lmre-stage2-operator-serve-gemma` |
| Non-authorizing template | `manifests/stage-2-optiq-route-benchmark.json.template` |
| Direct route | `http://127.0.0.1:8080/v1` |
| Routed route | `http://127.0.0.1:1337/v1` |
| Route order | counterbalanced within each workload |
| Workloads | `short-chat`, `structured-tool-json` |
| Warm-ups | `12` excluded (3 per workload×route cell) |
| Measured | `60` included (15 per workload×route cell) |
| Request timeout | 120 seconds |
| Memory stop level | `warning` |
| Maximum in-flight requests | `1` |
| Total request limit | `72` |
| Coordinator model | `gemma-4-12b-it-qat-jang_4m` |
| Plugin | `local.jrazz.model-runtime-evaluation-harness` `0.3.0` |
| Expected routed ID | `optiq//Users/jrazz/.cache/huggingface/hub/mlx-community/gemma-4-12B-it-qat-OptiQ-4bit:no-think` (exact inventory match) |

Schema `3.3.0` / `operator_inference_probe` remains the Stage 2B-1 rollback smoke
shape. It must not start a Stage 2B-2 run.

Acceptance decisions: `inference_path_acceptance`, `behavioral_contract_acceptance`,
and observational `route_overhead_summary` (medians and direct↔routed deltas for
qualified fields on this pin only). Evidence remains sanitized: no prompts,
generated output, request payloads, headers, credentials, or process details.

## Gate Boundaries

| Gate | Scope | Status |
|---|---|---|
| **A** | Code, tests, schemas, suite, docs, non-installed prompt draft | **Passed** (review closed) |
| **B** | Live read-only readiness (launcher, provider, identities, memory); no POST | Ready to authorize separately |
| **C** | Jason authorizes one unused run ID + short-lived `3.4.0` manifest | **Authorized** — `stage2-20260721-006` through EOD Eastern |
| **D** | 72 POSTs, manual shutdown, cleanup, manager review | **Complete** — `stage2-20260721-006` sealed PASS |

Gate A is implementation and deterministic verification only. It does not create a
live manifest, select a usable run ID, install a Coordinator prompt into Osaurus,
start OptiQ, reconnect a provider, send a request, or grant inference authority.

Gate B reuses read-only checks against profile revision `2` while Jason owns the
Gemma foreground OptiQ launcher and reconnects the existing provider without editing
it. Only after Gate B passes may Jason explicitly authorize one exact unused run ID
in the current session. That authorization permits one short-lived manifest for
that ID only. Gate A review is closed. Do not run Gate B against live services until Jason
gives current-session authorization for Gate B.

The accepted Stage 2A revision-3 baseline remains rollback (`bin/lmre-stage2-operator-serve`
+ VibeThinker). Stage 2B-1 PASS on `stage2-20260721-005` remains smoke rollback
(`3.3.0` + `bin/lmre-stage2-operator-serve-gemma`). Plugin `0.3.0` and its six
one-time-approval tools are unchanged; no rebuild or reinstall is authorized from
Gate A.

## Operator Sequence After Separate Authorization

1. Keep OptiQ Lab closed.
2. Start the Stage 2B-2 foreground launcher `bin/lmre-stage2-operator-serve-gemma` and leave it open.
3. Reconnect the existing `Optiq` provider without editing it.
4. Ask the host agent to run read-only Gate B (`bin/lmre-stage2-gate-b-check`), which pins `gemma-4-12b-optiq-4bit` revision `2` and the exact path-based `:no-think` routed ID.
5. Authorize one exact unused ID only after Gate B reports ready.
6. Have the host agent materialize a short-lived manifest from `manifests/stage-2-optiq-route-benchmark.json.template` for that ID only (`approved_by` remains Jason; placeholder approval fields are never live authority).
7. Install the Stage 2B-2 Coordinator prompt (from reviewed vault copy; repo draft at `docs/stage-2b2-coordinator-prompt.md` is **not installed**) and use a fresh Coordinator chat.
8. Approve `inventory`, `preflight`, and `run_scenario` individually with one-time approval.
9. Run `bin/lmre-stage2-wait <run-id>` and wait for the operator shutdown result.
10. Stop the foreground OptiQ launcher with `Control-C`.
11. Return to the Coordinator for one `status` call and one `cleanup` call.
12. Return the sanitized Coordinator report to the host agent for manager review.

No tool may be approved persistently. The Coordinator has no ambient filesystem,
Sandbox, Search, MCP, memory, provider-editing, service-lifecycle, or subagent
authority.

## Operator prep checklist

Day-to-day manual steps (exact launcher, Osaurus reconnect, Coordinator copy-paste
prompts, waiter, shutdown, cleanup) live in `docs/stage-2b2-operator-prep.md`.
Vault mirror is optional and not required for Gate A.

## Gate A static scans (expected empty / PASS)

Run from the repository root:

```bash
rg -n 'stage2-2026' manifests/ | rg -v 'template|smoke|lifecycle|operator-route-00|optiq-inference-00' || true
rg -n 'operator_route_benchmark|3\.4\.0' src/local_model_runtime_evaluation --glob '*.py'
ls manifests/stage-2-optiq-route-benchmark*.json 2>/dev/null || echo 'no live 2B-2 manifest'
```

Expected:

- First command: historical consumed manifests only (or empty after filters); no new live 2B-2 ID.
- Second command: Gate A symbols present in policy, manifest, factory, benchmark engine, suite, and measurement modules.
- Third command: `no live 2B-2 manifest` (template `.json.template` only).

Optional full Gate A test sweep:

```bash
cd /Users/jrazz/Dev/active/local-model-runtime-evaluation-harness
PYTHONPATH=src /opt/homebrew/bin/python3 -m unittest \
  tests.test_stage_two_benchmark_suite \
  tests.test_stage_two_benchmark_measurement \
  tests.test_stage_two_benchmark_engine \
  tests.test_manifest \
  tests.test_policy \
  tests.test_stage_two_inference_engine \
  tests.test_stage_two_gate_a_e2e \
  tests.test_transport \
  tests.test_package -q
```
