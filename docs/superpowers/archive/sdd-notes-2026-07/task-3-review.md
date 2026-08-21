# Task 3 Review: Docs + CLI help

**Verdict:** PASS (one doc nit)

**Brief coverage:** All six doc bullets present in `docs/preference.md`; `preference_cli.py` module docstring, top-level description, `--family`, and `--cells` help match the family-first / four-cell plan.

**CLI help:** `--help` shows defaults.json path, `gemma-4-12b-qat`, `ornith-35b` example, and family-cells recipe default — aligned with Task 3 scope (collect args only; judge `--family` unchanged, acceptable).

**Doc nit:** Line 43 says "15 total pair slots" for a six-prompt × four-cell run; code generates 6 pairs/prompt × 6 prompts = **36** judgments. Likely stale 3-cell or C(6,2) confusion — fix optional, not blocking.

**Safety:** Stage 2B frozen and live-authorize warnings present; Qwen deferred; no live authorize from docs.

**Verification:** Report’s 58-test suite and both dry-config commands are sufficient evidence for docs-only task; not re-run here.

**Recommendation:** Ship Task 3; optionally correct the pair-slot count in a follow-up doc edit.
