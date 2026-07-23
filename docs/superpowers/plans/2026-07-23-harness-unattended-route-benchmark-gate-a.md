# Harness-Unattended Route Benchmark (3.6.0) Gate A Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Land Design 2 Gate A only: schema `3.6.0` / mode `harness_route_benchmark` / comparison `gemma-optiq-042-harness-route-benchmark` / profile revision `5` / cloned 72-POST suite — fake-only wiring of `StageTwoBenchmarkEngine` + `HarnessOptiQController`; no live contact.

**Architecture:** Mirror how `3.5.0` attaches `HarnessOptiQController` to the inference engine, but attach the same harness controller to **`StageTwoBenchmarkEngine`**. Clone the operator `042` benchmark suite JSON with a new `suite_id`. Extend fail-closed pairing so r5↔`3.6.0` harness bench only (keep r4↔`3.5.0` smoke and operator `3.4.0`/r3 untouched). Port harness lifecycle ledger + inventory wait from `StageTwoInferenceEngine` into the benchmark engine behind an `_is_harness_contract` guard — do **not** mutate frozen `_STAGE_2B_2_*` operator constants.

**Tech Stack:** Python 3 stdlib, `unittest`, existing Stage 2 factory/policy/manifest/benchmark engine. Prefer `/opt/homebrew/bin/python3`. Plugin `0.3.0` unchanged.

## Global Constraints

- Spec: `docs/superpowers/specs/2026-07-23-harness-unattended-route-benchmark-design.md`
- Prerequisites done: Design 1 Gate A + live inventory-wait proof (`2026-07-23-slice-1c-inventory-wait-r5-proof.md`); profile r5 already in tree
- No live manifests, run IDs, POSTs, provider edits, OptiQ upgrade, or plugin rebuild
- Do not mutate sealed operator `3.4.0` / r2 / r3 / `007` or harness smoke `3.5.0` / r4 / `003` contracts beyond additive allowlists
- No commits of `config/matrix/omlx-roots/**` or `.harness-lifecycle/**`
- Prefer `/opt/homebrew/bin/python3` with `PYTHONPATH=src`

## Locked names

| Field | Value |
|---|---|
| Schema | `3.6.0` |
| Mode | `harness_route_benchmark` |
| Comparison class | `gemma-optiq-042-harness-route-benchmark` |
| Profile | `gemma-4-12b-optiq-4bit` revision `5` |
| Suite | `gemma-optiq-042-harness-route-benchmark-v1` revision `1` |
| Ownership / activation | `harness` / `verify_routed_id_only_no_tap` |
| Total POSTs | `72` |
| Routes | `http://127.0.0.1:8080/v1`, `http://127.0.0.1:1337/v1` |

## File map

| Area | Files |
|---|---|
| Suite | Create `suites/gemma-optiq-042-harness-route-benchmark-v1.json`; modify `stage_two_benchmark_suite.py` |
| Fixture | Create `tests/fixtures/valid-stage-2-harness-benchmark.json` |
| Manifest / schema / policy | Modify `manifest.py`, `schemas/benchmark-manifest.schema.json`, `policy.py` |
| Factory | Modify `stage_two_factory.py` |
| Engine | Modify `stage_two_benchmark.py` (harness branch only) |
| Artifacts / waiter | Modify `artifacts.py`, `wait_for_review.py` |
| Docs | `docs/stage-2-harness-unattended-gate-a.md` (or sibling), `AGENTS.md`, Design 2 status, brief `docs/architecture.md` |
| Tests | `test_manifest.py`, `test_stage_two_manifest.py`, `test_policy.py`, `test_stage_two_runner.py`, `test_stage_two_benchmark_engine.py`, `test_artifacts.py`, `test_wait_for_review.py` |

---

### Task 1: Suite clone + approved suite ID + fixture

**Files:**
- Create: `suites/gemma-optiq-042-harness-route-benchmark-v1.json`
- Create: `tests/fixtures/valid-stage-2-harness-benchmark.json`
- Modify: `src/local_model_runtime_evaluation/stage_two_benchmark_suite.py`
- Test: `tests/test_stage_two_benchmark_suite.py` (or add load assertion in existing suite tests)

**Interfaces:**
- Clone `suites/gemma-optiq-042-operator-route-benchmark-v1.json`; change only `suite_id` to `gemma-optiq-042-harness-route-benchmark-v1`
- Add that ID to `_APPROVED_SUITE_IDS`
- Fixture mirrors `valid-stage-2-benchmark-gemma-042.json` but with schema `3.6.0`, mode `harness_route_benchmark`, comparison `gemma-optiq-042-harness-route-benchmark`, revision `5`, new suite id, `total_request_limit: 72`

- [ ] **Step 1: Write failing suite/fixture load test**

