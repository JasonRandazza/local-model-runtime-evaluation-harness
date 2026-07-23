# Architecture

## Boundaries

The Python harness owns manifest validation, static Stage 0 policy, passive inventory, persisted lifecycle state, cancellation, cleanup, and checksummed artifacts. Runtime adapters exist only as disabled interfaces during Stage 0.

The native Swift plugin is the typed macOS bridge. It exposes six tools and invokes one fixed executable with an operation and validated run ID as separate arguments. It does not invoke a shell or use Osaurus host callbacks.

The Benchmark Coordinator runs with Sandbox enabled. It calls the reviewed native tools through the normal Osaurus tool loop. The host runner validates the plugin-owned artifact bundle during `cleanup` and returns only a bounded evidence summary; the Coordinator does not require host filesystem access or an `/output` Sandbox mount.

```text
Benchmark Coordinator
  -> one reviewed native tool
  -> fixed Stage 0 wrapper
  -> manifest and policy validation
  -> simulated persisted lifecycle
  -> host artifact validation
  -> bounded cleanup evidence summary
  -> manager review
```

## Source Precedence

1. Repository source and tests define executable behavior.
2. The Deep Wiki records durable architecture, decisions, and reviewed outcomes.
3. Generated artifacts provide run evidence but do not become durable conclusions automatically.

## Deferred Generic Runtime Adapters

The broad Osaurus, OpenAI-compatible, and mlx-optiq adapters still raise `LiveExecutionDisabled`. Stage-specific capabilities use narrow profile-bound components rather than enabling those generic interfaces.

## Stage 1 Route-Overhead Lane

Stage 1 preserves the same six Coordinator tools and fixed native bridge. A reviewed profile and manifest select one oMLX-owned model and two loopback routes. The direct route retrieves a dedicated credential from macOS Keychain; the routed Osaurus request never receives that credential.

The host runner validates Osaurus `/health`, system memory pressure, route identity, suite revision, and the absence of a competing run. It starts only a fixed harness-owned background worker so status and cancellation remain available during the 60-request cohort. External services remain operator-owned.

```text
Benchmark Coordinator
  -> six typed native tools
  -> fixed host runner
  -> approved profile + manifest + suite
  -> fixed background measurement worker
  -> direct oMLX and Osaurus-routed requests, serially
  -> raw evidence, summaries, checksums
  -> manager review
```

The generic deferred adapters remain disabled; Stage 1 transport is implemented as a narrow loopback-only component rather than enabling those broad interfaces.

## Stage 2A Operator-Owned Route Lane

Stage 2A revision `3` retains the same six Coordinator tools but changes the service boundary. The operator starts the fixed foreground `bin/lmre-stage2-operator-serve` launcher, leaves it running, and explicitly retries or reconnects the existing Osaurus `Optiq` provider. The harness observes both systems and never starts, stops, signals, restarts, or configures either one.

The runtime profile pins `mlx-optiq 0.3.3`, the immutable VibeThinker OptiQ snapshot, four artifact hashes, the API-only command, and the loopback routes. The installed MLX-LM generation worker calls `load_default()` at startup, while `/health` returns only `status: ok`; the health response alone cannot prove residency or model identity. Revision `3` binds the model through the exact command, snapshot, and hashes, requires health availability before and after GET-only inventory, rejects conflicting optional model diagnostics, and requires optional activity counters to remain zero.

```text
Benchmark Coordinator
  -> six typed native tools
  -> fixed Stage 2A worker
  -> operator-owned foreground OptiQ service
  -> explicit operator Osaurus Optiq reconnect
  -> GET-only direct and routed health/model inventory
  -> awaiting_review while service remains running
  -> operator Ctrl+C and two-observation shutdown proof
  -> checksummed evidence + manager review
```

Only `GET /health` and `GET /v1/models` are permitted on `127.0.0.1:8080` and `127.0.0.1:1337`. Route acceptance is exact and case-sensitive: `optiq/mlx-community/VibeThinker-3B-OptiQ-4bit`. The Osaurus-local ID and unprefixed upstream ID are rejected. Sanitized model evidence retains only `id`, `owned_by`, and `root`; ownership metadata is diagnostic.

