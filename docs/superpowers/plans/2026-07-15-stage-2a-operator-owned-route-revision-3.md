# Stage 2A Operator-Owned Route Revision 3 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace Stage 2A harness-owned OptiQ lifecycle with a fail-closed operator-owned route-discovery contract.

**Architecture:** Jason runs one fixed foreground OptiQ service and explicitly reconnects the existing Osaurus provider. Gate B and the harness observe exact process and route identity with GET requests only; the harness never signals the service, and final cleanup requires Jason to stop it and free port `8080`.

**Tech Stack:** Python 3.11 standard library, `unittest`, JSON schemas and profiles, zsh foreground launcher, existing Swift plugin `0.3.0` unchanged.

## Global Constraints

- No live manifest or run ID is created during implementation.
- No test contacts Osaurus, OptiQ, oMLX, Keychain, or a real model.
- Stage 2A uses GET only and contains no model-load, inference, benchmark, or HTTP POST path.
- The harness never starts, stops, signals, restarts, or configures the operator-owned OptiQ service.
- The required routed identity is exactly `optiq/mlx-community/VibeThinker-3B-OptiQ-4bit`.
- The existing six-tool plugin `0.3.0` remains unchanged.
- Both consumed Stage 2 run IDs and their artifacts remain untouched.

---

### Task 1: Revision-3 Profile and Manifest Contract

**Files:**
- Create: `config/runtime-profiles/vibethinker-3b-optiq-4bit-r3.json`
- Modify: `src/local_model_runtime_evaluation/stage_two_profiles.py`
- Modify: `src/local_model_runtime_evaluation/manifest.py`
- Modify: `src/local_model_runtime_evaluation/policy.py`
- Modify: `schemas/runtime-profile.schema.json`
- Modify: `schemas/benchmark-manifest.schema.json`
- Modify: `tests/fixtures/valid-stage-2.json`
- Modify: `tests/test_stage_two_profile.py`
- Modify: `tests/test_stage_two_manifest.py`
- Modify: `tests/test_policy.py`

**Interfaces:**
- Produces: `RuntimeProfile.service_ownership`, `RuntimeProfile.provider_activation`, and revision-aware registry lookup.
- Produces: Stage 2 manifest mode `operator_route_probe` and comparison class `optiq-operator-route-discovery`.

- [x] Write tests asserting revision `3`, operator ownership fields, provider-prefixed route identity, rejection of raw and local routed IDs, and the reduced revision-3 limits object.
- [x] Run the focused tests and confirm they fail because revision `3` is unsupported.
- [x] Add the revision-3 profile while preserving revision `2` as historical input.
- [x] Make registry lookup select exactly one `(profile_id, revision)` pair rather than rejecting multiple revisions.
- [x] Make manifest and policy validation accept only the revision-3 mode and comparison contract for new active fixtures.
- [x] Run the focused tests and confirm they pass.

Expected test command:

```zsh
python3 -m unittest tests.test_stage_two_profile tests.test_stage_two_manifest tests.test_policy -v
```

### Task 2: Operator Service Identity Controller

**Files:**
- Modify: `src/local_model_runtime_evaluation/stage_two_host.py`
- Modify: `tests/test_stage_two_host.py`

**Interfaces:**
- Produces: `OperatorOptiQController.capture() -> ProcessOwnership`.
- Produces: `OperatorOptiQController.matches(identity) -> bool`.
- Produces: `OperatorOptiQController.assert_stopped(identity) -> None`.

- [x] Write tests proving exact foreground `serve` capture, interpreter-prefix tolerance, Lab rejection, command-drift rejection, conflicting-model health rejection, listener-PID mismatch rejection, identity replacement, and two-observation shutdown verification without signals.
- [x] Run the host tests and confirm the new controller tests fail.
- [x] Implement the observation-only controller using the existing process backend and direct health callback.
- [x] Ensure no controller method calls `spawn`, `terminate_group`, or `wait_exit`.
- [x] Run the host tests and confirm they pass.

Expected test command:

```zsh
python3 -m unittest tests.test_stage_two_host -v
```

### Task 3: Revision-3 Engine and Evidence

**Files:**
- Modify: `src/local_model_runtime_evaluation/stage_two.py`
- Modify: `src/local_model_runtime_evaluation/artifacts.py`
- Modify: `src/local_model_runtime_evaluation/lifecycle.py`
- Modify: `tests/test_stage_two_engine.py`
- Modify: `tests/test_stage_two_contract.py`
- Modify: `tests/test_artifacts.py`

**Interfaces:**
- Consumes: `OperatorOptiQController.capture`, `matches`, and `assert_stopped`.
- Produces: revision-3 operator identity and shutdown evidence with `service_lifecycle_actions: 0`.

