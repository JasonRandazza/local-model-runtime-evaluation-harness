# Multi-Family RAG and Overhead Design (Step 3)

**Status:** Approved in conversation by Jason on 2026-07-20. This document authorizes implementation planning only. It does not authorize live RAG collect, live overhead runs, Stage 2B Gate B, plugin rebuild, Qwen wiring, or a third Ornith overhead pair.

**Depends on:** Ornith matrix Step 1 on `main`; preference Step 2 design/plan (implementation may be uncommitted on the working tree). Umbrella: `docs/superpowers/specs/2026-07-20-multi-family-ornith-first-design.md`.

**Approach:** Family-first CLI for `lmre-rag` and `lmre-overhead`, matching preference Step 2. Checked-in defaults name Gemma explicitly. `--family` overrides. Ornith recipes use screen evidence cell sets.

## Goal

Remove Gemma-only dead ends from RAG and overhead. Operators select **Gemma** or **Ornith** via `--family`, or use checked-in defaults. Expand Gemma RAG defaults to four full-pass cells (add `optiq_4bit__omlx`). Ship Ornith RAG four-cell recipe and two Ornith overhead pairs (`ornith_oq4`, `ornith_optiq_4bit`). Prefer config over silent Python family constants.

## Locked Decisions

| Topic | Choice |
| --- | --- |
| Shape | Same as preference: defaults JSON + family recipes + `--family` |
| Default family | Checked-in; `gemma-4-12b-qat` |
| Gemma RAG cells | Four: add `optiq_4bit__omlx` to prior three |
| Ornith RAG cells | Four 12/12: same as preference Ornith recipe |
| Gemma overhead | Existing pairs `oq4_fp16`, `optiq_4bit` |
| Ornith overhead | Two pairs mirroring Gemma shape: oQ4 oMLX + OptiQ native |
| Third Ornith overhead pair (`ornith_optiq_4bit__omlx`) | Out of scope |
| Routed model ids | Structural placeholders allowed; pin exact live inventory before authorize |
| Suite / corpus | Unchanged (`gemma-rag-oracle-v1`, keyword mode as today) |
| Live runs | Separately authorized |

## Screen Evidence (inputs)

**Gemma** combined screen: four 12/12 — `jang_4m__osaurus`, `oq4_fp16__omlx`, `optiq_4bit__omlx`, `optiq_4bit__optiq`.

**Ornith** `ornith-35b-3x3-screen-20260720-143726`: four 12/12 — `ornith_jang_4m__omlx`, `ornith_oq4__omlx`, `ornith_optiq_4bit__omlx`, `ornith_optiq_4bit__optiq`.

## Architecture

### RAG config

- `config/rag/defaults.json` — `family_id` + cells (Gemma four, same order as recipe)
- `config/rag/family-cells.json` — `gemma-4-12b-qat` and `ornith-35b` cell lists
- Resolver: `--family` → defaults → fail closed; cells from `--cells` or recipe
- Remove `DEFAULT_CELL_FAMILY = load_family("gemma-4-12b-qat")` and hard-coded three-cell `DEFAULT_RAG_CELLS` in favor of config loaders
- Dry-config emits `family_id`, resolved `cells`, suite/mode fields as today

### Overhead config

- `config/overhead/defaults.json` — `family_id` + default pair ids `["oq4_fp16", "optiq_4bit"]`
- `config/overhead/family-pairs.json` — map family → pair id list
- New pair files:
  - `config/overhead/pairs/ornith_oq4.json` — direct/backend `ornith_oq4__omlx`; `routed_base_url` `http://127.0.0.1:1337/v1`; `routed_model_id` a string that is already (or will be) on the Ornith family oQ4 `model_ids` allowlist (e.g. `omlx/Ornith-1.0-35B-MLX-oQ4` style — must match family JSON; operator re-pins if live inventory differs)
  - `config/overhead/pairs/ornith_optiq_4bit.json` — direct/backend `ornith_optiq_4bit__optiq`; routed id must be on Ornith OptiQ allowlist (path / `optiq//…:no-think` forms as used by Gemma pair pattern)
- CLI: `--family`; `--pairs` continues to filter pair ids within the selected family’s recipe
- `make_routed_measure_cell` / `Cell.load` use resolved `ModelFamily`
- Dry-config emits `family_id` and pair list

### Resolution order (both CLIs)

1. `--family` if set  
2. Else defaults file `family_id`  
3. Else fail: family required  

### Docs

- Update `docs/rag.md` and `docs/overhead.md`: family-first, defaults, Ornith examples, pin routed ids before live, Stage 2B frozen, no live authorize
- Cross-link preference/matrix multi-family docs

## Operator Flow (non-live)

```bash
./bin/lmre-rag --dry-config
./bin/lmre-rag --dry-config --family ornith-35b

./bin/lmre-overhead --dry-config
./bin/lmre-overhead --dry-config --family ornith-35b
```

## Testing

- Fakes only; no live Osaurus / oMLX / OptiQ / Keychain  
- Cover defaults load, `--family` override, missing family fails, Ornith recipes, Gemma four-cell RAG default, Ornith pair load + Cell validation  
- Existing RAG/overhead tests updated for four-cell / family resolution  

## Stage 2B Boundary

- Do not run Gate B, authorize Stage 2B run IDs, or rebuild plugin `0.3.0`  
- Do not modify Stage 0–2A accepted evidence or frozen Stage 2B-1 paths  

## Later Options (Not This Phase)

- Qwen RAG/overhead recipes after Qwen matrix  
- Third Ornith overhead pair (OptiQ-4bit via oMLX)  
- Shared cross-lane defaults library refactor (YAGNI unless duplication hurts)  
- Live authorize for Ornith RAG/overhead  

## Definition Of Done

- Spec + plan can ship Step 3 independently with tests + docs  
- RAG and overhead defaults are explicit in checked-in JSON  
- Ornith dry-config works via `--family ornith-35b`  
- Gemma RAG includes `optiq_4bit__omlx`  
- No live authorize implied  

## Spec Self-Check

| Item | Covered |
| --- | --- |
| Family-first RAG + overhead | Yes |
| Gemma four-cell RAG; Ornith four | Yes |
| Two Ornith overhead pairs; third out | Yes |
| Placeholder routed ids + pin before live | Yes |
| Suite/corpus unchanged; Stage 2B frozen | Yes |
