# Task 1 Review: RAG family-first

**Verdict:** Approve for Task 1 scope.

## Spec compliance: ✅

| Requirement | Status |
| --- | --- |
| `config/rag/defaults.json` + `family-cells.json` (Gemma/Ornith four-cell, preference parity) | ✅ |
| Resolver: `--family` → defaults → fail closed; recipe or `--cells` | ✅ |
| Errors: `family is required`, `rag family recipe is missing`, `cells filter is empty` | ✅ |
| Gemma defaults include `optiq_4bit__omlx`; order matches recipe | ✅ |
| CLI `--family`; dry-config `family_id`; removed `DEFAULT_CELL_FAMILY` | ✅ |
| Config-backed `DEFAULT_RAG_CELLS`; collect uses `load_family(family_id)` | ✅ |
| Suite/corpus unchanged; Stage 2B untouched | ✅ |
| Docs (Task 3) | Out of scope |

Verified: 35 RAG tests OK; dry-config Gemma + Ornith match report.

## Quality: Good

Mirrors `preference_config.py` resolver shape; cell validation via `Cell.load` + family is correct fail-closed wiring.

## Findings

**Critical:** none

**Important:** none

**Minor:**
1. No unit test for unknown `--family` → `rag family recipe is missing` (resolver path untested).
2. `family_id` persisted in `raw.json` but no collect test asserts it.
3. Resolver does not require `--cells` ⊆ recipe (same as preference; `Cell.load` catches cross-family ids).
