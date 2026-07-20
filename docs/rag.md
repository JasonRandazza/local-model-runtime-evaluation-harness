# Gemma RAG Oracle and Keyword Phase 2

Oracle-injected gold context or **keyword** term-overlap retrieval on the three screen **PASS** cells (`jang_4m__osaurus`, `oq4_fp16__omlx`, `optiq_4bit__optiq`). Automatic **fact-hit rate** scoring for all modes; keyword runs also score **recall@k** and **precision@k** against suite gold chunk ids. Separate from `lmre-preference` and `lmre-matrix`; Stage 0–2B machinery stays frozen.

## Modes

| Mode | Default | Context source |
| --- | --- | --- |
| `oracle` | yes | Suite `gold_chunk_ids` injected (Phase 1 behavior) |
| `keyword` | no | Top-k chunks ranked by case-insensitive term overlap |

Default `--top-k` is **2** (keyword only; ignored in oracle mode).

## Prerequisites

Same artifact paths, credentials, RAM floor, and server rules as the matrix campaign for these three cells — see [matrix.md](matrix.md) (Osaurus Keychain, oMLX loopback key, OptiQ `:no-think` ids, `20%` free RAM).

## Non-live check

```bash
PYTHONPATH=src python3 -m unittest \
  tests.test_rag_retrieve \
  tests.test_rag_config \
  tests.test_rag_prompt \
  tests.test_rag_score \
  tests.test_rag_collect \
  tests.test_rag_cli \
  tests.test_preference_collect -v
```

Unit tests use fakes only — no live Osaurus, oMLX, or OptiQ contact.

## Validate config

```bash
./bin/lmre-rag collect --dry-config
./bin/lmre-rag collect --mode keyword --dry-config
```

Prints JSON with `ok: true`, default cell ids, `questions: 6`, `corpus_id: rag-oracle-v1`, `mode`, and `top_k`. No network or server start.

## Workflow

1. **Collect** — one cell at a time, six prompts per cell:

```bash
./bin/lmre-rag collect
./bin/lmre-rag collect --mode keyword --top-k 2
```

Optional filters: `--cells id,id`, `--suite PATH`, `--corpus-root PATH`, `--results-dir PATH`, `--mode oracle|keyword`, `--top-k N`.

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

- `raw.json` — suite id, corpus id, cell ids, `mode`, `top_k` (when keyword), timestamps
- `answers/<cell_id>.json` — per-prompt content, success/error, timings; keyword rows include `retrieved_chunk_ids`
- `scores.json` — per-cell / per-prompt hit rates; keyword adds retrieval metrics
- `report.md` — human-readable ranking by mean hit rate (and mean recall for keyword)

Latency is metadata only; scoring uses case-sensitive required-fact substring hits.

## Safety

- **Live collect requires Jason's in-session authorization.** Do not run collect without explicit operator approval.
- Pinned cell start argv only; harness starts and stops only what each cell defines.
- One cell at a time; verify port free and RAM floor between cells.

## Not implemented

- BM25, TF-IDF, or embedding retrieval
- Pairwise preference or local judge on RAG answers
- New corpus or suite (reuses Phase 1 `rag-oracle-v1` / `gemma-rag-oracle-v1`)
