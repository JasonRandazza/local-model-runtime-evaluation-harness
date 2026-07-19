# Stage 2A Gate A

## Status

Revision `3` documentation and implementation reconcile the Stage 2A boundary around an operator-owned foreground service and explicit Osaurus provider reconnect. The implementation itself was not a live authorization. The later revision-3 run `stage2-20260715-002` is now also consumed historical evidence; a fresh Gate B and explicit authorization of a new unused run ID remain required.

## Implemented Authority

- strict `stage2-YYYYMMDD-NNN` lifecycle manifests only
- strict runtime-profile revision `3` for `mlx-optiq 0.3.3`
- immutable VibeThinker OptiQ snapshot and four artifact hashes
- exact no-argument foreground launcher `bin/lmre-stage2-operator-serve`
- operator-owned service and explicit retry/reconnect of the existing Osaurus `Optiq` provider
- observation of PID, parent PID, process group, start token, command hash, and listener association
- direct health requiring `status: ok`, no model diagnostic that conflicts with the pinned command/artifact identity, and zero optional activity counters
- GET-only `/health` and `/v1/models` discovery
- exact case-sensitive routed identity `optiq/mlx-community/VibeThinker-3B-OptiQ-4bit`
- explicit rejection of the Osaurus-local and unprefixed upstream IDs
- sanitized model descriptors limited to `id`, `owned_by`, and `root`
- endpoint inventory persisted with route status `PENDING` before acceptance and rewritten to `PASS` only after exact validation
- direct safe health rechecked after Gate B inventory before manifest authorization
- consumed-run refusal whenever the canonical output directory already exists
- cooperative worker cancellation without service signaling
- manual operator shutdown with recorded-process absence and two free-port observations before cleanup
- exact routed identity revalidated during final cleanup, atomic checksum replacement, and lock release only after successful final validation
- failed-preflight partial recovery that never invokes operator-service cleanup
- operator-observation lifecycle evidence, memory samples, endpoint inventory, and checksums
- `service_lifecycle_actions: 0` in preflight, run, and cleanup summaries
- exactly six native plugin tools with per-call approval

## Explicitly Absent

- no Stage 2B manifest or measured cohort
- no manifest or run ID was created by the Gate A implementation; all three later historical Stage 2 IDs remain consumed
- no POST, chat, responses, messages, warm-up, or generation method
- no provider mutation by the harness; operator reconnect remains a manual action
- no model download or remote network path
- no OptiQ Lab lifecycle control
- no agent-supplied endpoint, model, path, command, credential, PID, or argument

## Historical Gate C Finding

Run `stage2-20260714-001` proved the owned service lifecycle but stopped because revision `1` expected an `optiq/` model-ID prefix that Osaurus does not expose. The run was safely cleaned with zero harness model-load requests, inference requests, or HTTP POST requests and is permanently consumed; the operator service's startup load is a separate lifecycle fact.

Revision `2` replaced that hypothesis with the full upstream repository ID, but the live route still failed because Osaurus had not reconnected its provider. The local ID and unprefixed upstream ID remain rejection cases. Revision `3` accepts only `optiq/mlx-community/VibeThinker-3B-OptiQ-4bit` after the operator explicitly retries or reconnects `Optiq`.

Run `stage2-20260715-001` then proved the owned service lifecycle again and preserved endpoint inventory. The direct endpoint exposed the pinned artifact, but Osaurus exposed no active `Optiq` provider route because the provider had failed connection while OptiQ was absent and was not automatically reconnected after service start. Manager cleanup released port `8080`; harness model-load, inference, and HTTP POST request counts remained zero.

Run `stage2-20260715-002` exercised the operator-owned revision-3 path after the hidden routed model was exposed. Gate B and preflight passed, but the worker stopped before route inventory because it accepted `status: ok` while the live Osaurus `/health` contract reports `status: healthy`. Cleanup verified manual operator shutdown, sealed the partial evidence, and preserved zero harness model-load, inference, HTTP POST, and service-lifecycle actions. The worker now accepts both healthy forms, and Gate B applies the same shared predicate before authorization. The run remains permanently consumed.

Run `stage2-20260715-003` then completed the corrected revision-3 path. It discovered exactly `optiq/mlx-community/VibeThinker-3B-OptiQ-4bit`, reached `awaiting_review`, required manual operator shutdown, and cleaned with checksum validation passing. Manager validation confirmed the complete bundle and five GET-only observations. Harness model-load, inference, HTTP POST, and service-lifecycle action counts remained zero. This run is the accepted Stage 2A baseline and is permanently consumed.

The operator-owned revision-3 sequence does not claim that a UI reconnect action is machine-verifiable. It requires the resulting exact provider-prefixed route to be observable before a future Gate B authorization.

## Activation Boundary

Plugin `0.3.0` remains unchanged and is the active reviewed contract. The preserved `0.2.0` package remains the rollback baseline. Implementation of revision `3` does not authorize a live run; Gate B, explicit new-run authorization, and the coordinated operator sequence remain required.

The Gate B checker reports runtime profile identity and rejects historical output directories as `run_id_consumed`. That protection remains valid, but a revision-2 readiness pass no longer authorizes manifest preparation.

The operator starts the launcher, explicitly retries or reconnects the existing provider, and stops it with `Ctrl+C` only after the worker reaches `awaiting_review`. The worker never controls that lifecycle.

## Verification

- Non-live tests cover the revision-3 profile, exact routed ID, strict health contract, GET-only transport, operator observation, awaiting-review handoff, manual-shutdown cleanup, failed/cancelled cleanup, and consumed IDs.
- Runtime profile, schema, fixture, launcher, and template JSON parse statically; plugin source and version remain unchanged.
- The expanded Python suite passed all 123 tests, including the live Osaurus `status: healthy` regression, Gate B/worker predicate parity, localhost transport, injected failure paths, and interrupted-checksum recovery.
- The unchanged native plugin passed all 4 contract tests.
- Sixteen configuration, schema, manifest, suite, template, and plugin JSON documents parsed successfully.
- The revision-3 implementation review itself created no live manifest, run ID, endpoint contact, model load, inference request, POST request, provider mutation, or service lifecycle action.
- Stage 2A is accepted. Any repeat requires a fresh Gate B and separate authorization; Stage 2B requires its own design and approval.

## Rollback

Plugin `0.3.0` remains active and unchanged. If its existing contract must be rolled back, reinstall the already-reviewed `0.2.0` package only with current-session approval. Preserve all three consumed Stage 2 run bundles as diagnostic baselines; do not modify or reuse them. Stage 0 and Stage 1 behavior remains covered by the shared regression suite.
