# Multi-Family RAG and Overhead (Step 3) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `lmre-rag` and `lmre-overhead` family-first with checked-in Gemma defaults, Ornith recipes (four RAG cells; two overhead pairs), and `--family` override.

**Architecture:** Mirror preference Step 2: per-lane `defaults.json` + recipe map; resolve `--family` → defaults → fail; validate cells via matrix `load_family` / `Cell.load`. Overhead adds Ornith pair JSON files with allowlisted `routed_model_id` strings.

**Tech Stack:** Python 3 stdlib (≥3.10; `/opt/homebrew/bin/python3`), existing rag/overhead modules, `unittest`.

## Global Constraints

- Spec: `docs/superpowers/specs/2026-07-20-multi-family-rag-overhead-design.md`
- Umbrella Step 3 only; preference Step 2 may already be uncommitted on the tree — do not revert it
- Suite/corpus unchanged (`gemma-rag-oracle-v1`, keyword modes as today; overhead suite `gemma-matrix-v1`)
- Default family: `gemma-4-12b-qat` in checked-in defaults JSON
- Gemma RAG cells (4): `jang_4m__osaurus`, `oq4_fp16__omlx`, `optiq_4bit__omlx`, `optiq_4bit__optiq`
- Ornith RAG cells (4): `ornith_jang_4m__omlx`, `ornith_oq4__omlx`, `ornith_optiq_4bit__omlx`, `ornith_optiq_4bit__optiq`
- Ornith overhead pairs: `ornith_oq4`, `ornith_optiq_4bit` only (no third pair)
- Routed ids must be on Ornith family `model_ids` allowlists; docs say pin live inventory before authorize
- Unit tests: fakes only; no live endpoints
- Do not implement Qwen, Stage 2B, plugin, or live RAG/overhead
- Only create git commits when the user explicitly asks
- PATH: `PATH="/Users/jrazz/.local/bin:/opt/homebrew/bin:$PATH"` for `./bin/lmre-*`

---

## File Structure

| File | Responsibility |
|------|----------------|
| `config/rag/defaults.json` | Gemma default family + four cells |
| `config/rag/family-cells.json` | Gemma + Ornith cell recipes |
| `rag_config.py` | Loaders + `resolve_rag_selection` |
| `rag_cli.py` / `rag_collect.py` | `--family`; drop `DEFAULT_CELL_FAMILY` |
| `config/overhead/defaults.json` | Gemma default + pair ids |
| `config/overhead/family-pairs.json` | Family → pair id list |
| `config/overhead/pairs/ornith_oq4.json` | New Ornith oQ4 pair |
| `config/overhead/pairs/ornith_optiq_4bit.json` | New Ornith OptiQ pair |
| `overhead_config.py` | Loaders + `resolve_overhead_selection` |
| `overhead_cli.py` / `overhead_runner.py` | `--family`; pass `ModelFamily` |
| `docs/rag.md`, `docs/overhead.md` | Family-first docs |
| Tests | `test_rag_*`, `test_overhead_*` |

---

### Task 1: RAG defaults + resolver + CLI wiring

**Files:**
- Create: `config/rag/defaults.json`, `config/rag/family-cells.json`
- Modify: `src/local_model_runtime_evaluation/rag_config.py`
- Modify: `src/local_model_runtime_evaluation/rag_cli.py`
- Modify: `src/local_model_runtime_evaluation/rag_collect.py`
- Modify: `tests/test_rag_config.py`, `tests/test_rag_cli.py`, `tests/test_rag_collect.py` as needed

**Interfaces:**
- Produces (in `rag_config.py`):
  - `DEFAULT_RAG_ROOT = REPOSITORY_ROOT / "config" / "rag"`
  - `@dataclass(frozen=True) class RagDefaults` — `family_id: str`, `cells: tuple[str, ...]`
  - `@dataclass(frozen=True) class RagSelection` — `family_id: str`, `cells: tuple[str, ...]`
  - `load_rag_defaults(...)`, `load_rag_family_cell_recipes(...)`
  - `resolve_rag_selection(*, family_id: str | None, cells: tuple[str, ...] | None, ...) -> RagSelection`
- Resolution rules: same as preference (`family is required` / `preference family recipe is missing` → use RAG-worded errors: `"family is required"`, `"rag family recipe is missing"`, `"cells filter is empty"`)
- Gemma defaults cells **exact match** recipe order
- CLI: `--family`; dry-config includes `family_id`; remove `DEFAULT_CELL_FAMILY`
- `run_collect` accepts `family_id` and loads `load_family(family_id)` for cells; optional persist `family_id` in run metadata if raw.json exists today

**`family-cells.json` / `defaults.json`:** same four-cell lists as preference for Gemma and Ornith.

- [ ] **Step 1: Failing tests** — defaults load (4 cells, includes `optiq_4bit__omlx`); resolve Ornith; dry-config `family_id`; reject ornith cell under gemma family

- [ ] **Step 2: Run — expect FAIL**

```bash
PYTHONPATH=src /opt/homebrew/bin/python3 -m unittest tests.test_rag_config tests.test_rag_cli -v
```

- [ ] **Step 3: Implement config + wire CLI/collect**

- [ ] **Step 4: RAG unit tests + dry-config PASS**

