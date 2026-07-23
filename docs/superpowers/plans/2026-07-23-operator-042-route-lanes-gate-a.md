# Operator Gemma OptiQ 0.4.2 Route Lanes Gate A Implementation Plan

> **For agentic workers:** Fake-only. No live contact, run IDs, or manifests.

**Goal:** Land Gate A for `gemma-optiq-042-operator-route-smoke` / `-benchmark` on profile revision `3`, preserving sealed rev-2 `005`/`006` contracts.

**Design:** `docs/superpowers/specs/2026-07-23-operator-042-route-lanes-design.md`

## Tasks

### 1. Suites + launcher + fixtures
- Clone smoke/benchmark suite JSON with new suite_ids
- Add `bin/lmre-stage2-operator-serve-gemma-042`
- Add test fixtures for 042 smoke/benchmark

### 2. Schema + manifest + policy
- Add oneOf branches; extend `manifest.py` pairing; add policy tuples
- Tests: accept 042+r3; reject cross-pairing

### 3. Factory + engines + suite allowlists + artifacts
- Branch validation/suite paths; `_STAGE_2B_*_042_PROFILE`; artifact rev-3 branches
- Tests: factory builds; fail-closed pairings

### 4. Docs
- Point checklist step 6 / architecture / AGENTS at Gate A landed (not live)

Prefer `/opt/homebrew/bin/python3` with `PYTHONPATH=src`.
