# Multi-Family Model Wiring Design (Ornith First)

**Status:** Approved in conversation by Jason on 2026-07-20. This document authorizes implementation planning only. It does not authorize a live Ornith screen, preference collect, RAG/overhead live runs, Stage 2B Gate B, plugin rebuild, Qwen campaign implementation, or Approach 3 free-form cells.

**Depends on:** Gemma 3×3 matrix, preference, RAG, and overhead tooling on `main`.

**Approach:** Family campaigns + registry-driven validation (Approach 1). Approach 3 (arbitrary user-defined cells for a future standalone tool) is a documented later goal only.

## Goal

Make the harness **multi-family**: add **Ornith 1.0 35B** as a full **3×3** matrix campaign (JANG / oQ4 / OptiQ-4bit × Osaurus / oMLX / OptiQ), then wire preference and RAG/overhead hooks so Ornith PASS winners can use the same lanes as Gemma. **Qwen 3.6** is the next family campaign after Ornith matrix ships — not implemented in this design’s first implementation plan.

Answer: which Ornith quant×server pairs load and perform on this Mac, without forking the runner stack.

## Locked Decisions

| Topic | Choice |
| --- | --- |
| First family | Ornith 35B (Qwen 3.6 later) |
| Matrix width | Full 3×3 |
| Suite / depth | Reuse `gemma-matrix-v1` + screen depth |
| Packaging | One umbrella design; sequenced delivery |
| Structure | Approach 1 (family registry + campaigns) |
| Future freedom | Approach 3 deferred (standalone-tool era) |
| Lane reach | Matrix → preference → RAG/overhead hooks |

## Delivery Sequence

| Step | Surface | Deliverable |
| --- | --- | --- |
| 1 | `lmre-matrix` | Ornith family registry, 9 cells, campaign; generalize Gemma hardcodes into registry |
| 2 | `lmre-preference` | Ornith PASS cell ids usable via `--cells` / docs (no Gemma-only dead ends) |
| 3 | `lmre-rag` / `lmre-overhead` | Optional Ornith cell/pair hooks + docs for native winners |

Each step may have its own implementation plan under this umbrella. Live runs remain separately authorized.

## Ornith Control Artifacts

| Quant key | Intended artifact |
| --- | --- |
| `ornith_jang_4m` | `/Users/jrazz/MLXModels/OsaurusAI/Ornith-1.0-35B-JANG_4M` |
| `ornith_oq4` | HF `georgeis55/Ornith-1.0-35B-MLX-oQ4` (local snapshot path once complete) |
| `ornith_optiq_4bit` | HF `mlx-community/Ornith-1.0-35B-OptiQ-4bit` (local snapshot path once complete) |

**Prep risk (observed 2026-07-20):** oQ4 and OptiQ HF hub dirs may be **refs-only** (no `snapshots/`). JANG is present (~18G). Incomplete artifacts → dry-config warning and/or live `N/A`; do not invent weights. Operator downloads before live screen.

Cell ids must not collide with Gemma (`jang_4m__osaurus`, etc.). Prefer prefixed ids such as `ornith_jang_4m__osaurus`, `ornith_oq4__omlx`, `ornith_optiq_4bit__optiq`.

Osaurus inventory id for JANG is expected to resemble `ornith-1.0-35b-jang_4m` (confirm at wire time). OptiQ cells use `:no-think` where streaming text must land in `delta.content`.

## Architecture

### Family registry

Replace hard-coded `QUANT_CONTROL_ARTIFACTS` / Gemma-only `ALLOWED_QUANTS` with loadable family files, e.g.:

- `config/matrix/families/gemma-4-12b-qat.json` — migrate existing Gemma allowlists (behavior unchanged)
- `config/matrix/families/ornith-35b.json` — Ornith allowlists

Each family declares: `family_id`, quants, per-quant `artifact_path` + allowed `model_ids`, notes for oMLX `--model-dir` roots when needed.

Campaign or cell load resolves which family validates a cell (explicit `family_id` on campaign recommended).

### Campaign & cells

- `config/matrix/ornith-35b-campaign.json` — same ports (`1337`/`8100`/`8080`), suite `suites/gemma-matrix-v1.json`, screen defaults, `memory_floor_percent: 20`, `on_cell_failure: continue`
- Nine cell JSONs under `config/matrix/cells/` with Ornith start argv mirroring Gemma patterns (Osaurus serve/stop, oMLX `--model-dir` + harness api-key injection, OptiQ `--model` + `--no-auth` / `:no-think`)

### Preference / RAG / overhead (steps 2–3)

- Preference: accept Ornith cell ids in `--cells`; document defaults remain Gemma PASS until Jason opts in
- RAG: optional `--cells` including Ornith winners; corpus/suite unchanged unless a later design says otherwise
- Overhead: optional pairs only for non-Osaurus native winners (same hybrid lifecycle as Gemma overhead)

## Operator Flow (matrix step)

```bash
./bin/lmre-matrix --dry-config --campaign config/matrix/ornith-35b-campaign.json
# After authorize + complete artifacts:
./bin/lmre-matrix --mode screen --campaign config/matrix/ornith-35b-campaign.json
```

One cell at a time; unloadable → `N/A`. Expect longer load times than Gemma 12B.

## Testing

- Fakes only in unit tests; no live Osaurus/oMLX/OptiQ in CI
- Cover registry load, Ornith cell validation, Gemma regression (existing tests still pass)
- Incomplete-artifact / missing-path behavior fail-closed or explicit `N/A` reason

## Stage 2B Boundary

- Do not run Gate B, authorize Stage 2B run IDs, or rebuild plugin `0.3.0`
- Do not modify Stage 0–2A accepted evidence or frozen Stage 2B-1 paths

## Later Options (Not This Phase)

### Qwen 3.6 family campaign

After Ornith matrix ships: same pattern (`families/qwen36-….json` + 3×3 campaign). Out of the first implementation plan.

### Approach 3 — free-form / user-defined cells

Future standalone-tool goal: operators define arbitrary artifact paths and server bindings without a curated family allowlist. **Pros:** maximum flexibility for third-party setups. **Cons:** easier misconfiguration; weaker fail-closed guarantees. Keep registry-driven Approach 1 until the product is ready to expose that freedom deliberately.

## Definition Of Done

- Sequenced plans can ship step 1 (matrix) independently with tests + docs
- Steps 2–3 remove Gemma-only dead ends for Ornith PASS ids
- Spec records Approach 3 and Qwen as later
- No live authorize implied by this document

## Spec Self-Check

| Item | Covered |
| --- | --- |
| Ornith 3×3 first; Qwen later | Yes |
| Suite/depth reuse | Yes |
| Registry Approach 1; Approach 3 future | Yes |
| Sequenced matrix → preference → RAG/overhead | Yes |
| Incomplete HF prep risk | Yes |
| Stage 2B frozen; no live authorize | Yes |
