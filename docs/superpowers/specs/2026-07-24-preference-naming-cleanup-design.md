# Preference naming cleanup (design)

**Status:** APPROVED (Jason, 2026-07-24) — naming only; judge defaults unchanged  
**Scope:** Canonical suite id / docs / tests. No live preference re-runs. No judge policy change.

## Decision

1. Default suite remains `suites/multi-family-preference-v1.json` (`suite_id`
   `multi-family-preference-v1`).
2. `suites/gemma-preference-v1.json` stays on disk as a **historical alias** for
   sealed run artifacts and RAG gold fact `gemma-preference-v1` (do not change
   the RAG corpus required fact — that would invalidate sealed RAG scores).
3. Active docs and “current path” unit tests refer to `multi-family-preference-v1`
   and `<family>-preference-*` run dirs.
4. Self-judge defaults stay as implemented (`jang_4m__osaurus` CLI default;
   per-run `--judge-cell` overrides). Bias accepted.

## Out of scope

Non-self-judge defaults, live preference recollect, RAG corpus rewrites,
Approach 3, other Stage 2 lanes.
