# Qwen 3.6 Matrix + Osaurus-Native Role Design

**Status:** Approved in conversation by Jason on 2026-07-20. This document authorizes implementation planning and matrix config work only. It does not authorize a live Qwen screen, preference/RAG/overhead recipes, Stage 2B Gate B, plugin rebuild, or Approach 3 free-form cells.

**Depends on:** Multi-family matrix registry (Gemma + Ornith) on `main`. Umbrella note: `docs/superpowers/specs/2026-07-20-multi-family-ornith-first-design.md` deferred Qwen here.

**Approach:** Same Approach 1 family registry as Ornith, plus an optional family-quant `role` so Osaurus curated natives may be JANG **or** MXFP without hard-coding “native = JANG”.

## Goal

Add **Qwen3.6-35B-A3B** as a full **3×3** matrix campaign with controls **MXFP4 / oQ4 / OptiQ-4bit** × Osaurus / oMLX / OptiQ. Generalize documentation and registry metadata so future families can pick either Osaurus-native quantization format.

Answer: which Qwen quant×server pairs load and perform on this Mac, without forking the runner stack.

## Locked Decisions

| Topic | Choice |
| --- | --- |
| Family | `qwen36-35b-a3b` |
| Controls | MXFP4, oQ4-mtp, OptiQ-4bit (no JANG in this family) |
| Matrix width | Full 3×3; N/A is valid evidence |
| Suite / depth | Reuse `gemma-matrix-v1` + screen depth |
| Osaurus native | Optional `role: "osaurus_native"` on family quants (JANG or MXFP) |
| Delivery | Matrix Step 1 only |
| Report order | Derive from campaign cell appearance order (not Gemma hardcodes) |

## Delivery Sequence

| Step | Surface | Deliverable |
| --- | --- | --- |
| 1 (this) | `lmre-matrix` | `osaurus_native` role; Qwen family + 9 cells + campaign; report order fix; docs |
| Later | preference / RAG / overhead | Recipes after screen PASS cells exist |

Live runs remain separately authorized.

## Qwen Control Artifacts

| Quant key | Role | Intended artifact |
| --- | --- | --- |
| `qwen_mxfp4` | `osaurus_native` | `/Users/jrazz/MLXModels/OsaurusAI/Qwen3.6-35B-A3B-MXFP4-MTP` |
| `qwen_oq4` | — | `/Users/jrazz/.cache/huggingface/hub/Jundot/Qwen3.6-35B-A3B-oQ4-mtp` |
| `qwen_optiq_4bit` | — | `/Users/jrazz/.cache/huggingface/hub/mlx-community/Qwen3.6-35B-A3B-OptiQ-4bit` |

**Prep risk (observed 2026-07-20):** MXFP weights present (~22G). oQ4 and OptiQ HF hub dirs may be **refs-only** (no usable flat snapshot) until download/symlink prep finishes. Incomplete artifacts → dry-config `artifact_missing` and/or live `N/A`; do not invent weights.

Cell ids: `qwen_mxfp4__osaurus`, `qwen_oq4__omlx`, `qwen_optiq_4bit__optiq`, etc.

Primary MXFP Osaurus inventory pin: `qwen3.6-35b-a3b-mxfp4-mtp` (confirm at wire time against live `/v1/models`; adjust allowlist if the GUI slug differs). OptiQ-4bit cells use `:no-think` so streams put text in `delta.content`.

## Architecture

### Optional `role` on family quants

Family quant entries keep required `artifact_path` + `model_ids`. Optional field:

- `"role": "osaurus_native"` — curated Osaurus library artifact (JANG **or** MXFP)
- Omit for HF / routed quants (oQ4, OptiQ-4bit)
- Any other `role` value fails closed

Gemma `jang_4m` and Ornith `ornith_jang_4m` gain the role annotation without path renames. Qwen `qwen_mxfp4` uses the same role.

Validation of cells remains allowlist match (`model_id` ∈ `model_ids`, `artifact_path` exact). Role is policy metadata for docs, tests, and future lane recipes (e.g. overhead excluding natives).

### Campaign & cells

- `config/matrix/families/qwen36-35b-a3b.json`
- `config/matrix/qwen36-35b-a3b-campaign.json` — ports `1337`/`8100`/`8080`, suite `suites/gemma-matrix-v1.json`, screen defaults, `memory_floor_percent: 20`, `on_cell_failure: continue`
- Nine cells under `config/matrix/cells/` mirroring Ornith start argv patterns
- `config/matrix/omlx-roots/qwen_*/README.md` with operator symlink instructions (do not commit weight trees)

### Report order

Replace Gemma-hardcoded `QUANT_ORDER` with ordered unique quant keys from `raw["cells"]` appearance order so Ornith and Qwen reports show the correct rows.

## Operator Flow

```bash
./bin/lmre-matrix --dry-config --campaign config/matrix/qwen36-35b-a3b-campaign.json
# After authorize + complete artifacts:
./bin/lmre-matrix --mode screen --campaign config/matrix/qwen36-35b-a3b-campaign.json
```

## Later Options (Not This Phase)

- Preference / RAG / overhead Qwen recipes after screen PASS cells
- Replacing Gemma/Ornith JANG with MXFP
- Expanding campaigns past nine cells
- Approach 3 free-form cells
- Stage 2B

## Definition Of Done

- Spec + implementation plan exist
- Family/cells/campaign/omlx-root stubs + `role` field + report-order fix + tests + docs land
- Qwen dry-config succeeds (warnings OK for incomplete HF)
- Gemma and Ornith dry-config still OK
- No live authorize implied

## Spec Self-Check

| Item | Covered |
| --- | --- |
| MXFP / oQ4 / OptiQ 3×3; no JANG | Yes |
| Full grid; N/A OK | Yes |
| `osaurus_native` role (JANG or MXFP) | Yes |
| Matrix-only; lanes later | Yes |
| Report order from campaign cells | Yes |
| HF prep risk | Yes |
| Stage 2B frozen; no live authorize | Yes |
