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

## Stage 2A Boundary (operator-owned lane)

Applies to runtime profile revision `3` / schema `3.1.0` operator-route observation only. The harness-unattended lane (schema `3.5.0`, profile revision `4`) is governed separately below.

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

## Stage 2B-1 Boundary (operator-owned lane)

Applies to schemas `3.2.0` / `3.3.0` and profile revision `2` (and historical revision `1` evidence). The harness-unattended lane (`3.5.0` / profile revision `4`) is governed separately below.

- Current decision: `GATE_A_FINDINGS_CLOSED` (Jason, 2026-07-20). Gate A
  remediation for the five findings is accepted. Slice 2 Gemma retarget is in
  tree as schema `3.3.0` with authorizing profile revision `2`. On 2026-07-21
  Gate B reported `READY_FOR_MANIFEST_AUTHORIZATION` and Jason authorized
  unused run `stage2-20260721-001` (short-lived manifest; expires end of day
  Eastern). Cohorts `001`, `002`, and `003` all cleaned as `STOPPED` on the
  first direct POST (`stream_failed` / transport failure). Root cause confirmed
  after `003`: harness SSE client applied a 1s socket timeout that permanently
  poisons `http.client` after the first idle gap (OptiQ keepalives often arrive
  later). Direct-route timeout fix is in tree (`256b78e`). Jason authorized
  unused run `stage2-20260721-004`; direct request 1 completed, routed request 2
  failed with `unsupported_sse` (Osaurus HTTP chunked encoding vs raw `response.fp`).
  That cohort cleaned as sealed `STOPPED` (`checksum_validation: PASS`). Chunked-SSE
  decode fix is in tree (`ce107b2`). Jason authorized unused run
  `stage2-20260721-005`; that cohort cleaned as sealed **PASS** (8/8 POSTs;
  inference_path_acceptance and behavioral_contract_acceptance `PASS`;
  checksum_validation `PASS`). Manager-reviewed. Stage 2B-1 Gemma OptiQ
  inference-path acceptance for schema `3.3.0` / profile revision `2` is
  evidenced by `005`. Stage 2B-2 Gate A is `GATE_A_PASSED`; live 2B-2 Gate B–D
  remain separately gated.
- Do not create additional run IDs or manifests without Jason's separate
  current-session authorization. For **this operator-owned lane**, do not operate OptiQ/Osaurus lifecycle from
  the harness. Do not install a Coordinator prompt or issue inference without
  the operator sequence in `docs/stage-2b1-gate-a.md`.
- Stage 2B-1 is one bounded inference-path acceptance cohort, not a benchmark. It permits exactly eight serial inference requests and eight HTTP POSTs only after separately completed Gate B, Jason's explicit current-session authorization of one exact unused ID, and a short-lived manifest for that exact ID.
- Historical authorizing shape (evidence only): schema `3.2.0`, comparison class `optiq-operator-route-smoke`, profile `vibethinker-3b-optiq-4bit` revision `3`, suite `optiq-route-smoke-v1` revision `1`, launcher `bin/lmre-stage2-operator-serve`. New live authorization must use schema `3.3.0` with comparison class `gemma-optiq-operator-route-smoke`, profile `gemma-4-12b-optiq-4bit` revision `2`, suite `gemma-optiq-route-smoke-v1` revision `1`, and launcher `bin/lmre-stage2-operator-serve-gemma`. The required routed ID is the exact inventory string `optiq//Users/jrazz/.cache/huggingface/hub/mlx-community/gemma-4-12B-it-qat-OptiQ-4bit:no-think`. Revision `1` remains historical evidence only.
- The only permitted routes are `http://127.0.0.1:8080/v1` and `http://127.0.0.1:1337/v1`. Limits are 120 seconds per request, warning-level memory stop, one in-flight request, and eight total requests.
- Gate A, templates, package tests, and documentation are non-live. They must not create a usable ID or manifest, install a prompt, start or stop OptiQ, reconnect or edit a provider, or issue an endpoint request.
- For **this operator-owned lane**, Jason remains the sole owner of the foreground OptiQ service lifecycle and existing-provider reconnect. The harness never starts, stops, signals, restarts, configures, loads, or unloads OptiQ or Osaurus on schemas `3.3.0` / profile revision `2`.
- Preserve the accepted Stage 2A revision-3 baseline as rollback (`bin/lmre-stage2-operator-serve`). Plugin `0.3.0` and its six one-time-approval tools remain unchanged; do not rebuild or reinstall it. Stage 2B-2 remains separately gated.

## Stage 2B-2 Boundary (operator-owned lane)

Applies to schema `3.4.0` and profile revision `2`. The harness-unattended lane (`3.5.0` / profile revision `4`) is governed separately below.