```python
def test_harness_route_benchmark_suite_loads_approved_id(self) -> None:
    suite = StageTwoBenchmarkSuite.load(
        REPO / "suites" / "gemma-optiq-042-harness-route-benchmark-v1.json"
    )
    self.assertEqual(suite.suite_id, "gemma-optiq-042-harness-route-benchmark-v1")
    self.assertEqual(len(suite.schedule), 72)
```

- [ ] **Step 2: Create suite JSON + fixture; approve suite ID**

- [ ] **Step 3: Run tests PASS**

```bash
PYTHONPATH=src /opt/homebrew/bin/python3 -m unittest tests.test_stage_two_benchmark_suite -q
```

- [ ] **Step 4: Commit**

```bash
git commit -m "$(cat <<'EOF'
Add harness OptiQ 0.4.2 route-benchmark suite clone for schema 3.6.0.

EOF
)"
```

---

### Task 2: Manifest schema + policy fail-closed pairing

**Files:**
- Modify: `src/local_model_runtime_evaluation/manifest.py`
- Modify: `schemas/benchmark-manifest.schema.json`
- Modify: `src/local_model_runtime_evaluation/policy.py`
- Modify: `tests/test_manifest.py`, `tests/test_stage_two_manifest.py`, `tests/test_policy.py`

**Interfaces:**
- Accept `3.6.0` + `harness_route_benchmark` + `gemma-optiq-042-harness-route-benchmark` + profile revision `5` + suite `gemma-optiq-042-harness-route-benchmark-v1` + limit `72`
- Reject: `3.6.0` + r4; `3.6.0` + operator comparison; `3.5.0` + harness benchmark comparison; `3.4.0` + r5; r5 + smoke comparison
- Policy `active_contracts` gains `("3.6.0", "harness_route_benchmark", "gemma-optiq-042-harness-route-benchmark", "5")`

- [ ] **Step 1: Failing tests** — valid fixture loads; cross-wiring rejected; policy authorizes six ops for harness bench and rejects wrong comparison/revision

- [ ] **Step 2: Implement manifest branch + schema `oneOf` + policy tuple**

- [ ] **Step 3: PASS**

```bash
PYTHONPATH=src /opt/homebrew/bin/python3 -m unittest \
  tests.test_manifest tests.test_stage_two_manifest tests.test_policy -q
```

- [ ] **Step 4: Commit**

```bash
git commit -m "$(cat <<'EOF'
Authorize Stage 2 schema 3.6.0 harness route-benchmark contract.

EOF
)"
```

---

### Task 3: Factory branch — `StageTwoBenchmarkEngine` + `HarnessOptiQController`

**Files:**
- Modify: `src/local_model_runtime_evaluation/stage_two_factory.py`
- Modify: `tests/test_stage_two_runner.py`, `tests/test_stage_two_benchmark_engine.py`

**Interfaces:**
- Add `_validate_stage_two_harness_benchmark_manifest(manifest)` pinning the locked tuple (mirror `_validate_stage_two_harness_manifest` but 3.6.0 / bench / r5 / 72)
- In `build_stage_two_engine`, accept `("3.6.0", "harness_route_benchmark")`
- Build like the `3.5.0` harness branch (`wait_ready` poll on direct health, `HarnessOptiQController(...)`) but return **`StageTwoBenchmarkEngine`** with suite `gemma-optiq-042-harness-route-benchmark-v1.json`
- Keep operator `3.4.0` branch unchanged

- [ ] **Step 1: Failing factory test**

```python
def test_factory_builds_harness_benchmark_engine_for_schema_360(self) -> None:
    # load valid-stage-2-harness-benchmark.json via factory
    # assert isinstance(engine, StageTwoBenchmarkEngine)
    # assert isinstance(engine.controller, HarnessOptiQController)
```

- [ ] **Step 2: Implement validator + factory branch**

- [ ] **Step 3: PASS + commit**

```bash
git commit -m "$(cat <<'EOF'
Wire schema 3.6.0 factory to harness-owned benchmark engine.

EOF
)"
```

---

### Task 4: Benchmark engine harness contract + lifecycle + inventory wait

**Files:**
- Modify: `src/local_model_runtime_evaluation/stage_two_benchmark.py`
- Modify: `tests/test_stage_two_benchmark_engine.py` (mirror harness tests from `test_stage_two_inference_engine.py`)

