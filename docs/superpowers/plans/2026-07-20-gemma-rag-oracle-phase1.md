# Gemma RAG Oracle Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship `bin/lmre-rag` collect → automatic fact-hit score for oracle-injected gold context on the three screen PASS cells.

**Architecture:** New RAG package mirrors preference collect lifecycle (matrix `Cell`, `build_server`, credentials, `LoopbackTransport`) but injects gold chunks into prompts and scores case-sensitive required-fact substrings. No pairwise preference. Phase 2 keyword retrieval is out of scope.

**Tech Stack:** Python 3 stdlib, existing matrix/preference modules, `unittest`.

## Global Constraints

- Spec: `docs/superpowers/specs/2026-07-20-gemma-rag-oracle-phase1-design.md`
- Separate CLI `bin/lmre-rag` — do not fold into `lmre-preference`
- Default cells exactly: `jang_4m__osaurus`, `oq4_fp16__omlx`, `optiq_4bit__optiq`
- Suite: `suites/gemma-rag-oracle-v1.json` revision `1` with exactly 6 questions; `corpus_id` = `rag-oracle-v1`
- Fact match: case-sensitive exact substring; unsuccessful answers → hit_rate `0.0`
- Timeouts: ready 180s, request 120s, memory floor 20%
- Unit tests: fakes only; no live Osaurus/oMLX/OptiQ/Keychain
- Do not implement Phase 2 retrieval, preference/judge on RAG, Stage 2B, Ornith/Qwen
- Live collect requires Jason’s in-session authorization (docs only until authorized)
- Only create git commits when the user explicitly asks

---

## File Structure

| File | Responsibility |
|------|----------------|
| `corpora/rag-oracle-v1/manifest.json` + chunk `.md` files | Pinned corpus |
| `suites/gemma-rag-oracle-v1.json` | Six oracle questions |
| `src/.../rag_config.py` | Load corpus + suite; defaults |
| `src/.../rag_prompt.py` | Build oracle prompt from gold chunks |
| `src/.../rag_score.py` | Fact-hit scoring + report |
| `src/.../rag_collect.py` | One-at-a-time collect into `results/rag/` |
| `src/.../rag_cli.py` | `collect` / `score` / `--dry-config` |
| `bin/lmre-rag` | Bootstrap like `bin/lmre-preference` |
| `docs/rag.md` | Operator guide + live smoke checklist |
| `docs/preference.md`, `docs/matrix.md` | One-line pointers |
| `tests/test_rag_*.py` | Fakes-only unit tests |

---

### Task 1: Corpus + suite + config loaders

**Files:**
- Create: `corpora/rag-oracle-v1/manifest.json`
- Create: `corpora/rag-oracle-v1/syn-ports.md`
- Create: `corpora/rag-oracle-v1/syn-auth.md`
- Create: `corpora/rag-oracle-v1/syn-ram.md`
- Create: `corpora/rag-oracle-v1/syn-lifecycle.md`
- Create: `corpora/rag-oracle-v1/excerpt-matrix-auth.md` (pinned copy of Keychain service name facts)
- Create: `corpora/rag-oracle-v1/excerpt-preference-pointer.md` (pinned copy: preference POC exists; CLI name `lmre-preference`)
- Create: `suites/gemma-rag-oracle-v1.json`
- Create: `src/local_model_runtime_evaluation/rag_config.py`
- Create: `tests/test_rag_config.py`

**Interfaces:**
- Produces:
  - `DEFAULT_RAG_CELLS: tuple[str, ...] = ("jang_4m__osaurus", "oq4_fp16__omlx", "optiq_4bit__optiq")`
  - `RagError(RuntimeError)`
  - `CorpusChunk(chunk_id: str, title: str, text: str)`
  - `RagCorpus.load(root: Path) -> RagCorpus` with `.get(chunk_id) -> CorpusChunk` and `.chunks`
  - `RagQuestion(prompt_id, question, gold_chunk_ids: tuple[str, ...], required_facts: tuple[str, ...], max_tokens: int)`
  - `RagSuite.load(path: Path) -> RagSuite` with `suite_id`, `revision`, `corpus_id`, `questions` (len 6)

