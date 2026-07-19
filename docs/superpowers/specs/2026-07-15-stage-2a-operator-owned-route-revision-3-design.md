# Stage 2A Operator-Owned Route Revision 3 Design

## Decision

Stage 2A revision `3` separates the already-proven OptiQ process lifecycle from Osaurus remote-provider activation.

The operator starts one fixed OptiQ API service in a foreground terminal and remains its sole lifecycle owner. The operator then explicitly retries or reconnects the existing `Optiq` provider in Osaurus. The harness verifies the service and route but never starts, stops, restarts, signals, configures, or mutates either system.

This design was approved by Jason on 2026-07-15. Implementation does not authorize a live run, manifest, model load, inference request, benchmark, provider mutation, or plugin replacement.

## Problem Being Corrected

Revision `2` started OptiQ after Osaurus had already marked the provider disconnected. Osaurus did not automatically reconnect the provider, so the routed catalog never exposed the remote route. Revision `2` also treated the raw upstream model ID as the routed API identity, while connected Osaurus remote-provider IDs use a provider prefix.

The two stopped Stage 2A runs remain valid evidence that the harness-owned lifecycle was safe. Revision `3` does not attempt a third lifecycle proof.

## Fixed Contract

- runtime profile: `vibethinker-3b-optiq-4bit` revision `3`
- runtime: `mlx-optiq 0.3.3`
- operator command: the existing pinned `optiq serve` executable and argument array
- direct route: `http://127.0.0.1:8080/v1`
- routed route: `http://127.0.0.1:1337/v1`
- direct model evidence: the pinned upstream repository ID or immutable snapshot path
- required routed ID: `optiq/mlx-community/VibeThinker-3B-OptiQ-4bit`
- rejected routed IDs: `vibethinker-3b-optiq-4bit` and unprefixed `mlx-community/VibeThinker-3B-OptiQ-4bit`
- service ownership: `operator`
- provider activation: `operator_reconnect_required`
- network methods: GET only
- harness service lifecycle actions: `0`
- model-load, inference, and HTTP POST attempts: `0`

## Operator Setup

The repository provides one no-argument foreground launcher, `bin/lmre-stage2-operator-serve`. It executes only the fixed canonical command and accepts no user-selected model, path, endpoint, port, credential, or argument.

Jason must:

1. keep OptiQ Lab closed
2. start `bin/lmre-stage2-operator-serve` in a dedicated terminal and leave it running
3. use Osaurus's existing provider retry or reconnect control for `Optiq` without editing provider settings
4. ask Codex to run the no-manifest Gate B checker
5. authorize a new unused run ID only after Gate B passes

The launcher remains foreground so `Ctrl+C` is the unambiguous operator stop action. It does not daemonize, write a PID file, or claim ownership on behalf of the harness.

## Gate B

The no-manifest Gate B check is read-only and must pass all of these together:

- runtime, package, artifact, and provider configuration identity
- exactly one visible OptiQ `serve` process and no OptiQ Lab process
- process command ends with the complete canonical executable and argument array
- the exact recorded process is the listener for `127.0.0.1:8080`
- direct health reports `status: ok`; optional model diagnostics must agree with the pinned identity and optional activity counters must be zero. The minimal endpoint does not prove residency, so the exact command, immutable snapshot, and hashes bind the startup-loaded model; Stage 2A itself issues no model-load or inference request
- direct inventory contains an approved pinned artifact identity
- routed Osaurus inventory contains exactly one required provider-prefixed ID
- resource policy allows the exact Gemma Coordinator state
- provider headers remain empty
- plugin `0.3.0` version and checksum match
- all prohibited-attempt and harness lifecycle counters remain zero

Gate B never starts or stops OptiQ and never changes Osaurus. It rechecks direct safe health and process identity after inventory. A missing, drifting, or ambiguous process, health state, route, or identity stops authorization.

## Run Lifecycle

The successful revision-3 sequence is:

```text
queued
-> preflight
-> resource_gate
-> ready
-> running
-> service_ready
-> endpoint_identity
-> artifact_validation
-> awaiting_review
-> operator stops service
-> cleaned
```

Gate B proves the direct service and routed identity before manifest authorization. Once a manifest is authorized, preflight captures a sanitized operator-service identity containing PID, parent PID, process group, start token, command hash, and listener association; validates direct health, runtime, artifact, provider, and resource state; and returns `ready`. The worker then independently revalidates the exact routed identity.

