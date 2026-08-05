# Sealed Cross-Run Comparison (2026-08-05)

Read-only comparison views over sealed evidence bundles, extending the
existing `lmre browse` static HTML browser. No new executable, no runtime
authority, no JavaScript, no network, no new scoring.

## Frozen contract

1. **Grouping.** Bundles are discovered through the existing browser boundary
   (`build_index`). A bundle joins a comparison group only when its persisted
   `identity.comparison_id` is non-empty and matches the safe shape
   `[a-z0-9][a-z0-9-]{0,79}` (the shape `sanitize_run_name` guarantees at
   plan build). Missing or malformed identity never invents a group; those
   runs stay visible in the run index only.
2. **Acceptance.** Health is re-derived through the existing
   `classify_bundle` / `EvidenceBundle.verify` path. A member contributes
   accepted comparison data only when health is exactly `SEALED_VERIFIED`.
3. **Exclusion visibility.** `UNSEALED`, `SEALED_CORRUPT`,
   `UNSUPPORTED_SCHEMA`, `UNREADABLE`, and `UNRECOGNIZED` members are listed
   with the group, carrying their health and deterministic reason. They never
   contribute metrics and never leak withheld report content.
4. **Comparability dimensions.** Accepted members must agree on the portable
   immutable plan dimensions: `schema_version`, `family_id`, `recipe_id`,
   `matrix_mode`, `steps`, `cell_ids`, `pair_ids`, and `input_hashes`
   (relative path → sha256; this is the portable suite/campaign/corpus
   identity). `campaign_path`, `suite_paths`, `cells_root`, `pairs_root`,
   and `rag_corpus_path` are machine paths and are never compared as
   identities.
5. **Verdicts.** Per group:
   - `COMPARABLE` — two or more accepted members, all required dimensions
     agree.
   - `INCOMPARABLE` — two or more accepted members disagree on at least one
     required dimension. Reason is the stable string
     `plan_dimension_mismatch: <dim>, <dim>, ...` with dimension names in
     the fixed order of point 4. No aggregation or ranking occurs.
   - `N/A (fewer than two accepted members)` — zero or one accepted member.
   A mismatch never hides individual run pages.
6. **Status fidelity.** Recorded statuses and qualifiers pass through
   verbatim: `PASS`, `FAIL`, `N/A`, `INCOMPARABLE`, `PARTIAL_BLOCKED`,
   `BLOCKED_PROVIDER_RECONNECT`, `est.`, `—`. No winner, delta, confidence,
   or score is manufactured.
7. **Metrics scope (MVP).** Comparison pages show plan identity metadata and
   recorded run statuses only. No parsing of raw model responses, no new
   benchmark math, no derived rankings. Richer metric comparison stays
   deferred.
8. **Ordering.** Deterministic and filesystem-independent: groups by
   comparison ID ascending; members by created timestamp ascending, then
   run ID, then run directory name.
9. **Degradation.** A malformed member degrades only itself; other members
   and other groups still render. No single bad bundle aborts the
   comparison index.
10. **Unattributed exclusions.** An entry with no vetted comparison identity
    at all is listed separately, never assigned to any group. This covers
    degraded health (`UNREADABLE`, `UNSUPPORTED_SCHEMA`, `UNRECOGNIZED`,
    including symlinked entries -- the symlink is never followed) and a
    present-but-malformed `comparison_id` (non-string, or failing the safe
    shape in point 1) on an otherwise vetted bundle. A genuinely absent
    `comparison_id` on a healthy bundle is unchanged solo-run behavior, not
    an exclusion. Each record carries exactly `run_dir_name` (the safe run
    directory name, or a fixed placeholder for names that fail the safe
    run-id shape), `health`, and a fixed `reason` string -- never
    `health_detail`, exception text, or any bundle-derived content.
    Ordering is deterministic: by `(health, run_dir.name)` using the raw
    directory name as the internal sort tiebreaker.

## Shape

- `build_comparisons(results_root)` in `results_browser.py`: plain-dict view
  model, never raises.
- `render_comparisons_index` / `render_comparison_group` in
  `results_browser_html.py`: pure renderers; `write_browser` writes
  `comparisons/index.html` and `comparisons/<comparison-id>.html` under the
  existing output root, links the comparison index from `index.html`, and
  keeps refusing output paths inside the evidence root.
- `lmre browse` JSON stays backwards-compatible and adds
  `comparison_index` (path) and `comparisons` (group count).
- `build_comparisons` return dict gains one additive key,
  `unattributed_exclusions` (a list, present in every branch including
  missing-root and empty-root). `render_comparisons_index` gains an
  "Unattributed exclusions" section after the groups content. `write_browser`
  and `lmre browse` JSON both gain an additive `unattributed_exclusions`
  key (int count).
