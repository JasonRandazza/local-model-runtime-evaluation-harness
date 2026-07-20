# Gemma RAG Keyword Phase 2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `lmre-rag collect --mode keyword` with simple term-overlap top-k retrieval, dual scoring (recall/precision@k + fact-hit), while keeping oracle mode default and unchanged in behavior.

**Architecture:** New `rag_retrieve.py` ranks corpus chunks by case-insensitive token overlap. Collect branches on mode: oracle uses gold chunk ids; keyword retrieves top-k and records `retrieved_chunk_ids`. Shared context prompt builder. Score extends reports for keyword runs. CLI gains `--mode` and `--top-k`.

**Tech Stack:** Python 3 stdlib, existing `rag_*` + preference `AnswerRecord`, `unittest`.

## Global Constraints

- Spec: `docs/superpowers/specs/2026-07-20-gemma-rag-keyword-phase2-design.md`
- Reuse corpus `rag-oracle-v1` and suite `gemma-rag-oracle-v1` (gold ids = retrieval ground truth)
- Modes: `oracle` (default) | `keyword`; default `--top-k` = `2` (keyword only; ignored for oracle)
- Retriever: case-insensitive term overlap; ties by ascending `chunk_id`
- Fact-hit remains case-sensitive exact substring
- Unit tests: fakes only; no live endpoints
- Do not implement BM25/embeddings, Stage 2B, preference/judge, Ornith/Qwen
- Only create git commits when the user explicitly asks

---

## File Structure

| File | Responsibility |
|------|----------------|
| `rag_retrieve.py` | Tokenize + rank + top-k |
| `rag_prompt.py` | Shared `build_context_prompt(chunk_ids, question, corpus)`; thin oracle/keyword wrappers |
| `preference_collect.py` | Optional `retrieved_chunk_ids` on `AnswerRecord` (default `None`) |
| `rag_collect.py` | Mode + top_k; persist retrieved ids; raw.json mode/top_k |
| `rag_score.py` | recall@k / precision@k + fact-hit for keyword |
| `rag_cli.py` / `docs/rag.md` | `--mode`, `--top-k`, docs |
| `tests/test_rag_retrieve.py` + updates to collect/score/cli/prompt tests | Fakes only |

---

### Task 1: Term-overlap retriever

**Files:**
- Create: `src/local_model_runtime_evaluation/rag_retrieve.py`
- Create: `tests/test_rag_retrieve.py`

**Interfaces:**
- Produces:
  - `tokenize(text: str) -> tuple[str, ...]` — split on non-alphanumeric, lowercase, drop empties
  - `score_chunk(query_tokens: tuple[str, ...], chunk_text: str) -> int`
  - `retrieve_top_k(query: str, corpus: RagCorpus, *, k: int) -> tuple[str, ...]`
  - Raise `RagError` if `k < 1`

- [ ] **Step 1: Write failing tests**

```python
def test_tokenize_lowercases_and_splits(self) -> None:
    self.assertEqual(tokenize("OSAURUS_PORT=1337!"), ("osaurus", "port", "1337"))

def test_retrieve_ports_query_ranks_syn_ports_first(self) -> None:
    corpus = RagCorpus.load(ROOT / "corpora/rag-oracle-v1")
    ids = retrieve_top_k(
        "What TCP ports do Osaurus oMLX OptiQ use OSAURUS_PORT OMLX_PORT OPTIQ_PORT",
        corpus,
        k=2,
    )
    self.assertEqual(ids[0], "syn-ports")
    self.assertEqual(len(ids), 2)

def test_retrieve_tie_break_by_chunk_id(self) -> None:
    # Construct tiny fake corpus with equal scores; assert ascending chunk_id order

def test_retrieve_rejects_non_positive_k(self) -> None:
    with self.assertRaises(RagError):
        retrieve_top_k("x", corpus, k=0)
```

- [ ] **Step 2: Run — expect FAIL**

`PYTHONPATH=src python3 -m unittest tests.test_rag_retrieve -v`

- [ ] **Step 3: Implement `rag_retrieve.py`**

Use `re.findall(r"[a-z0-9]+", text.lower())` or equivalent for tokenize.

- [ ] **Step 4: Run — expect PASS**

- [ ] **Step 5: Commit only if user asked**

---

### Task 2: Prompt + collect keyword mode

**Files:**
- Modify: `src/local_model_runtime_evaluation/rag_prompt.py`
- Modify: `src/local_model_runtime_evaluation/preference_collect.py` (`AnswerRecord`)
- Modify: `src/local_model_runtime_evaluation/rag_collect.py`
- Modify: `tests/test_rag_prompt.py`
- Modify: `tests/test_rag_collect.py`
- Modify: `tests/test_preference_collect.py` only if AnswerRecord change breaks constructors (add `retrieved_chunk_ids=None` default — existing calls should still work)