- [x] Write engine tests proving preflight route activation, no service start/stop, exact prefixed identity, strict health before and after inventory, same-process and listener checks before and after GET inventory, cancellation without service signaling, cleanup refusal while the operator service runs, and successful cleanup after process absence plus two free-port observations.
- [x] Write transport tests proving that only the four approved GET requests are possible and that sanitized request evidence contains method, endpoint label, status, and payload digest.
- [x] Write artifact tests for the revision-3 required-file set.
- [x] Run focused tests and confirm they fail under lifecycle-owned behavior.
- [x] Replace StageTwoEngine's active path with operator observation and add revision-3 lifecycle transitions `running -> service_ready -> endpoint_identity -> artifact_validation`.
- [x] Preserve pending sanitized inventory on route failure and partial evidence on cancellation.
- [x] Finalize only after `assert_stopped` passes.
- [x] Add a partial-cleanup path for `cancelled` and `failed` states that also requires operator shutdown before releasing the run lock.
- [x] Run focused tests and confirm they pass.

Expected test command:

```zsh
python3 -m unittest tests.test_stage_two_engine tests.test_stage_two_contract tests.test_artifacts tests.test_lifecycle -v
```

### Task 4: Factory and Gate B Activation Proof

**Files:**
- Modify: `src/local_model_runtime_evaluation/stage_two_factory.py`
- Modify: `src/local_model_runtime_evaluation/stage_two_gate_b_check.py`
- Modify: `tests/test_stage_two_gate_b_check.py`
- Modify: `tests/test_stage_two_runner.py`
- Modify: `src/local_model_runtime_evaluation/wait_for_review.py`
- Modify: `tests/test_wait_for_review.py`

**Interfaces:**
- Consumes: revision-3 profile and `OperatorOptiQController`.
- Produces: Gate B results `operator_service_identity: PASS`, `route_identity: PASS`, and `READY_FOR_MANIFEST_AUTHORIZATION` only after explicit provider activation.

- [x] Write tests requiring one exact running service, occupied port, safe non-conflicting health, and one exact provider-prefixed routed model.
- [x] Write stop tests for missing service, free port, wrong command, missing route, duplicate route, and prohibited counters.
- [x] Run focused tests and confirm they fail under the revision-2 free-port contract.
- [x] Wire the factory and Gate B checker to the observation-only controller and GET-only route proof.
- [x] Keep plugin `0.3.0` checks and six-tool behavior unchanged.
- [x] Make the Stage 2 waiter report `OPERATOR_SHUTDOWN_REQUIRED` for review-ready and terminal operator-owned runs.
- [x] Run focused tests and confirm they pass.

Expected test command:

```zsh
python3 -m unittest tests.test_stage_two_gate_b_check tests.test_stage_two_runner -v
```

### Task 5: Fixed Operator Launcher and Documentation

**Files:**
- Create: `bin/lmre-stage2-operator-serve`
- Create: `manifests/stage-2-optiq-operator-route.json.template`
- Modify: `README.md`
- Modify: `AGENTS.md`
- Modify: `docs/architecture.md`
- Modify: `docs/stage-2-gate-a.md`

**Interfaces:**
- Produces: one no-argument foreground launcher using `exec` and the exact profile command.
- Produces: a non-authorizing manifest template with no usable run ID or approval window.

- [x] Add a package test asserting the launcher has no variable inputs, contains the exact executable and arguments, and uses foreground `exec`.
- [x] Run the package test and confirm it fails before the launcher exists.
- [x] Create the launcher and mark it executable.
- [x] Add the revision-3 template and reconcile repository documentation.
- [x] Run the package and JSON parsing tests.

Expected test command:

```zsh
python3 -m unittest tests.test_package -v
jq empty config/runtime-profiles/vibethinker-3b-optiq-4bit-r3.json manifests/stage-2-optiq-operator-route.json.template schemas/runtime-profile.schema.json schemas/benchmark-manifest.schema.json
```

### Task 6: Full Non-Live Verification and Deep Wiki Reconciliation

**Files:**
- Modify: Deep Wiki project, runbook, Coordinator prompt, project board, audit record, and a new revision-3 Gate A review.

**Interfaces:**
- Produces: one consistent future operator sequence and a blocked live boundary pending Gate B and explicit run authorization.

- [x] Run the full Python suite and all Swift plugin contract tests.
- [x] Scan Stage 2 code for POST, inference, model-load, provider mutation, and process-signal paths reachable from revision `3`.
- [x] Confirm no new `.json` manifest with a usable run ID exists.
- [x] Update the Deep Wiki with the approved architecture, exact manual steps, rollback, and remaining Gate B boundary.
- [x] Run the vault validator.
- [x] Request a final architecture and code review from a capable Codex subagent, resolve material findings, and rerun verification.

Expected verification commands:

```zsh
python3 -m unittest discover -s tests -v
swift test --package-path plugins/osaurus-evaluation-harness
python3 "/Users/jrazz/Documents/ObsidianNotes/00 System/Automation/validate_vault.py" "/Users/jrazz/Documents/ObsidianNotes"
```
