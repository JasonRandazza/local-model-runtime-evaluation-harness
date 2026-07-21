# Stage 2B-1 Slice 2 Gemma OptiQ Retarget Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make schema `3.3.0` the only new live-authorizing Stage 2B-1 shape, pinned to Gemma OptiQ-4bit native (direct `:8080` / routed `:1337`), while keeping schema `3.2.0` VibeThinker manifests parseable for evidence review but non-authorizing for new runs.

**Architecture:** Extend the existing Stage 2B-1 policy/manifest/factory/engine allowlists with a parallel `3.3.0` contract. Add a new approved runtime profile and smoke suite cloned from the VibeThinker shape with Gemma identity pins. Do not change plugin `0.3.0`, Stage 2A GET-only observation, or operator lifecycle ownership. Live Gate B and eight POSTs remain out of this plan.

**Tech Stack:** Python 3 + `unittest`, JSON manifests/profiles/suites, existing Stage 2B-1 engine.

## Global Constraints

- Spec: `docs/superpowers/specs/2026-07-20-stage-2b1-gemma-retarget-design.md` — **Slice 2 only**.
- Decision: `GATE_A_FINDINGS_CLOSED`. Still **no Gate B**, usable run ID, live POST, provider reconnect, or Coordinator prompt install in this plan.
- Preserve Stage 2A revision-3 VibeThinker baseline and historical `3.2.0` parseability.
- New live authorization accepts only:
  - schema `3.3.0`
  - mode `operator_inference_probe`
  - comparison class `gemma-optiq-operator-route-smoke`
  - profile `gemma-4-12b-optiq-4bit` revision `1`
  - suite `gemma-optiq-route-smoke-v1` revision `1`
  - routes `http://127.0.0.1:8080/v1` and `http://127.0.0.1:1337/v1`
  - limits: 120s, memory `warning`, in-flight `1`, total `8`
- Expected routed ID: `optiq/mlx-community/gemma-4-12B-it-qat-OptiQ-4bit` (exact, case-sensitive).
- Plugin `0.3.0` unchanged; harness never starts/stops OptiQ/Osaurus.
- Tests: deterministic fakes only (`PYTHONPATH=src python3 -m unittest …`). Prefer `/opt/homebrew/bin/python3`.
- Commit only with Jason’s current-session approval (or SDD execution authorization).

## Draft profile pins (local artifact hashes, 2026-07-20)

Model directory observed locally:

`/Users/jrazz/.cache/huggingface/hub/mlx-community/gemma-4-12B-it-qat-OptiQ-4bit`

| Artifact | SHA-256 |
|---|---|
| `config.json` | `10c3765fec68c1cd13e6b67dd968468fa71c0e66f33b4c8003d9e7565f68b209` |
| `optiq_metadata.json` | `e64e0271ef661b18c1d6b54c395266681be08771aa3e11804c7a206ada32dddf` |
| `model.safetensors.index.json` | `62d43537384d711cd4af06295524cb92e1f6d3f3df7fdfbcbcb2628ea5d0f08d` |
| `model-00001-of-00002.safetensors` | `515896784d9237ed8545ee2668eb886f665b075abe8ae50dc70f10cf173763c1` |
| `model-00002-of-00002.safetensors` | `0bea2433d5812dbb20fddc75b4adaa2d33a964420209eabefef94579048b0457` |

Runtime executable family: same as VibeThinker r3 (`/Users/jrazz/Dev/tools/mlx-optiq/.venv/bin/optiq`, `mlx-optiq 0.3.3`) unless inventory proves drift during pin confirmation.

Serve argv draft (operator-owned; launcher update is a later task):

```text
serve --model /Users/jrazz/.cache/huggingface/hub/mlx-community/gemma-4-12B-it-qat-OptiQ-4bit
  --host 127.0.0.1 --port 8080 --no-anthropic --no-responses --no-auth
  --single-model --max-concurrent 1 --idle-timeout 0 --max-context 8192
  --context-scale 1.0 --no-stream-experts --decode-concurrency 1 --prompt-concurrency 1
```

Matrix cell note: streaming may need `:no-think` on the **direct model id** used by clients; pin confirmation must record whether OptiQ serve argv and/or direct identity strings require a `:no-think` suffix for Stage 2B contracts. Do not invent a suffix in policy without inventory evidence.

## File map