**Corpus content (exact locked tokens — use these strings in files and suite facts):**

`syn-ports.md` must contain: `OSAURUS_PORT=1337`, `OMLX_PORT=8100`, `OPTIQ_PORT=8080`  
`syn-auth.md` must contain: `KEYCHAIN_SERVICE=local.jrazz.lmre.osaurus`, `OMLX_LOOPBACK_KEY=lmre-matrix-local`, `OPTIQ_FLAG=--no-auth`  
`syn-ram.md` must contain: `MEMORY_FLOOR_PERCENT=20`, `READY_TIMEOUT_SECONDS=180`  
`syn-lifecycle.md` must contain: `ONE_CELL_AT_A_TIME=true`, `STAGE2B_FROZEN=true`  
`excerpt-matrix-auth.md` must contain: `local.jrazz.lmre.osaurus` and `benchmark-harness`  
`excerpt-preference-pointer.md` must contain: `lmre-preference` and `gemma-preference-v1`

`manifest.json` shape:

```json
{
  "corpus_id": "rag-oracle-v1",
  "chunks": [
    {"chunk_id": "syn-ports", "path": "syn-ports.md", "title": "Loopback ports"},
    {"chunk_id": "syn-auth", "path": "syn-auth.md", "title": "Auth tokens"},
    {"chunk_id": "syn-ram", "path": "syn-ram.md", "title": "RAM and timeouts"},
    {"chunk_id": "syn-lifecycle", "path": "syn-lifecycle.md", "title": "Lifecycle rules"},
    {"chunk_id": "excerpt-matrix-auth", "path": "excerpt-matrix-auth.md", "title": "Matrix Keychain excerpt"},
    {"chunk_id": "excerpt-preference-pointer", "path": "excerpt-preference-pointer.md", "title": "Preference pointer excerpt"}
  ]
}
```

Suite: exactly 6 questions; each uses 1–2 gold chunk ids; `required_facts` are subsets of the locked tokens above. Example first item:

```json
{
  "prompt_id": "ports-lookup",
  "question": "According to the context only, what TCP ports do Osaurus, oMLX, and OptiQ use for the matrix campaign?",
  "gold_chunk_ids": ["syn-ports"],
  "required_facts": ["OSAURUS_PORT=1337", "OMLX_PORT=8100", "OPTIQ_PORT=8080"],
  "max_tokens": 256
}
```

Remaining five prompt_ids (required): `auth-lookup`, `ram-floor`, `lifecycle-rule`, `keychain-account`, `preference-cli-name` — map gold chunks and required_facts to the locked tokens so each fact appears in its gold chunk(s).

- [ ] **Step 1: Write failing tests**

```python
# tests/test_rag_config.py
ROOT = Path(__file__).resolve().parents[1]

def test_corpus_loads_six_chunks(self) -> None:
    corpus = RagCorpus.load(ROOT / "corpora/rag-oracle-v1")
    self.assertEqual(corpus.corpus_id, "rag-oracle-v1")
    self.assertEqual(len(corpus.chunks), 6)
    self.assertIn("OSAURUS_PORT=1337", corpus.get("syn-ports").text)

def test_suite_loads_six_questions(self) -> None:
    suite = RagSuite.load(ROOT / "suites/gemma-rag-oracle-v1.json")
    self.assertEqual(suite.suite_id, "gemma-rag-oracle-v1")
    self.assertEqual(suite.revision, "1")
    self.assertEqual(suite.corpus_id, "rag-oracle-v1")
    self.assertEqual(len(suite.questions), 6)
    self.assertEqual(DEFAULT_RAG_CELLS, ("jang_4m__osaurus", "oq4_fp16__omlx", "optiq_4bit__optiq"))

def test_suite_rejects_wrong_question_count(self) -> None:
    # temp JSON with 5 questions → RagError
```

- [ ] **Step 2: Run — expect FAIL**

`PYTHONPATH=src python3 -m unittest tests.test_rag_config -v`

