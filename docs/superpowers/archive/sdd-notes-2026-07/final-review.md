# Senior Code Review — Multi-Family Preference Step 2

**Base:** e4c992ee24e6b082e6322f46a5cc34cfac92ea6e (uncommitted, on main)
**Scope:** `docs/preference.md`, `preference_cli.py`, `preference_collect.py`, `preference_config.py`, `preference_judge.py`, matching tests, plus untracked `config/preference/defaults.json` and `config/preference/family-cells.json`.

## Verification performed
- Read spec + plan in full; diffed against actual code (not just the plan's sketch).
- Read `config/preference/defaults.json` and `family-cells.json` directly (untracked, correctly excluded from `final-pref.diff`).
- Ran full preference suite: `PYTHONPATH=src /opt/homebrew/bin/python3 -m unittest tests.test_preference_config tests.test_preference_collect tests.test_preference_review tests.test_preference_tally tests.test_preference_judge tests.test_preference_cli -v` → **58/58 pass**.
- Ran both dry-configs live: Gemma default (4 cells incl. `optiq_4bit__omlx`) and `--family ornith-35b` (4 `ornith_*` cells) → both `ok: true`, matches spec exactly.
- Traced cross-family rejection to `Cell.validate_for_family` (quant-membership check) — confirms `test_collect_rejects_ornith_cell_under_gemma_family` isn't a false-positive.
- Confirmed `resolve_preference_selection` matches the plan's exact 5-step resolution algorithm; `DEFAULT_CELL_FAMILY` import-time hardcodes removed from both `preference_collect.py` and `preference_judge.py` as required.

## Strengths
- Faithful, minimal implementation of the plan — no scope creep (no Qwen, no Stage 2B, no live wiring).
- Single source of truth enforced by test (`test_gemma_defaults_match_recipe`), not just convention.
- Fail-closed judge family inference (`resolve_judge_family`) correctly rejects a default `--judge-cell` that doesn't belong to an explicitly-passed `--family`, rather than silently loading the wrong family.

## Critical
- None.

## Important
- None.

## Minor
- Two new untracked local symlinks (`config/matrix/omlx-roots/ornith_optiq_4bit/mlx-community__Ornith-1.0-35B-OptiQ-4bit`, `ornith_oq4/Ornith-1.0-35B-MLX-oQ4`) point to this machine's absolute paths and aren't covered by `.gitignore` (unlike the sibling `optiq_4bit/mlx-community/` pattern). Not part of Step 2's code scope, but flag before any commit so machine-specific artifact symlinks don't get checked in.
- `resolve_judge_family`'s "cell appears in multiple family recipes" ambiguity branch has no direct unit test (only reachable if a cell id were ever shared across recipes — currently impossible, so low risk).

## Verdict
**Approve.**

Review path: `/Users/jrazz/Dev/active/local-model-runtime-evaluation-harness/.superpowers/sdd/final-review.md`
