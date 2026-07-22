# Slice 1b OptiQ 0.4.2 Pin + Gemma Profile Revision 3 Gate A Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Land Package 1 / Slice 1b Gate A only: an approved `gemma-4-12b-optiq-4bit` revision **`3`** runtime profile pinned to **`mlx-optiq` / `optiq` `0.4.2`**, with fail-closed loader tests and a documented pin-confirm checklist — without upgrading OptiQ on disk, without live Gate B, without Slice 1c unattended wiring, and without invalidating sealed `005`/`006` on revision `2` / `0.3.3`.

**Architecture:** Extend `stage_two_profiles.py` with a dedicated Gemma revision-3 parser (mirror `_parse_gemma_revision_two`) that requires `runtime_version == "0.4.2"` and a new package-version constant map. Keep revision `1`/`2` parsers and on-disk profiles unchanged as rollback. Do **not** add a new live-authorizing manifest schema or comparison class in this plan — only name the future classes for later authorization. Host identity probes against a real `0.4.2` install remain pin-confirm / Gate B work.

**Tech Stack:** Python 3 stdlib, `unittest` via `PYTHONPATH=src /opt/homebrew/bin/python3 -m unittest …`, existing Stage 2 profile registry. Plugin `0.3.0` unchanged.

## Global Constraints

- Spec: `docs/superpowers/specs/2026-07-21-stack-review-gate-a-queue-design.md` (Slice 1b section)
- Implications note: `docs/superpowers/notes/2026-07-21-mlx-optiq-0.3.3-to-0.4.2-implications.md`
- Do **not** implement slices 1a extras, 1c, or Package 2 in this plan (1a already landed).
- Do **not** run Gate B, create run IDs/manifests, upgrade OptiQ/`mlx-optiq` on disk, contact live OptiQ/Osaurus for POSTs, or rebuild plugin `0.3.0`.
- Do **not** authorize live inference under revision `3` — no new schema enum / comparison allowlist that would let a coordinator start a live cohort.
- Preserve revision `2` / `0.3.3` profiles, launchers (`bin/lmre-stage2-operator-serve-gemma`), and sealed `005`/`006` as rollback.
- Prefer `/opt/homebrew/bin/python3`. No commits of `config/matrix/omlx-roots/**`.
- Current disk probe (2026-07-21): venv still reports `mlx-optiq==0.3.3` — Gate A must not change that.

## Provisional pin policy (Gate A)

Because `0.4.2` is **not** installed on disk yet, Gate A locks **contract constants** that pin-confirm must re-measure after a separately authorized upgrade:

| Field | Gate A provisional value | Pin-confirm action |
|---|---|---|
| `runtime_version` / `package_versions["mlx-optiq"]` | `"0.4.2"` | Confirm `importlib.metadata` after upgrade |
| `package_versions` mlx / mlx-lm / transformers | Provisional map in parser constants (clone r2 numbers until pin-confirm replaces) | Replace with exact post-upgrade versions |
| `runtime_executable` | Same path as r2: `/Users/jrazz/Dev/tools/mlx-optiq/.venv/bin/optiq` | Confirm path + hash after upgrade |
| Model repo / snapshot / artifact hashes / `model_revision` | Clone r2 values (weights may be unchanged; template sync is OptiQ-side) | Re-hash artifacts; re-check Hub revision |
| `routed_model_id` / direct identities | Clone r2 path-based `:no-think` IDs | Re-measure `GET /v1/models` after Google chat-template sync; rewrite profile if ID drifts |
| `service_ownership` / `provider_activation` | Keep `operator` / `operator_reconnect_required` until Slice 1c | 1c may change ownership |

**Named future live comparison classes (not authorized here):**

- Smoke: `gemma-optiq-042-operator-route-smoke`
- Benchmark: `gemma-optiq-042-operator-route-benchmark`

Do not add these to policy allowlists in this plan.

## File map

