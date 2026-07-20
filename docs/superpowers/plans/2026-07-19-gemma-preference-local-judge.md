# Gemma Preference Local Judge Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `lmre-preference judge` that scores an existing blind preference run with `jang_4m__osaurus` (overrideable) and writes `judgments.json` in the same shape humans edit.

**Architecture:** New `preference_judge.py` reuses matrix `Cell` lifecycle + `LoopbackTransport` like collect. Pure parse/prompt helpers are unit-tested with fakes; `run_judge` starts the judge cell once, scores pairs serially with one parse retry, writes `judgments.json` + `judge_raw.json`, updates `raw.json` metadata. CLI gains `judge` with `--dry-config`. Tally stays unchanged (already ignores extra judgment fields).

**Tech Stack:** Python 3 stdlib, existing preference + matrix modules, `unittest`.

## Global Constraints

- Spec: `docs/superpowers/specs/2026-07-19-gemma-preference-local-judge-design.md`
- Default judge cell exactly: `jang_4m__osaurus`; override via `--judge-cell`
- Separate `judge` subcommand — do **not** add `review --judge local`
- Judgment labels: exact `A` | `B` | `tie` (case-sensitive); optional `reason` truncated to 500 chars
- One automatic retry on parse failure; then `winner: null` + error in `judge_raw.json`
- Self-pairs involving the judge cell are still judged (document bias)
- Reuse matrix cell JSON + lifecycle/auth (Osaurus Keychain, OptiQ `:no-think`, oMLX key)
- Unit tests: fakes only; no live Osaurus/oMLX/OptiQ/Keychain contact
- Do not modify Stage 0–2B contracts, plugin, or Gate B paths
- Do not implement RAG or Osaurus routing overhead
- Live judge requires Jason’s in-session authorization (docs only in this plan)
- Only create git commits when the user explicitly asks (ignore per-task commit steps unless requested)

---

## File Structure

| File | Responsibility |
|------|----------------|
| `src/.../preference_judge.py` | Prompt, parse, `run_judge`, artifact writers |
| `tests/test_preference_judge.py` | Fakes-only unit tests for parse + run_judge |
| `src/.../preference_cli.py` | Add `judge` subcommand + dry-config |
| `tests/test_preference_cli.py` | Dry-config + error-path CLI tests |
| `tests/test_preference_tally.py` | Assert optional `reason` does not break tally |
| `docs/preference.md` | Operator docs for judge + bias + auth |

---

### Task 1: Judge prompt + response parser

**Files:**
- Create: `src/local_model_runtime_evaluation/preference_judge.py`
- Create: `tests/test_preference_judge.py`

**Interfaces:**
- Consumes: `PreferenceError` from `preference_config`
- Produces:
  - `DEFAULT_JUDGE_CELL: str = "jang_4m__osaurus"`
  - `REASON_MAX_CHARS: int = 500`
  - `build_judge_prompt(prompt_text: str, answer_a: str, answer_b: str) -> str`
  - `parse_judge_response(text: str) -> dict[str, str | None]` returning `{"winner": "A"|"B"|"tie", "reason": str | None}` or raising `PreferenceError`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_preference_judge.py
from __future__ import annotations
import unittest
from local_model_runtime_evaluation.preference_config import PreferenceError
from local_model_runtime_evaluation.preference_judge import (
    DEFAULT_JUDGE_CELL,
    REASON_MAX_CHARS,
    build_judge_prompt,
    parse_judge_response,
)

class PreferenceJudgeParseTests(unittest.TestCase):
    def test_default_judge_cell(self) -> None:
        self.assertEqual(DEFAULT_JUDGE_CELL, "jang_4m__osaurus")

    def test_parse_happy_path(self) -> None:
        result = parse_judge_response('{"winner": "A", "reason": "Clearer structure."}')
        self.assertEqual(result["winner"], "A")
        self.assertEqual(result["reason"], "Clearer structure.")

    def test_parse_winner_only(self) -> None:
        result = parse_judge_response('{"winner": "tie"}')
        self.assertEqual(result["winner"], "tie")
        self.assertIsNone(result["reason"])

    def test_parse_rejects_invalid_winner(self) -> None:
        with self.assertRaises(PreferenceError):
            parse_judge_response('{"winner": "C"}')

    def test_parse_rejects_malformed_json(self) -> None:
        with self.assertRaises(PreferenceError):
            parse_judge_response("not json")

    def test_parse_extracts_json_object_from_fenced_text(self) -> None:
        # Model may wrap JSON in prose or fences; extract first {...} object
        text = 'Here is my verdict:\n```json\n{"winner": "B", "reason": "More concrete."}\n```'
        result = parse_judge_response(text)
        self.assertEqual(result["winner"], "B")

    def test_reason_truncated(self) -> None:
        long_reason = "x" * (REASON_MAX_CHARS + 50)
        result = parse_judge_response(
            '{"winner": "A", "reason": "' + long_reason + '"}'
        )
        self.assertEqual(len(result["reason"] or ""), REASON_MAX_CHARS)

    def test_build_judge_prompt_hides_cell_ids(self) -> None:
        prompt = build_judge_prompt(
            "Explain tradeoffs.",
            "Answer text A mentioning nothing sensitive.",
            "Answer text B.",
        )
        self.assertIn("Explain tradeoffs.", prompt)
        self.assertIn("Answer text A", prompt)
        self.assertIn("Answer text B", prompt)
        self.assertNotIn("jang_4m", prompt)
        self.assertNotIn("osaurus", prompt)
        self.assertIn('"winner"', prompt)
