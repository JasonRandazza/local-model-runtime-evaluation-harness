# Slice 1c Stage 2 Unattended Path Gate A Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Land Package 1 / Slice 1c Gate A only: a new Stage 2 **harness-owned** lane that starts and stops OptiQ via Slice 1a `LifecycleController`, records honest `service_lifecycle_actions > 0`, and cleans up without Jason’s Ctrl+C — while preserving operator-owned schemas `3.3.0`/`3.4.0` and sealed `005`/`006` as rollback. Fake-only tests. No Gate B, run IDs, disk OptiQ upgrade, provider edits, or plugin rebuild.

**Architecture:** Add a parallel authorizing contract (schema / mode / comparison / profile revision) that injects a harness lifecycle adapter instead of `OperatorOptiQController`. Reuse `harness_lifecycle.LifecycleController` for OptiQ `:8080` (and observe-only Osaurus readiness when needed). Do **not** delete or change operator-owned engines for `3.3.0`/`3.4.0`. Provider *edit* stays forbidden; Gate A verifies routed inventory ID after OptiQ is up and documents at most one remaining reconnect tap.

**Tech Stack:** Python 3 stdlib, `unittest`, existing Stage 2 engines/factory/policy/profiles, Slice 1a `harness_lifecycle`, Slice 1b Gemma `0.4.2` pin constants. Prefer `/opt/homebrew/bin/python3`. Plugin `0.3.0` unchanged.

## Global Constraints

- Spec: `docs/superpowers/specs/2026-07-21-stack-review-gate-a-queue-design.md` (Slice 1c)
- Depends on landed 1a (`harness_lifecycle.py`) and 1b (Gemma r3 / `0.4.2` parser). Disk may still be `0.3.3` — Gate A uses fakes; live pin-confirm remains separately gated.
- Do **not** authorize a live run, create manifests/IDs, upgrade OptiQ on disk, edit Osaurus providers, rebuild plugin, or implement Package 2.
- Do **not** change operator-owned cleanup to kill foreign OptiQ; historical lanes still require operator Ctrl+C + `assert_stopped`.
- Provider *edit* forbidden. Prefer eliminate reconnect tap; if no safe API, document **one** remaining operator tap only.
- No commits of `config/matrix/omlx-roots/**`.

## Locked contract names (Gate A)

| Field | Value |
|---|---|
| Schema | `3.5.0` |
| Mode | `harness_inference_probe` |
| Comparison class | `gemma-optiq-042-harness-route-smoke` |
| Profile id | `gemma-4-12b-optiq-4bit` |
| Profile revision | `4` (harness ownership; same `0.4.2` pins as r3) |
| Suite | Reuse `gemma-optiq-route-smoke-v1` revision `1` **or** clone to `gemma-optiq-042-harness-route-smoke-v1` revision `1` if suite id must match comparison — prefer **clone suite file** with identical eight-request shape and new `suite_id` matching comparison for fail-closed identity |
| Routes / limits | Same as Stage 2B-1 smoke: `8080`/`1337`, 120s, warning memory, in-flight 1, total 8 |
| `service_ownership` | `harness` |
| `provider_activation` | `verify_routed_id_only` |

**Rollback lane (unchanged):** schemas `3.3.0`/`3.4.0`, profile revision `2`, `service_ownership: operator`, `service_lifecycle_actions: 0`.

**Why revision 4 (not mutate r3):** r3 remains the operator-shaped `0.4.2` pin for pin-confirm. Harness ownership is a new fail-closed profile revision so shared constants stay safe.

## File map