| Area | Files |
|---|---|
| Profile | Create `config/runtime-profiles/gemma-4-12b-optiq-4bit-r3.json` |
| Parser | Modify `src/local_model_runtime_evaluation/stage_two_profiles.py` |
| Tests | Modify `tests/test_stage_two_profile.py`; add mix-rejection coverage in factory/policy tests if a cheap hook exists without new live schema |
| Docs | Create `docs/superpowers/notes/2026-07-21-slice-1b-optiq-042-pin-confirm-checklist.md`; short pointer in `docs/architecture.md` + Slice 1b plan line in stack-review spec |
| Launchers | **Do not** change `bin/lmre-stage2-operator-serve-gemma` (stays 0.3.3 rollback). Optional note-only in checklist. |

---

### Task 1: Gemma revision-3 parser constants + fail-closed tests

**Files:**
- Modify: `src/local_model_runtime_evaluation/stage_two_profiles.py`
- Modify: `tests/test_stage_two_profile.py`

**Interfaces:**
- Dispatch: `profile_id == "gemma-4-12b-optiq-4bit" and revision == "3"` → `_parse_gemma_revision_three`
- Require `runtime_version == "0.4.2"` and `package_versions["mlx-optiq"] == "0.4.2"`
- Field set: same as revision 2 (`_REVISION_THREE_FIELDS` / current r2 field set — do not invent new keys in Gate A)
- Reject: r3 JSON with `0.3.3`; r3 with wrong package map; r3 with r2 serve argv drift if constants say otherwise
- Keep r1/r2 loaders green and unchanged in behavior

- [ ] **Step 1: Write failing tests**

Minimum cases:
1. Registry loads fixture/profile revision `3` → `runtime_version == "0.4.2"`
2. Mutated r3 with `runtime_version: "0.3.3"` → `RuntimeProfileError`
3. Mutated r3 with wrong `mlx-optiq` package version → error
4. Existing tests for revision `2` still pass unchanged

- [ ] **Step 2: Run — expect FAIL**

```bash
PYTHONPATH=src /opt/homebrew/bin/python3 -m unittest tests.test_stage_two_profile -v
```

- [ ] **Step 3: Implement `_parse_gemma_revision_three` + constants**

Clone `_parse_gemma_revision_two` structure; swap version pins to `0.4.2`. Provisional sibling package versions: start from r2 map (`mlx 0.32.0`, `mlx-lm 0.31.3`, `transformers 5.12.1`) unless pin-confirm note already records otherwise — document in module comment that pin-confirm must replace `_GEMMA_R3_PACKAGE_VERSIONS`.

- [ ] **Step 4: Re-run — expect PASS for parser tests that use temp fixtures** (committed r3 file may land in Task 2)

- [ ] **Step 5: Commit**

```bash
git commit -m "$(cat <<'EOF'
Add Gemma OptiQ profile revision 3 parser for mlx-optiq 0.4.2.

EOF
)"
```

---

### Task 2: Commit `gemma-4-12b-optiq-4bit-r3.json` + registry load test

**Files:**
- Create: `config/runtime-profiles/gemma-4-12b-optiq-4bit-r3.json`
- Modify: `tests/test_stage_two_profile.py`

**Interfaces:**
- On-disk profile: `revision: "3"`, `approved: true`, `runtime_version: "0.4.2"`, package map matching parser constants, model/route fields cloned from r2 until pin-confirm
- Registry `get("gemma-4-12b-optiq-4bit", "3")` returns the profile
- Registry still returns unique r2 for revision `"2"`

- [ ] **Step 1: Write failing registry test against missing r3 file**

- [ ] **Step 2: Create r3 JSON cloned from r2 with version/revision fields updated**

- [ ] **Step 3: Re-run profile tests — PASS**

- [ ] **Step 4: Commit**

```bash
git commit -m "$(cat <<'EOF'
Add gemma-4-12b-optiq-4bit revision 3 profile pin for OptiQ 0.4.2.

EOF
)"
```

---

### Task 3: Reject mixing r2-authorizing manifests with r3 profile identity

