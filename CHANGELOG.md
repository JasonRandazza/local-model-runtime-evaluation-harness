# Changelog

Notable operator-visible changes. Pre-1.0: minor versions may change behavior,
but never the meaning of already-sealed evidence.

## 0.4.0 (unreleased)

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
