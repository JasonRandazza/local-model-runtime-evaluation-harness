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

## Findings still open (verified 2026-08-21)

`final-review-step3.md` approved Step 3 with three follow-ups. Two still hold:

- `resolve_rag_selection` (`rag_config.py`) and `resolve_preference_selection`
  (`preference_config.py`) accept a `--cells` filter without checking it
  against the family recipe. `resolve_overhead_selection` does check
  (`pairs filter is not in family recipe`). Behavior is still fail-closed —
  a foreign cell is rejected later by `Cell.load` → `validate_for_family` —
  so this is error-message quality, not a correctness hole.
- `OverheadPair.load` (`overhead_config.py`) validates `pair_id` is non-empty
  but never checks it against the filename stem. Every caller loads by
  `pairs_root / f"{pair_id}.json"` and then attributes results under the
  *requested* id, so a hand-edited file whose inner `pair_id` disagrees with
  its name would be silently mislabeled in evidence. All six shipped pair
  files agree today.

The third — `DEFAULT_RAG_CELLS` doing file I/O at import time — is fixed.
It is now the `default_rag_cells()` function, explicitly documented as
uncached.