```

- [ ] **Step 2: Run — expect FAIL**

Run: `PYTHONPATH=src python3 -m unittest tests.test_preference_judge -v`  
Expected: FAIL (module missing)

- [ ] **Step 3: Implement prompt + parser only**

In `preference_judge.py`:

- `build_judge_prompt`: instruct the model to reply with **only** a JSON object `{"winner":"A"|"B"|"tie","reason":"..."}`; include the user prompt and labeled **A** / **B** answer bodies; never include cell ids.
- `parse_judge_response`:
  1. Strip whitespace.
  2. Try `json.loads` on the whole string; if that fails, find the first `{` … matching `}` substring and parse that.
  3. Require a dict with `winner` in `{"A","B","tie"}`.
  4. Optional `reason`: if present and not `None`, coerce to str and truncate to `REASON_MAX_CHARS`.
  5. Otherwise raise `PreferenceError` with a short message.

Do **not** implement `run_judge` yet (stubbing it is fine if imports need a placeholder — prefer leaving it for Task 2).

- [ ] **Step 4: Run — expect PASS**

Run: `PYTHONPATH=src python3 -m unittest tests.test_preference_judge -v`

- [ ] **Step 5: Commit only if user asked**

---

### Task 2: `run_judge` with fake transport + server

**Files:**
- Modify: `src/local_model_runtime_evaluation/preference_judge.py`
- Modify: `tests/test_preference_judge.py`

**Interfaces:**
- Consumes:
  - `Cell.load`, `build_server` (matrix), credentials via duplicated/shared pattern from `preference_collect.resolve_credential`
  - `load_answers` from `preference_review` (or duplicate thin loader)
  - `preference_review._answer_content` — **do not import private helpers**; copy a small public `answer_content_for_pair` helper into `preference_judge` or export a public `get_answer_content` from `preference_review`. Prefer adding `get_answer_content(answers_by_cell, cell_id, prompt_id) -> str` to `preference_review.py` and use it from both modules if needed.
  - `LoopbackTransport`, `TransportError`, `ServerError`
- Produces:
  - `run_judge(run_dir: Path, *, judge_cell_id: str, cells_root: Path, suite: PreferenceSuite, build_server=..., transport_factory=..., credential_for=..., ready_timeout=180, request_timeout=120, cancel=...) -> Path`
  - Writes `judgments.json`, `judge_raw.json`; updates `raw.json` with `judge_cell_id` and `judged_at`

Judge prompt `max_tokens`: use `256` (constant `JUDGE_MAX_TOKENS = 256`).

Logic:

1. Load `pairs.json` → `{"pairs": [...]}`; fail closed if missing/malformed.
2. Load answers via `load_answers(run_dir)`.
3. Build `prompts_by_id` from `suite`.
4. Resolve credential; `build_server`; start; wait_ready.
5. For each pair (in order):
   - Build prompt from suite prompt text + answer A/B (fail closed if missing content).
   - `transport.chat(...)`; on `TransportError`, treat like parse failure (retry once, then null).
   - Parse; on `PreferenceError`, retry once with the same prompt; if still bad → `winner: null`, record error.
6. Stop handle in `finally`.
7. Write artifacts; merge judge metadata into existing `raw.json` if present.

`judgments.json` shape:

```json
{
  "judgments": [
    {"pair_id": "...", "winner": "A", "reason": "..."},
    {"pair_id": "...", "winner": null}
  ]
}
```

Omit `reason` key when `None` (or include `"reason": null` — prefer omit for cleanliness).

`judge_raw.json` shape:

```json
{
  "judge_cell_id": "jang_4m__osaurus",
  "pairs": [
    {
      "pair_id": "...",
      "attempts": [
        {"raw": "...", "ok": true, "error": null}
      ],
      "winner": "A",
      "reason": "..."
    }
  ]
}
```

- [ ] **Step 1: Write failing tests**

```python
def test_run_judge_fills_judgments(self) -> None:
    # temp run_dir with pairs.json (2 pairs), answers for two cells, tiny suite with those prompts
    # Fake transport.chat returns '{"winner":"A","reason":"ok"}'
    # Fake build_server / handle start/wait_ready/stop no-ops
    # Assert judgments.json winners are A; judge_raw.json has judge_cell_id; raw.json has judged_at