The worker persists inventory with route status `PENDING` before identity validation, rewrites only that decision to `PASS` after an exact match, and reaches `awaiting_review` without signaling the operator service. Gate B repeats direct safe-health validation after inventory. Cleanup requires the recorded process to be absent, two consecutive observations that port `8080` is free, and the persisted routed ID to equal the pinned profile. Failed and cancelled cleanup follows the same manual shutdown requirement. Checksums are replaced atomically, a post-transition seal failure is retryable, and the active-run lock is released only after final validation. Every summary reports `service_lifecycle_actions: 0`.

### Revision 2 Historical Boundary

Runs `stage2-20260714-001`, `stage2-20260715-001`, and `stage2-20260715-002` remain consumed evidence. The first two proved safe harness-owned lifecycle behavior and exposed the missing automatic Osaurus provider reconnect. The third exercised operator-owned revision `3` and exposed a Gate B/worker mismatch between Osaurus `status: healthy` and the worker's former `status: ok` requirement. The shared routed-health predicate now covers both healthy forms and is enforced before authorization and during execution. No consumed ID is reusable; a new Gate B pass and explicit authorization remain required.

Run `stage2-20260715-003` is the accepted operator-owned revision-3 baseline. The exact OptiQ route was observed through Osaurus, the worker reached `awaiting_review`, the operator shut down the foreground service, and cleanup validated the sealed GET-only evidence. Stage 2A is complete. Stage 2B inference and benchmarking remain outside this architecture boundary.

Stage 2B POST, inference, generation, warm-up, evaluation, conversion, quantization, and benchmark authority remain absent. Plugin `0.3.0` is unchanged.

## Stage 2B-1 Inference-Path Acceptance Lane

Stage 2B-1 retains the accepted Stage 2A service boundary and the same six typed plugin tools. It adds a narrow, separately gated `3.2.0` manifest contract for one counterbalanced smoke cohort: two fixed workloads are sent once per route as four excluded warm-ups and four measured observations. The resulting eight serial requests and eight POSTs establish only whether the direct and routed inference paths satisfy the fixed HTTP, streaming, and response contracts. They do not produce stable medians or support performance, throughput, quality, or route-cost conclusions.

```text
Benchmark Coordinator
  -> one approval-gated native tool at a time
  -> fixed Stage 2B worker
  -> operator-owned foreground OptiQ service
  -> direct and routed serialized inference smoke requests
  -> host waiter
  -> operator Control-C shutdown
  -> one status read and one cleanup call
  -> sanitized acceptance evidence + manager review
```

The contract fixes `vibethinker-3b-optiq-4bit` revision `3`, `optiq-route-smoke-v1` revision `1`, direct `http://127.0.0.1:8080/v1`, routed `http://127.0.0.1:1337/v1`, a 120-second timeout, warning-level memory stop, one in-flight request, and an eight-request total limit. Final evidence reports independent `inference_path_acceptance` and `behavioral_contract_acceptance` decisions while omitting prompts, responses, payloads, headers, credentials, and process details.

Gate A is non-authorizing. It cannot create a usable run ID or live manifest, install the prompt, operate the service or provider, or invoke inference. Gate B, Jason's exact-ID approval, the one-ID manifest, manual service shutdown, cleanup, and manager review are separate. Stage 2A revision `3` remains the rollback baseline; plugin `0.3.0` is unchanged and Stage 2B-2 remains separately gated.

## Stage 2B-2 Route Benchmark Lane

Stage 2B-2 retains the accepted Stage 2B-1 service boundary and the same six typed plugin tools. It adds a separately gated `3.4.0` manifest contract for one counterbalanced benchmark cohort: two fixed workloads run across direct and routed paths as twelve excluded warm-ups and sixty measured observations. The resulting seventy-two serial requests and seventy-two POSTs support sealed medians and direct↔routed deltas for this Gemma OptiQ pin only. They do not support preference winners, RAG quality, matrix cells, or cross-runtime rankings.

```text
Benchmark Coordinator
  -> one approval-gated native tool at a time
  -> fixed Stage 2B benchmark worker
  -> operator-owned foreground OptiQ service
  -> direct and routed serialized benchmark requests (72 POSTs)
  -> host waiter
  -> operator Control-C shutdown
  -> one status read and one cleanup call
  -> sanitized acceptance + route-overhead evidence + manager review
```