The worker reloads that identity and verifies the same process and listener before inventory. A revision-3-only transport permits only direct `GET /health`, direct `GET /v1/models`, routed `GET /health`, and routed `GET /v1/models`; it accepts no body or caller-supplied header. The worker persists a sanitized request journal containing method, endpoint label, response status, and payload digest. It then persists sanitized model evidence with route status `PENDING`, accepts only one exact routed match, strictly rechecks direct health, provider metadata, resource state, process identity, and listener association, and exits at `awaiting_review` without signaling the service.

## Shutdown and Cleanup

After the host waiter reports `awaiting_review`, Jason stops the foreground OptiQ terminal with `Ctrl+C`. Only then may the Coordinator call `cleanup`.

Cleanup succeeds only when:

- the recorded operator process identity is no longer present
- no OptiQ Lab or `serve` process remains
- two consecutive free-port observations confirm port `8080` is free
- routed identity evidence is `PASS`
- zero prohibited attempts are recorded
- all revision-3 artifacts are complete and checksummed

If the recorded process is still running, a replacement process exists, or port `8080` remains occupied, cleanup stops with manager review and does not signal anything. The run remains recoverable at `awaiting_review` so Jason can stop the service and retry `cleanup` with a new one-time approval. Cleanup revalidates the exact routed ID before sealing, atomically replaces checksums after the `cleaned` transition, and releases the active-run lock only after final validation. A sealing failure after the transition remains recoverable through another approved cleanup call.

If preflight fails before a usable operator identity is captured, the runner records bounded partial recovery evidence and transitions to `failed`. Manager cleanup seals that partial record and releases the lock without invoking operator-service cleanup.

## Cancellation and Failure

Cancellation applies only to the harness worker. It never stops the operator service. After cancellation or worker failure, Jason stops the foreground service manually and then requests cleanup of the partial evidence. Partial cleanup must verify the recorded identity is absent, no OptiQ process remains, and two free-port observations pass before releasing the run lock or transitioning to `cleaned`.

The Coordinator prompt must not call `cancel` after the run is already terminal. It calls `status` once when needed and uses cleanup only after the operator shutdown condition is satisfied.

## Evidence Contract

Revision `3` replaces lifecycle-owned artifacts with operator-observation artifacts:

- `operator-service-identity.json`
- `service-events.jsonl` containing observation and shutdown-verification events only
- `request-evidence.jsonl` containing sanitized GET request metadata and payload digests
- no `process-ownership.json`
- no captured OptiQ service log
- no `redacted-log.md`

The final summary records:

- `service_ownership: operator`
- `provider_activation: operator_reconnect_required`
- `provider_route_observed: PASS`
- `operator_service_identity: PASS`
- `operator_shutdown_verified: PASS`
- `service_lifecycle_actions: 0`
- `model_load_attempts: 0`
- `inference_request_attempts: 0`
- `http_post_attempts: 0`

Raw endpoint payloads, credentials, provider secrets, and model output are never stored.

The evidence may prove that the provider-prefixed route was observed. It must not claim that a particular UI reconnect action occurred because that human action is not machine-verifiable.

## Waiter Contract

For revision `3`, the host waiter reports `OPERATOR_SHUTDOWN_REQUIRED` rather than the generic Coordinator-ready message when the worker reaches `awaiting_review`, `cancelled`, or `failed` with an observed operator service. The message states that the foreground service may still be running and instructs Jason to stop it before Coordinator cleanup. It exposes no command line, provider payload, or credential.

## Plugin Boundary

Plugin `0.3.0` remains unchanged. Revision `3` uses the same six tools and the same Stage 2 run-ID pattern. No plugin rebuild or reinstall is needed unless tests prove the native contract changed.

## Rollback

Revision-1 and revision-2 profiles, manifests, tests, documentation, and run artifacts remain historical evidence. A revision-3 rollback means removing the new active profile and restoring the blocked documentation state; it never means reusing either consumed run ID.

## Acceptance Criteria

Implementation is ready for a future Gate B review only when:

- new tests first fail against revision `2` behavior and then pass
- all existing Stage 0 and Stage 1 tests still pass
- revision `3` performs no live endpoint contact during automated tests
- static scans find no Stage 2 POST, inference, model-load, provider mutation, or process-signaling path
- deterministic tests cover process replacement, listener replacement, pre/post-inventory health drift, cancellation, shutdown-pending cleanup, route-evidence tampering, preflight failure recovery, and finalization failure recovery
- the Coordinator prompt and runbook describe the same operator sequence
- no live manifest or run ID exists
- vault validation passes after durable documentation reconciliation
