# Stage 2B-1 OptiQ Inference Acceptance Design

**Status:** Approved in conversation by Jason on 2026-07-15. This document authorizes implementation planning only. It does not authorize a manifest, live request, model load, provider change, or Stage 2B-1 run.

## Goal

Prove that the accepted operator-owned OptiQ service can execute a small, controlled direct-versus-Osaurus-routed inference cohort while preserving route identity, memory safety, cancellation, manual shutdown, and checksummed evidence.

Stage 2B-1 is an inference-path acceptance test. It is not a statistically meaningful benchmark. A full 72-request Stage 2B-2 cohort requires a separate proposal and authorization after Stage 2B-1 manager acceptance.

## Accepted Foundation

Stage 2A run `stage2-20260715-003` is the immutable accepted baseline. Stage 2B-1 reuses:

- operator-owned `bin/lmre-stage2-operator-serve`
- `mlx-optiq 0.3.3` and runtime profile `vibethinker-3b-optiq-4bit` revision `3`
- the pinned VibeThinker snapshot and artifact hashes
- direct route `http://127.0.0.1:8080/v1`
- routed route `http://127.0.0.1:1337/v1`
- exact routed ID `optiq/mlx-community/VibeThinker-3B-OptiQ-4bit`
- exact Gemma Benchmark Coordinator residency allowance
- manual provider reconnect and manual OptiQ shutdown
- native plugin `0.3.0` and the existing six typed operations

The accepted Stage 2A engine, manifests, bundles, and policy behavior remain unchanged.

## Non-Goals

Stage 2B-1 does not:

- produce stable medians, p95 values, throughput conclusions, or runtime rankings
- compare mlx-optiq with oMLX, Osaurus-native serving, JANG, or another artifact
- use `osaurus bench`, `optiq benchmark`, or an evaluation framework
- use `/v1/responses`, `/v1/messages`, tools, structured-output API parameters, or variant suffixes
- switch models, start OptiQ Lab, mutate providers, forward credentials, or contact a remote endpoint
- enable concurrent requests, unattended execution, scheduled execution, or automatic Deep Wiki writes
- authorize Stage 2B-2

## Architecture

The operator sequence remains:

```text
Jason starts the fixed OptiQ foreground launcher
-> Jason reconnects the existing Optiq provider
-> Codex runs read-only Gate B
-> Jason authorizes one exact Stage 2B-1 run ID
-> Benchmark Coordinator performs inventory and preflight
-> background worker executes the fixed eight-request cohort
-> waiter reports OPERATOR_SHUTDOWN_REQUIRED
-> Jason stops OptiQ with Control-C
-> Coordinator cleanup validates shutdown and seals evidence
-> Codex performs manager review
```

The harness never starts, stops, signals, restarts, or configures OptiQ or Osaurus.

## Manifest And Policy Contract

Stage 2B-1 adds one active manifest shape:

- schema version: `3.2.0`
- stage: `2`
- mode: `operator_inference_probe`
- comparison class: `optiq-operator-route-smoke`
- runtime profile: `vibethinker-3b-optiq-4bit` revision `3`
- suite: `optiq-route-smoke-v1` revision `1`
- measured repetitions: `1`
- route order: `counterbalanced`
- request timeout: `120` seconds
- memory stop level: `warning`
- maximum in-flight requests: `1`
- total request limit: `8`
- operations: exactly `inventory`, `preflight`, `run-scenario`, `status`, `cancel`, and `cleanup`
- output root: `/Users/jrazz/.osaurus/container/output/benchmark-runs`

The Stage 2B-1 policy accepts only that exact shape. Historical schemas `3.0.0` and `3.1.0` remain parseable for evidence review but retain their existing authorization behavior.

## Fixed Smoke Suite

The suite is deterministic, streaming, temperature `0`, and contains two workloads:

1. `short-chat`
   - prompt: `In two sentences, explain why reproducible measurements matter.`
   - maximum output: `128` tokens
   - response contract: non-empty text