| Area | Files |
|---|---|
| Profile | Create `config/runtime-profiles/gemma-4-12b-optiq-4bit-r4.json`; extend `stage_two_profiles.py` |
| Suite | Create `suites/gemma-optiq-042-harness-route-smoke-v1.json` (clone smoke v1; new suite_id) |
| Lifecycle adapter | Create `src/local_model_runtime_evaluation/stage_two_harness_lifecycle.py` (wraps `LifecycleController`) |
| Factory / policy / manifest | Modify `stage_two_factory.py`, `policy.py`, `manifest.py` / schema JSON as needed for `3.5.0` |
| Engine path | Prefer thin harness smoke engine **or** parameterize inference engine cleanup/preflight via injected controller protocol — inspect before coding; avoid duplicating the full 2B-1 engine if a small adapter + factory branch suffices |
| Docs | `docs/architecture.md`, `AGENTS.md` (new lane only), stack-review spec pointer, optional `docs/stage-2-harness-unattended-gate-a.md` |
| Tests | `tests/test_stage_two_harness_lifecycle.py`, profile/policy/factory/engine tests |

---

### Task 1: Profile revision 4 parser + on-disk pin

**Files:**
- Modify: `src/local_model_runtime_evaluation/stage_two_profiles.py`
- Create: `config/runtime-profiles/gemma-4-12b-optiq-4bit-r4.json`
- Modify: `tests/test_stage_two_profile.py`

**Interfaces:**
- `_parse_gemma_revision_four`: same `0.4.2` / `_GEMMA_R3_PACKAGE_VERSIONS` (or alias `_GEMMA_R4_PACKAGE_VERSIONS = _GEMMA_R3_PACKAGE_VERSIONS`) and model/route pins as r3
- Require `service_ownership == "harness"` and `provider_activation == "verify_routed_id_only"`
- Reject r4 with `operator` ownership; keep r3 requiring `operator`

- [ ] **Step 1: Failing tests** for load r4, reject wrong ownership, r3 still operator-only

- [ ] **Step 2: Implement parser + JSON**

- [ ] **Step 3: PASS + commit**

```bash
git commit -m "$(cat <<'EOF'
Add Gemma OptiQ profile revision 4 for harness-owned lifecycle.

EOF
)"
```

---

### Task 2: Schema `3.5.0` manifest + policy allowlist (non-live Gate A)

**Files:**
- Modify: `manifest.py`, `policy.py`, `schemas/benchmark-manifest.schema.json` (if enums live there)
- Create: `tests/fixtures/valid-stage-2-harness-smoke.json`
- Modify: `tests/test_manifest.py`, `tests/test_policy.py` (or Stage 2 equivalents)

**Interfaces:**
- Accept schema `3.5.0` + mode `harness_inference_probe` + comparison `gemma-optiq-042-harness-route-smoke` + profile revision `4` + new suite id
- Reject `3.5.0` paired with revision `2`/`3` or operator comparison classes
- Keep `3.3.0`/`3.4.0` contracts unchanged
- **Still no Gate B / run ID** — policy authorize for Stage 2 operations is for Gate A factory tests only; docs state live remains gated

- [ ] **Step 1–4: TDD + commit**

```bash
git commit -m "$(cat <<'EOF'
Authorize Stage 2 schema 3.5.0 harness-unattended smoke contract.

EOF
)"
```

---

### Task 3: Harness lifecycle adapter (OptiQ start/stop + action counter)

**Files:**
- Create: `src/local_model_runtime_evaluation/stage_two_harness_lifecycle.py`
- Create: `tests/test_stage_two_harness_lifecycle.py`

**Interfaces:**
- `HarnessOptiQController` (name may vary) built on `LifecycleController`:
  - `ensure_started(pin)` → owned OptiQ spawn + ready; increments lifecycle actions via underlying controller
  - `ensure_stopped()` → owned stop + port `8080` free twice; increments stop action
  - `lifecycle_actions: int` (honest count; never force `0`)
  - Lab closed + RAM floor via injected fakes in tests
- Never kill observe-only / foreign processes
- Do **not** call `OperatorOptiQController.assert_stopped` (that path expects operator Ctrl+C)

- [ ] **Step 1: Failing tests** — start then stop → actions ≥ 2; foreign busy OptiQ → fail closed; double-stop safe

- [ ] **Step 2–4: Implement with fakes + commit**

```bash
git commit -m "$(cat <<'EOF'
Add harness OptiQ lifecycle adapter for Stage 2 unattended lane.

EOF
)"
```

