# Package 2 oMLX Thinking-Measure Gate A Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Land Package 2 Gate A only: a fake-only oMLX thinking-model measurement lane that starts/stops oMLX via Slice 1a `LifecycleController`, applies a thinking-aware preflight token budget, and distinguishes transport vs contract vs token-cap failures — without live runs, disk oMLX upgrade, Stage 2 OptiQ retarget, or OptiQ↔oMLX matrix work.

**Architecture:** Standalone suite + small runner module (not a new Stage 2 schema by default). Reuse `harness_lifecycle` for oMLX `:8100`. Pin contract `omlx-0.5.2-thinking` revision `1` with provisional constants; pin-confirm later. Measurement helpers extend existing `measurement.py` reasoning-token awareness.

**Tech Stack:** Python 3 stdlib, `unittest`, Slice 1a lifecycle, existing measurement helpers. Prefer `/opt/homebrew/bin/python3`. Plugin `0.3.0` unchanged.

## Global Constraints

- Design: `docs/superpowers/specs/2026-07-22-package-2-omlx-thinking-measure-design.md`
  (Jason confirmed option 1 — harness chat path — 2026-07-22)
- Implications: `docs/superpowers/notes/2026-07-21-omlx-0.5.2-implications.md`
- Gate A uses harness chat-completions path (not oMLX external-bench in this plan).
- Do **not** run Gate B, create run IDs, upgrade oMLX on disk, retarget Stage 2, edit providers, or rebuild plugin.
- Do **not** commit `config/matrix/omlx-roots/**`.
- Preserve Stage 2 operator/harness OptiQ lanes unchanged.

## Locked names

| Field | Value |
|---|---|
| Comparison class | `omlx-thinking-measure-v1` |
| Suite | `omlx-thinking-smoke-v1` revision `1` |
| Pin id | `omlx-0.5.2-thinking` revision `1` |
| Base URL | `http://127.0.0.1:8100/v1` |
| Requests | ≤8 serial; 120s timeout; 20% RAM floor via lifecycle |
| Preflight `max_tokens` floor | `512` thinking-aware default (constant; tests lock) |

## File map

| Area | Files |
|---|---|
| Pin | Create `config/runtime-profiles/omlx-0.5.2-thinking-r1.json` (or `config/omlx-pins/…` if profiles are OptiQ-shaped — prefer minimal JSON pin module `omlx_thinking_pin.py` if Stage profile schema is a poor fit) |
| Suite | Create `suites/omlx-thinking-smoke-v1.json` |
| Preflight / measure | Create `src/local_model_runtime_evaluation/omlx_thinking_measure.py` |
| Lifecycle glue | Thin helper using `LifecycleController` + `ServerPin(kind="omlx", …)` |
| Tests | `tests/test_omlx_thinking_measure.py` |
| Docs | Architecture note + pin-confirm checklist stub |

---

### Task 1: Thinking-aware preflight budget + failure classes (pure logic)

**Files:**
- Create: `omlx_thinking_measure.py` (functions only)
- Create: `tests/test_omlx_thinking_measure.py`

**Interfaces:**
- `THINKING_PREFLIGHT_MAX_TOKENS = 512` (or named constant)
- `classify_thinking_outcome(...)` → `ok` | `transport_failed` | `empty_visible` | `contract_failed` | `token_capped`
- `preflight_budget_ok(max_tokens: int) -> bool` — rejects budgets below floor
- No network

- [ ] **Step 1–4: TDD + commit**

```bash
git commit -m "$(cat <<'EOF'
Add thinking-aware preflight budget and outcome classification.

EOF
)"
```

---

### Task 2: oMLX pin types + suite JSON

**Files:**
- Create pin JSON + loader (fail-closed version `0.5.2`, base URL, optional extra_body allowlist)
- Create `suites/omlx-thinking-smoke-v1.json` (2 short workloads; thinking-friendly prompts; max_tokens ≥ floor)
- Tests for loader reject wrong version / missing fields

- [ ] **Step 1–4: TDD + commit**

```bash
git commit -m "$(cat <<'EOF'
Add oMLX 0.5.2 thinking-measure pin and smoke suite.

EOF
)"
```

---

### Task 3: Lifecycle-bound runner skeleton (fake transport)

**Files:**
- Extend `omlx_thinking_measure.py` with `ThinkingMeasureRunner`
- Tests inject `LifecycleController` fakes + fake transport

**Interfaces:**
- `run_preflight()` → start oMLX pin, thinking preflight POST, record lifecycle_actions
- `run_smoke()` → ≤8 serial POSTs, classify outcomes
- `cleanup()` → stop owned oMLX; port 8100 free
- Never live network in tests

- [ ] **Step 1–4: TDD + commit**

```bash
git commit -m "$(cat <<'EOF'
Wire oMLX thinking-measure runner to harness lifecycle with fakes.

EOF
)"
```

---

### Task 4: Qualification + docs / pin-confirm checklist

**Files:**
- Qualification helpers for reasoning-heavy samples (reuse smoke labels where possible)
- `docs/superpowers/notes/2026-07-22-package-2-omlx-052-pin-confirm-checklist.md`
- `docs/architecture.md` short Package 2 Gate A note
- Update queue design Package 2 section from stub → design+plan pointers

- [ ] **Step 1: Docs + qualification tests**

- [ ] **Step 2: Full verification**

```bash
PYTHONPATH=src /opt/homebrew/bin/python3 -m unittest \
  tests.test_omlx_thinking_measure \
  tests.test_harness_lifecycle \
  tests.test_stage_two_inference_engine -q
```

- [ ] **Step 3: Commit**

```bash
git commit -m "$(cat <<'EOF'
Document Package 2 oMLX thinking-measure Gate A and pin-confirm checklist.

EOF
)"
```

---

## Spec coverage

| Design requirement | Task |
|---|---|
| Thinking-aware preflight budget | 1 |
| Failure-class distinction | 1, 3 |
| oMLX 0.5.2 pin + suite | 2 |
| Lifecycle via 1a | 3 |
| Honest lifecycle actions | 3 |
| Qualification / docs | 4 |
| No live / no Stage 2 retarget | Global |

## Placeholder scan

Assumes design open-question option 1 (harness chat path). If Jason selects external-bench-first, revise Tasks 2–3 before implementation.

---

## Execution handoff

Plan: `docs/superpowers/plans/2026-07-22-package-2-omlx-thinking-measure-gate-a.md`.

Design open question locked to option 1 (harness chat path).

**Two execution options:**

1. **Subagent-Driven (recommended)**  
2. **Inline Execution**

Which approach?