**Interfaces:**
- `_is_harness_contract(manifest)` → `(3.6.0, harness_route_benchmark)`
- `_validate_contract`: harness branch accepts registry-loaded r5 profile (`service_ownership=harness`, `provider_activation=verify_routed_id_only_no_tap`), harness suite id, comparison class, 72-schedule; **operator branch unchanged** (still compares to frozen `_STAGE_2B_2_*`)
- When harness: `ServiceLifecycleLedger` + `_sync_lifecycle_ledger` / `_service_lifecycle_actions()` from controller (same semantics as inference harness); preflight uses inventory wait emitting `routed_inventory_waiting` / `routed_inventory_ready` (reuse pattern from `StageTwoInferenceEngine._observe_routes_for_preflight` — extract shared helper only if copy would exceed ~40 lines and duplication is painful; otherwise duplicate the short loop once)
- Artifact summaries: harness must record `service_lifecycle_actions > 0` after capture/stop; operator path remains `0`
- Cleanup: harness stop proof (port free twice via controller), not operator Ctrl+C message

- [ ] **Step 1: Failing tests**
  - harness contract accepts r5 fixture profile
  - rejects wrong activation / comparison
  - fake preflight+cleanup records controller lifecycle actions
  - inventory wait emits non-tap event names
  - operator `3.4.0` path still reports `service_lifecycle_actions: 0`

- [ ] **Step 2: Implement harness guard paths**

- [ ] **Step 3: PASS**

```bash
PYTHONPATH=src /opt/homebrew/bin/python3 -m unittest \
  tests.test_stage_two_benchmark_engine -q
```

- [ ] **Step 4: Commit**

```bash
git commit -m "$(cat <<'EOF'
Teach StageTwoBenchmarkEngine harness lifecycle for schema 3.6.0.

EOF
)"
```

---

### Task 5: Artifacts, waiter, docs, Gate A verification sweep

**Files:**
- Modify: `src/local_model_runtime_evaluation/artifacts.py`
- Modify: `src/local_model_runtime_evaluation/wait_for_review.py`
- Modify: `tests/test_artifacts.py`, `tests/test_wait_for_review.py`
- Docs: `docs/stage-2-harness-unattended-gate-a.md` (follow-on / Gate A note for `3.6.0`), `AGENTS.md` (Slice 1c / Design 2 Gate A fake-only), Design 2 spec status → Gate A landed (fake-only), brief `docs/architecture.md` pointer

**Interfaces:**
- `_required_files()`: `harness_route_benchmark` + `3.6.0` + r5 → `STAGE_TWO_BENCHMARK_REQUIRED_FILES`
- `_require_operator_shutdown()`: `False` for `harness_route_benchmark` (keep existing `harness_inference_probe`)
- Docs must state: Gate A fake-only; live Gate B–D separately gated; no usable ID created

- [ ] **Step 1: Failing artifact + waiter tests**

- [ ] **Step 2: Implement + docs**

- [ ] **Step 3: Focused sweep**

```bash
PYTHONPATH=src /opt/homebrew/bin/python3 -m unittest \
  tests.test_manifest \
  tests.test_stage_two_manifest \
  tests.test_policy \
  tests.test_stage_two_runner \
  tests.test_stage_two_benchmark_engine \
  tests.test_stage_two_benchmark_suite \
  tests.test_artifacts \
  tests.test_wait_for_review \
  tests.test_stage_two_harness_lifecycle \
  -q

# Boundary scans
rg -n 'harness_route_benchmark|3\.6\.0' src schemas suites tests --glob '!*.pyc'
rg -n 'OPERATOR_SHUTDOWN_REQUIRED' src/local_model_runtime_evaluation/wait_for_review.py
# Ensure no live manifest for 3.6.0
ls manifests/ | rg '3\.6\.0|harness-route-benchmark' || true
```

- [ ] **Step 4: Commit**

```bash
git commit -m "$(cat <<'EOF'
Complete schema 3.6.0 harness route-benchmark Gate A docs and wiring.

EOF
)"
```

---

## Self-review (plan author)

| Spec success criterion | Task |
|---|---|
| Fixtures load for 3.6.0 / r5 / cloned suite | 1–2 |
| Policy + factory reject wrong pairings | 2–3 |
| Fake engine uses harness controller; lifecycle counted | 3–4 |
| Waiter skips operator Ctrl+C for new mode | 5 |
| Fake-only tests; no live contact | All + sweep |

**Gaps closed:** Task 4 explicitly ports inventory wait + lifecycle ledger; operator frozen constants preserved; Design 1 r5 reused (no profile work).

**Out of scope:** Gate B–D live, timeout-fail-closed test follow-up on inference engine (optional separate), Design 1 already done.

---

## Execution handoff

Plan saved to `docs/superpowers/plans/2026-07-23-harness-unattended-route-benchmark-gate-a.md`.

**Two execution options:**

1. **Subagent-Driven (recommended)** — dispatch a fresh subagent per task, review between tasks, fast iteration
2. **Inline execution** — execute tasks in this session with executing-plans checkpoints

Which approach?
