# Package 2 D4 Reasoning-Content Decode Gate A Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Land fake-only D4: derive reasoning/visible token split from streamed `reasoning_content`, add `DERIVED_REASONING_CONTENT` + decode `QUALIFIED_REASONING_CONTENT_SPLIT`, without live POSTs or Responses retarget.

**Architecture:** Extend `LoopbackTransport` SSE loop to accumulate `delta.reasoning_content`; optional injectable `TokenCounter`; prefer usage `EXACT_VISIBLE` when present; else derive and reconcile with `completion_tokens`. Update `qualify_thinking_metrics` for the new decode label.

**Tech Stack:** Python 3 stdlib + unittest; optional `transformers` only inside live `ModelDirTokenCounter` (tests never require it). Prefer `/opt/homebrew/bin/python3`.

## Global Constraints

- Design: `docs/superpowers/specs/2026-07-22-package-2-d4-reasoning-content-decode-design.md`
- No live oMLX contact; no new run IDs; no D3; no Responses API
- Do not edit sealed `001`–`003` evidence
- Do not claim derived counts as `EXACT_VISIBLE`
- Pin r2 / measure suite r2 unchanged

## File map

| Area | Files |
|---|---|
| Counter | Create `src/local_model_runtime_evaluation/token_counter.py` |
| Transport | Modify `transport.py` |
| Qualify | Modify `omlx_thinking_measure.py` |
| Wire | Modify `omlx_thinking_transport.py` (pass counter from pin.model_dir) |
| Tests | `tests/test_token_counter.py`, `tests/test_transport.py`, `tests/test_omlx_thinking_measure.py` |
| Docs | `docs/package-2-omlx-thinking-d2.md`, `docs/package-2-omlx-thinking-gate-d.md`, short status `docs/package-2-omlx-thinking-d4.md` |

---

### Task 1: TokenCounter + derived accounting helper

**Files:**
- Create: `token_counter.py`
- Create or extend pure helper in `transport.py` or `token_counter.py`: `resolve_token_accounting(...)`
- Test: `tests/test_token_counter.py`

**Interfaces:**
```python
class TokenCounter(Protocol):
    def count(self, text: str) -> int: ...

class FakeTokenCounter:  # test helper OK in test module
    ...

def resolve_token_accounting(
    *,
    reasoning_text: str,
    visible_text: str,
    completion_tokens: int | None,
    usage_reasoning_tokens: int | None,
    token_counter: TokenCounter | None,
) -> tuple[int | None, int | None, str]:
    # returns reasoning_tokens, visible_output_tokens, token_accounting_status
```

Precedence: usage reasoning → `EXACT_VISIBLE`; else counter derive → `DERIVED_REASONING_CONTENT` / `INCOMPARABLE` per design.

- [x] TDD + commit: `Add token accounting resolver for derived reasoning_content.`

---

### Task 2: LoopbackTransport SSE reasoning_content

**Files:**
- Modify: `transport.py` — `LoopbackTransport.__init__(..., token_counter=None)`; accumulate reasoning deltas; call resolver
- Test: `tests/test_transport.py` — override stream with reasoning + content deltas

- [x] TDD: derived path with FakeTokenCounter; exact path still wins; mismatch → incomparable; TTFT ignores reasoning-only first deltas
- [x] Commit: `Derive chat token accounting from streamed reasoning_content.`

---

### Task 3: qualify_thinking_metrics + transport wire + docs

**Files:**
- Modify: `omlx_thinking_measure.py`
- Modify: `omlx_thinking_transport.py` — `for_pin` builds `ModelDirTokenCounter(pin.model_dir)` best-effort (catch ImportError → None)
- Tests: `tests/test_omlx_thinking_measure.py`
- Docs: D4 status + follow-on rows

- [x] TDD decode label + mixed cohort suppress
- [x] Docs `D4_GATE_A_READY`
- [x] Commit: `Qualify derived reasoning-content decode and document D4 Gate A.`

## Verification

```bash
PYTHONPATH=src /opt/homebrew/bin/python3 -m unittest \
  tests.test_token_counter \
  tests.test_transport \
  tests.test_omlx_thinking_measure \
  tests.test_omlx_thinking_transport \
  tests.test_omlx_thinking_runner -q
```

## Out of scope

- Live `004` authorization  
- D3  
- Responses API  

## Execution

Inline in this session (Jason asked to write the implementation).