- [ ] **Step 3: Implement corpus files + suite + `rag_config.py`**

Loader rules: exact suite fields `schema_version,suite_id,revision,temperature,streaming,corpus_id,questions`; `schema_version=="1.0.0"`; `temperature==0`; `streaming is True`; `corpus_id=="rag-oracle-v1"`; exactly 6 unique `prompt_id`; each question exact fields `prompt_id,question,gold_chunk_ids,required_facts,max_tokens`; lists non-empty; `max_tokens` int > 0.

- [ ] **Step 4: Run — expect PASS**

- [ ] **Step 5: Commit only if user asked**

---

### Task 2: Oracle prompt builder + scorer

**Files:**
- Create: `src/local_model_runtime_evaluation/rag_prompt.py`
- Create: `src/local_model_runtime_evaluation/rag_score.py`
- Create: `tests/test_rag_prompt.py`
- Create: `tests/test_rag_score.py`

**Interfaces:**
- Consumes: `RagCorpus`, `RagQuestion`, `RagError`
- Produces:
  - `build_oracle_prompt(question: RagQuestion, corpus: RagCorpus) -> str`
  - `score_answer(content: str | None, required_facts: tuple[str, ...], *, success: bool) -> dict` with keys `hits`, `total`, `hit_rate`, `missing_facts`
  - `score_run(run_dir: Path, suite: RagSuite) -> Path` writes `scores.json` + `report.md`

`build_oracle_prompt` must:
1. Fail closed if any `gold_chunk_id` missing from corpus
2. Include instruction: use only provided context
3. Include each gold chunk labeled with its `chunk_id`
4. Append the question
5. Not include text from non-gold chunks

`score_answer`: case-sensitive `fact in content` for each fact; if `success is False` or `content is None` → `hit_rate=0.0`, all facts in `missing_facts`.

`score_run`: load `answers/*.json` (same shape as preference: `answers` list with `prompt_id`, `content`, `success`); compute per-prompt and mean per cell; rank cells by mean hit rate descending in `report.md`.

- [ ] **Step 1: Write failing tests**

```python
def test_oracle_prompt_includes_gold_excludes_other(self) -> None:
    # load real corpus; question gold=[syn-ports]; assert OSAURUS_PORT in prompt;
    # assert KEYCHAIN_SERVICE not in prompt (from syn-auth)

def test_score_full_partial_zero_and_case(self) -> None:
    full = score_answer("... OSAURUS_PORT=1337 ... OMLX_PORT=8100 ... OPTIQ_PORT=8080",
                        ("OSAURUS_PORT=1337", "OMLX_PORT=8100", "OPTIQ_PORT=8080"), success=True)
    self.assertEqual(full["hit_rate"], 1.0)
    partial = score_answer("OSAURUS_PORT=1337", ("OSAURUS_PORT=1337", "OMLX_PORT=8100"), success=True)
    self.assertAlmostEqual(partial["hit_rate"], 0.5)
    self.assertEqual(score_answer("osaurus_port=1337", ("OSAURUS_PORT=1337",), success=True)["hit_rate"], 0.0)
    self.assertEqual(score_answer(None, ("X",), success=False)["hit_rate"], 0.0)

def test_score_run_writes_report(self) -> None:
    # temp run_dir with answers for one cell; assert scores.json + report.md
```

- [ ] **Step 2: Run — expect FAIL**

- [ ] **Step 3: Implement `rag_prompt.py` + `rag_score.py`**

- [ ] **Step 4: Run — expect PASS**

Also re-run `tests.test_rag_config`.

- [ ] **Step 5: Commit only if user asked**

---

### Task 3: Collect (fakeable)

**Files:**
- Create: `src/local_model_runtime_evaluation/rag_collect.py`
- Create: `tests/test_rag_collect.py`

**Interfaces:**
- Consumes: `Cell`, `build_server`, `resolve_credential` from `preference_collect` (prefer import), `RagSuite`, `RagCorpus`, `build_oracle_prompt`, `LoopbackTransport`
- Produces:
  - `run_collect(cell_ids, suite_path, corpus_root, cells_root, results_root, ...) -> Path`
  - Run dir: `results_root / f"gemma-rag-{timestamp}"` with `raw.json`, `answers/<cell_id>.json`

