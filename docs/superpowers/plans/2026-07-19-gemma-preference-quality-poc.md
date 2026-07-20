# Gemma Preference Quality POC Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship `bin/lmre-preference` collect → blind review → human judgments → tally for the three screen PASS cells on a 6-prompt preference pack.

**Architecture:** Separate preference package reuses matrix `Cell` configs, server lifecycle, credentials, and `LoopbackTransport`. Collect writes per-cell answers; review builds shuffled A/B pairs; tally reads human `judgments.json` and writes `report.md`. No local judge or RAG in this plan.

**Tech Stack:** Python 3 stdlib, existing `local_model_runtime_evaluation` matrix modules, `unittest`.

## Global Constraints

- Spec: `docs/superpowers/specs/2026-07-19-gemma-preference-quality-poc-design.md`
- Default cells exactly: `jang_4m__osaurus`, `oq4_fp16__omlx`, `optiq_4bit__optiq`
- Suite: `suites/gemma-preference-v1.json` revision `1` with exactly 6 prompts
- Pairwise: round-robin → 3 pairs × 6 prompts = 18 judgments; labels `A` | `B` | `tie` only
- Separate CLI `bin/lmre-preference` — do not add a `lmre-matrix` quality mode
- Reuse matrix cell JSON + lifecycle/auth as-is (including OptiQ `:no-think` model ids)
- Unit tests: fakes only; no live Osaurus/oMLX/OptiQ/Keychain contact
- Do not modify Stage 0–2B contracts, plugin, or Gate B paths
- Do not implement local judge, RAG, or Osaurus overhead in this plan
- Results under `results/preference/` (already covered by `results/` gitignore)
- Only create git commits when the user explicitly asks (ignore per-task commit steps unless requested)

---

## File Structure

| File | Responsibility |
|------|----------------|
| `suites/gemma-preference-v1.json` | Six preference prompts |
| `src/.../preference_config.py` | Load/validate preference suite + default cell ids |
| `src/.../preference_collect.py` | One-at-a-time answer collection into `answers/` |
| `src/.../preference_review.py` | Build `pairs.json` + blind `review.md` + empty `judgments.json` stub |
| `src/.../preference_tally.py` | Score judgments → `report.md` |
| `src/.../preference_cli.py` | argparse subcommands `collect` / `review` / `tally` |
| `bin/lmre-preference` | PYTHONPATH bootstrap → `preference_cli.main` |
| `docs/preference.md` | Operator guide |
| `docs/matrix.md` | One-line pointer to preference POC |
| `tests/test_preference_*.py` | Unit tests with fakes |

---

### Task 1: Preference suite + config loader

**Files:**
- Create: `suites/gemma-preference-v1.json`
- Create: `src/local_model_runtime_evaluation/preference_config.py`
- Create: `tests/test_preference_config.py`

**Interfaces:**
- Consumes: none (stdlib + pathlib)
- Produces:
  - `DEFAULT_PREFERENCE_CELLS: tuple[str, ...] = ("jang_4m__osaurus", "oq4_fp16__omlx", "optiq_4bit__optiq")`
  - `PreferencePrompt(prompt_id: str, prompt: str, max_tokens: int)`
  - `PreferenceSuite(suite_id: str, revision: str, prompts: tuple[PreferencePrompt, ...])`
  - `PreferenceSuite.load(path: Path) -> PreferenceSuite`
  - `PreferenceError(RuntimeError)`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_preference_config.py
from __future__ import annotations
import unittest
from pathlib import Path
from local_model_runtime_evaluation.preference_config import (
    DEFAULT_PREFERENCE_CELLS,
    PreferenceError,
    PreferenceSuite,
)

ROOT = Path(__file__).resolve().parents[1]

class PreferenceConfigTests(unittest.TestCase):
    def test_suite_loads_six_prompts(self) -> None:
        suite = PreferenceSuite.load(ROOT / "suites/gemma-preference-v1.json")
        self.assertEqual(suite.suite_id, "gemma-preference-v1")
        self.assertEqual(suite.revision, "1")
        self.assertEqual(len(suite.prompts), 6)
        self.assertEqual(len({p.prompt_id for p in suite.prompts}), 6)
        self.assertEqual(
            DEFAULT_PREFERENCE_CELLS,
            ("jang_4m__osaurus", "oq4_fp16__omlx", "optiq_4bit__optiq"),
        )

    def test_rejects_wrong_prompt_count(self) -> None:
        # write temp json with 5 prompts in the test using tempfile
        ...