| Deliverable | Paths |
|---|---|
| Profile | Create `config/runtime-profiles/gemma-4-12b-optiq-4bit-r1.json` |
| Suite | Create `suites/gemma-optiq-route-smoke-v1.json` |
| Fixture | Create `tests/fixtures/valid-stage-2-inference-gemma.json` |
| Template | Create/update `manifests/stage-2-optiq-inference-smoke.json.template` (Gemma `3.3.0`) and keep VibeThinker template as historical if present |
| Manifest/policy | Modify `manifest.py`, `policy.py`, `schemas/benchmark-manifest.schema.json` |
| Factory/engine | Modify `stage_two_factory.py`, `stage_two_inference.py`, `stage_two_smoke_suite.py`, `stage_two_profiles.py`, `stage_two_gate_b_check.py`, `artifacts.py` (schema branch for required files if needed) |
| Operator launcher | Modify `bin/lmre-stage2-operator-serve` to Gemma model path **or** add `bin/lmre-stage2-operator-serve-gemma` and document which is Stage 2B-1 live — prefer updating the existing launcher only if Stage 2A docs clearly remain VibeThinker-historical; otherwise add a Gemma-specific launcher and leave Stage 2A script untouched |
| Docs | `docs/stage-2b1-gate-a.md`, runbook pointers, `AGENTS.md` after green tests |
| Tests | `tests/test_manifest.py`, `tests/test_policy.py`, `tests/test_stage_two_factory.py` (or equivalent), `tests/test_stage_two_smoke_suite.py`, `tests/test_stage_two_gate_a_e2e.py` / inference e2e fixtures |

---

### Task 1: Schema `3.3.0` manifest + policy allowlist

**Files:**
- Create: `tests/fixtures/valid-stage-2-inference-gemma.json`
- Modify: `src/local_model_runtime_evaluation/manifest.py`
- Modify: `src/local_model_runtime_evaluation/policy.py`
- Modify: `schemas/benchmark-manifest.schema.json` (if schema enum lives there)
- Modify: `tests/test_manifest.py`, `tests/test_policy.py`

**Interfaces:**
- Produces: `validate_manifest` accepts schema `3.3.0` with Gemma pins; rejects `3.3.0` + VibeThinker pins; keeps `3.2.0` parseable for fixtures but policy must not authorize new live `3.2.0` runs (match design: parseable evidence, non-authorizing for new live)

- [ ] **Step 1: Add failing Gemma fixture + tests**

Create `tests/fixtures/valid-stage-2-inference-gemma.json` cloned from `valid-stage-2-inference.json` with:

```json
{
  "schema_version": "3.3.0",
  "comparison_class": "gemma-optiq-operator-route-smoke",
  "runtime_profile_id": "gemma-4-12b-optiq-4bit",
  "runtime_profile_revision": "1",
  "suite_id": "gemma-optiq-route-smoke-v1",
  "suite_revision": "1"
}
```

(keep mode, routes, limits, operations identical)

Add tests:

```python
def test_valid_stage_two_inference_gemma_manifest_loads(self) -> None:
    ...
    self.assertEqual(manifest.schema_version, "3.3.0")
    self.assertEqual(manifest.comparison_class, "gemma-optiq-operator-route-smoke")
    self.assertEqual(manifest.runtime_profile_id, "gemma-4-12b-optiq-4bit")
    self.assertEqual(manifest.runtime_profile_revision, "1")
    self.assertEqual(manifest.suite_id, "gemma-optiq-route-smoke-v1")

def test_schema_330_rejects_vibethinker_pins(self) -> None: ...
def test_schema_320_still_parses_historical_fixture(self) -> None: ...
```

Policy tests: active Stage 2B authorization path accepts only the Gemma `3.3.0` tuple; `3.2.0` is historical-only (exact behavior must match how policy distinguishes authorize vs parse — mirror existing Stage 2 patterns).

- [ ] **Step 2: Run tests red**

```bash
PYTHONPATH=src python3 -m unittest tests.test_manifest tests.test_policy -v
```

- [ ] **Step 3: Implement minimal allowlists**

Update `manifest.py` allowed schemas for stage 2 to include `3.3.0`; branch required keys like `3.2.0`; enforce Gemma pin fields for `3.3.0` and keep VibeThinker pin checks for `3.2.0`.

Update `policy.py` active authorization contract to prefer/require `3.3.0` Gemma for new live Stage 2B inference (do not authorize new `3.2.0` live runs).

- [ ] **Step 4: Run tests green**

```bash
PYTHONPATH=src python3 -m unittest tests.test_manifest tests.test_policy -v
```

- [ ] **Step 5: Commit if authorized**

```bash
git commit -m "$(cat <<'EOF'
Add Stage 2B-1 schema 3.3.0 Gemma manifest allowlist.

Keep 3.2.0 VibeThinker parseable for evidence while authorizing only the
Gemma OptiQ inference-probe contract for new runs.
EOF
)"
```

---

### Task 2: Gemma runtime profile + profile loader

**Files:**
- Create: `config/runtime-profiles/gemma-4-12b-optiq-4bit-r1.json`
- Modify: `src/local_model_runtime_evaluation/stage_two_profiles.py`
- Modify/add tests under `tests/test_stage_two_profiles.py` (or existing profile tests)

**Interfaces:**
- Produces: loadable approved profile with draft pins from Global Constraints; rejected locals include unprefixed hub id and short alias; routed id exact

- [ ] **Step 1: Failing profile load/identity tests**

