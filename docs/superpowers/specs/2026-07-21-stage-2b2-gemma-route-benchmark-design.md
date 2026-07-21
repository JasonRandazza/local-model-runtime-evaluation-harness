# Stage 2B-2 Gemma OptiQ Route Benchmark Design

**Status:** Approved in conversation by Jason on 2026-07-21. This document
authorizes implementation planning only. It does **not** authorize Gate B, a
manifest, a usable run ID, live inference, provider changes, plugin
rebuild/reinstall, or Stage 2B-3+.

**Prerequisite evidence:** Stage 2B-1 Gemma OptiQ cohort `stage2-20260721-005`
sealed PASS (schema `3.3.0`, profile `gemma-4-12b-optiq-4bit` revision `2`).

## Goal

Prove direct-versus-Osaurus-routed latency on the same pinned Gemma OptiQ
artifact with a cohort large enough for sealed medians and pair deltas.

Stage 2B-2 is a **route benchmark**, not path smoke. It does not authorize
preference, RAG, matrix, or cross-runtime rankings.

## Authorizing contract

| Field | Value |
|---|---|
| Schema | `3.4.0` |
| Mode | `operator_route_benchmark` |
| Comparison class | `gemma-optiq-operator-route-benchmark` |
| Runtime profile | `gemma-4-12b-optiq-4bit` revision `2` |
| Suite | `gemma-optiq-route-benchmark-v1` revision `1` |
| Total POSTs | `72` serial |
| Warmups | `12` excluded (3 per workload×route cell) |
| Measured | `60` included (15 per workload×route cell) |
| Workloads | `short-chat`, `structured-tool-json` (same prompts/contracts as Stage 2B-1) |
| Direct route | `http://127.0.0.1:8080/v1` |
| Routed route | `http://127.0.0.1:1337/v1` |
| Routed model ID | exact inventory string from profile revision `2` |
| Plugin | `0.3.0` unchanged (six tools) |
| OptiQ ownership | operator foreground launcher only |
| Limits | `request_timeout_seconds: 120`, `memory_stop_level: warning`, `maximum_in_flight_requests: 1`, `total_request_limit: 72` |

Schema `3.3.0` / `operator_inference_probe` remains the historical Stage 2B-1
authorizing shape and rollback for smoke. It must not start a Stage 2B-2 run.

## Non-goals

- Deriving Stage 2B-2 statistics from the eight-POST Stage 2B-1 cohort
- Preference winners, RAG quality, or family matrix cells
- Harness starting, stopping, signaling, or configuring OptiQ or Osaurus
- Plugin rebuild, reinstall, or tool-surface change
- Concurrent requests, remote endpoints, credentials, or provider mutation
- Reusing consumed Stage 2 run IDs (including `001`–`005`)
- Committing weight trees or `omlx-roots` artifacts
- Raising `request_timeout_seconds` in v1 (separate reviewed change if needed)

## Architecture

### Operator sequence

```text
Jason starts bin/lmre-stage2-operator-serve-gemma
-> Jason reconnects existing Optiq provider (no edits)
-> Host agent runs read-only Gate B
-> Jason authorizes one exact unused Stage 2B-2 run ID
-> Short-lived 3.4.0 manifest for that ID only
-> Coordinator inventory / preflight / run_scenario
-> Background _stage2-worker executes the fixed 72-request schedule
-> Host waiter reports OPERATOR_SHUTDOWN_REQUIRED
-> Jason Ctrl+C OptiQ; port 8080 free
-> Coordinator status / cleanup
-> Manager review of sealed bundle
```

### Engine dispatch

`build_stage_two_engine` routes by exact `(schema_version, mode)`:

- `(3.1.0, …)` Stage 2A observation — unchanged
- `(3.3.0, operator_inference_probe)` → `StageTwoInferenceEngine` (2B-1)
- `(3.4.0, operator_route_benchmark)` → new `StageTwoBenchmarkEngine`

### Reuse

- Loopback transport with SSE timeout and chunked-decode fixes
- Post-attempt journal, operator identity checks, resource gates
- Lifecycle, artifact bundle, checksums, waiters
- Plugin `0.3.0` and the six typed operations
- Profile revision `2` identity / hash / argv allowlists
- Gate B static identity checks against the Gemma pin

### New dedicated pieces

