# Package 2 D2 Expanded Thinking Measure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Land fake-only D2: measure suite + metric plumbing + qualification rollup on the thinking runner, without live POSTs.

**Architecture:** Keep smoke suite for Gate C. Add measure suite JSON. Extend transport/runner chat results with TransportResult accounting fields; roll up via `qualify_thinking_metrics`.

**Tech Stack:** Python 3 stdlib, unittest. Prefer `/opt/homebrew/bin/python3`. Plugin `0.3.0` unchanged.

## Global Constraints

- Design: `docs/superpowers/specs/2026-07-22-package-2-d2-expanded-thinking-measure-design.md`
- No live oMLX contact; no new run IDs
- Do not modify sealed Gate C/D evidence
- ≤8 serial requests including preflight

## File map

| Area | Files |
|---|---|
| Suite | `suites/omlx-thinking-measure-v1.json`; `omlx_thinking_pin.py` loader |
| Transport | `omlx_thinking_transport.py` |
| Runner | `omlx_thinking_runner.py` |
| Tests | `tests/test_omlx_thinking_pin.py`, `tests/test_omlx_thinking_runner.py`, `tests/test_omlx_thinking_transport.py` |
| Docs | `docs/package-2-omlx-thinking-d2.md`; Gate D follow-on status |

---

### Task 1: Measure suite + loader

- [x] Create suite JSON (5 workloads, max_tokens ≥ 512)
- [x] Loader accepts smoke (2) or measure (5) by suite_id
- [x] Tests

### Task 2: Metric plumbing + qualification rollup

- [x] Extend chat response/result with accounting fields
- [x] Runner stores samples; `qualification_labels` property
- [x] Fake-only tests

### Task 3: Status docs

- [x] `docs/package-2-omlx-thinking-d2.md` (`D2_GATE_A_READY`)
- [x] Update Gate D follow-on row; architecture one-liner

## Verification

- [x] `PYTHONPATH=src` Package 2 thinking tests pass (66 OK)
- [x] Smoke suite still loads; measure suite loads with 5 workloads
- [x] No live scripts invoked