Assert profile loads, `revision == "1"`, `routed_model_id` exact, artifact hashes match the draft table, serve argv model path points at the Gemma directory, coordinator model remains `gemma-4-12b-it-qat-jang_4m`.

- [ ] **Step 2: Run red**

- [ ] **Step 3: Write profile JSON + loader acceptance**

Clone VibeThinker r3 structure; swap identity fields; include all five artifact hashes; set `approved: true` only if loader requires it for tests (pin confirmation task may flip flags — prefer `approved: true` with hashes already measured locally, and document that Gate B still needs live inventory confirmation of the routed ID).

- [ ] **Step 4: Green + commit if authorized**

```bash
git commit -m "$(cat <<'EOF'
Add gemma-4-12b-optiq-4bit runtime profile revision 1.

Pin local OptiQ artifact hashes and loopback routes for Stage 2B-1
schema 3.3.0 authorization.
EOF
)"
```

---

### Task 3: Gemma smoke suite + factory/engine wiring

**Files:**
- Create: `suites/gemma-optiq-route-smoke-v1.json` (same workloads as `optiq-route-smoke-v1.json`)
- Modify: `stage_two_smoke_suite.py`, `stage_two_factory.py`, `stage_two_inference.py`, `artifacts.py` if schema-gated
- Modify: e2e / inference engine tests to run on Gemma fixture (fakes only)

**Interfaces:**
- Factory routes `("3.3.0", "operator_inference_probe")` → Gemma suite + Gemma profile
- Engine contract checks accept Gemma pins; keep `3.2.0` path for historical tests or retire live factory authorization for `3.2.0`

- [ ] **Step 1: Failing factory/engine tests using Gemma fixture**

- [ ] **Step 2: Red**

- [ ] **Step 3: Wire suite load + engine allowlists; keep eight-POST schedule**

- [ ] **Step 4: Green including `tests.test_stage_two_gate_a_e2e` (update fixture to Gemma `3.3.0`)**

- [ ] **Step 5: Commit if authorized**

```bash
git commit -m "$(cat <<'EOF'
Wire Stage 2B-1 factory and engine to Gemma 3.3.0 smoke suite.

Retain the eight-request counterbalanced schedule under the Gemma
profile and comparison class.
EOF
)"
```

---

### Task 4: Gate B checker, template, operator launcher docs

**Files:**
- Modify: `stage_two_gate_b_check.py` (profile id + routed id constants)
- Create/update: non-authorizing Gemma template under `manifests/`
- Launcher: prefer **new** `bin/lmre-stage2-operator-serve-gemma` with Gemma `--model` path so Stage 2A VibeThinker launcher remains historical rollback; document in Stage 2B-1 runbook
- Docs: `docs/stage-2b1-gate-a.md`, short runbook note

**Interfaces:**
- Gate B dry tests against Gemma profile fixtures (no network)

- [ ] **Step 1: Failing Gate B dry tests for Gemma pins**

- [ ] **Step 2: Implement checker + template + Gemma launcher script**

- [ ] **Step 3: Docs — Slice 2 complete pending retarget review; still no Gate B without Jason auth**

- [ ] **Step 4: Full Python unittest discover; note Swift plugin unchanged**

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

- [ ] **Step 5: Commit if authorized**

```bash
git commit -m "$(cat <<'EOF'
Point Stage 2B Gate B and operator launcher at Gemma OptiQ.

Add a Gemma-specific serve launcher and non-authorizing 3.3.0 template
while leaving the Stage 2A VibeThinker launcher as historical rollback.
EOF
)"
```

---

### Task 5: Pin confirmation checklist (manual, non-live code)

Not automatic Gate B. Produce `docs/superpowers/verification/2026-07-20-stage-2b1-gemma-pin-confirmation.md` listing operator steps Jason must approve later:

1. Start `bin/lmre-stage2-operator-serve-gemma` (or chosen launcher)
2. Reconnect existing `Optiq` provider without editing
3. `GET /health` and `GET /v1/models` on both ports — record exact routed id
4. Confirm hashes still match profile; update profile only if drift found (new revision, not silent overwrite)
5. Only then consider Gate B in a separate session

- [ ] **Step 1: Write the checklist doc (no live commands executed by the agent unless Jason explicitly authorizes in-session)**

- [ ] **Step 2: Commit if authorized**

---

## Out of plan

- Gate B execution
- Unused run ID / live eight-POST smoke
- Measurement-lane Stage wrappers (roadmap annex)
- Plugin rebuild
- Updating Stage 2A VibeThinker revision-3 evidence

## Spec coverage

| Spec Slice 2 item | Task |
|---|---|
| Schema `3.3.0` only for new live auth | Task 1 |
| Gemma profile rev 1 + hashes | Task 2 |
| Suite + factory/engine | Task 3 |
| Gate B checker / template / launcher / docs | Task 4 |
| Live pin confirmation before Gate B | Task 5 (checklist only) |
