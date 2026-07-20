# Gemma RAG Keyword Phase 2 Design

**Status:** Approved in conversation by Jason on 2026-07-20. This document authorizes implementation planning only. It does not authorize a live keyword collect, Stage 2B Gate B, plugin rebuild, BM25/embedding retrieval, pairwise preference on RAG answers, or Osaurus routing-overhead measurement.

**Depends on:** RAG oracle Phase 1 on `main` (`docs/superpowers/specs/2026-07-20-gemma-rag-oracle-phase1-design.md`). Reuses corpus `rag-oracle-v1` and suite `gemma-rag-oracle-v1`.

## Goal

**Phase 2:** End-to-end **keyword** RAG over the pinned corpus:

1. Retrieve top-k chunks by **simple term overlap**
2. Generate with retrieved context (not oracle gold injection)
3. Score both **retrieval quality** (vs suite `gold_chunk_ids`) and **fact-hit rate** (case-sensitive, unchanged from Phase 1)

Oracle mode remains available and default for backward compatibility.

## Approach

Extend `bin/lmre-rag` with `--mode oracle|keyword` (Approach 1):

```bash
./bin/lmre-rag collect --mode oracle|keyword [--top-k N] [--cells …] [--dry-config]
./bin/lmre-rag score --run DIR
```

- Default `--mode`: `oracle`
- Default `--top-k`: `2` (applies to keyword mode; ignored in oracle mode — document that)
- Default cells: same three screen PASS cells
- Live collect requires Jason’s in-session authorization

## Retriever

**Algorithm:** case-insensitive term overlap.

1. Tokenize query and chunk text by splitting on non-alphanumeric characters; drop empty tokens; lowercase for ranking.
2. `score(chunk) =` number of query tokens that appear at least once in the chunk’s token set.
3. Rank by score descending; ties broken by ascending `chunk_id` (deterministic).
4. Return top-k chunk ids (k ≥ 1).

No BM25, TF-IDF, or embeddings in this phase.

## Prompts

- **Oracle:** unchanged — inject suite `gold_chunk_ids` only.
- **Keyword:** same prompt template as oracle, but inject **retrieved** chunk bodies labeled by chunk id. Persist `retrieved_chunk_ids` on each answer record.

## Metrics

### Retrieval (keyword runs; vs `gold_chunk_ids`)

- `recall@k = |retrieved ∩ gold| / |gold|`
- `precision@k = |retrieved ∩ gold| / |retrieved|` (0 if retrieved empty)
- Per cell: mean recall@k, mean precision@k over prompts

### Generation (both modes)

- Case-sensitive required-fact hit rate (Phase 1 `score_answer` unchanged)
- Unsuccessful answers → hit_rate `0.0`

### Report

`report.md` / `scores.json` include mode, top-k (if keyword), retrieval means (keyword), and fact-hit means. Latency remains metadata only.

For **oracle** runs, retrieval metrics are omitted or recorded as N/A (prefer omit from ranking tables; note mode in header).

## Artifacts

Under `results/rag/<run-id>/` (same layout as Phase 1):

| Path | Role |
|------|------|
| `raw.json` | Must include `mode`, and `top_k` when mode is keyword |
| `answers/<cell_id>.json` | Answers; keyword rows include `retrieved_chunk_ids` |
| `scores.json` | Fact-hit + retrieval metrics when applicable |
| `report.md` | Human ranking |

## Docs

Update `docs/rag.md`:

- Modes `oracle` / `keyword`
- `--top-k` default 2
- Retrieval + fact-hit metrics
- Optional live smoke checklist for keyword mode
- BM25/embeddings still not implemented

## Testing

**Automated (fakes only):**

- Retriever ranking + top-k + tie-break determinism
- Keyword prompt uses retrieved ids (not gold unless equal)
- Score recall/precision@k + fact-hit for keyword fixtures
- Oracle path regression (fact-hit only)
- CLI `--mode keyword --dry-config`; `--top-k` accepted
- Fake collect records `retrieved_chunk_ids`

**Not in CI:** live keyword smoke (documented checklist).

## Non-goals

- BM25, TF-IDF, or embedding retrieval
- New corpus or suite (reuse Phase 1)
- Pairwise preference / local judge on RAG answers
- Osaurus routing overhead
- Ornith / Qwen cells
- Stage 2B / plugin
- Live unit tests against real endpoints

## Likely Files

- `src/.../rag_retrieve.py` (+ tests)
- Modify: `rag_prompt.py`, `rag_collect.py`, `rag_score.py`, `rag_cli.py`, `docs/rag.md`
- Tests: `tests/test_rag_retrieve.py` + updates to collect/score/cli tests

## Definition Of Done

- Fake unit tests green; dry-config works for oracle and keyword
- Docs describe modes, top-k, metrics, optional live keyword smoke
- On Jason’s authorize: keyword live collect + score produces a report with retrieval and fact-hit rankings

## Explicit Confirmations

- Extend `lmre-rag` with `--mode` (oracle default; keyword Phase 2)
- Simple term-overlap retriever; default top-k 2, overridable
- End-to-end: retrieval metrics + fact-hit
- Reuse Phase 1 corpus and suite (gold ids = retrieval ground truth)
- Fakes in CI; optional documented live smoke
