# Repository Agent Rules

The repository defines current executable reality. Consult the Deep Wiki for durable architecture and history, then verify repository state before editing.

## Stage 0 Boundary

- Stage 0 is dry-run only and must never load a model or issue inference requests.
- Do not contact Osaurus, oMLX, mlx-optiq, or remote endpoints from Stage 0 code.
- Do not add arbitrary shell execution, user-selected executable paths, provider modification, credentials, memory, subagents, schedules, or vault writes.
- Raw artifacts belong under the configured Osaurus output root and must not be committed.
- The reviewed native plugin exposes exactly six typed operations with per-call approval.
- Do not install or replace the plugin without explicit current-session approval.
- Do not stage, commit, push, add remotes, or run live benchmarks unless explicitly requested.

## Stage 1 Boundary

- Stage 1 source may contact only profile-approved loopback routes after an active, approved, unexpired Stage 1 manifest exists.
- Non-live tests use fakes and must not contact Osaurus, oMLX, Keychain, or a real model.
- The direct oMLX credential must never be sent to Osaurus or serialized.
- The harness may start and stop only its fixed background measurement worker, never Osaurus, oMLX, a provider, or a model lifecycle.
- Keep the six plugin tools and approval policy unchanged. Do not install plugin `0.2.0` without explicit current-session approval.
- Stop at Gate A until operator preparation and live inference are separately approved.

Run the Python and Swift test suites after relevant changes. Preserve the legacy benchmark reference unchanged.

## Stage 2A Boundary

- Revision `2` and both previous Stage 2 run IDs remain consumed historical evidence. Never overwrite, resume, or reauthorize them.
- Revision `3` is observation-only. The operator owns the foreground OptiQ service through `bin/lmre-stage2-operator-serve`, explicitly retries or reconnects the existing Osaurus `Optiq` provider, and stops the launcher with `Ctrl+C` after the worker reaches `awaiting_review`.
- The harness never starts, stops, signals, restarts, or configures OptiQ or Osaurus. It records `service_lifecycle_actions: 0`.
- Stage 2A may use only the pinned `mlx-optiq 0.3.3` executable, snapshot, hashes, approved argument array, and exact loopback routes in runtime profile revision `3`.
- OptiQ Lab must remain closed. Exactly one canonical foreground `optiq serve` process must own port `8080`; process identity, command, listener, provider metadata, runtime/hash identity, route identity, and the exact idle Coordinator resource state are fail-closed checks.
- Direct `/health` must report `status: ok`; if optional model diagnostics appear, they must agree with the pinned model, and optional activity counters must be zero. The minimal response does not prove residency, so exact command, snapshot, and artifact hashes provide model identity. `model_load_attempts: 0` counts harness requests, not the operator-owned startup load.
- Network activity is limited to `GET /health` and `GET /v1/models` on the exact approved loopback endpoints. The required routed ID is exactly `optiq/mlx-community/VibeThinker-3B-OptiQ-4bit`; local and unprefixed alternatives are rejected.
- Endpoint inventory may retain only `id`, `owned_by`, and `root`; ownership metadata is diagnostic and never substitutes for exact ID acceptance. Persist route status `PENDING` before identity validation, then rewrite only that decision to `PASS` after exact validation.
- Cleanup is allowed only after manual operator shutdown. It verifies the recorded process is absent and port `8080` free twice. Failed and cancelled cleanup paths require the same manual shutdown proof before cleanup can finalize.
- Never release the active-run lock merely because lifecycle state says `cleaned`. Exact route evidence, final checksums, and bundle validation must pass. A post-transition sealing failure remains retryable; failed preflight uses bounded partial cleanup without invoking operator-service cleanup.
- Plugin `0.3.0` is the active unchanged reviewed contract. Rebuild, reinstall, replacement, or rollback still requires explicit current-session approval.
- This implementation does not authorize a live manifest or run. Gate B and explicit authorization of a new unused run ID remain required. Stage 2B POST, inference, and benchmark authority does not exist.

## Stage 2B-1 Boundary

- Current decision: `GATE_A_FINDINGS_CLOSED` (Jason, 2026-07-20). Gate A
  remediation for the five findings is accepted. Slice 2 Gemma retarget is in
  tree as schema `3.3.0` with authorizing profile revision `2`. On 2026-07-21
  Gate B reported `READY_FOR_MANIFEST_AUTHORIZATION` and Jason authorized
  unused run `stage2-20260721-001` (short-lived manifest; expires end of day
  Eastern). Cohorts `001`, `002`, and `003` all cleaned as `STOPPED` on the
  first direct POST (`stream_failed` / transport failure). Root cause confirmed
  after `003`: harness SSE client applied a 1s socket timeout that permanently
  poisons `http.client` after the first idle gap (OptiQ keepalives often arrive
  later). Transport fix is in tree (`256b78e`). Jason authorized unused run
  `stage2-20260721-004` (manifest `manifests/stage-2-optiq-inference-004.json`;
  expires end of day Eastern). Live eight-POST attempt still requires operator
  OptiQ up + warm-up, Gate B `READY_FOR_MANIFEST_AUTHORIZATION`, Coordinator
  prompt, and one-time tool approvals. Stage 2B-2 remains unauthorized.
- Do not create additional run IDs or manifests without Jason's separate
  current-session authorization. Do not operate OptiQ/Osaurus lifecycle from
  the harness. Do not install a Coordinator prompt or issue inference without
  the operator sequence in `docs/stage-2b1-gate-a.md`.
- Stage 2B-1 is one bounded inference-path acceptance cohort, not a benchmark. It permits exactly eight serial inference requests and eight HTTP POSTs only after separately completed Gate B, Jason's explicit current-session authorization of one exact unused ID, and a short-lived manifest for that exact ID.
- Historical authorizing shape (evidence only): schema `3.2.0`, comparison class `optiq-operator-route-smoke`, profile `vibethinker-3b-optiq-4bit` revision `3`, suite `optiq-route-smoke-v1` revision `1`, launcher `bin/lmre-stage2-operator-serve`. New live authorization must use schema `3.3.0` with comparison class `gemma-optiq-operator-route-smoke`, profile `gemma-4-12b-optiq-4bit` revision `2`, suite `gemma-optiq-route-smoke-v1` revision `1`, and launcher `bin/lmre-stage2-operator-serve-gemma`. The required routed ID is the exact inventory string `optiq//Users/jrazz/.cache/huggingface/hub/mlx-community/gemma-4-12B-it-qat-OptiQ-4bit:no-think`. Revision `1` remains historical evidence only.
- The only permitted routes are `http://127.0.0.1:8080/v1` and `http://127.0.0.1:1337/v1`. Limits are 120 seconds per request, warning-level memory stop, one in-flight request, and eight total requests.
- Gate A, templates, package tests, and documentation are non-live. They must not create a usable ID or manifest, install a prompt, start or stop OptiQ, reconnect or edit a provider, or issue an endpoint request.
- Jason remains the sole owner of the foreground OptiQ service lifecycle and existing-provider reconnect. The harness never starts, stops, signals, restarts, configures, loads, or unloads OptiQ or Osaurus.
- Preserve the accepted Stage 2A revision-3 baseline as rollback (`bin/lmre-stage2-operator-serve`). Plugin `0.3.0` and its six one-time-approval tools remain unchanged; do not rebuild or reinstall it. Stage 2B-2 remains separately gated.
