# Multi-Family Ornith Matrix (Step 1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generalize matrix config to family registries and add a full Ornith 35B 3×3 campaign (9 cells) that dry-configs and unit-tests cleanly; Gemma behavior unchanged.

**Architecture:** Load per-family JSON allowlists (`config/matrix/families/*.json`). Campaign gains `family_id`. Cells keep `quant__server` ids with Ornith-prefixed quants. Prefer registry validation over hard-coded `QUANT_CONTROL_ARTIFACTS`.

**Tech Stack:** Python 3 stdlib, existing `matrix_config` / `lmre-matrix`, `unittest`.

## Global Constraints

- Spec: `docs/superpowers/specs/2026-07-20-multi-family-ornith-first-design.md` (Step 1 only)
- Suite: `suites/gemma-matrix-v1.json`; screen depth unchanged
- Ports: Osaurus 1337, oMLX 8100, OptiQ 8080
- Cell ids: `ornith_<quant>__<server>` (no collision with Gemma)
- Incomplete HF snapshots: configs may pin intended paths; dry-config reports missing artifacts; live → `N/A` — do not invent weights
- Unit tests: fakes only; no live endpoints
- Do not implement preference/RAG/overhead hooks (Steps 2–3), Qwen, Approach 3, Stage 2B, plugin
- Only create git commits when the user explicitly asks

---

## File Structure

| File | Responsibility |
|------|----------------|
| `config/matrix/families/gemma-4-12b-qat.json` | Migrated Gemma allowlist |
| `config/matrix/families/ornith-35b.json` | Ornith allowlist |
| `matrix_config.py` | Load family; validate cells against campaign family |
| `config/matrix/gemma-4-12b-qat-campaign.json` | Add `family_id` |
| `config/matrix/ornith-35b-campaign.json` | New 9-cell campaign |
| `config/matrix/cells/ornith_*.json` | Nine Ornith cells |
| `config/matrix/omlx-roots/ornith_oq4/` | oMLX model-dir layout (symlink/README when artifact exists) |
| `docs/matrix.md` | Multi-family + Ornith campaign + download prep |
| `tests/test_matrix_config.py` (+ optional `test_matrix_family.py`) | Registry + Ornith + Gemma regression |

---

### Task 1: Family registry + Gemma migration

**Files:**
- Create: `config/matrix/families/gemma-4-12b-qat.json`
- Modify: `src/local_model_runtime_evaluation/matrix_config.py`
- Modify: `tests/test_matrix_config.py`

**Interfaces:**
- Produces:
  - `@dataclass(frozen=True) class FamilyQuant` — `quant: str`, `artifact_path: str`, `model_ids: tuple[str, ...]`
  - `@dataclass(frozen=True) class ModelFamily` — `family_id: str`, `quants: dict[str, FamilyQuant]`
  - `ModelFamily.load(path: Path) -> ModelFamily`
  - `load_family(family_id: str, *, families_root: Path | None = None) -> ModelFamily`
  - `DEFAULT_FAMILIES_ROOT = REPOSITORY_ROOT / "config" / "matrix" / "families"`
  - Validation helpers take `ModelFamily` (or quant map) instead of global `QUANT_CONTROL_ARTIFACTS`
- Gemma JSON must contain today’s exact `artifact_path` / `model_ids` for `jang_4m`, `oq4_fp16`, `optiq_4bit` (copy from current `QUANT_CONTROL_ARTIFACTS`)
- Keep module-level `QUANT_CONTROL_ARTIFACTS` only as a deprecated alias **or** remove and update all call sites — prefer remove after family load is wired through `Cell` (Task 2 may finish Cell wiring; Task 1 can load family + unit-test `ModelFamily` in isolation)

**Gemma family JSON shape:**

```json
{
  "family_id": "gemma-4-12b-qat",
  "quants": {
    "jang_4m": {
      "artifact_path": "/Users/jrazz/MLXModels/OsaurusAI/gemma-4-12B-it-qat-JANG_4M",
      "model_ids": ["gemma-4-12b-it-qat-jang_4m", "/Users/jrazz/MLXModels/OsaurusAI/gemma-4-12B-it-qat-JANG_4M"]
    },
    "oq4_fp16": { "...": "..." },
    "optiq_4bit": { "...": "..." }
  }
}
```