```

Include a temp-file test that raises `PreferenceError` when prompt count ≠ 6.

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src python3 -m unittest tests.test_preference_config -v`  
Expected: FAIL (module or suite file missing)

- [ ] **Step 3: Write suite JSON + loader**

`suites/gemma-preference-v1.json` exact shape:

```json
{
  "schema_version": "1.0.0",
  "suite_id": "gemma-preference-v1",
  "revision": "1",
  "temperature": 0,
  "streaming": true,
  "prompts": [
    {
      "prompt_id": "tradeoff-explain",
      "prompt": "In 4-6 sentences, explain the tradeoff between running a larger local model slowly versus a smaller one that answers instantly for everyday coding questions on a 64 GB Mac. End with one concrete recommendation.",
      "max_tokens": 256
    },
    {
      "prompt_id": "local-ops-advice",
      "prompt": "Give practical advice for keeping one heavy local LLM resident without thrashing memory when switching between chat and a short benchmark. Use short bullets.",
      "max_tokens": 256
    },
    {
      "prompt_id": "multi-step-plan",
      "prompt": "Outline a concise 5-step plan to compare two local model servers on the same artifact without overlapping their ports or leaving orphan processes.",
      "max_tokens": 256
    },
    {
      "prompt_id": "uncertainty-handling",
      "prompt": "A user asks which unpublished quantization will be fastest on their machine next month. Respond helpfully while clearly marking what is unknown versus what can be measured today.",
      "max_tokens": 256
    },
    {
      "prompt_id": "clarity-rewrite",
      "prompt": "Rewrite this for clarity without adding new claims: \"We should maybe like try the thing with the servers but only one at a time because RAM and also the key might be wrong so check inventory first I guess.\"",
      "max_tokens": 256
    },
    {
      "prompt_id": "compare-recommend",
      "prompt": "Briefly compare wall-clock latency versus answer quality when choosing a daily-driver local 12B model, then recommend which to prioritize for interactive coding help and why (one short paragraph).",
      "max_tokens": 256
    }
  ]
}
```

Loader rules: exact fields `schema_version,suite_id,revision,temperature,streaming,prompts`; `schema_version=="1.0.0"`; `temperature==0`; `streaming is True`; exactly 6 prompts; unique `prompt_id`; each prompt has `prompt_id`, `prompt`, `max_tokens` (int > 0).

- [ ] **Step 4: Run tests — expect PASS**

Run: `PYTHONPATH=src python3 -m unittest tests.test_preference_config -v`

- [ ] **Step 5: Commit only if user asked**

---

### Task 2: Collect answers (fakeable)

**Files:**
- Create: `src/local_model_runtime_evaluation/preference_collect.py`
- Create: `tests/test_preference_collect.py`
- Modify: none of Stage 2B

**Interfaces:**
- Consumes:
  - `Cell.load`, `build_server`, matrix `_credential_for` pattern (import or duplicate thin wrapper in preference_collect that calls the same Keychain/oMLX/OptiQ rules)
  - `PreferenceSuite`, `LoopbackTransport`, `HostResourceProbe`
- Produces:
  - `AnswerRecord` dataclass with fields: `prompt_id`, `cell_id`, `model_id`, `content`, `success`, `error`, `total_seconds`, `ttft_seconds`
  - `collect_cell(cell, suite, transport, *, credential, build_server, probe, cancel, ready_timeout, log_dir) -> list[AnswerRecord]`
  - `write_answers(path: Path, cell_id: str, records: list[AnswerRecord]) -> None`
  - `run_collect(cell_ids, suite_path, cells_root, results_root, ...) -> Path` returning run dir

- [ ] **Step 1: Write failing unit test with fake transport + fake server**

```python
def test_collect_cell_writes_one_answer_per_prompt(self) -> None:
    # Fake handle: start/wait_ready/stop no-ops
    # Fake transport.chat returns TransportResult-like object OR patch LoopbackTransport
    # Prefer injecting a tiny protocol:
    #   class FakeTransport:
    #       def list_models(...): return (cell.model_id,)
    #       def chat(...): return SimpleNamespace(content="ok", total_seconds=1.0, ttft_seconds=0.2, ...)
```

Assert: `len(records)==6`, each `success is True`, `content=="ok"`.

Also test: if `chat` raises `TransportError`, record `success=False` and continue remaining prompts (do not abort the whole cell unless server start fails).

- [ ] **Step 2: Run test — expect FAIL**

Run: `PYTHONPATH=src python3 -m unittest tests.test_preference_collect -v`

- [ ] **Step 3: Implement collect**

Logic for one cell:

1. `credential = resolve_credential(cell.server)` (copy the matrix `_credential_for` function into `preference_collect.py` or import from `matrix_runner` if already exported; prefer a shared thin `matrix_credentials.py` **only if** import from `matrix_runner` pulls CLI — do **not** create a big refactor. Duplicating the 20-line `_credential_for` into preference_collect is acceptable for YAGNI.)
2. `handle = build_server(cell, transport, log_dir, credential=credential)`
3. `handle.start(); handle.wait_ready(cell.model_id, ready_timeout)`
4. For each prompt in suite: call `transport.chat(base_url, model_id, prompt, max_tokens, credential, cancel)`; on success store content + timings; on `TransportError` store error.
5. `handle.stop()` in `finally`
6. Write `answers/<cell_id>.json` as `{"cell_id", "model_id", "answers":[...]}`

`run_collect`:

- Create `results/preference/gemma-preference-<timestamp>/`
- Write `raw.json` with suite id, cell ids, started_at
- For each cell id: load `config/matrix/cells/<id>.json`, check memory floor, collect, persist answers
- On cell server failure: write answers file with empty/error marker and continue (mirror matrix `continue` policy)
- Return run dir Path

Default timeouts: ready 180s, request 120s, memory floor 20 (match campaign).

- [ ] **Step 4: Run tests — expect PASS**

- [ ] **Step 5: Commit only if user asked**

---

### Task 3: Review pack (pairs + blind markdown + judgments stub)

**Files:**
- Create: `src/local_model_runtime_evaluation/preference_review.py`
- Create: `tests/test_preference_review.py`

**Interfaces:**
- Consumes: answer files from Task 2
- Produces:
  - `build_pairs(cell_ids: tuple[str, ...], prompt_ids: tuple[str, ...], *, rng: random.Random) -> list[dict]`
  - `write_review(run_dir: Path, pairs: list[dict], answers_by_cell: dict[str, dict]) -> None`
  - Each pair item keys: `pair_id`, `prompt_id`, `cell_a`, `cell_b`, `answer_a`, `answer_b` (answers in review file only as A/B text; `pairs.json` includes `cell_a`/`cell_b` mapping)

Pair construction:

```python
# round-robin unique unordered pairs
pairs_cells = [("jang_4m__osaurus","oq4_fp16__omlx"), ("jang_4m__osaurus","optiq_4bit__optiq"), ("oq4_fp16__omlx","optiq_4bit__optiq")]
for prompt_id in prompt_ids:
    for left, right in pairs_cells:
        a, b = (left, right) if rng.random() < 0.5 else (right, left)
        ...
```

`pair_id` format: `{prompt_id}__{index:02d}` unique across the run.

- [ ] **Step 1: Write failing tests**

```python
def test_build_pairs_count_is_eighteen(self) -> None:
    pairs = build_pairs(DEFAULT_PREFERENCE_CELLS, prompt_ids, rng=random.Random(0))
    self.assertEqual(len(pairs), 18)

def test_review_hides_cell_ids_in_markdown_body(self) -> None:
    # after write_review, review.md must contain "**A**" / "**B**"
    # and must NOT contain the substring "jang_4m__osaurus" in the judgment sections
    # (cell ids may appear only in an HTML comment or not at all — prefer not at all in review.md)
```

Also assert `judgments.json` stub is created as:

```json
{"judgments": [{"pair_id": "...", "winner": null}, ...]}
```

- [ ] **Step 2: Run — expect FAIL**

- [ ] **Step 3: Implement review writer**

`review.md` template per item:

```markdown
### Pair `{pair_id}`
Prompt (`{prompt_id}`):

> {prompt text}

**A**

{answer_a}

**B**

{answer_b}

Winner: _(set in judgments.json: A | B | tie)_
```

Header note: “Do not look up cell ids; mark judgments.json only.”

- [ ] **Step 4: Run — expect PASS**

- [ ] **Step 5: Commit only if user asked**

---

### Task 4: Tally

**Files:**
- Create: `src/local_model_runtime_evaluation/preference_tally.py`
- Create: `tests/test_preference_tally.py`

**Interfaces:**
- Consumes: `pairs.json`, `judgments.json`
- Produces:
  - `tally(pairs, judgments) -> dict` with per-cell `{wins, losses, ties, win_rate}`
  - `win_rate = wins / (wins + losses)` or `null` if wins+losses==0
  - `render_tally_report(...) -> str`
  - `run_tally(run_dir: Path) -> Path` writes `report.md`

- [ ] **Step 1: Write failing tests**