- Immutable 72-request benchmark suite loader and schedule
- `StageTwoBenchmarkEngine` (or equivalent) with benchmark summary reporting
- Manifest/policy/schema branch for `3.4.0`
- Stage 2B-2 Coordinator prompt and operator prep (separate from 2B-1)
- Sealed route-overhead summary artifacts

## Schedule

Immutable in code and suite fixtures. Workload order: `short-chat`, then
`structured-tool-json`. Within each workload:

1. Three warmup pairs, counterbalanced direct/routed (excluded)
2. Fifteen measured pairs, counterbalanced direct/routed (included)

Fail closed on a 73rd POST attempt. No concurrency.

## Metrics and acceptance

### Per-request observations

Same qualification spirit as Stage 2B-1:

- Always: HTTP status, stream validity, finish reason, contract status, output hash, total seconds
- TTFT only when incremental content delivery qualifies
- Decode rate only when incremental delivery and exact visible-token accounting both qualify
- Otherwise mark token/decode fields incomparable (non-blocking for path acceptance when contracts pass)

Raw prompts and generated text never enter artifacts, logs, summaries, or exceptions.

### Summary decisions

- `inference_path_acceptance`: PASS only when all 72 requests complete under infrastructure, route, memory, lifecycle, shutdown, and evidence rules
- `behavioral_contract_acceptance`: PASS only when all 60 measured requests satisfy their response contracts
- `route_overhead_summary`: per `(workload_id, route)` medians and direct↔routed deltas for qualified fields — observational for this pin only; not a cross-model ranking

Path PASS with behavioral FAIL remains possible and must be manager-reviewed before treating the suite as useful for timing claims.

## Evidence

Retain applicable Stage 2 identity/lifecycle/memory/request-evidence artifacts and add at least:

- `benchmark-suite.json`
- `benchmark-summary.json`
- `direct-observations.json`
- `routed-observations.json`
- `raw-runs.jsonl` (workload IDs, sequence metadata, qualified measurements, contract results, output hashes — no content)

Cleanup requires manual operator shutdown proof, evidence reconciliation, final lifecycle inclusion, checksum validation, and lock release only after the sealed bundle validates.

## Gates

None implies the next:

1. **Gate A** — deterministic implementation (code, tests, schemas, suite, prompt, runbook); no live actions
2. **Gate B** — live read-only readiness (launcher, provider, identities, memory); no POST
3. **Gate C** — Jason authorizes one unused run ID + short-lived `3.4.0` manifest
4. **Gate D** — 72 POSTs, manual shutdown, cleanup, manager review

This design authorizes planning and Gate A implementation only.

## Tests and verification (Gate A)

- Exact schema/policy/suite/schedule/route/limit invariants
- 12 warmups excluded, 60 measured retained, counterbalancing preserved
- Hard stop at 72 POSTs; no concurrency
- Memory/identity/route drift fail-closed between requests
- Transport/SSE/cancel/timeout behavior preserved
- Content and credentials never leak into artifacts or errors
- Stage 0/1/2A/2B-1 regression suites remain green
- Plugin `0.3.0` contract tests remain green without rebuild
- Static scans: no live 2B-2 manifest/usable ID in-tree from Gate A; no Stage 2B-3 authority

## Rollback

- **Before live:** disable or revert the `3.4.0` authorization path; leave Stage 2B-1 `3.3.0` and Stage 2A revision 3 untouched
- **After a bad live attempt:** consume the run ID; keep sealed/partial evidence; never reuse the ID
- **Program abandonment:** remove Stage 2B-2 authorization materials; accepted 2B-1 PASS evidence and plugin `0.3.0` remain

## References

- `docs/superpowers/specs/2026-07-20-stage-2b1-gemma-retarget-design.md` — roadmap annex defining 2B-2 as route benchmark
- `docs/superpowers/specs/2026-07-15-stage-2b1-optiq-inference-acceptance-design.md` — historical Gate E 72-request sketch
- `docs/stage-2b1-gate-a.md` / `AGENTS.md` — Stage 2B-1 PASS on `stage2-20260721-005`
- `config/runtime-profiles/gemma-4-12b-optiq-4bit-r2.json` — authorizing pin
- `suites/gemma-optiq-route-smoke-v1.json` — workload prompt/contract source for the benchmark suite