- [ ] **Step 1: Write failing tests** for `ModelFamily.load` / `load_family("gemma-4-12b-qat")` asserting known artifact paths

- [ ] **Step 2: Run — expect FAIL**

`PYTHONPATH=src python3 -m unittest tests.test_matrix_config -v`

- [ ] **Step 3: Implement family JSON + loader**

- [ ] **Step 4: Run — expect PASS** for new tests (existing Cell tests may still use old globals until Task 2)

- [ ] **Step 5: Commit only if user asked**

---

### Task 2: Campaign `family_id` + Cell validation via family

**Files:**
- Modify: `src/local_model_runtime_evaluation/matrix_config.py` (`Campaign`, `Cell`)
- Modify: `config/matrix/gemma-4-12b-qat-campaign.json` — add `"family_id": "gemma-4-12b-qat"`
- Modify: `tests/test_matrix_config.py`
- Modify: any CLI dry-config that assumes campaign_id hardcode

**Interfaces:**
- `CAMPAIGN_FIELDS` gains `family_id`
- `Campaign` gains `family_id: str` and `family: ModelFamily` (loaded at `Campaign.load`)
- Remove hard-coded `campaign_id != "gemma-4-12b-qat-3x3"` rejection; instead require non-empty `campaign_id` string and valid `family_id` file
- `Cell.load` stays path-based; add `Cell.load_for_family(path, family: ModelFamily) -> Cell` **or** pass family into validation:
  - Recommended: `Cell.load(path, *, family: ModelFamily)` — quant must be in `family.quants`; artifact/model_id must match that quant entry
- `ALLOWED_QUANTS` becomes family-specific (no global Gemma-only set)
- Existing Gemma cells must still load when validated with gemma family

- [ ] **Step 1: Write failing tests**

```python
def test_gemma_campaign_loads_with_family_id(self) -> None:
    campaign = Campaign.load(ROOT / "config/matrix/gemma-4-12b-qat-campaign.json")
    self.assertEqual(campaign.family_id, "gemma-4-12b-qat")
    self.assertEqual(campaign.campaign_id, "gemma-4-12b-qat-3x3")

def test_cell_rejects_ornith_quant_on_gemma_family(self) -> None:
    # temp cell with quant ornith_jang_4m + gemma family → MatrixError
```

- [ ] **Step 2: Run — expect FAIL**

- [ ] **Step 3: Implement** — update `matrix_runner` / CLI call sites that `Cell.load` / `Campaign.load` if signatures change

- [ ] **Step 4: Full Gemma matrix config + runner unit tests PASS**

- [ ] **Step 5: Commit only if user asked**

---

### Task 3: Ornith family, 9 cells, campaign, oMLX roots

**Files:**
- Create: `config/matrix/families/ornith-35b.json`
- Create: `config/matrix/ornith-35b-campaign.json`
- Create: nine `config/matrix/cells/ornith_*.json`
- Create: `config/matrix/omlx-roots/ornith_oq4/` (README or symlink pattern like Gemma `oq4_fp16`)
- Modify: `tests/test_matrix_config.py`

**Quant keys & cell ids (exact):**

| Quant | Native cell_id examples |
|-------|-------------------------|
| `ornith_jang_4m` | `ornith_jang_4m__osaurus`, `__omlx`, `__optiq` |
| `ornith_oq4` | `ornith_oq4__osaurus`, `__omlx`, `__optiq` |
| `ornith_optiq_4bit` | `ornith_optiq_4bit__osaurus`, `__omlx`, `__optiq` |

**Pinned paths (intended; may be incomplete on disk):**