```bash
PYTHONPATH=src /opt/homebrew/bin/python3 -m unittest \
  tests.test_rag_retrieve tests.test_rag_config tests.test_rag_prompt \
  tests.test_rag_score tests.test_rag_collect tests.test_rag_cli -q
PATH="/Users/jrazz/.local/bin:/opt/homebrew/bin:$PATH" ./bin/lmre-rag --dry-config
PATH="/Users/jrazz/.local/bin:/opt/homebrew/bin:$PATH" ./bin/lmre-rag --dry-config --family ornith-35b
```

Expected: Gemma dry-config 4 cells + `family_id` `gemma-4-12b-qat`; Ornith 4 `ornith_*` cells.

- [ ] **Step 5: Commit only if user asked**

---

### Task 2: Overhead defaults + Ornith pairs + resolver + CLI wiring

**Files:**
- Create: `config/overhead/defaults.json`, `config/overhead/family-pairs.json`
- Create: `config/overhead/pairs/ornith_oq4.json`, `config/overhead/pairs/ornith_optiq_4bit.json`
- Modify: `src/local_model_runtime_evaluation/overhead_config.py`
- Modify: `src/local_model_runtime_evaluation/overhead_cli.py`
- Modify: `src/local_model_runtime_evaluation/overhead_runner.py`
- Modify: `tests/test_overhead_config.py`, `tests/test_overhead_cli.py` (create CLI tests if missing)

**Interfaces:**
- Produces:
  - `@dataclass(frozen=True) class OverheadDefaults` — `family_id: str`, `pairs: tuple[str, ...]`
  - `@dataclass(frozen=True) class OverheadSelection` — `family_id: str`, `pairs: tuple[str, ...]`
  - `load_overhead_defaults`, `load_family_pair_recipes`, `resolve_overhead_selection`
- When `--pairs` omitted → use recipe for resolved family (not always Gemma `DEFAULT_PAIR_IDS`)
- When `--pairs` set → those ids must be ⊆ family’s recipe (else `OverheadError`)
- Remove `DEFAULT_CELL_FAMILY` from cli/runner; `family = load_family(selection.family_id)`
- Dry-config includes `family_id`

**Ornith pair JSON (exact routed ids from family allowlist):**

`ornith_oq4.json`:

```json
{
  "pair_id": "ornith_oq4",
  "direct_cell_id": "ornith_oq4__omlx",
  "backend_cell_id": "ornith_oq4__omlx",
  "routed_base_url": "http://127.0.0.1:1337/v1",
  "routed_model_id": "omlx/Ornith-1.0-35B-MLX-oQ4"
}
```

`ornith_optiq_4bit.json`:

```json
{
  "pair_id": "ornith_optiq_4bit",
  "direct_cell_id": "ornith_optiq_4bit__optiq",
  "backend_cell_id": "ornith_optiq_4bit__optiq",
  "routed_base_url": "http://127.0.0.1:1337/v1",
  "routed_model_id": "optiq//Users/jrazz/.cache/huggingface/hub/mlx-community/Ornith-1.0-35B-OptiQ-4bit:no-think"
}
```

**`family-pairs.json`:**

```json
{
  "gemma-4-12b-qat": ["oq4_fp16", "optiq_4bit"],
  "ornith-35b": ["ornith_oq4", "ornith_optiq_4bit"]
}
```

- [ ] **Step 1: Failing tests** — load Ornith pairs; resolve Ornith selection; dry-config family_id; Gemma default still two pairs

- [ ] **Step 2: Run — expect FAIL**

```bash
PYTHONPATH=src /opt/homebrew/bin/python3 -m unittest tests.test_overhead_config -v
```

- [ ] **Step 3: Implement**

- [ ] **Step 4: Overhead tests + dry-config PASS**

```bash
PYTHONPATH=src /opt/homebrew/bin/python3 -m unittest tests.test_overhead_config tests.test_overhead_cli -q
PATH="/Users/jrazz/.local/bin:/opt/homebrew/bin:$PATH" ./bin/lmre-overhead --dry-config
PATH="/Users/jrazz/.local/bin:/opt/homebrew/bin:$PATH" ./bin/lmre-overhead --dry-config --family ornith-35b
```

- [ ] **Step 5: Commit only if user asked**

---

### Task 3: Docs

**Files:**
- Modify: `docs/rag.md`, `docs/overhead.md`
- CLI help strings if not already updated in Tasks 1–2

**Docs must include:** family-first; defaults paths; Gemma four-cell RAG; Ornith `--family`; overhead Ornith pairs; pin `routed_model_id` from live inventory before authorize; Stage 2B frozen; Qwen later; no live authorize.

- [ ] **Step 1: Update docs**

- [ ] **Step 2: Re-run RAG + overhead unit suites and all four dry-config commands from Tasks 1–2**

- [ ] **Step 3: Commit only if user asked**

---

## Spec Coverage Check

| Spec item | Task |
|-----------|------|
| RAG defaults + family-cells + `--family` | 1 |
| Gemma four-cell RAG; Ornith four | 1 |
| Overhead defaults + family-pairs + Ornith pair files | 2 |
| Overhead `--family` + dry-config | 2 |
| Docs | 3 |
| No live / Qwen / third pair / Stage 2B | constraints |

---

## Execution Handoff

Plan complete for **Step 3 (RAG + overhead)**. After implementation, batch-commit with preference Step 2 when Jason requests.
