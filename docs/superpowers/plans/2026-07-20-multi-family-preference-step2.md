# Multi-Family Preference (Step 2) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `lmre-preference` family-first with a checked-in Gemma default, four-cell recipes for Gemma and Ornith, and `--family` override — without silent Python-hardcoded family selection.

**Architecture:** Preference config loads `defaults.json` + `family-cells.json`. CLI resolves `family_id` (`--family` → defaults → fail). Cells come from `--cells` or the selected family’s recipe. Matrix `load_family` / `Cell.load(..., family=)` validate cells. Dry-config emits `family_id`.

**Tech Stack:** Python 3 stdlib (≥3.10; prefer `/opt/homebrew/bin/python3`), existing preference + matrix modules, `unittest`.

## Global Constraints

- Spec: `docs/superpowers/specs/2026-07-20-multi-family-preference-design.md`
- Umbrella: `docs/superpowers/specs/2026-07-20-multi-family-ornith-first-design.md` Step 2 only
- Suite: reuse `suites/gemma-preference-v1.json`
- Default family: explicit in `config/preference/defaults.json` → `gemma-4-12b-qat` (not a silent code constant)
- Gemma recipe cells (4): `jang_4m__osaurus`, `oq4_fp16__omlx`, `optiq_4bit__omlx`, `optiq_4bit__optiq`
- Ornith recipe cells (4): `ornith_jang_4m__omlx`, `ornith_oq4__omlx`, `ornith_optiq_4bit__omlx`, `ornith_optiq_4bit__optiq`
- Unit tests: fakes only; no live endpoints / Keychain
- Do not implement RAG/overhead Step 3, Qwen recipe (beyond omitting), Approach 3, Stage 2B, plugin, or live collect/judge
- Only create git commits when the user explicitly asks
- PATH for CLI: `PATH="/Users/jrazz/.local/bin:/opt/homebrew/bin:$PATH"` when invoking `./bin/lmre-*`

---

## File Structure

| File | Responsibility |
|------|----------------|
| `config/preference/defaults.json` | Checked-in `family_id` + default cells (Gemma four) |
| `config/preference/family-cells.json` | Single source of truth: `family_id` → cell id list |
| `preference_config.py` | Load defaults/recipes; `resolve_preference_selection`; drop hard-coded 3-tuple |
| `preference_cli.py` | `--family`; wire resolution; dry-config `family_id` |
| `preference_collect.py` / `preference_judge.py` | Accept `ModelFamily` (or family_id); persist `family_id` in `raw.json` |
| `docs/preference.md` | Family-first UX + both recipes |
| `tests/test_preference_config.py`, `test_preference_cli.py`, (+ collect/judge/review as needed) | Resolution + four-cell + Ornith dry-config |

---

### Task 1: Preference defaults + family-cells + resolver

**Files:**
- Create: `config/preference/defaults.json`
- Create: `config/preference/family-cells.json`
- Modify: `src/local_model_runtime_evaluation/preference_config.py`
- Modify: `tests/test_preference_config.py`

**Interfaces:**
- Produces:
  - `DEFAULT_PREFERENCE_ROOT = REPOSITORY_ROOT / "config" / "preference"`
  - `@dataclass(frozen=True) class PreferenceDefaults` — `family_id: str`, `cells: tuple[str, ...]`
  - `@dataclass(frozen=True) class PreferenceSelection` — `family_id: str`, `cells: tuple[str, ...]`
  - `load_preference_defaults(path: Path | None = None) -> PreferenceDefaults`
  - `load_family_cell_recipes(path: Path | None = None) -> dict[str, tuple[str, ...]]`
  - `resolve_preference_selection(*, family_id: str | None, cells: tuple[str, ...] | None, defaults: PreferenceDefaults | None = None, recipes: dict[str, tuple[str, ...]] | None = None) -> PreferenceSelection`
- Resolution rules (exact):
  1. `resolved_family = family_id if family_id else defaults.family_id` — if still empty → `PreferenceError("family is required")`
  2. If `resolved_family` not in recipes → `PreferenceError("preference family recipe is missing")`
  3. `resolved_cells = cells if cells is not None else recipes[resolved_family]`
  4. If `resolved_cells` empty → `PreferenceError("cells filter is empty")`
  5. Return `PreferenceSelection(resolved_family, resolved_cells)`