def test_run_judge_retries_once_then_null(self) -> None:
    # First chat returns "not json"; second still "not json"
    # Assert winner null and attempts length 2

def test_run_judge_retry_succeeds(self) -> None:
    # First "not json"; second valid JSON B
    # Assert winner B and attempts length 2
```

Keep fixtures free of live network. Reuse patterns from `tests/test_preference_collect.py`.

- [ ] **Step 2: Run — expect FAIL**

Run: `PYTHONPATH=src python3 -m unittest tests.test_preference_judge -v`

- [ ] **Step 3: Implement `run_judge`**

Import `resolve_credential` from `preference_collect` if already exported; otherwise duplicate the thin `_credential_for` (YAGNI — prefer import from collect).

If exporting `get_answer_content` from `preference_review`, add a one-line re-export of the existing private logic and update `preference_review` to call it — keep behavior identical.

- [ ] **Step 4: Run — expect PASS**

Also re-run:  
`PYTHONPATH=src python3 -m unittest tests.test_preference_review tests.test_preference_collect -v`

- [ ] **Step 5: Commit only if user asked**

---

### Task 3: CLI + docs + tally reason tolerance

**Files:**
- Modify: `src/local_model_runtime_evaluation/preference_cli.py`
- Modify: `tests/test_preference_cli.py`
- Modify: `tests/test_preference_tally.py`
- Modify: `docs/preference.md`

**Interfaces:**
- Consumes: `run_judge`, `DEFAULT_JUDGE_CELL`
- Produces: `main(["judge", "--run", DIR, ...]) -> int`

Subcommand:

```text
lmre-preference judge --run DIR [--judge-cell ID] [--cells-root PATH] [--suite PATH] [--dry-config]
```

Defaults: judge cell `jang_4m__osaurus`; suite/cells-root same as other commands.

`--dry-config`: load judge `Cell`, load suite, verify `run_dir/pairs.json` and `run_dir/answers/` exist; print:

```json
{"ok": true, "judge_cell": "jang_4m__osaurus", "run_dir": "...", "pairs": <int>}
```

No network.

- [ ] **Step 1: Write failing tests**

```python
def test_judge_dry_config_ok(self) -> None:
    # Use temp run_dir with minimal pairs.json + answers/ dir
    # main(["judge", "--run", str(run_dir), "--dry-config"]) == 0
    # stdout JSON ok true, judge_cell default

def test_judge_missing_run_fails(self) -> None:
    code = main(["judge", "--run", "/tmp/lmre-preference-missing-run-xyz"])
    self.assertEqual(code, 1)

def test_tally_allows_optional_reason(self) -> None:
    # existing tally fixtures + reason on judgments → still scores wins
```

- [ ] **Step 2: Run — expect FAIL**

Run: `PYTHONPATH=src python3 -m unittest tests.test_preference_cli tests.test_preference_tally -v`

- [ ] **Step 3: Implement CLI + docs**

Wire `_cmd_judge` like collect (try/except already in `main`).

Update `docs/preference.md`:

- Workflow includes `judge` between review and tally
- Default judge cell + `--judge-cell`
- Self-preference bias note
- Live judge requires Jason’s in-session authorization
- Follow-ons still list RAG / Osaurus overhead as not implemented

- [ ] **Step 4: Run full preference + matrix smoke**

```bash
PYTHONPATH=src python3 -m unittest \
  tests.test_preference_config \
  tests.test_preference_collect \
  tests.test_preference_review \
  tests.test_preference_tally \
  tests.test_preference_judge \
  tests.test_preference_cli -v

PYTHONPATH=src python3 -m unittest \
  tests.test_matrix_config tests.test_matrix_metrics \
  tests.test_matrix_runner tests.test_matrix_servers -q
```

Expected: all PASS

- [ ] **Step 5: Commit only if user asked**

---

## Spec Coverage Check

| Spec requirement | Task |
|------------------|------|
| `judge` subcommand (not review flag) | 3 |
| Default `jang_4m__osaurus` + `--judge-cell` | 1, 2, 3 |
| JSON + optional reason (500 truncate) | 1 |
| Fail closed + one retry | 1, 2 |
| Self-pairs still judged / bias documented | 2 (behavior), 3 (docs) |
| Lifecycle reuse / serial chat | 2 |
| `judgments.json` + `judge_raw.json` + `raw.json` metadata | 2 |
| `--dry-config` | 3 |
| Fakes-only tests | 1–3 |
| Tally unchanged with reason | 3 |
| No RAG / overhead / Stage 2B | all (constraints) |
| Live auth docs | 3 |

---

## Execution Handoff

Plan complete. Two execution options:

1. **Subagent-Driven (recommended)** — fresh subagent per task, review between tasks  
2. **Inline Execution** — execute tasks in this session with checkpoints  

Which approach?