**Interfaces:**
- Produces:
  - `build_context_prompt(chunk_ids: tuple[str, ...], question: RagQuestion, corpus: RagCorpus) -> str`
  - `build_oracle_prompt(...)` → delegates to gold ids via `build_context_prompt`
  - `build_keyword_prompt(question, corpus, *, k: int) -> tuple[str, tuple[str, ...]]`  # prompt, retrieved_ids
  - `run_collect(..., *, mode: str = "oracle", top_k: int = 2)`
  - `AnswerRecord` gains `retrieved_chunk_ids: tuple[str, ...] | None = None`

Collect keyword path: call `build_keyword_prompt`; store `retrieved_chunk_ids` on each `AnswerRecord`.  
`raw.json` includes `"mode"` and, when keyword, `"top_k"`.  
Reject unknown mode with `RagError`.

- [ ] **Step 1: Write failing tests**

```python
def test_keyword_prompt_uses_retrieved_not_necessarily_gold(self) -> None:
    # For a query that retrieves syn-ports, prompt contains syn-ports text;
    # build_keyword_prompt returns retrieved ids

def test_collect_keyword_records_retrieved_ids(self) -> None:
    # Fake collect mode=keyword; each answer dict/asdict has retrieved_chunk_ids list/tuple

def test_collect_oracle_omits_or_nulls_retrieved_ids(self) -> None:
    # mode=oracle → retrieved_chunk_ids is None
```

- [ ] **Step 2: Run — expect FAIL**

- [ ] **Step 3: Implement**

Keep oracle behavior byte-compatible for prompts (same instruction + gold order).

- [ ] **Step 4: Run all rag + preference_collect tests — expect PASS**

- [ ] **Step 5: Commit only if user asked**

---

### Task 3: Score retrieval metrics + CLI + docs

**Files:**
- Modify: `src/local_model_runtime_evaluation/rag_score.py`
- Modify: `src/local_model_runtime_evaluation/rag_cli.py`
- Modify: `docs/rag.md`
- Modify: `tests/test_rag_score.py`
- Modify: `tests/test_rag_cli.py`

**Interfaces:**
- Produces:
  - `score_retrieval(retrieved: tuple[str, ...] | list[str], gold: tuple[str, ...]) -> dict` with `recall`, `precision`, `hits`, `gold_total`, `retrieved_total`
  - `score_run` reads `raw.json` mode; if keyword, include per-prompt retrieval + cell means; report tables for both
  - CLI: `--mode` choices oracle|keyword default oracle; `--top-k` type int default 2
  - dry-config JSON includes `mode` and `top_k` when mode is keyword (always include both for clarity: `"mode"`, `"top_k"`)

- [ ] **Step 1: Write failing tests**

```python
def test_score_retrieval_metrics(self) -> None:
    r = score_retrieval(("syn-ports", "syn-auth"), ("syn-ports",))
    self.assertAlmostEqual(r["recall"], 1.0)
    self.assertAlmostEqual(r["precision"], 0.5)

def test_score_run_keyword_includes_retrieval(self) -> None:
    # temp run with raw mode=keyword, answers with retrieved_chunk_ids; assert scores.json has mean_recall

def test_cli_keyword_dry_config(self) -> None:
    code = main(["collect", "--mode", "keyword", "--dry-config"])
    # stdout mode keyword, top_k 2, ok true
```

- [ ] **Step 2: Run — expect FAIL**

- [ ] **Step 3: Implement score + CLI + docs**

Docs must include: modes, `--top-k`, retrieval metrics, optional live keyword smoke checklist, BM25/embeddings not implemented.

- [ ] **Step 4: Full suite**

```bash
PYTHONPATH=src python3 -m unittest \
  tests.test_rag_retrieve tests.test_rag_config tests.test_rag_prompt \
  tests.test_rag_score tests.test_rag_collect tests.test_rag_cli \
  tests.test_preference_collect -v
```

- [ ] **Step 5: Commit only if user asked**

---

## Spec Coverage Check

| Spec item | Task |
|-----------|------|
| Term-overlap retriever + top-k + tie-break | 1 |
| `--mode` oracle\|keyword; default oracle; top-k 2 | 2, 3 |
| Keyword prompt from retrieved chunks | 2 |
| Persist retrieved_chunk_ids; raw mode/top_k | 2 |
| recall@k / precision@k + fact-hit | 3 |
| Oracle regression | 2, 3 |
| Docs + live smoke note | 3 |
| Fakes only; no BM25 | all |

---

## Execution Handoff

Plan complete. Proceeding with **Subagent-Driven Development** per “let's implement it”.
