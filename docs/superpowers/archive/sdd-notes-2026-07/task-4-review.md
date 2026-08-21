# Task 4 Review: Docs + dry-config polish

**Reviewer:** subagent (read-only)  
**Artifacts:** `task-4-brief.md`, `task-4-report.md`, `task-4.diff`, design spec `2026-07-20-multi-family-ornith-first-design.md`  
**Verification:** 30/30 matrix tests OK; dry-config CLI for Gemma + Ornith matches report.

## Spec compliance — ✅

| Requirement | Status |
| --- | --- |
| `family_id` in dry-config JSON | ✅ |
| `artifact_missing` (sorted unique missing paths) | ✅ |
| Docs: multi-family overview + campaign table | ✅ |
| Docs: Ornith dry-config / screen / finalist / subset commands | ✅ |
| Docs: HF snapshot prep + `artifact_missing` semantics | ✅ |
| Docs: Steps 2–3 deferred; Qwen / Approach 3 later | ✅ |
| Docs: Stage 2B frozen; no live authorize | ✅ |
| No live authorize / Gate B / plugin changes | ✅ |
| Tests for `family_id` + Ornith missing artifacts | ✅ |

Bonus (in scope, good): `run_campaign` and dry-config both pass `family=campaign.family` to `Cell.load`, keeping live and dry paths aligned.

## Code quality — Good (minor nits)

**Strengths:** Small focused diff; dry-config logic is clear; tests capture stdout JSON; Ornith test sanity-checks listed paths are absent; `--cells` filter correctly scopes `artifact_missing`.

**Findings (non-blocking):**

1. **Unused imports** — `tests/test_matrix_cli.py`: `sys` and `ROOT` imported, never used.
2. **Environment-coupled test** — `test_ornith_dry_config_reports_missing_artifacts` assumes HF Ornith dirs absent; passes today but weakens if operator downloads weights (test still valid, just less diagnostic).
3. **Cosmetic doc duplication** — live-authorize warning appears in intro and Safety section (harmless).
4. **Out of scope (noted in report)** — `matrix_runner.py` module docstring still Gemma-only.

## Verdict

**Approve.** Task 4 meets brief and design-spec doc/boundary requirements. Safe to merge with optional cleanup of unused test imports.
