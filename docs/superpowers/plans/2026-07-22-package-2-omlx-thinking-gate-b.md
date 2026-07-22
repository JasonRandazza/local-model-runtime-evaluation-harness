# Package 2 Gate B Development Plan — oMLX Thinking Measure

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build Package 2 **Gate B readiness** (fail-closed identity + auth + lifecycle mode + non-live check script) so a later, separately authorized live thinking-measure cohort can run on oMLX `0.5.2` — without issuing thinking POSTs, creating run IDs, or reclaiming Jason’s current multi-model `:8100` pool in this plan’s default path.

**Architecture:** Extend Gate A pin/runner with (1) locked model id + auth, (2) an explicit ownership mode (`dedicated_serve` recommended vs `attach_pool`), (3) a read-only Gate B check CLI mirroring Stage 2’s `gate_b_check` shape but for oMLX thinking-measure, and (4) fake-only tests. Live smoke remains a **separate** authorization after Gate B reports ready.

**Tech Stack:** Python 3, existing `ThinkingMeasureRunner` / `LifecycleController`, matrix local API key pattern (`lmre-matrix-local`). Prefer `/opt/homebrew/bin/python3`. Plugin `0.3.0` unchanged.

## Global Constraints

- Design: `docs/superpowers/specs/2026-07-22-package-2-omlx-thinking-measure-design.md`
- Gate A: landed (`ThinkingMeasureRunner`, pin, suite, qualify helpers)
- Pin-confirm evidence: `docs/superpowers/notes/2026-07-22-package-2-omlx-052-pin-confirm-evidence.md`
- oMLX **`0.5.2` confirmed on disk** (2026-07-22).
- Do **not** POST thinking smoke / create run IDs / manifests in this plan.
- Do **not** run `omlX stop` against the observed multi-model pool unless Jason explicitly authorizes reclaim in-session.
- Do **not** retarget Stage 2 OptiQ or mix sealed `005`/`006` evidence.
- Prefer `/opt/homebrew/bin/python3`. No `config/matrix/omlx-roots/**` commits.

## Decision required before Task 1 coding (Jason)

**Ownership mode for Gate B+ live:**

1. **`dedicated_serve` (recommended)** — harness starts a single-model `omlX serve --model-dir … --port 8100` via Slice 1a; requires port free first (operator stops pool or uses another port — keep **8100** locked unless design revises).
2. **`attach_pool`** — observe-only attach to existing multi-model server; never `omlX stop`; verify exact model id in inventory; lifecycle_actions may stay 0 for attach.

**Model id for binding:**

- A. `Qwen3.6-35B-A3B-OptiQ-4bit` (**selected** — comparable Qwen line; present in inventory)
- B. `ThinkingCap-Qwen3.6-27B-OptiQ-4bit` (**rejected** — OptiQ-specific variation; not built like the other Qwen models under test; not useful for comparison)

**Jason decisions (2026-07-22):**

- Ownership: **`dedicated_serve`**
- Model id: **`Qwen3.6-35B-A3B-OptiQ-4bit`**
- ThinkingCap explicitly out of scope for Package 2 comparison work.

## File map

| Area | Files |
|---|---|
| Pin refresh | `config/omlx-pins/omlx-0.5.2-thinking-r1.json`, `omlx_thinking_pin.py` |
| Auth transport | Extend runner or add `omlx_thinking_transport.py` (Bearer matrix key; never log key) |
| Gate B check | Create `src/local_model_runtime_evaluation/omlx_thinking_gate_b_check.py` + `bin/lmre-omlx-thinking-gate-b-check` |
| Docs | Update pin-confirm checklist checkboxes; `docs/architecture.md`; optional `docs/package-2-omlx-thinking-gate-b.md` |
| Tests | Fake-only Gate B check + pin loader + transport auth header tests |

---

### Task 1: Lock pin fields (model id, start_command, ownership mode, auth)

**Files:** pin JSON + `omlx_thinking_pin.py` + tests

**Interfaces:**
- Add required fields: `model_id`, `ownership_mode` (`dedicated_serve` \| `attach_pool`), `api_key_source` (`matrix_local` only for Gate B)
- Refresh `start_command` for dedicated mode with `--model-dir` when mode is dedicated
- Fail-closed loader

- [ ] **Step 1:** Apply Jason’s ownership + model decisions (or defaults above)
- [ ] **Step 2:** TDD loader + commit

```bash
git commit -m "$(cat <<'EOF'
Lock oMLX thinking pin model identity and ownership mode for Gate B.

EOF
)"
```

---

### Task 2: Authenticated loopback transport (no live POSTs in tests)

**Files:** transport helper + runner wiring + tests

**Interfaces:**
- Chat/completions + GET models with `Authorization: Bearer lmre-matrix-local` (or Credential injectable)
- Never include API key in evidence/events
- Fake transport remains default in unit tests

- [ ] **Step 1–4: TDD + commit**

```bash
git commit -m "$(cat <<'EOF'
Add authenticated oMLX thinking transport for Gate B readiness.

EOF
)"
```

---

### Task 3: Non-live Gate B check CLI

**Files:** `omlx_thinking_gate_b_check.py`, bin wrapper, tests

**Checks (GET / identity only):**
- oMLX version == `0.5.2`
- Port / ownership mode consistent (dedicated: port free before start OR exact single serve; attach: pool present, exact model id listed)
- Health status healthy/ok
- Inventory contains exact `model_id`
- Pin file hashes / start_command match mode
- Report `READY_FOR_LIVE_AUTHORIZATION` or fail-closed codes
- **Never** POST; never create run IDs

- [ ] **Step 1–4: TDD with fakes + commit**

```bash
git commit -m "$(cat <<'EOF'
Add Package 2 oMLX thinking Gate B readiness check.

EOF
)"
```

---

### Task 4: Docs + Gate B status surface

**Files:**
- `docs/package-2-omlx-thinking-gate-b.md` (`GATE_B_READY` / not live)
- Update architecture + pin-confirm checklist with completed measurements
- Point queue design at this Gate B plan

- [ ] **Step 1:** Docs
- [ ] **Step 2:** Verification suite for Package 2 + harness lifecycle
- [ ] **Step 3:** Commit

```bash
git commit -m "$(cat <<'EOF'
Document Package 2 oMLX thinking Gate B readiness surface.

EOF
)"
```

---

## Explicitly deferred (not this plan)

- Live thinking POSTs / smoke cohort  
- Run ID / manifest creation  
- Reclaiming Jason’s multi-model pool without explicit approval  
- Stage 2 OptiQ changes  
- Wrapping oMLX external-bench CLI  

## Spec coverage

| Need | Task |
|---|---|
| Pin 0.5.2 confirmed | Evidence note + Task 1 |
| Model + ownership lock | Task 1 (needs Jason A/B + 1/2) |
| Auth for /v1/models and chat | Task 2 |
| Gate B ready report | Task 3 |
| Docs | Task 4 |

---

## Execution handoff

**Locked before Task 1:** ownership `dedicated_serve`; model
`Qwen3.6-35B-A3B-OptiQ-4bit` (ThinkingCap rejected as OptiQ-specific / non-comparable).

**Two execution options:**

1. **Subagent-Driven (recommended)**  
2. **Inline Execution**

Which approach?