- When both `defaults.json` and `family-cells.json` list Gemma cells, they **must match exactly** (test asserts equality for `gemma-4-12b-qat`)
- Remove module-level `DEFAULT_PREFERENCE_CELLS` 3-tuple **or** replace with `load_family_cell_recipes()["gemma-4-12b-qat"]` helper used only by tests that need a stable tuple — prefer `def default_preference_cells() -> tuple[str, ...]` reading recipes+defaults so there is one source of truth

**`config/preference/family-cells.json`:**

```json
{
  "gemma-4-12b-qat": [
    "jang_4m__osaurus",
    "oq4_fp16__omlx",
    "optiq_4bit__omlx",
    "optiq_4bit__optiq"
  ],
  "ornith-35b": [
    "ornith_jang_4m__omlx",
    "ornith_oq4__omlx",
    "ornith_optiq_4bit__omlx",
    "ornith_optiq_4bit__optiq"
  ]
}
```

**`config/preference/defaults.json`:** same Gemma cell list **in the same order** as `family-cells.json` (single source of truth enforced by `test_gemma_defaults_match_recipe`).

- [ ] **Step 1: Write failing tests**

```python
def test_defaults_load_gemma_family(self) -> None:
    defaults = load_preference_defaults()
    self.assertEqual(defaults.family_id, "gemma-4-12b-qat")
    self.assertEqual(len(defaults.cells), 4)
    self.assertIn("optiq_4bit__omlx", defaults.cells)

def test_resolve_family_override_ornith(self) -> None:
    selection = resolve_preference_selection(family_id="ornith-35b", cells=None)
    self.assertEqual(selection.family_id, "ornith-35b")
    self.assertEqual(len(selection.cells), 4)
    self.assertTrue(all(c.startswith("ornith_") for c in selection.cells))

def test_resolve_missing_family_fails(self) -> None:
    empty = PreferenceDefaults(family_id="", cells=())
    with self.assertRaises(PreferenceError):
        resolve_preference_selection(family_id=None, cells=None, defaults=empty)

def test_gemma_defaults_match_recipe(self) -> None:
    defaults = load_preference_defaults()
    recipes = load_family_cell_recipes()
    self.assertEqual(defaults.cells, recipes["gemma-4-12b-qat"])
```

- [ ] **Step 2: Run — expect FAIL**

```bash
PYTHONPATH=src /opt/homebrew/bin/python3 -m unittest tests.test_preference_config -v
```

- [ ] **Step 3: Implement JSON files + loaders + resolver**

- [ ] **Step 4: Run — expect PASS** for new tests; update any `DEFAULT_PREFERENCE_CELLS` imports in this file’s tests

- [ ] **Step 5: Commit only if user asked**

---

### Task 2: Wire CLI / collect / judge to selection + `--family`

**Files:**
- Modify: `src/local_model_runtime_evaluation/preference_cli.py`
- Modify: `src/local_model_runtime_evaluation/preference_collect.py`
- Modify: `src/local_model_runtime_evaluation/preference_judge.py`
- Modify: `tests/test_preference_cli.py`
- Modify: `tests/test_preference_collect.py`, `tests/test_preference_judge.py`, `tests/test_preference_review.py` as needed for four-cell defaults

**Interfaces:**
- Consumes: `resolve_preference_selection`, `load_preference_defaults`, `load_family_cell_recipes`, `load_family`, `Cell.load`
- Produces:
  - `collect` argparse: `--family` optional string
  - Dry-config JSON includes `"family_id": <str>` plus existing `ok`, `suite_id`, `cells`, `prompts`
  - `run_collect(..., family_id: str, ...)` writes `"family_id"` into `raw.json`
  - Remove `DEFAULT_CELL_FAMILY = load_family("gemma-4-12b-qat")` from preference modules
  - Collect/judge: `family = load_family(selection.family_id)` then `Cell.load(..., family=family)` for every collect cell
  - Judge: resolve judge cell’s family via `load_family` for the family that owns that cell id (look up which recipe contains `judge_cell_id`; if none, try `load_family` from `--family` on judge subcommand **or** require judge cell to appear in some recipe). Minimal approach: add optional `--family` on `judge` too; if omitted, infer family as the unique recipe containing `judge_cell_id`, else `PreferenceError`
