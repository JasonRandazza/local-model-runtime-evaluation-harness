# Multi-Family RAG Oracle and Keyword

Family-first oracle-injected gold context or **keyword** term-overlap retrieval on matrix **PASS** cells. Automatic **fact-hit rate** scoring for all modes; keyword runs also score **recall@k** and **precision@k** against suite gold chunk ids. Separate from `lmre-preference` and `lmre-matrix`; Stage 0–2B machinery stays frozen.

**Related:** matrix campaign — see [matrix.md](matrix.md); preference POC — see [preference.md](preference.md); routing overhead — see [overhead.md](overhead.md).

## Family selection

RAG resolves a matrix **family** first, then that family’s cell recipe:

1. `--family <family_id>` if set
2. Else `config/rag/defaults.json` → `family_id` (checked-in default: **`gemma-4-12b-qat`**)
3. Else fail closed — family is required

Cell ids come from `--cells` or the selected family’s recipe in `config/rag/family-cells.json`. Every cell must load for the selected matrix family; mixed-family lists are rejected.

### Default family (Gemma)

`config/rag/defaults.json` names the repo default explicitly (not a silent Python constant):

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

Four screen 12/12 cells (adds `optiq_4bit__omlx` to the prior three-cell default).

### Ornith override

```bash
./bin/lmre-rag collect --dry-config --family ornith-35b
```

Ornith recipe (four screen 12/12 cells): `ornith_jang_4m__omlx`, `ornith_oq4__omlx`, `ornith_optiq_4bit__omlx`, `ornith_optiq_4bit__optiq`.

### Qwen override

```bash
./bin/lmre-rag collect --dry-config --family qwen36-35b-a3b
```

Qwen recipe (four screen PASS cells from `qwen36-35b-a3b-3x3-screen-20260720-201114`): `qwen_mxfp4__osaurus`, `qwen_oq4__omlx`, `qwen_optiq_4bit__omlx`, `qwen_optiq_4bit__optiq`.

## Modes

| Mode | Default | Context source |
| --- | --- | --- |
| `oracle` | yes | Suite `gold_chunk_ids` injected (Phase 1 behavior) |
| `keyword` | no | Top-k chunks ranked by case-insensitive term overlap |

Default `--top-k` is **2** (keyword only; ignored in oracle mode).

## Prerequisites

Same artifact paths, credentials, RAM floor, and server rules as the matrix campaign for the selected family’s cells — see [matrix.md](matrix.md) (Osaurus Keychain, oMLX loopback key, OptiQ `:no-think` ids, `20%` free RAM).

## Non-live check

```bash
PYTHONPATH=src /opt/homebrew/bin/python3 -m unittest \
  tests.test_rag_retrieve \
  tests.test_rag_config \
  tests.test_rag_prompt \
  tests.test_rag_score \
  tests.test_rag_collect \
  tests.test_rag_cli -v
```

Unit tests use fakes only — no live Osaurus, oMLX, or OptiQ contact.

## Validate config (dry-config)

Gemma default (four cells):

```bash
./bin/lmre-rag collect --dry-config
```

Prints JSON with `ok: true`, `"family_id": "gemma-4-12b-qat"`, four default cell ids (including `optiq_4bit__omlx`), `questions: 6`, `corpus_id: rag-oracle-v1`, `mode`, and `top_k`. No network or server start.

Ornith four-cell recipe:

```bash
./bin/lmre-rag collect --dry-config --family ornith-35b
```

Prints JSON with `ok: true`, `"family_id": "ornith-35b"`, four `ornith_*` cell ids.

Qwen four-cell recipe:

```bash
./bin/lmre-rag collect --dry-config --family qwen36-35b-a3b
```

Prints JSON with `ok: true`, `"family_id": "qwen36-35b-a3b"`, four `qwen_*` cell ids.

Keyword mode:

```bash
./bin/lmre-rag collect --mode keyword --dry-config
```

## Workflow

1. **Collect** — one cell at a time, six prompts per cell:

```bash
./bin/lmre-rag collect
./bin/lmre-rag collect --mode keyword --top-k 2
```

Ornith live collect (only after separate operator authorize):

```bash
./bin/lmre-rag collect --family ornith-35b
```

Qwen live collect (only after separate operator authorize):

```bash
./bin/lmre-rag collect --family qwen36-35b-a3b
./bin/lmre-rag collect --family qwen36-35b-a3b --mode keyword --top-k 2
```

Optional filters: `--family`, `--cells id,id`, `--suite PATH`, `--corpus-root PATH`, `--results-dir PATH`, `--mode oracle|keyword`, `--top-k N`.

2. **Score** — fact-hit rate per prompt and mean hit rate per cell; keyword runs add retrieval metrics:

```bash
./bin/lmre-rag score --run results/rag/gemma-rag-<timestamp>
```

## Metrics

### Generation (both modes)

- Case-sensitive required-fact substring hit rate per prompt
- Mean hit rate per cell
- Unsuccessful answers → hit rate `0.0`

### Retrieval (keyword only)

Compared to suite `gold_chunk_ids`:

- `recall@k = |retrieved ∩ gold| / |gold|`
- `precision@k = |retrieved ∩ gold| / |retrieved|` (0 if retrieved empty)
- Mean recall and mean precision per cell

Oracle runs omit retrieval metrics from `scores.json` and ranking tables.

## Optional live smoke checklist

Not CI — manual operator verification only:

**Oracle (Phase 1 regression):**

- [ ] `./bin/lmre-rag collect --dry-config`
- [ ] Obtain Jason's in-session authorization for live collect
- [ ] `./bin/lmre-rag collect`
- [ ] `./bin/lmre-rag score --run results/rag/gemma-rag-<timestamp>`
- [ ] Confirm `report.md` ranks cells by mean hit rate

**Keyword (Phase 2):**

- [ ] `./bin/lmre-rag collect --mode keyword --dry-config`
- [ ] Obtain Jason's in-session authorization for live keyword collect
- [ ] `./bin/lmre-rag collect --mode keyword --top-k 2`
- [ ] `./bin/lmre-rag score --run results/rag/gemma-rag-<timestamp>`
- [ ] Confirm `report.md` includes retrieval and fact-hit rankings
- [ ] Confirm `answers/*.json` rows include `retrieved_chunk_ids`

## Outputs

Under `results/rag/gemma-rag-<timestamp>/`:

- `raw.json` — `family_id`, suite id, corpus id, cell ids, `mode`, `top_k` (when keyword), timestamps
- `answers/<cell_id>.json` — per-prompt content, success/error, timings; keyword rows include `retrieved_chunk_ids`
- `scores.json` — per-cell / per-prompt hit rates; keyword adds retrieval metrics
- `report.md` — human-readable ranking by mean hit rate (and mean recall for keyword)

Latency is metadata only; scoring uses case-sensitive required-fact substring hits.

## Safety

- **Live collect requires Jason's in-session authorization.** Do not run collect without explicit operator approval.
- **Stage 2B remains frozen.** These docs do not authorize Gate B, Stage 2B run IDs, or plugin changes.
- Pinned cell start argv only; harness starts and stops only what each cell defines.
- One cell at a time; verify port free and RAM floor between cells.

## Not implemented

- BM25, TF-IDF, or embedding retrieval
- Pairwise preference or local judge on RAG answers
- New corpus or suite (reuses Phase 1 `rag-oracle-v1` / `gemma-rag-oracle-v1`)