2. `structured-tool-json`
   - prompt: `Return exactly this JSON object with no markdown or extra text: {"name":"status","arguments":{"run_id":"stage2b-test","include_details":false}}`
   - maximum output: `512` tokens
   - response contract: exact JSON object

The prompt called `structured-tool-json` is a plain text-to-JSON response check. No `tools` field or tool invocation is sent.

The exact request schedule is:

1. short-chat direct warm-up
2. short-chat routed warm-up
3. short-chat direct measured
4. short-chat routed measured
5. structured-tool-json routed warm-up
6. structured-tool-json direct warm-up
7. structured-tool-json routed measured
8. structured-tool-json direct measured

This yields four excluded warm-ups, four measured requests, and two measured direct/routed pairs. Route-first order is balanced across workloads. All requests are serial.

## Request Authority

The worker may send only:

- `GET /health`
- `GET /v1/models`
- `POST /v1/chat/completions`

All requests must use the two fixed loopback base URLs. The direct request model label is `mlx-community/VibeThinker-3B-OptiQ-4bit`; the routed label is the exact provider-prefixed ID. Both routes use the canonical base model without a variant suffix.

Direct and routed requests carry no credential or authorization header. Each POST contains only the fixed model label, one fixed user message, temperature `0`, fixed maximum tokens, `stream: true`, and `stream_options.include_usage: true`.

## Preflight And Per-Request Gates

Preflight must pass every Stage 2A revision-3 identity and safety check before POST authority exists. It additionally validates the exact smoke suite, Stage 2B-1 manifest, request limits, and inference transport allowlist.

Immediately before every POST, the worker must verify:

- cancellation has not been requested
- the recorded operator process, command, listener, and start identity still match
- direct health is safe and non-conflicting
- Osaurus health is accepted by the shared routed-health predicate
- direct and routed inventories still contain the exact approved identities
- no unexpected Osaurus-native model is resident beyond the exact Gemma Coordinator allowance
- macOS memory pressure is `normal`, meaning at least 20 percent free under the existing probe
- the active-run lock belongs to the current run and no competing harness run exists

Immediately after every POST, the worker records another memory sample and rechecks process identity. Warning or critical memory after a request fails infrastructure acceptance and prevents the next request.

## Failure Semantics

Infrastructure failures stop before another POST:

- route, process, listener, runtime, artifact, provider, or model identity drift
- memory pressure at warning or critical
- HTTP failure, malformed SSE, empty stream, timeout, or cancellation
- request count, route order, model label, endpoint, or method outside the fixed contract
- unexpected credential or authorization metadata
- evidence write or lifecycle failure

Cancellation is cooperative and checked before every request and while consuming SSE events. A request has a hard 120-second transport timeout. The harness does not kill the operator-owned service; failed and cancelled runs still require Jason's manual shutdown before cleanup.

Behavioral failures do not stop the remaining safe cohort:

- empty text
- invalid JSON
- JSON contract mismatch
- different output hashes between direct and routed requests
- token-capped completion
- buffered delivery
- missing or ambiguous token-accounting fields

These conditions remain evidence. They may fail behavioral acceptance or suppress affected metrics without being mislabeled as infrastructure failure.

## Measurement Qualification

Raw generated content exists only in memory long enough to validate its response contract and compute a SHA-256 digest. It is never written to disk.

Each request records:

- workload, route, warm-up or measured status, and deterministic sequence
- HTTP and SSE contract status
- total response time
- TTFT only when incremental content delivery qualifies it
- completion, reasoning, and visible-output token fields when supplied and valid
- decode rate only when incremental delivery and exact visible-token accounting both qualify
- finish reason, response-contract status, output hash, and memory phase

Stage 2B-1 reports observations and measured pair deltas. It must not label single observations as stable medians or make performance conclusions.

## Acceptance Decisions

The summary contains two independent decisions:

