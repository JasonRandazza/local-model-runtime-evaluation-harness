# Step 3 Final Review — Multi-Family RAG + Overhead

Base: `7671af34f65e860ba8a24f03279a3de34f4a33df`. All 58 rag/overhead unit tests pass; all 4 dry-config commands (Gemma/Ornith × rag/overhead) produce correct `family_id`, cell/pair sets, and unchanged suite ids. Ornith `routed_model_id` strings verified against `config/matrix/families/ornith-35b.json` allowlists — exact matches. One pre-existing, unrelated `test_stage_two_host` failure confirmed present on base too (missing local OptiQ snapshot fixture).

**Strengths**
- Clean family-first resolver pattern in both `rag_config.py`/`overhead_config.py`, symmetric with preference Step 2.
- `--family`/`--cells`/`--pairs` CLI wiring, dry-config `family_id` output, and docs all match spec/plan exactly.
- Good cross-family rejection tests at CLI level (`test_collect_rejects_ornith_cell_under_gemma_family`, `test_dry_config_rejects_ornith_pair_under_gemma_family`).
- Overhead pair JSONs correctly reference allowlisted routed ids; no third Ornith pair, no Qwen/Stage 2B scope creep.

**Important**
- `resolve_rag_selection` (rag_config.py) has no subset/membership check for `cells` against the family recipe (unlike `resolve_overhead_selection`'s explicit `unknown` check). Cross-family rejection only happens later via `Cell.load`→`validate_for_family`, so behavior is correct but the RAG/overhead resolvers are asymmetric and the RAG error path is less direct/friendly. Recommend adding the same membership check for consistency.

**Minor**
- `DEFAULT_RAG_CELLS`/`DEFAULT_PAIR_IDS` are computed via file I/O at module import time — any import failure (bad JSON, missing file) now raises at import rather than at call time; acceptable but slightly fragile vs. lazy loading.
- `OverheadPair.load` pair_id check loosened from allowlist to "non-empty string" (necessary for multi-family), but nothing verifies `pair_id` matches its filename stem — pre-existing gap, not introduced here.
- Two new untracked `omlx-roots` symlinks (`ornith_oq4`, `ornith_optiq_4bit`) exist on disk outside this diff's file scope (Step 1 matrix territory) — flag for later commit, not a Step 3 defect.

**Verdict: Approve.** Import-time I/O and the RAG resolver's missing membership check are worth a follow-up but don't block; functional behavior, tests, and docs meet spec/plan.