---

### Task 4: Factory + engine preflight/cleanup wiring (fake-only)

**Files:**
- Modify: `stage_two_factory.py`
- Modify: inference engine **or** new thin `stage_two_harness_inference.py` if parameterization would be too invasive — choose the smaller diff after reading `stage_two_inference.py` cleanup/preflight
- Modify: focused engine/factory tests
- Create suite JSON from Task 2 file map

**Interfaces:**
- `build_stage_two_engine` for `(3.5.0, harness_inference_probe)` builds harness controller, not `OperatorOptiQController`
- Preflight: harness ensure OptiQ started; verify routed model id equals profile `routed_model_id` (transport fake)
- Evidence: `service_lifecycle_actions` equals controller count (may be `2` for start+stop in a full fake run)
- Cleanup: harness ensure stopped; port free twice; **no** `operator_shutdown_pending` waiting on Ctrl+C
- Operator schemas still force `service_lifecycle_actions: 0`

- [ ] **Step 1: Inspect engine; write failing factory/engine tests for 3.5.0 path**

- [ ] **Step 2–4: Implement smallest wiring + PASS**

- [ ] **Step 5: Commit**

```bash
git commit -m "$(cat <<'EOF'
Wire Stage 2 factory to harness lifecycle for schema 3.5.0.

EOF
)"
```

---

### Task 5: Provider verify-only + one-tap reconnect note + AGENTS/docs

**Files:**
- Docs: `docs/architecture.md`, `AGENTS.md` (add harness-unattended lane; keep historical operator-owned Stage 2 rules for `3.3.0`/`3.4.0`), stack-review spec pointer under Slice 1c
- Create: `docs/superpowers/notes/2026-07-22-slice-1c-provider-reconnect-note.md` — states provider edit forbidden; verify routed ID after OptiQ up; if reconnect required and no safe API, **one** remaining operator tap; prefer eliminating tap later
- Optional: `docs/stage-2-harness-unattended-gate-a.md` with `GATE_A` status (not live)

**Interfaces:**
- Code: routed-id verification already in Task 4; this task locks docs + any tiny `provider_activation` branch that refuses edit APIs (no provider file writes)

- [ ] **Step 1: Docs + AGENTS lane section**

- [ ] **Step 2: Full verification**

```bash
PYTHONPATH=src /opt/homebrew/bin/python3 -m unittest \
  tests.test_stage_two_profile \
  tests.test_stage_two_harness_lifecycle \
  tests.test_harness_lifecycle \
  tests.test_policy \
  tests.test_stage_two_runner \
  tests.test_stage_two_inference_engine \
  tests.test_stage_two_benchmark_engine -q
```

Expected: OK (adjust module list if suite file names differ)

- [ ] **Step 3: Commit**

```bash
git commit -m "$(cat <<'EOF'
Document Stage 2 harness-unattended Gate A and provider verify-only policy.

EOF
)"
```

---

## Spec coverage check

| Spec requirement | Task |
|---|---|
| Harness starts/stops OptiQ via 1a lifecycle | 3–4 |
| Honest `service_lifecycle_actions` > 0 | 3–4 |
| Cleanup without Ctrl+C | 4 |
| New mode/schema/profile flag | 1–2 |
| Operator `0.3.3`/`3.3.0`/`3.4.0` rollback | Global |
| Provider edit forbidden; verify routed ID; ≤1 reconnect tap | 4–5 |
| Fake-only Gate A; no live auth | Global |
| Depends on 1a + 1b | Global |

## Placeholder scan

No TBD steps. Real Lab probe, disk `0.4.2` pin-confirm, and live Gate B remain explicitly out of scope. Engine vs thin-adapter choice is deferred to Task 4 inspection (allowed decision, not an open requirement).

---

## Execution handoff

Plan saved to `docs/superpowers/plans/2026-07-22-slice-1c-harness-unattended-gate-a.md`.

**Two execution options:**

1. **Subagent-Driven (recommended)**  
2. **Inline Execution**  

Which approach?
