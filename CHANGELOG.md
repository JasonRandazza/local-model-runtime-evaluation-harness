# Changelog

Notable operator-visible changes. Pre-1.0: minor versions may change behavior,
but never the meaning of already-sealed evidence.

## Unreleased

### Added

- **Linter configuration.** Added a `[tool.ruff]` section to `pyproject.toml`
  (line-length 79, target py311, rule set E/F/W/I/UP/B), pinned `ruff==0.16.5`
  in a `dev` dependency group, and added a non-blocking lint step to CI so the
  existing violation count can be cleared before the gate goes live.

- **Rulings.** The harness now draws the conclusion its evidence supports
  instead of stopping one step short. A **rubric** is a checked-in declaration
  of criteria -- the quality floors a cell must clear, and the single metric
  that orders whatever clears them -- and a **ruling** is the conclusion drawn
  from one sealed run under one rubric, naming the cell to serve.
  `lmre-managed ruling make --run <dir> --rubric <file>` produces one and
  `lmre-managed ruling list` indexes what has been concluded, both emitting
  JSON on stdout. Producing a ruling contacts no runtime, provider, credential
  store, or model, and requires no adopted policy: interpreting evidence is not
  an act of running anything.

  A ruling names a **cell**, never a native server, because the diagonal runs a
  different quant per server and the evidence cannot support a server-level
  claim. Floors gate and one metric orders the survivors -- never a weighted
  score. When no cell clears every floor the outcome says so rather than
  naming the least-bad candidate.

  The rubric is hashed into the ruling but never into the plan or
  `input_hashes`, so **changing a rubric leaves sealed evidence untouched and
  still comparable** -- old evidence can be re-ruled under new criteria without
  re-running any model. A later ruling supersedes an earlier one by being a
  separate file; the earlier ruling is never edited or removed, and superseding
  is derived when the directory is read. Rulings live under the results tree
  rather than in version control, following the same boundary as the evidence
  they cite.

  Fails closed: an unsealed, corrupt, or incomplete run produces no ruling, and
  a rubric that gates on a metric the run cannot supply produces no ruling
  rather than one with a floor silently skipped.

### Changed

- Rubric metric names now carry the step that produced them: `rag.fact_hit_rate`
  and friends became `rag_oracle.fact_hit_rate`, `rag_keyword.fact_hit_rate`,
  `rag_keyword.retrieval_recall` and `rag_keyword.retrieval_precision`. Two
  steps produce RAG scores, so an unprefixed name could not say which one a
  floor gated on, and retrieval metrics only exist in keyword mode. No sealed
  evidence changes meaning.


- `--cells` on `lmre-preference` and `lmre-rag` must now be a subset of the
  selected family's recipe. A cell outside it was already rejected, but only
  later, by cell loading; it now fails at selection with
  `cells filter is not in family recipe`, matching `--pairs` on
  `lmre-overhead`.
- An overhead pair file whose `pair_id` disagrees with its file name is now
  rejected by `OverheadPair.load`. Callers load pairs by requested id and
  attribute results under that id, so such a file would previously have been
  mislabeled in sealed evidence rather than refused. All shipped pair files
  already agree; no sealed evidence changes meaning.

## 0.4.0 (2026-08-07)

First tagged release. Verification record:
[docs/releases/0.4.0-verification.md](docs/releases/0.4.0-verification.md).

### Added

- The harness is installable. `pip install` provides all seven console scripts;
  previously only two were declared and an installed copy could not run at all.
- `lmre init [target]` scaffolds a workspace from configuration shipped inside
  the wheel, and creates empty `results/runs` and `.lmre` directories. It
  refuses to overwrite existing trees without `--force`, and `--force` replaces
  rather than merges. It adopts no policy and downloads no model.
- Paths resolve from a workspace root: `LMRE_WORKSPACE`, else the nearest parent
  holding a `.lmre-workspace` marker or `config/managed-runs/`, else the
  surrounding source checkout. A `LMRE_WORKSPACE` pointing at a non-directory is
  a hard error rather than a silent fallback.
- `lmre ui`: a fixed-loopback operator console over existing immutable plans.
  Starting it grants no authority; start and resume each require the full plan
  hash, explicit acknowledgement, same-origin CSRF proof, and a fresh
  single-use ten-minute grant.
- Sealed cross-run comparison pages expose recorded matrix and
  direct-versus-Osaurus summary values, read verbatim from checksummed rows.
  No winner, ranking, delta, or confidence value is derived.

### Fixed

- Every CLI crashed before argument parsing when configuration was absent,
  because three modules read config at import time. `lmre --help` now works
  from an installed copy.
- `lmre doctor` reported `ACTION_REQUIRED` for missing `bin/` wrappers and
  missing `docs/` when run from an installed copy, faults an installed operator
  could not fix. The harness section is now mode-aware and checks console-script
  reachability instead.
- The comparisons page failed entirely with a `TypeError` when a bundle's state
  became unreadable after classification. The affected member now reports
  `UNAVAILABLE` metrics and stays visible.
- The run console index could be taken down by a single racing bundle, because
  auto-selection had no handler for a load failure. It now degrades to the plan
  list; an explicit run request still fails closed.

### Changed

- Released under the MIT license, declared in `LICENSE` and in package metadata.
  The project is built for the open-source community.
- Continuous integration runs the retained suite on Python 3.11 and 3.13, the
  six dry-config commands, and a clean-environment install smoke test that
  walks the documented first-run path. All non-live.
- MXFP quantization is retired and must not be reintroduced into any active
  family, cell, campaign, suite map, open mix, or comparison class. The sealed
  MXFP failure evidence is preserved: retirement means "not selectable for
  future runs", never "erase the record".
- The package version is single-sourced from `__init__.py`; it was previously
  maintained separately there and in `pyproject.toml`.

### Evidence compatibility

Plan hashes and recorded `input_hashes` keys are unchanged. Runs planned before
and after this release remain comparable, and existing sealed bundles still
verify. This was gated on a reproducible plan-hash oracle covering the managed
and open-mix planning paths, checked on every commit of the packaging work.

## 0.3.0 and earlier

See [docs/status.md](docs/status.md) for accepted evidence and
[docs/history.md](docs/history.md) for the historical lane summary. No git tags
exist for these versions, so 0.4.0 is the first release with a changelog entry.
