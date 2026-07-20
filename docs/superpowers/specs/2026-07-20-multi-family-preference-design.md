# Multi-Family Preference Design (Step 2)

**Status:** Approved in conversation by Jason on 2026-07-20. This document authorizes implementation planning only. It does not authorize a live preference collect, local judge run, RAG/overhead live work, Stage 2B Gate B, plugin rebuild, or Qwen family wiring beyond placeholders.

**Depends on:** Ornith matrix Step 1 on `main` (family registry, Ornith screen evidence). Umbrella: `docs/superpowers/specs/2026-07-20-multi-family-ornith-first-design.md`.

**Approach:** Family-first preference CLI. Checked-in `config/preference/defaults.json` explicitly names the default family (Gemma 4 12B QAT). `--family` overrides. Cell-id prefix inference is validation only, not family selection.

## Goal

Make `lmre-preference` multi-family: operators choose **Gemma**, **Ornith**, or (later) **Qwen** via `--family`, or rely on an **explicit** checked-in default. Expand Gemma preference cells to all four combined-screen full passes (add `optiq_4bit__omlx`). Ship Ornith’s four screen 12/12 winners as that family’s recipe. Prefer config over silent Python constants inherited from early Gemma-only development.

## Locked Decisions

| Topic | Choice |
| --- | --- |
| Family selection | Required unless `defaults.json` sets `family_id` |
| Default location | Checked-in `config/preference/defaults.json` (not gitignored) |
| Default family | `gemma-4-12b-qat` (proven; editable in config) |
| Gemma cells | Four full-pass: add `optiq_4bit__omlx` to prior three |
| Ornith cells | Four 12/12: `ornith_jang_4m__omlx`, `ornith_oq4__omlx`, `ornith_optiq_4bit__omlx`, `ornith_optiq_4bit__optiq` |
| Pair shape | 4 cells → 6 unordered pairs per prompt |
| Family resolution | `--family` then defaults file; never infer family solely from cell prefix for selection |
| Prefix / allowlist | Reject cells not valid for the selected matrix family |
| Suite | Reuse `suites/gemma-preference-v1.json` across families for this step |
| Live runs | Separately authorized; not implied by this design |

## Screen Evidence (inputs)

**Gemma** (`gemma-4-12b-qat-3x3-screen-combined`): four 12/12 cells — `jang_4m__osaurus`, `oq4_fp16__omlx`, `optiq_4bit__omlx`, `optiq_4bit__optiq`.

**Ornith** (`ornith-35b-3x3-screen-20260720-143726`): four 12/12 cells listed above. Other Ornith cells were partial or N/A and are not in the recipe.

## Architecture

### Preference defaults (checked in)

`config/preference/defaults.json`:

```json
{
  "family_id": "gemma-4-12b-qat",
  "cells": [
    "jang_4m__osaurus",
    "oq4_fp16__omlx",
    "optiq_4bit__omlx",
    "optiq_4bit__optiq"
  ]
}
```

Changing the repo default family later means editing this file (or always passing `--family`).

### Per-family cell recipes

Prefer a small preference config map (e.g. `config/preference/family-cells.json` or per-family files) keyed by matrix `family_id`:

- `gemma-4-12b-qat` → Gemma four-cell list  
- `ornith-35b` → Ornith four-cell list  
- Qwen: omit until that matrix family exists  

`defaults.json` may duplicate Gemma’s cell list for clarity, or reference the recipe by `family_id` only; implementation should avoid drift (single source of truth for recipes preferred).

### CLI resolution order

1. If `--family` is set → use that `family_id`.  
2. Else if `defaults.json` has a non-empty `family_id` → use it.  
3. Else → fail closed: family required; list known preference recipes / matrix families.  

Cells:

- If `--cells` is set → use that list (must all belong to the selected family’s matrix allowlist).  
- Else → use the selected family’s preference recipe (from recipe map; for default family, must match `defaults.json` cells when both specify cells).  

Load matrix `ModelFamily` via existing `load_family(family_id)` and `Cell.load(..., family=...)`.

### Validation

- Selected `family_id` must exist under `config/matrix/families/`.  
- Every cell id must load successfully for that family.  
- Do not accept a mixed list that spans families in one collect.  
- Optional defensive check: `ornith_*` cell ids require `family_id == ornith-35b` (and similarly for future prefixes) — validation aid only.

### Code migration

- Remove import-time / hard-coded Gemma-only `DEFAULT_CELL_FAMILY = load_family("gemma-4-12b-qat")` from preference modules in favor of resolved family.  
- `DEFAULT_PREFERENCE_CELLS` in Python either disappears or becomes a thin loader over the recipe/defaults config.  
- Dry-config should emit `family_id`, resolved `cells`, and suite id.

### Docs

- Document family-first UX, `defaults.json`, `--family ornith-35b`, both 4-cell recipes, 6 pairs/prompt.  
- Note historical 3-cell Gemma preference runs remain valid artifacts; new defaults are four cells.  
- Stage 2B frozen; no live authorize from docs.

## Operator Flow (non-live → live)

```bash
# Dry-config with repo default (Gemma four)
./bin/lmre-preference collect --dry-config

# Ornith four
./bin/lmre-preference collect --dry-config --family ornith-35b

# After separate authorize:
./bin/lmre-preference collect --family ornith-35b
```

## Testing

- Fakes only; no live Osaurus / oMLX / OptiQ / Keychain in unit tests.  
- Cover: defaults load; `--family` override; missing family fails; Ornith recipe cells validate; Gemma four-cell default; reject wrong-family cell ids.  
- Existing preference unit tests updated for four-cell Gemma default where they assumed three.

## Stage 2B Boundary

- Do not run Gate B, authorize Stage 2B run IDs, or rebuild plugin `0.3.0`.  
- Do not modify Stage 0–2A accepted evidence or frozen Stage 2B-1 paths.

## Later Options (Not This Phase)

### Explicit `--family` already in this design

Primary selection is `--family` + checked-in defaults. No separate “Approach B later” for selection — that concern is absorbed here.

### Qwen 3.6 preference recipe

After Qwen matrix ships and screen PASS cells exist, add recipe entry and docs. Out of this plan’s implementation.

### RAG / overhead Step 3

Optional Ornith (and family-first) hooks remain a separate plan under the umbrella design.

### Free-form cells (Approach 3)

Deferred to standalone-tool era.

## Definition Of Done

- Spec + implementation plan can ship Step 2 independently with tests + docs  
- Repo default family is explicit in `config/preference/defaults.json`  
- Ornith four-cell collect works via `--family ornith-35b` (dry-config / unit tests)  
- Gemma defaults include `optiq_4bit__omlx`  
- No live authorize implied  

## Spec Self-Check

| Item | Covered |
| --- | --- |
| Family-first; no silent code default | Yes |
| Checked-in defaults with Gemma | Yes |
| Gemma + Ornith four-cell recipes | Yes |
| `--family` override; fail-closed | Yes |
| Suite reuse; live separate | Yes |
| Qwen / RAG / Stage 2B out | Yes |
