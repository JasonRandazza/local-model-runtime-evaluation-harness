# Harden Preference + Matrix Non-Live Tests Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close deferred preference/judge unit-test gaps and add thin matrix regression for OptiQ `:no-think` cell ids — fakes only.

**Architecture:** Extend existing `tests/test_preference_*.py` and `tests/test_matrix_*.py`. Share pair validation between CLI dry-config and `preference_judge._load_pairs` via a small public helper. No new product features.

**Tech Stack:** Python 3 stdlib, `unittest`, existing preference/matrix modules.

## Global Constraints

- Spec: `docs/superpowers/specs/2026-07-19-harden-preference-matrix-tests-design.md`
- Fakes only; no live Osaurus/oMLX/OptiQ/Keychain
- Do not redesign abort-on-missing-answer or cancel/`judged_at` semantics
- Do not modify Stage 0–2B / plugin
- Only create git commits when the user explicitly asks

---

## File Structure

| File | Responsibility |
|------|----------------|
| `preference_judge.py` | Export `load_pairs(run_dir) -> list` (public wrapper around `_load_pairs`) if needed |
| `preference_cli.py` | Dry-config uses shared pair loader; fail closed on invalid pairs |
| `tests/test_preference_judge.py` | Case winner, fenced reason, TransportError retry |
| `tests/test_preference_cli.py` | `--judge-cell`, mock live judge, capture missing-run stdout |
| `tests/test_matrix_config.py` or new focused test | OptiQ `:no-think` on `optiq_4bit__optiq` |

---

### Task 1: Preference / judge deferred test gaps + dry-config validation

**Files:**
- Modify: `src/local_model_runtime_evaluation/preference_judge.py`
- Modify: `src/local_model_runtime_evaluation/preference_cli.py`
- Modify: `tests/test_preference_judge.py`
- Modify: `tests/test_preference_cli.py`

**Interfaces:**
- Produces: public `load_pairs(run_dir: Path) -> list[dict[str, str]]` (rename/export `_load_pairs`)
- CLI dry-config calls `load_pairs` instead of weak `_count_pairs`

- [ ] **Step 1: Write failing tests**

```python
# test_preference_judge.py
def test_parse_rejects_lowercase_winner(self) -> None:
    with self.assertRaises(PreferenceError):
        parse_judge_response('{"winner": "a"}')

def test_parse_fenced_includes_reason(self) -> None:
    text = '```json\n{"winner": "B", "reason": "More concrete."}\n```'
    result = parse_judge_response(text)
    self.assertEqual(result["winner"], "B")
    self.assertEqual(result["reason"], "More concrete.")

def test_run_judge_transport_error_retries_then_null(self) -> None:
    # FakeTransport raises TransportError twice → winner null, attempts length 2

# test_preference_cli.py
def test_judge_dry_config_judge_cell_override(self) -> None:
    # dry-config with --judge-cell oq4_fp16__omlx → JSON judge_cell matches

def test_judge_live_delegates_to_run_judge(self) -> None:
    # patch run_judge; main(["judge", "--run", tmp]) == 0; assert called

def test_judge_missing_run_fails(self) -> None:
    # capture stdout with contextlib.redirect_stdout; assert code 1 and no uncaptured print
```

Also: dry-config with empty `{"pairs":[]}` or invalid pair object → exit 1.

- [ ] **Step 2: Run — expect FAIL**

`PYTHONPATH=src python3 -m unittest tests.test_preference_judge tests.test_preference_cli -v`

- [ ] **Step 3: Implement**

- Export `load_pairs = _load_pairs` or rename to public `load_pairs`
- `_cmd_judge` dry-config: `pairs = load_pairs(run_dir)`; `pair_count = len(pairs)`; remove weak `_count_pairs` or make it call `load_pairs`
- Add tests above; for TransportError reuse existing FakeTransport pattern from Task 2 tests
- Capture stdout in missing-run test so suite `-q` stays quiet

- [ ] **Step 4: Run — expect PASS**

```bash
PYTHONPATH=src python3 -m unittest \
  tests.test_preference_judge tests.test_preference_cli \
  tests.test_preference_tally tests.test_preference_config \
  tests.test_preference_collect tests.test_preference_review -q
```

Confirm no stray JSON lines on stdout when running `-q`.

- [ ] **Step 5: Commit only if user asked**

---

### Task 2: Matrix OptiQ `:no-think` regression

**Files:**
- Modify: `tests/test_matrix_config.py`

**Interfaces:**
- Consumes: `Cell.load` for `config/matrix/cells/optiq_4bit__optiq.json`

- [ ] **Step 1: Write failing test**

```python
def test_optiq_native_cell_uses_no_think_model_id(self) -> None:
    cell = Cell.load(ROOT / "config/matrix/cells/optiq_4bit__optiq.json")
    self.assertTrue(cell.model_id.endswith(":no-think"), cell.model_id)
    self.assertEqual(cell.server, "optiq")
```

If metrics already cover Option A/B adequately, do **not** add a redundant metrics test (YAGNI).

- [ ] **Step 2: Run — expect PASS** (config already has `:no-think`; this locks it)

If somehow FAIL, fix cell JSON only with operator-approved path — do not invent new model paths.

- [ ] **Step 3: Run matrix smoke**

```bash
PYTHONPATH=src python3 -m unittest \
  tests.test_matrix_config tests.test_matrix_metrics \
  tests.test_matrix_runner tests.test_matrix_servers \
  tests.test_matrix_measure tests.test_matrix_lifecycle \
  tests.test_matrix_cli -q
```

- [ ] **Step 4: Commit only if user asked**

---

## Spec Coverage Check

| Spec item | Task |
|-----------|------|
| Case-sensitive winner | 1 |
| Fenced reason assert | 1 |
| TransportError retry | 1 |
| `--judge-cell` dry-config | 1 |
| Mock live judge | 1 |
| Silence missing-run stdout | 1 |
| Dry-config uses real pair validation | 1 |
| OptiQ `:no-think` lock | 2 |
| No extra metrics unless hole | 2 (skip if covered) |

---

## Execution Handoff

Plan complete. Two execution options:

1. **Subagent-Driven (recommended)**
2. **Inline Execution**

Which approach?
