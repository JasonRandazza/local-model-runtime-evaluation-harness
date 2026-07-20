# Gemma RAG Oracle Phase 1 Design

**Status:** Approved in conversation by Jason on 2026-07-20. This document authorizes implementation planning only. It does not authorize a live RAG collect, Stage 2B Gate B, plugin rebuild, keyword/embedding retrieval (Phase 2), pairwise preference on RAG answers, or Osaurus routing-overhead measurement.

**Depends on:** matrix cell lifecycle + auth; preference collect patterns (`docs/superpowers/specs/2026-07-19-gemma-preference-quality-poc-design.md`). Preference CLI stays unchanged.

## Goal

**Phase 1:** Measure how well the three screen PASS cells use **oracle-injected gold context** (grounded generation). Scoring is automatic **fact-hit rate** on required substrings from gold chunks.

**Phase 2 (out of this design):** Keyword retrieval over the corpus with retrieval-quality metrics. Do not implement Phase 2 here.

## Approach

**Thin `bin/lmre-rag` CLI** (Approach 1), separate from `lmre-preference`:

```bash
./bin/lmre-rag collect [--cells id,id] [--suite PATH] [--corpus-root PATH] [--dry-config]
./bin/lmre-rag score --run DIR
```

- Default cells: `jang_4m__osaurus`, `oq4_fp16__omlx`, `optiq_4bit__optiq`
- Reuse matrix `Cell` configs, server lifecycle, and credentials (same as preference collect)
- Live collect requires Jason’s in-session authorization

## Corpus

Under `corpora/rag-oracle-v1/` (committed, small):

- Mostly **synthetic** markdown docs with locked facts (stable chunk ids, e.g. `syn-ports`, `syn-auth`)
- **1–2 excerpts** copied from existing harness docs (e.g. matrix auth / preference pointer). Runtime loads only from `corpora/` — **not** live-read from `docs/` (avoids doc drift)

Manifest `corpora/rag-oracle-v1/manifest.json` maps `chunk_id` → relative file path (and optional title).

## Suite

`suites/gemma-rag-oracle-v1.json`, revision `1`, **exactly 6** questions (parity with preference pack size):

Each item fields (exact):

- `prompt_id` (unique)
- `question` (user-facing question text)
- `gold_chunk_ids` (non-empty list of chunk ids from the corpus manifest)
- `required_facts` (non-empty list of exact substrings that should appear if gold context was used)
- `max_tokens` (positive int)

Suite also carries: `schema_version`, `suite_id`, `revision`, `temperature` (0), `streaming` (true), `corpus_id` (`rag-oracle-v1`).

## Collect

For each question:

1. Resolve gold chunks from the corpus; fail closed if any id missing.
2. Build prompt: short instruction (“Use only the provided context…”) + concatenated gold chunk bodies (labeled by chunk id) + question. Do **not** include non-gold chunks.
3. Call the cell via `LoopbackTransport.chat` (same lifecycle as preference: start → ready → prompts → stop).
4. Persist answers under the run dir.

One cell at a time; memory floor and timeouts match preference/matrix defaults (ready 180s, request 120s, memory floor 20%).

## Score

Automatic; no pairwise preference in Phase 1.

- Fact match: **case-sensitive** exact substring of each `required_facts` entry in answer `content`
- Per answer: `hit_rate = hits / len(required_facts)`
- Per cell: mean hit rate over successful answers; unsuccessful answers count as hit_rate 0 for that prompt (or N/A — prefer **0** and record error)
- Write `scores.json` + `report.md`. Latency is metadata only.

## Artifacts

Under `results/rag/<run-id>/` (gitignored via `results/`):

| Path | Role |
|------|------|
| `raw.json` | Suite, cells, corpus id, timestamps |
| `answers/<cell_id>.json` | Per-prompt content, success/error, timings |
| `scores.json` | Per-cell / per-prompt hit rates |
| `report.md` | Human-readable ranking by mean hit rate |

## Operator docs & live smoke

`docs/rag.md` must include:

- Prerequisites (point at matrix.md for the three cells)
- `--dry-config` and unit-test commands
- Workflow: collect → score
- **Live collect requires Jason’s in-session authorization**
- **Optional live smoke checklist** (not CI): dry-config → authorize → collect default three cells → score → confirm `report.md` ranks cells by mean hit rate
- Phase 2 keyword retrieval listed as not implemented

Short pointer from `docs/preference.md` and/or `docs/matrix.md`.

## Testing

**Automated (fakes only):**

- Corpus + suite loaders; fail closed on missing chunk ids / bad fields
- Oracle prompt includes all gold text and excludes non-gold chunks
- Score: full / partial / zero hits; case-sensitive facts
- Collect with fake transport/server; CLI dry-config

**Not in CI:** live smoke (documented checklist only).

## Non-goals

- Keyword or embedding retrieval (Phase 2)
- Pairwise preference / local judge on RAG answers
- Osaurus routing overhead
- Ornith / Qwen cells
- Stage 2B / plugin
- Live unit tests against real endpoints

## Likely Files

- `bin/lmre-rag`
- `corpora/rag-oracle-v1/` (+ manifest)
- `suites/gemma-rag-oracle-v1.json`
- `src/local_model_runtime_evaluation/rag_*.py`
- `tests/test_rag_*.py`
- `docs/rag.md` (+ short pointers)

## Definition Of Done

- Fake unit tests green; `--dry-config` works
- Docs include optional live smoke checklist
- On Jason’s authorize: live collect + score produces a ranked `report.md` for the three PASS cells

## Explicit Confirmations

- Separate `lmre-rag` CLI (not folded into preference)
- Phase 1 = oracle injection + fact-hit scoring; Phase 2 = keyword retrieval (separate design)
- Corpus = synthetic + 1–2 pinned doc excerpts under `corpora/`
- Case-sensitive required facts
- Fakes in CI; optional documented live smoke
- Default cells = three screen PASS cells
