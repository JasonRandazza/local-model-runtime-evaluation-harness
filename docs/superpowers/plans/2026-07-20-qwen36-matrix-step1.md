# Qwen 3.6 Matrix + Osaurus-Native Role (Step 1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add optional `osaurus_native` family-quant role, fix matrix report quant order, and ship a Qwen3.6-35B-A3B 3×3 campaign (MXFP4 / oQ4 / OptiQ-4bit) that dry-configs and unit-tests cleanly.

**Architecture:** Extend family JSON with optional `role`; annotate Gemma/Ornith JANG; add Qwen family + nine cells + campaign; derive report rows from campaign cell order.

**Tech Stack:** Python 3 stdlib, existing `matrix_config` / `lmre-matrix`, `unittest`.

## Global Constraints

- Spec: `docs/superpowers/specs/2026-07-20-qwen36-matrix-osaurus-native-design.md`
- Suite: `suites/gemma-matrix-v1.json`; screen depth unchanged
- Ports: Osaurus 1337, oMLX 8100, OptiQ 8080
- Cell ids: `qwen_<quant>__<server>`
- Incomplete HF: dry-config `artifact_missing`; live → `N/A` — do not invent weights
- Unit tests: fakes only; no live endpoints
- No preference/RAG/overhead recipes, Stage 2B, plugin, Approach 3
- Only create git commits when the user explicitly asks

---

## File Structure

| File | Responsibility |
|------|----------------|
| `matrix_config.py` | Optional `role` on `FamilyQuant` |
| `matrix_runner.py` | Quant order from campaign cells |
| `families/gemma-4-12b-qat.json` / `ornith-35b.json` | Annotate JANG with `role` |
| `families/qwen36-35b-a3b.json` | Qwen allowlist |
| `qwen36-35b-a3b-campaign.json` | Nine-cell campaign |
| `cells/qwen_*.json` | Nine cells |
| `omlx-roots/qwen_*/README.md` | Symlink instructions |
| `docs/matrix.md` | Qwen + Osaurus native JANG/MXFP |
| `tests/test_matrix_*.py` | Role, Qwen, report order |

---

### Task 1: Optional `osaurus_native` role

**Files:**
- Modify: `src/local_model_runtime_evaluation/matrix_config.py`
- Modify: `config/matrix/families/gemma-4-12b-qat.json`
- Modify: `config/matrix/families/ornith-35b.json`
- Modify: `tests/test_matrix_config.py`

- [ ] **Step 1:** Allow required `{artifact_path, model_ids}` plus optional `role`; only `"osaurus_native"` accepted; extend `FamilyQuant.role: str | None`
- [ ] **Step 2:** Annotate Gemma `jang_4m` and Ornith `ornith_jang_4m`
- [ ] **Step 3:** Tests for role present/absent/reject unknown
- [ ] **Step 4:** Run `tests.test_matrix_config` — expect PASS

### Task 2: Report quant order

**Files:**
- Modify: `src/local_model_runtime_evaluation/matrix_runner.py`
- Modify: `tests/test_matrix_metrics.py`

- [ ] **Step 1:** Replace `QUANT_ORDER` with helper that preserves first-seen quant order from `raw["cells"]`
- [ ] **Step 2:** Test that a Qwen-ordered raw report lists `qwen_mxfp4` before empty Gemma rows disappear
- [ ] **Step 3:** Run `tests.test_matrix_metrics` — expect PASS

### Task 3: Qwen family + cells + campaign

**Files:**
- Create: family, campaign, nine cells, three omlx-roots READMEs

- [ ] **Step 1:** Write `qwen36-35b-a3b.json` with pinned paths and allowlists
- [ ] **Step 2:** Write nine cells (Ornith argv patterns)
- [ ] **Step 3:** Write campaign JSON
- [ ] **Step 4:** Write omlx-roots READMEs
- [ ] **Step 5:** Tests for family load + nine cells + campaign; CLI dry-config test
- [ ] **Step 6:** Run config + cli tests — expect PASS

### Task 4: Docs + verification

**Files:**
- Modify: `docs/matrix.md`

- [ ] **Step 1:** Document Qwen campaign, `osaurus_native` (JANG or MXFP), HF prep, later lanes, Stage 2B frozen
- [ ] **Step 2:** Run unit suites + dry-config for Gemma, Ornith, Qwen

## Self-Review

1. Spec coverage: role, Qwen 3×3, report order, docs, non-live — each has a task
2. No placeholders
3. Gemma/Ornith behavior unchanged except role annotation + report order for non-Gemma families
