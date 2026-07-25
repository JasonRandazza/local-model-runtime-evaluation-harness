# Approach 3 — Free-form cell binding (Gate A scaffold)

**Status:** APPROVED for scaffold / dry-config / fake tests (Jason, 2026-07-24 night).  
**Live collect:** not sealed; mark UNTESTED until a separate live cohort passes.  
**Scope tonight:** Gemma-heavy; no Ornith/Qwen OptiQ live; no provider edit.

## Intent

Let an operator bind an ordered list of existing matrix `cell_id`s for a family
without requiring the curated native-triple recipe. This is the free-bind
ingredient of the north star — not Discovery, not Stage 2.

## Contract

1. Recipe JSON under `config/approach3/` with `family_id`, ordered `cell_ids`,
   and `require_native_server` (default `false` for Approach 3).
2. Cells still load from `config/matrix/cells/{cell_id}.json` and must pass
   family quant / artifact validation. No silent model copy or `place`.
3. Lifecycle stays on collector A+C / server builders — Approach 3 does not
   spawn OptiQ itself.
4. CLI: `bin/lmre-approach3 dry-config|show|collect-preference`.
5. `collect-preference` reuses `preference_collect.run_collect`; live requires
   explicit `--i-understand-live`.
6. Fail-closed on missing cells, wrong family quants, empty lists, duplicate
   cell ids, or unknown recipe fields.

## Out of scope tonight

- Cross-family mixes in one recipe
- RAG/overhead Approach 3 collectors (preference first)
- Plugin tool for Approach 3
- Deep Wiki

## Definition of done (Gate A)

- Design + recipe(s) + module + CLI + unit tests for dry-config / load
- Handoff documents UNTESTED live collect
- Does **not** claim sealed PASS