**Files:**
- Modify: whichever of `policy.py` / `stage_two_factory.py` / `stage_two_host.py` already binds schema → profile revision (inspect before coding)
- Modify: focused tests (`tests/test_stage_two_factory.py` and/or `tests/test_policy.py` / gate-b check tests)

**Interfaces:**
- Current live-authorizing Gemma contracts remain revision **`2`** / `0.3.3` only
- If a caller asks the factory/registry path to build a Stage 2 engine for an authorizing manifest (3.3.0 smoke / 3.4.0 benchmark) while forcing profile revision `3`, fail closed with a clear error (do not silently run)
- Conversely: loading profile r3 alone via registry remains allowed (Gate A)
- **Do not** add schema `3.5.0` or new comparison allowlists

- [ ] **Step 1: Inspect factory/policy binding; write the smallest failing mix-rejection test**

- [ ] **Step 2–4: TDD implement + PASS**

- [ ] **Step 5: Commit**

```bash
git commit -m "$(cat <<'EOF'
Reject pairing live Gemma manifests with OptiQ 0.4.2 profile revision 3.

EOF
)"
```

---

### Task 4: Pin-confirm checklist + architecture pointer

**Files:**
- Create: `docs/superpowers/notes/2026-07-21-slice-1b-optiq-042-pin-confirm-checklist.md`
- Modify: `docs/architecture.md` (one short Slice 1b Gate A landed / pin-confirm pending note)
- Modify: `docs/superpowers/specs/2026-07-21-stack-review-gate-a-queue-design.md` — one line under Slice 1b pointing at this plan

**Checklist must include (operator-owned, separately gated):**

1. Authorize and perform `mlx-optiq` upgrade to `0.4.2` in the pinned venv (not part of Gate A).
2. Record `optiq` path, file hash, and `package_versions` for mlx-optiq/mlx/mlx-lm/transformers.
3. Start OptiQ with the profile argv; confirm Lab closed; `GET /health` ok.
4. Capture exact `GET /v1/models` IDs (direct + after Osaurus reconnect); update `routed_model_id` / identities / rejected list if chat-template sync changed them.
5. Re-hash model artifacts; update profile constants + JSON if any drift.
6. Only then open a **separate** Gate A/B plan for new comparison classes `gemma-optiq-042-operator-route-smoke` / `gemma-optiq-042-operator-route-benchmark`.

- [ ] **Step 1: Write checklist + pointers**

- [ ] **Step 2: Full verification**

```bash
PYTHONPATH=src /opt/homebrew/bin/python3 -m unittest \
  tests.test_stage_two_profile \
  tests.test_stage_two_factory \
  tests.test_stage_two_inference_engine \
  tests.test_stage_two_benchmark_engine \
  tests.test_harness_lifecycle -q
```

Expected: OK

- [ ] **Step 3: Commit**

```bash
git commit -m "$(cat <<'EOF'
Document OptiQ 0.4.2 pin-confirm checklist for Slice 1b Gate A.

EOF
)"
```

---

## Spec coverage check

| Spec requirement | Task |
|---|---|
| OptiQ `0.4.2` + Gemma profile rev `3` | 1–2 |
| Re-resolve hashes/argv/routed ID (checklist; provisional clone) | 2, 4 |
| Distinct future comparison evidence names | Global + 4 |
| Profile loader + hash/argv fail-closed tests | 1–2 |
| Factory rejects mixing r2 manifests with 0.4.2 lifecycle | 3 |
| Pin-confirm checklist | 4 |
| Rollback r2 / 0.3.3 / sealed 005–006 | Global |
| No disk upgrade / no live auth | Global |

## Placeholder scan

No TBD implementation steps. Package/sibling versions and routed ID are **explicitly provisional** pending pin-confirm — that is intentional Gate A scope, not an unfinished task.

---

## Execution handoff

Plan saved to `docs/superpowers/plans/2026-07-21-slice-1b-optiq-042-pin-gate-a.md`.

**Two execution options:**

1. **Subagent-Driven (recommended)** — fresh subagent per task, review between tasks  
2. **Inline Execution** — execute in this session with checkpoints  

Which approach?