- `_parse_cell_ids`: return `None` when `--cells` omitted (not the old three-cell default); resolution supplies cells
- Reject cell not in selected family’s matrix allowlist via `Cell.load` failure (`MatrixError` → surface as preference error)

**CLI collect selection sketch:**

```python
def _selection_from_args(args: argparse.Namespace) -> PreferenceSelection:
    cells = None
    if getattr(args, "cells", None):
        cells = _parse_cell_ids(args.cells)  # raises if empty string parts
    return resolve_preference_selection(
        family_id=getattr(args, "family", None),
        cells=cells,
    )
```

- [ ] **Step 1: Write failing tests**

```python
def test_collect_dry_config_includes_family_id(self) -> None:
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        code = main(["collect", "--dry-config"])
    self.assertEqual(code, 0)
    payload = json.loads(buffer.getvalue())
    self.assertEqual(payload["family_id"], "gemma-4-12b-qat")
    self.assertEqual(len(payload["cells"]), 4)
    self.assertIn("optiq_4bit__omlx", payload["cells"])

def test_collect_dry_config_family_ornith(self) -> None:
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        code = main(["collect", "--dry-config", "--family", "ornith-35b"])
    self.assertEqual(code, 0)
    payload = json.loads(buffer.getvalue())
    self.assertEqual(payload["family_id"], "ornith-35b")
    self.assertEqual(len(payload["cells"]), 4)

def test_collect_rejects_ornith_cell_under_gemma_family(self) -> None:
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        code = main([
            "collect", "--dry-config",
            "--family", "gemma-4-12b-qat",
            "--cells", "ornith_jang_4m__omlx",
        ])
    self.assertNotEqual(code, 0)
```

- [ ] **Step 2: Run — expect FAIL**

```bash
PYTHONPATH=src /opt/homebrew/bin/python3 -m unittest tests.test_preference_cli -v
```

- [ ] **Step 3: Implement wiring**; update review/tally fakes that loop `DEFAULT_PREFERENCE_CELLS` to use four cells from recipes

- [ ] **Step 4: Full preference unit suite PASS**

```bash
PYTHONPATH=src /opt/homebrew/bin/python3 -m unittest \
  tests.test_preference_config \
  tests.test_preference_collect \
  tests.test_preference_review \
  tests.test_preference_tally \
  tests.test_preference_judge \
  tests.test_preference_cli -q
```

```bash
PATH="/Users/jrazz/.local/bin:/opt/homebrew/bin:$PATH" \
  ./bin/lmre-preference collect --dry-config
PATH="/Users/jrazz/.local/bin:/opt/homebrew/bin:$PATH" \
  ./bin/lmre-preference collect --dry-config --family ornith-35b
```

Expected: both `ok: true`; Gemma dry-config has 4 cells including `optiq_4bit__omlx`; Ornith has 4 `ornith_*` cells and `"family_id": "ornith-35b"`.

- [ ] **Step 5: Commit only if user asked**

---

### Task 3: Docs + CLI help copy

**Files:**
- Modify: `docs/preference.md`
- Modify: `preference_cli.py` argparse description / `--cells` help (four cells; family-first)

**Docs must include:**
- Family-first overview; `config/preference/defaults.json` as explicit Gemma default
- `--family ornith-35b` and default Gemma four-cell list (including `optiq_4bit__omlx`)
- Note: 4 cells → 6 pairs/prompt; historical 3-cell runs remain valid artifacts
- Stage 2B frozen; no live authorize from docs
- Qwen recipe later

- [ ] **Step 1: Update docs + help strings**

- [ ] **Step 2: Re-run preference unittest suite + both dry-configs (Task 2 commands)**

- [ ] **Step 3: Commit only if user asked**

---

## Spec Coverage Check (Step 2)

| Spec item | Task |
|-----------|------|
| Checked-in `defaults.json` (Gemma) | 1 |
| `family-cells` recipes Gemma + Ornith four | 1 |
| `resolve_preference_selection` / fail-closed | 1 |
| `--family` + dry-config `family_id` | 2 |
| Remove silent `DEFAULT_CELL_FAMILY` hardcode | 2 |
| Cell validation via matrix family | 2 |
| Docs family-first | 3 |
| No live / Qwen / RAG / Stage 2B | constraints |

---

## Execution Handoff

Plan complete for **Step 2 (preference)**. After implementation, live Ornith/Gemma preference collect remains a separate operator authorize.