```python
def test_tally_win_rates(self) -> None:
    pairs = [
        {"pair_id": "p1", "prompt_id": "x", "cell_a": "c1", "cell_b": "c2"},
        {"pair_id": "p2", "prompt_id": "x", "cell_a": "c1", "cell_b": "c2"},
    ]
    judgments = [
        {"pair_id": "p1", "winner": "A"},  # c1 wins
        {"pair_id": "p2", "winner": "tie"},
    ]
    result = tally(pairs, judgments)
    self.assertEqual(result["c1"]["wins"], 1)
    self.assertEqual(result["c1"]["ties"], 1)
    self.assertEqual(result["c2"]["losses"], 1)
    self.assertAlmostEqual(result["c1"]["win_rate"], 1.0)

def test_rejects_unknown_winner(self) -> None:
    with self.assertRaises(PreferenceError):
        tally(pairs, [{"pair_id": "p1", "winner": "C"}])
```

Require every `pair_id` in pairs has a judgment with non-null winner before tally succeeds (fail closed with clear error listing missing ids).

- [ ] **Step 2: Run — expect FAIL**

- [ ] **Step 3: Implement tally + report markdown**

Report sections:

- Run id / suite
- Per-cell table: wins, losses, ties, win_rate
- Note that latency was not used for preference

- [ ] **Step 4: Run — expect PASS**

- [ ] **Step 5: Commit only if user asked**

---

### Task 5: CLI + docs + dry wiring test

**Files:**
- Create: `src/local_model_runtime_evaluation/preference_cli.py`
- Create: `bin/lmre-preference` (mirror `bin/lmre-matrix` bootstrap)
- Create: `docs/preference.md`
- Modify: `docs/matrix.md` (add short “Preference quality POC” pointer)
- Create: `tests/test_preference_cli.py`

**Interfaces:**
- Consumes: Tasks 1–4 entrypoints
- Produces: `main(argv) -> int`

Subcommands:

```text
lmre-preference collect [--cells id,id] [--suite PATH] [--results-dir PATH] [--dry-config]
lmre-preference review --run DIR [--seed INT]
lmre-preference tally --run DIR
```

`--dry-config` on collect: load suite + cell JSONs, print `{"ok": true, "cells":[...], "prompts": 6}` JSON, exit 0, no network.

- [ ] **Step 1: Write failing CLI dry-config test**

```python
def test_collect_dry_config_ok(self) -> None:
    code = main(["collect", "--dry-config"])
    self.assertEqual(code, 0)
```

Capture stdout JSON with `ok: true` and three default cells.

- [ ] **Step 2: Run — expect FAIL**

- [ ] **Step 3: Implement CLI + bin + docs**

`docs/preference.md` must include:

- Prerequisites (same as matrix for the three cells)
- collect → review → edit judgments → tally commands
- Judgment labels
- Explicit: live collect requires Jason’s in-session authorization
- Follow-ons listed (judge / RAG / overhead) as not implemented

- [ ] **Step 4: Run full preference unit suite**

Run:

```bash
PYTHONPATH=src python3 -m unittest \
  tests.test_preference_config \
  tests.test_preference_collect \
  tests.test_preference_review \
  tests.test_preference_tally \
  tests.test_preference_cli -v
```

Expected: all PASS

Also run matrix unit tests still green:

```bash
PYTHONPATH=src python3 -m unittest \
  tests.test_matrix_config tests.test_matrix_metrics \
  tests.test_matrix_runner tests.test_matrix_servers -q
```

- [ ] **Step 5: Commit only if user asked**

---

## Spec Coverage Check

| Spec requirement | Task |
|------------------|------|
| Separate `lmre-preference` CLI | 5 |
| Default three PASS cells | 1, 5 |
| `gemma-preference-v1` 6 prompts | 1 |
| Collect one-at-a-time reuse matrix lifecycle | 2 |
| Blind review + pairs.json + judgments stub | 3 |
| Human A/B/tie tally + report | 4 |
| Artifacts under `results/preference/` | 2–4 |
| No live unit tests | all tests |
| No judge/RAG/overhead | explicit non-goals; not scheduled |
| Docs pointer | 5 |

## Placeholder Scan

No TBD/TODO steps; suite prompt text included; interfaces named.

## Type Consistency

- `PreferenceSuite` / `PreferencePrompt` used across Tasks 1–2  
- `pair_id` + `winner` shared by Tasks 3–4  
- `AnswerRecord` fields match artifact schema in Task 2  

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-07-19-gemma-preference-quality-poc.md`.

**Two execution options:**

1. **Subagent-Driven (recommended)** — fresh subagent per task, review between tasks  
2. **Inline Execution** — execute tasks in this session with checkpoints  

Which approach?