- Current decision: `GATE_A_PASSED` (Jason, 2026-07-21). Gate A implementation and review are closed. Gate B reported `READY_FOR_MANIFEST_AUTHORIZATION` this session. Jason authorized unused run `stage2-20260721-006` (short-lived manifest `manifests/stage-2-optiq-route-benchmark-006.json`). Cohort `stage2-20260721-006` cleaned as sealed **PASS** (72/72 POSTs; inference_path_acceptance and behavioral_contract_acceptance `PASS`; checksum_validation `PASS`; manager-reviewed). Schema `3.4.0`, mode `operator_route_benchmark`, comparison class `gemma-optiq-operator-route-benchmark`, suite `gemma-optiq-route-benchmark-v1` revision `1`, profile `gemma-4-12b-optiq-4bit` revision `2`. Run ID `006` is consumed — do not reuse. Do not authorize a new Stage 2B-2 run ID without Jason's separate current-session authorization.
- Prerequisite evidence: Stage 2B-1 cohort `stage2-20260721-005` sealed **PASS** (schema `3.3.0` / profile revision `2`). Do not derive Stage 2B-2 statistics from the eight-POST smoke cohort. Do not reuse consumed run IDs (`001`–`005` or any prior Stage 2 run).
- Do not create additional run IDs or live manifests without Jason's separate current-session authorization. For **this operator-owned lane**, do not operate OptiQ/Osaurus lifecycle from the harness. Do not install a Coordinator prompt into Osaurus or issue inference without the operator sequence in `docs/stage-2b2-gate-a.md`.
- Stage 2B-2 is one bounded route benchmark cohort, not path smoke. It permits exactly seventy-two serial inference requests and seventy-two HTTP POSTs only after separately completed Gate B, Jason's explicit current-session authorization of one exact unused ID, and a short-lived `3.4.0` manifest for that exact ID.
- The only permitted routes are `http://127.0.0.1:8080/v1` and `http://127.0.0.1:1337/v1`. Limits are 120 seconds per request, warning-level memory stop, one in-flight request, and seventy-two total requests. Expected routed ID is the exact inventory string `optiq//Users/jrazz/.cache/huggingface/hub/mlx-community/gemma-4-12B-it-qat-OptiQ-4bit:no-think`.
- Gate A docs, templates, package tests, and the repo Coordinator draft (`docs/stage-2b2-coordinator-prompt.md`) are non-live. They must not create a usable ID or manifest, install a prompt into Osaurus, start or stop OptiQ, reconnect or edit a provider, or issue an endpoint request.
- For **this operator-owned lane**, Jason remains the sole owner of the foreground OptiQ service lifecycle and existing-provider reconnect. The harness never starts, stops, signals, restarts, configures, loads, or unloads OptiQ or Osaurus on schema `3.4.0` / profile revision `2`.
- Preserve Stage 2B-1 `3.3.0` smoke and Stage 2A revision-3 as rollback. Plugin `0.3.0` unchanged; do not rebuild or reinstall it.

## Stage 2 Harness-Unattended Boundary (Slice 1c)

- Current decision: `GATE_A_PASSED`; Gate B `READY_FOR_MANIFEST_AUTHORIZATION`
  (2026-07-23; pin-confirm + harness start/verify/stop GET-only). Schema `3.5.0`,
  mode `harness_inference_probe`, comparison class
  `gemma-optiq-042-harness-route-smoke`, profile `gemma-4-12b-optiq-4bit`
  revision `4`, suite `gemma-optiq-042-harness-route-smoke-v1` revision `1`.
  See `docs/stage-2-harness-unattended-gate-a.md`.
  Evidence: `docs/superpowers/verification/2026-07-23-slice-1b-optiq-042-pin-confirm.md`,
  `docs/superpowers/verification/2026-07-23-slice-1c-harness-unattended-gate-b.md`.
- The harness **may** start and stop OptiQ via Slice 1a `LifecycleController` for this lane only. It records honest `service_lifecycle_actions > 0`. Cleanup uses harness-owned process-group stop (mlx-optiq `0.4.2` has no `optiq stop` CLI); port `8080` must be free twice. Not operator `Ctrl+C`.
- Provider *edit* is forbidden (`provider_activation: verify_routed_id_only`). The harness verifies the exact routed inventory ID after OptiQ is up. If reconnect is required and no safe non-editing API exists, at most **one** operator reconnect tap is documented — prefer eliminating it later. See `docs/superpowers/notes/2026-07-22-slice-1c-provider-reconnect-note.md`.
- Do not create run IDs or live manifests, upgrade OptiQ on disk further, edit Osaurus providers, rebuild plugin `0.3.0`, or issue live POSTs without Jason's separate current-session authorization for Gate C–D.
- Operator-owned rollback unchanged: Stage 2A revision `3`, Stage 2B-1 schema `3.3.0` / profile revision `2` (sealed `005`), Stage 2B-2 schema `3.4.0` / profile revision `2` (sealed `006`). Those lanes still require operator OptiQ lifecycle and `service_lifecycle_actions: 0`.