Logic mirrors `preference_collect.run_collect`: memory floor break; server failure → empty/error answers file and continue; per-question `TransportError` → success=False continue; stop in `finally`.

Each chat uses `build_oracle_prompt(question, corpus)` as the prompt string and `question.max_tokens`.

- [ ] **Step 1: Write failing tests** with FakeHandle / FakeTransport (copy patterns from `tests/test_preference_collect.py`)

```python
def test_collect_writes_one_answer_per_question(self) -> None:
    # Fake chat returns content containing required facts; len(answers)==6; all success

def test_transport_error_continues(self) -> None:
    # first raises TransportError; rest ok
```

- [ ] **Step 2: Run — expect FAIL**

- [ ] **Step 3: Implement `rag_collect.py`**

- [ ] **Step 4: Run — expect PASS** + prior rag tests

- [ ] **Step 5: Commit only if user asked**

---

### Task 4: CLI + docs + dry-config

**Files:**
- Create: `src/local_model_runtime_evaluation/rag_cli.py`
- Create: `bin/lmre-rag` (chmod +x; mirror `bin/lmre-preference`)
- Create: `docs/rag.md`
- Modify: `docs/preference.md` (one-line RAG pointer)
- Modify: `docs/matrix.md` (one-line RAG pointer)
- Create: `tests/test_rag_cli.py`

**Interfaces:**
- Produces: `main(argv) -> int`
- Subcommands: `collect` (flags per spec), `score --run DIR`
- `--dry-config`: load suite + corpus + each cell JSON; print `{"ok": true, "cells":[...], "questions": 6, "corpus_id": "rag-oracle-v1"}`; exit 0; no network

- [ ] **Step 1: Write failing CLI tests**

```python
def test_collect_dry_config_ok(self) -> None:
    # capture stdout; code 0; ok true; questions 6; three default cells

def test_score_missing_run_fails(self) -> None:
    # redirect_stdout; code 1
```

- [ ] **Step 2: Run — expect FAIL**

- [ ] **Step 3: Implement CLI + docs**

`docs/rag.md` must include optional live smoke checklist exactly as a checklist:

1. `./bin/lmre-rag collect --dry-config`
2. Obtain Jason’s in-session authorization for live collect
3. `./bin/lmre-rag collect`
4. `./bin/lmre-rag score --run results/rag/gemma-rag-<timestamp>`
5. Confirm `report.md` ranks cells by mean hit rate

State Phase 2 keyword retrieval is not implemented.

- [ ] **Step 4: Full suite**

```bash
PYTHONPATH=src python3 -m unittest \
  tests.test_rag_config tests.test_rag_prompt tests.test_rag_score \
  tests.test_rag_collect tests.test_rag_cli -v

PYTHONPATH=src python3 -m unittest \
  tests.test_preference_cli tests.test_matrix_config -q
```

Expected: all PASS; preference/matrix untouched except doc pointers.

- [ ] **Step 5: Commit only if user asked**

---

## Spec Coverage Check

| Spec requirement | Task |
|------------------|------|
| `lmre-rag` collect/score CLI | 4 |
| Default three PASS cells | 1, 4 |
| Corpus synthetic + excerpts under `corpora/` | 1 |
| Suite 6 questions + loader | 1 |
| Oracle prompt gold-only | 2 |
| Case-sensitive fact-hit score + report | 2 |
| Collect lifecycle reuse | 3 |
| Artifacts under `results/rag/` | 3, 2 |
| Docs + live smoke checklist + Phase 2 note | 4 |
| Fakes-only unit tests | 1–4 |
| No Phase 2 / preference / Stage 2B | constraints |

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-07-20-gemma-rag-oracle-phase1.md`. Two execution options:

1. **Subagent-Driven (recommended)** — fresh subagent per task, review between tasks  
2. **Inline Execution** — execute in this session with checkpoints  

Which approach?
