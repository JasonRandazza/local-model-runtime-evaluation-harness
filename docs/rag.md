# Gemma RAG Oracle Phase 1

Oracle-injected gold context on the three screen **PASS** cells (`jang_4m__osaurus`, `oq4_fp16__omlx`, `optiq_4bit__optiq`). Automatic **fact-hit rate** scoring — no pairwise preference. Separate from `lmre-preference` and `lmre-matrix`; Stage 0–2B machinery stays frozen.

## Prerequisites

Same artifact paths, credentials, RAM floor, and server rules as the matrix campaign for these three cells — see [matrix.md](matrix.md) (Osaurus Keychain, oMLX loopback key, OptiQ `:no-think` ids, `20%` free RAM).

## Non-live check

```bash
PYTHONPATH=src python3 -m unittest \
  tests.test_rag_config \
  tests.test_rag_prompt \
  tests.test_rag_score \
  tests.test_rag_collect \
  tests.test_rag_cli -v
```

Unit tests use fakes only — no live Osaurus, oMLX, or OptiQ contact.

## Validate config

```bash
./bin/lmre-rag collect --dry-config
```

Prints JSON with `ok: true`, default cell ids, `questions: 6`, and `corpus_id: rag-oracle-v1`. No network or server start.

## Workflow

1. **Collect** — one cell at a time, six oracle prompts per cell:

```bash
./bin/lmre-rag collect
```

Optional filters: `--cells id,id`, `--suite PATH`, `--corpus-root PATH`, `--results-dir PATH`.

2. **Score** — fact-hit rate per prompt and mean hit rate per cell:

```bash
./bin/lmre-rag score --run results/rag/gemma-rag-<timestamp>
```

## Optional live smoke checklist

Not CI — manual operator verification only:

- [ ] `./bin/lmre-rag collect --dry-config`
- [ ] Obtain Jason's in-session authorization for live collect
- [ ] `./bin/lmre-rag collect`
- [ ] `./bin/lmre-rag score --run results/rag/gemma-rag-<timestamp>`
- [ ] Confirm `report.md` ranks cells by mean hit rate

## Outputs

Under `results/rag/gemma-rag-<timestamp>/`:

- `raw.json` — suite id, corpus id, cell ids, timestamps
- `answers/<cell_id>.json` — per-prompt content, success/error, timings
- `scores.json` — per-cell / per-prompt hit rates
- `report.md` — human-readable ranking by mean hit rate

Latency is metadata only; scoring uses case-sensitive required-fact substring hits.

## Safety

- **Live collect requires Jason's in-session authorization.** Do not run collect without explicit operator approval.
- Pinned cell start argv only; harness starts and stops only what each cell defines.
- One cell at a time; verify port free and RAM floor between cells.

## Not implemented (Phase 2)

- Keyword or embedding retrieval over the corpus
- Retrieval-quality metrics (recall@k, MRR, etc.)
- Pairwise preference or local judge on RAG answers

Phase 1 uses oracle-injected gold chunks only; retrieval is a documented follow-on.
