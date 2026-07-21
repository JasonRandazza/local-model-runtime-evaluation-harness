# Stage 2B-1 Gate A: Inference-Path Acceptance

## Current Decision

`GATE_A_FINDINGS_CLOSED` (Jason, 2026-07-20). The five architecture-review
findings have in-tree code-and-test remediation on `main`, and Jason accepted
Gate A as complete for moving to Slice 2 (Gemma schema `3.3.0` retarget).

**Slice 2 / Gate B status (2026-07-21):** Gemma profile revision `2` (path-based
`:no-think` route) is authorizing. Gate B reported
`READY_FOR_MANIFEST_AUTHORIZATION`. Jason authorized unused run
`stage2-20260721-001` with short-lived manifest
`manifests/stage-2-optiq-inference-001.json` (expires end of 2026-07-21 Eastern).
Live eight-POST cohort still requires Coordinator prompt install and one-time
tool approvals. Stage 2B-2 remains unauthorized. See
`docs/superpowers/specs/2026-07-20-stage-2b1-gemma-retarget-design.md`.

Historical note: the prior `GATE_A_STOPPED` decision and the five findings are
documented in `docs/handoffs/2026-07-15-stage-2b1-cursor-continuation-prompt.md`
and `docs/superpowers/verification/2026-07-20-stage-2b1-gate-a-findings.md`.

Stage 2B-1 is a bounded inference-path acceptance check, not a benchmark. It exercises two fixed workloads once per route as four excluded warm-ups and four measured requests: eight total serial inference requests and eight HTTP POSTs. The cohort is intentionally too small for stable medians, throughput claims, quality rankings, or route-performance conclusions.

## Fixed Contract

Historical Gate A / VibeThinker authorizing shape (parseable evidence only;
not for new live authorization):

| Item | Historical value |
|---|---|
| Manifest schema | `3.2.0` |
| Mode | `operator_inference_probe` |
| Comparison class | `optiq-operator-route-smoke` |
| Runtime profile | `vibethinker-3b-optiq-4bit` revision `3` |
| Suite | `optiq-route-smoke-v1` revision `1` |
| Operator launcher | `bin/lmre-stage2-operator-serve` (Stage 2A rollback) |

Live authorizing shape after Slice 2 review + separate Gate B authorization:

| Item | Required value |
|---|---|
| Manifest schema | `3.3.0` |
| Mode | `operator_inference_probe` |
| Comparison class | `gemma-optiq-operator-route-smoke` |
| Runtime profile | `gemma-4-12b-optiq-4bit` revision `2` |
| Suite | `gemma-optiq-route-smoke-v1` revision `1` |
| Operator launcher | `bin/lmre-stage2-operator-serve-gemma` |
| Non-authorizing template | `manifests/stage-2-optiq-inference-smoke.json.template` |
| Direct route | `http://127.0.0.1:8080/v1` |
| Routed route | `http://127.0.0.1:1337/v1` |
| Route order | one counterbalanced repetition |
| Request timeout | 120 seconds |
| Memory stop level | `warning` |
| Maximum in-flight requests | `1` |
| Total request limit | `8` |
| Coordinator model | `gemma-4-12b-it-qat-jang_4m` |
| Plugin | `local.jrazz.model-runtime-evaluation-harness` `0.3.0` |
| Expected routed ID | `optiq//Users/jrazz/.cache/huggingface/hub/mlx-community/gemma-4-12B-it-qat-OptiQ-4bit:no-think` (exact inventory match) |

The only acceptance decisions are `inference_path_acceptance` and `behavioral_contract_acceptance`. Evidence remains sanitized: it excludes prompts, generated output, request payloads, headers, credentials, and process details.

## Gate Boundaries

Gate A is implementation and deterministic verification only. It does not create a live manifest, select a usable run ID, install a Coordinator prompt, start OptiQ, reconnect a provider, send a request, or grant inference authority.

Gate B is a later read-only readiness check while Jason owns the Gemma foreground OptiQ launcher and reconnects the existing provider without editing it. Only after Gate B passes may Jason explicitly authorize one exact unused run ID in the current session. That authorization permits one short-lived manifest for that ID only. Do not run Gate B against live services until retarget review and Jason’s current-session authorization.

The accepted Stage 2A revision-3 baseline remains the rollback and service-ownership reference (`bin/lmre-stage2-operator-serve` + VibeThinker). Its `GET`-only observation procedure and plugin `0.3.0` stay intact. Stage 2B-2 is a separate future proposal and is not authorized by Stage 2B-1.

## Operator Sequence After Separate Authorization

1. Keep OptiQ Lab closed.
2. Start the Stage 2B-1 foreground launcher `bin/lmre-stage2-operator-serve-gemma` and leave it open. (Leave `bin/lmre-stage2-operator-serve` untouched as Stage 2A historical rollback.)
3. Reconnect the existing `Optiq` provider without editing it.
4. Ask Codex to run read-only Gate B (`bin/lmre-stage2-gate-b-check`), which pins `gemma-4-12b-optiq-4bit` revision `2` and the exact path-based `:no-think` routed ID.
5. Authorize one exact unused ID only after Gate B reports ready.
6. Materialize a short-lived manifest from `manifests/stage-2-optiq-inference-smoke.json.template` for that ID only (placeholder approval fields are never live authority).
7. Install the Stage 2B-1 Coordinator prompt and use a fresh Coordinator chat.
8. Approve `inventory`, `preflight`, and `run_scenario` individually with one-time approval.
9. Run `bin/lmre-stage2-wait <run-id>` and wait for the operator shutdown result.
10. Stop the foreground OptiQ launcher with `Control-C`.
11. Return to the Coordinator for one `status` call and one `cleanup` call.
12. Return the sanitized Coordinator report to Codex for manager review.

No tool may be approved persistently. The Coordinator has no ambient filesystem, Sandbox, Search, MCP, memory, provider-editing, service-lifecycle, or subagent authority.