The contract fixes `gemma-4-12b-optiq-4bit` revision `2`, `gemma-optiq-route-benchmark-v1` revision `1`, direct `http://127.0.0.1:8080/v1`, routed `http://127.0.0.1:1337/v1`, a 120-second timeout, warning-level memory stop, one in-flight request, and a seventy-two-request total limit. Final evidence reports `inference_path_acceptance`, `behavioral_contract_acceptance`, and observational `route_overhead_summary` while omitting prompts, responses, payloads, headers, credentials, and process details.

Gate A decision is `GATE_A_PASSED`. Cohort `stage2-20260721-006` sealed **PASS** (72/72 POSTs; both acceptance axes; checksums; manager-reviewed). That ID is consumed. New Stage 2B-2 live authorization still requires Gate B, Jason's exact unused-ID approval, a short-lived `3.4.0` manifest, manual shutdown, cleanup, and manager review. Stage 2B-1 PASS on `stage2-20260721-005` remains the smoke prerequisite; see `docs/stage-2b2-gate-a.md`.

## Stage 2 Harness-Unattended Lane (Slice 1c)

Package 1 / Slice 1c adds a parallel **harness-owned** Stage 2 smoke lane. The harness starts and stops OptiQ via Slice 1a `LifecycleController`, records honest `service_lifecycle_actions > 0`, and cleans up without operator `Ctrl+C`. Operator-owned schemas `3.3.0` / `3.4.0` and sealed `005` / `006` remain rollback.

```text
Benchmark Coordinator
  -> one approval-gated native tool at a time
  -> fixed Stage 2 harness smoke worker
  -> harness-owned OptiQ via LifecycleController
  -> read-only Osaurus provider identity + routed inventory verify
  -> direct and routed serialized inference smoke requests (8 POSTs)
  -> harness ensure_stopped (port 8080 free twice)
  -> sanitized acceptance evidence + manager review
```

The contract fixes schema `3.5.0`, mode `harness_inference_probe`, comparison class `gemma-optiq-042-harness-route-smoke`, profile `gemma-4-12b-optiq-4bit` revision `4`, suite `gemma-optiq-042-harness-route-smoke-v1` revision `1`, `service_ownership: harness`, and `provider_activation: verify_routed_id_only`. Provider *edit* remains forbidden; the harness verifies the exact routed inventory ID after OptiQ is up. If reconnect is required and no safe non-editing API exists, at most one operator reconnect tap is documented — see `docs/superpowers/notes/2026-07-22-slice-1c-provider-reconnect-note.md`.

Gate A is `GATE_A_PASSED`. Live Gate B–D for harness-unattended **smoke** sealed
**PASS** on `stage2-20260723-003` (2026-07-23). A harness-unattended **72-POST
benchmark** design is accepted (`3.6.0`; Gate A not yet implemented) — see
`docs/superpowers/specs/2026-07-23-harness-unattended-route-benchmark-design.md`
and `docs/stage-2-harness-unattended-gate-a.md`.

## Shared Harness Lifecycle (Slice 1a)

Package 1 / Slice 1a Gate A is landed in `harness_lifecycle.py`: a shared controller that starts and stops exactly one pinned OptiQ (`8080`), oMLX (`8100`), or Osaurus (`1337`) server under a 20% RAM floor, with fail-closed ownership rules, optional ready wait, and fake-only tests. Stage 2 operator-owned lanes above remain unchanged. Slice 1b Gate A + live pin-confirm are closed (`mlx-optiq 0.4.2` on disk; evidence `docs/superpowers/verification/2026-07-23-slice-1b-optiq-042-pin-confirm.md`). Slice 1c Gate A + live harness-unattended smoke are closed (`stage2-20260723-003` PASS) — see `docs/stage-2-harness-unattended-gate-a.md` and `docs/superpowers/notes/2026-07-22-slice-1c-provider-reconnect-note.md`. Package 2 Gate A–D and follow-ons **D2** / **D3** / **D4** are sealed live PASSED for this window — see `docs/package-2-omlx-thinking-gate-d.md`, `docs/package-2-omlx-thinking-d2.md`, `docs/package-2-omlx-thinking-d3.md`, `docs/package-2-omlx-thinking-d4.md`. Design and queue history: `docs/superpowers/specs/2026-07-21-stack-review-gate-a-queue-design.md`.
