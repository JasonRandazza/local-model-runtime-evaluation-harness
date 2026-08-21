# Task 2 Review: Overhead family-first

**Verdict:** PASS — matches brief; no blockers.

**Ornith pair JSON:** `ornith_oq4.json` and `ornith_optiq_4bit.json` match the brief byte-for-byte on `routed_model_id`, cell ids, and base URL. Both ids sit on `ornith-35b` allowlist (`config/matrix/families/ornith-35b.json`); dry-config family validation passes.

**`resolve_overhead_selection`:** Family resolution (CLI → defaults → fail), recipe lookup, default-to-recipe when `--pairs` omitted, subset check, and empty-filter rejection all match spec. Cross-family pair filter correctly raises `OverheadError`.

**`--family` dry-config:** Default emits `family_id: gemma-4-12b-qat` with two Gemma pairs; `--family ornith-35b` emits Ornith pair set. `DEFAULT_CELL_FAMILY` removed from CLI/runner.

**Verification:** 16 overhead tests OK; both dry-config commands exit 0.

**Notes (non-blocking):** Ornith dry-config still uses default `gemma-matrix-v1` suite; `run_overhead` keeps Gemma default for direct callers; `DEFAULT_PAIR_IDS` remains for test/back-compat.