- `inference_path_acceptance`: PASS only when all eight requests complete under the infrastructure, route, memory, lifecycle, shutdown, and evidence contract.
- `behavioral_contract_acceptance`: PASS only when all four measured requests satisfy their workload response contracts.

Stage 2B-1 may therefore report infrastructure PASS with behavioral FAIL. Only infrastructure PASS permits proposing Stage 2B-2. Behavioral failure becomes model capability evidence and must be reviewed before deciding whether the full suite remains useful.

## Evidence Contract

Stage 2B-1 retains all applicable Stage 2A artifacts and adds:

- `inference-suite.json`
- `raw-runs.jsonl`
- `smoke-summary.json`
- `direct-observations.json`
- `routed-observations.json`

`raw-runs.jsonl` contains no prompt text or generated content. It stores only fixed workload IDs, sequence metadata, qualified measurements, response-contract results, and output hashes.

No draft benchmark report is generated because Stage 2B-1 is not a benchmark cohort. Cleanup requires manual shutdown, exact evidence reconciliation, final lifecycle inclusion, checksum validation, and active-lock release only after the sealed bundle validates.

## Component Boundaries

- Keep `StageTwoEngine` as the accepted GET-only Stage 2A engine.
- Add a separate `StageTwoInferenceEngine` for Stage 2B-1.
- Keep `StageTwoReadOnlyTransport` unchanged.
- Add a separate fixed inference transport that permits only the approved loopback GET and chat-completions paths and never accepts credentials.
- Add a dedicated smoke-suite loader and schedule rather than weakening the six-workload Stage 1 suite contract.
- Route active Stage 2 manifests to the correct engine by exact mode and schema.
- Keep plugin `0.3.0` unchanged because its six typed operations and host executable path do not change.
- Replace the Coordinator system prompt with a separately reviewed Stage 2B-1 prompt before live use.

## Deterministic Verification

Gate A implementation must use test-driven development and prove:

- exact schema, policy, suite, schedule, routes, labels, methods, and request count
- four warm-ups excluded and four measurements retained
- direct-first and routed-first counterbalancing
- no concurrency and no ninth request
- memory checked before and after every request
- warning memory prevents the next POST
- route and process drift prevent the next POST
- timeout and cancellation stop safely
- behavioral failures finish the safe cohort and remain separate from infrastructure status
- invalid streaming or transport behavior fails immediately
- raw content and credentials never enter artifacts, logs, summaries, or exceptions
- failed, cancelled, and accepted runs all require manual operator shutdown
- cleanup verifies shutdown, route evidence, lifecycle, and checksums
- Stage 0, Stage 1, and Stage 2A regression suites remain green
- native plugin contract tests remain green without a version change

Gate A creates no live manifest or usable run ID and performs no endpoint request, model load, inference, provider mutation, service lifecycle action, or plugin installation.

## Approval Gates

1. **Gate A - deterministic implementation:** code, tests, schemas, fixed suite, prompt, and runbook; no live actions.
2. **Gate B - live read-only readiness:** operator launcher running, provider reconnected, exact identities and memory normal; no POST.
3. **Gate C - exact run authorization:** one new unused short-lived Stage 2B-1 manifest after Gate B passes.
4. **Gate D - Stage 2B-1 acceptance:** eight requests, manual shutdown, cleanup, manager artifact review.
5. **Gate E - future Stage 2B-2 proposal:** full 12-warm-up and 60-measurement cohort only after Gate D infrastructure PASS.

No gate authorizes the next one implicitly.

## Rollback

Before live authorization, rollback removes only Stage 2B-1 source, schema branch, fixed suite, tests, prompt, and runbook. Stage 2A revision `3`, plugin `0.3.0`, accepted artifacts, provider settings, and launcher remain untouched.

After any live attempt, preserve the checksummed or partial bundle and permanently consume its run ID. Correct the source under a new review; never rewrite accepted evidence or reuse an ID.
