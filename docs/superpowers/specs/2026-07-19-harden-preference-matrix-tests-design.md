# Harden Preference + Matrix Non-Live Tests Design

**Status:** Approved in conversation by Jason on 2026-07-19 (Step C of A→B→C). Authorizes implementation planning and fake-only test work. Does not authorize live collect, live judge, Stage 2B, plugin rebuild, or Ornith/Qwen cells.

**Depends on:** preference POC + local judge on `main` (`docs/superpowers/specs/2026-07-19-gemma-preference-quality-poc-design.md`, `docs/superpowers/specs/2026-07-19-gemma-preference-local-judge-design.md`).

## Goal

Close deferred non-live test gaps for preference/judge and add thin matrix regression coverage for OptiQ `:no-think` / metrics / auth-related behavior. Fakes only.

## Preference / judge coverage

1. Case-sensitive winner rejection (`"a"` → `PreferenceError`)
2. Fenced JSON extraction asserts `reason` as well as `winner`
3. `TransportError` on chat: one retry then `winner: null`
4. CLI `--judge-cell` override visible in `--dry-config` JSON
5. CLI live `judge` path mocked to `run_judge` (mirror collect)
6. Silence missing-run stdout noise (capture stdout in the CLI test)
7. Dry-config pair validation: empty/invalid `pairs` fail closed consistently with `_load_pairs` (prefer shared helper or call `_load_pairs` / a public wrapper)

**Out of scope:** abort-on-missing-answer redesign; cancel/`judged_at` partial-run semantics; live runs.

## Matrix hygiene

1. Assert OptiQ native cell `model_id` values that are intended for content streaming use the `:no-think` suffix (at least `optiq_4bit__optiq`)
2. One additional metrics assert only if a clear hole remains beyond existing `test_matrix_metrics.py` (otherwise skip)
3. No Keychain / live network in tests

## Non-goals

- New product features
- Stage 2B / plugin
- RAG / Osaurus overhead
- Ornith / Qwen wiring
- Docs overhaul (one-line test pointers only if needed)

## Definition Of Done

- New/updated unit tests green; full preference + matrix smoke green
- `unittest -q` preference CLI suite produces no stray JSON on stdout
- No live endpoints contacted

## Explicit Confirmations

- Fakes only
- Preference deferred gaps + thin matrix `:no-think`/metrics hygiene
- No live authorize in this slice