- JANG artifact: `/Users/jrazz/MLXModels/OsaurusAI/Ornith-1.0-35B-JANG_4M`
- JANG Osaurus `model_id`: `ornith-1.0-35b-jang_4m` (from live inventory)
- oQ4 artifact: `/Users/jrazz/.cache/huggingface/hub/georgeis55/Ornith-1.0-35B-MLX-oQ4` (or `models--georgeis55--…/snapshots/<rev>` once present — pick one layout and document; prefer flat `hub/georgeis55/...` if/when huggingface-cli materializes it)
- OptiQ artifact: `/Users/jrazz/.cache/huggingface/hub/mlx-community/Ornith-1.0-35B-OptiQ-4bit`
- OptiQ native `model_id`: `<artifact_path>:no-think`

**Start commands:** Mirror Gemma cells (osaurus serve/stop; omlX `--model-dir` → `config/matrix/omlx-roots/ornith_oq4`; optiq serve with `--no-anthropic --no-responses --no-auth`).

**Campaign:**

```json
{
  "campaign_id": "ornith-35b-3x3",
  "family_id": "ornith-35b",
  "suite_path": "suites/gemma-matrix-v1.json",
  "results_root": "results/matrix",
  "memory_floor_percent": 20,
  "ready_timeout_seconds": 300,
  "request_timeout_seconds": 180,
  "on_cell_failure": "continue",
  "ports": {"osaurus": 1337, "omlx": 8100, "optiq": 8080},
  "cells": [ /* nine ornith_*.json paths */ ]
}
```

(Slightly higher ready/request timeouts than Gemma for 35B — adjust if Jason prefers identical 180/120.)

- [ ] **Step 1: Write failing tests** — `Campaign.load(ornith…)` returns 9 cells; each `Cell.load(..., family=ornith)` succeeds for config shape

- [ ] **Step 2: Run — expect FAIL**

- [ ] **Step 3: Implement JSON + oMLX root stub**

- [ ] **Step 4: `lmre-matrix --dry-config --campaign config/matrix/ornith-35b-campaign.json`** succeeds structurally; if implementing artifact-existence reporting, missing HF paths appear as warnings in JSON (optional but recommended: `"artifact_missing": [...]`)

- [ ] **Step 5: Commit only if user asked**

---

### Task 4: Docs + CLI dry-config polish

**Files:**
- Modify: `docs/matrix.md`
- Modify: `src/local_model_runtime_evaluation/matrix_runner.py` (dry-config: include `family_id`, list missing artifacts if easy)
- Modify: `tests/test_matrix_cli.py` if present

**Docs must include:** multi-family overview; Ornith campaign command; download/complete HF snapshots before live; note Steps 2–3 (preference/RAG/overhead) and Qwen / Approach 3 as later; Stage 2B frozen.

- [ ] **Step 1: Failing test** for dry-config containing `family_id`

- [ ] **Step 2: Implement docs + dry-config fields**

- [ ] **Step 3: Full suite**

```bash
PYTHONPATH=src python3 -m unittest tests.test_matrix_config tests.test_matrix_cli tests.test_matrix_runner -q
./bin/lmre-matrix --dry-config --campaign config/matrix/gemma-4-12b-qat-campaign.json
./bin/lmre-matrix --dry-config --campaign config/matrix/ornith-35b-campaign.json
```

- [ ] **Step 4: Commit only if user asked**

---

## Follow-on Plans (Not This File)

| Step | Plan (write after Step 1 ships) |
|------|----------------------------------|
| 2 | Preference: Ornith PASS `--cells` + docs |
| 3 | RAG/overhead: optional Ornith cells/pairs + docs |
| Later | Qwen 3.6 family campaign |
| Later | Approach 3 free-form cells |

---

## Spec Coverage Check (Step 1)

| Spec item | Task |
|-----------|------|
| Family registry; Gemma migration | 1–2 |
| Campaign `family_id`; drop Gemma-only campaign_id lock | 2 |
| Ornith 9 cells + campaign | 3 |
| Suite/depth reuse | 3 |
| Incomplete artifact handling | 3–4 |
| Docs; no live authorize | 4 |
| No Steps 2–3 / Qwen / Approach 3 / Stage 2B | constraints |

---

## Execution Handoff

Plan complete for **Step 1 (matrix)**. Preference/RAG/overhead remain separate follow-on plans.
