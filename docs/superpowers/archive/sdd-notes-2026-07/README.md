# Archived SDD review notes (2026-07 to 2026-08-04)

Review verdicts from the retired Superpowers SDD workflow, kept when
`.superpowers/` was removed. They cover retired or shipped lanes: native
control triple Gate A, Stage 2B-1/2B-2 closeout, and multi-family
preference/RAG/overhead. Historical record only — no current process reads
them.

Deleted rather than archived, because each is reproducible from this
repository: the 65 `review-<base>..<head>.diff` snapshots (every commit pair
resolves, so `git diff <base>..<head>` regenerates them), the per-task briefs
(pre-implementation step plans for merged work), the per-task reports (restate
their commit messages), and the review packages (verbatim dumps of source files
that are still in `src/`).

## Deferred findings, now closed (2026-08-21)

`final-review-step3.md` approved Step 3 with three follow-ups. All three are
resolved:

- The missing `--cells` membership check in `resolve_rag_selection`
  (`rag_config.py`) is in place, as is the same check in
  `resolve_preference_selection` (`preference_config.py`), which had the same
  gap. Both now match `resolve_overhead_selection`.
- `OverheadPair.load` (`overhead_config.py`) now rejects a `pair_id` that
  disagrees with its file name. Callers load by
  `pairs_root / f"{pair_id}.json"` and attribute results under the requested
  id, so a hand-edited file could have been silently mislabeled in evidence.
- `DEFAULT_RAG_CELLS` no longer does file I/O at import time; it is the
  `default_rag_cells()` function, explicitly documented as uncached.
