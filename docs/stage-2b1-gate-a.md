# Stage 2B-1 Gate A: Inference-Path Acceptance

## Current Decision

`GATE_A_STOPPED`. The deterministic implementation passed its automated test
baseline, but final architecture review found five blocking safety gaps: hard
wall-clock deadline enforcement, strict SSE framing, cleanup lock/shutdown
rechecks, durable POST-attempt evidence, and exact lifecycle reconciliation
during resealing. Gate B and all live work remain blocked until focused
remediation and a clean independent review. See
`docs/handoffs/2026-07-15-stage-2b1-cursor-continuation-prompt.md`.

All five findings now have code-and-test remediation in-tree, pending an
independent architecture review. This does not change the decision:
`GATE_A_STOPPED` remains in effect and Gate B and live work remain blocked.

Stage 2B-1 is a bounded inference-path acceptance check, not a benchmark. It exercises two fixed workloads once per route as four excluded warm-ups and four measured requests: eight total serial inference requests and eight HTTP POSTs. The cohort is intentionally too small for stable medians, throughput claims, quality rankings, or route-performance conclusions.

## Fixed Contract

| Item | Required value |
|---|---|
| Manifest schema | `3.2.0` |
| Mode | `operator_inference_probe` |
| Comparison class | `optiq-operator-route-smoke` |
| Runtime profile | `vibethinker-3b-optiq-4bit` revision `3` |
| Suite | `optiq-route-smoke-v1` revision `1` |
| Direct route | `http://127.0.0.1:8080/v1` |
| Routed route | `http://127.0.0.1:1337/v1` |
| Route order | one counterbalanced repetition |
| Request timeout | 120 seconds |
| Memory stop level | `warning` |
| Maximum in-flight requests | `1` |
| Total request limit | `8` |
| Coordinator model | `gemma-4-12b-it-qat-jang_4m` |
| Plugin | `local.jrazz.model-runtime-evaluation-harness` `0.3.0` |

The only acceptance decisions are `inference_path_acceptance` and `behavioral_contract_acceptance`. Evidence remains sanitized: it excludes prompts, generated output, request payloads, headers, credentials, and process details.

## Gate Boundaries

Gate A is implementation and deterministic verification only. It does not create a live manifest, select a usable run ID, install a Coordinator prompt, start OptiQ, reconnect a provider, send a request, or grant inference authority.

Gate B is a later read-only readiness check while Jason owns the existing foreground OptiQ launcher and reconnects the existing provider without editing it. Only after Gate B passes may Jason explicitly authorize one exact unused run ID in the current session. That authorization permits one short-lived manifest for that ID only.

The accepted Stage 2A revision-3 baseline remains the rollback and service-ownership reference. Its `GET`-only observation procedure and plugin `0.3.0` stay intact. Stage 2B-2 is a separate future proposal and is not authorized by Stage 2B-1.

## Operator Sequence After Separate Authorization

1. Keep OptiQ Lab closed.
2. Start the existing foreground `bin/lmre-stage2-operator-serve` launcher and leave it open.
3. Reconnect the existing `Optiq` provider without editing it.
4. Ask Codex to run read-only Gate B.
5. Authorize one exact unused ID only after Gate B reports ready.
6. Install the Stage 2B-1 Coordinator prompt and use a fresh Coordinator chat.
7. Approve `inventory`, `preflight`, and `run_scenario` individually with one-time approval.
8. Run `bin/lmre-stage2-wait <run-id>` and wait for the operator shutdown result.
9. Stop the foreground OptiQ launcher with `Control-C`.
10. Return to the Coordinator for one `status` call and one `cleanup` call.
11. Return the sanitized Coordinator report to Codex for manager review.

No tool may be approved persistently. The Coordinator has no ambient filesystem, Sandbox, Search, MCP, memory, provider-editing, service-lifecycle, or subagent authority.
