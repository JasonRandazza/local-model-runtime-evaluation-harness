# Sealed Results Browser Implementation Plan

**Design:** `docs/superpowers/specs/2026-07-31-sealed-results-browser-design.md`
**Branch:** `claude/results-browser-mvp` from `main` at `3e17a2c`.
**Method:** test-driven; each behavior gets a failing test before code.

## Task 1: Evidence view-model boundary

**Files:** `src/local_model_runtime_evaluation/results_browser.py`,
`tests/test_results_browser.py`, `tests/results_browser_fixtures.py`.

1. Fixture helpers build synthetic bundles through the real `EvidenceBundle`
   API in temporary directories: sealed PASS with per-step `report.md`
   (overhead report includes an `N/A` pair with reason), sealed
   `PARTIAL_BLOCKED` with `attempts/attempt-00N.json` snapshots, unsealed
   `RUNNING`, sealed-then-tampered (checksum corrupt), missing `plan.json`,
   and `schema_version` `"9.9.9"`.
2. `classify_bundle(run_dir)` returns health + detail per the design's five
   states, checking `schema_version` before `EvidenceBundle.load` and calling
   `verify()` only for sealed bundles. All `EvidenceError` codes map to
   explicit health values; no exception escapes to the caller.
3. `build_index(results_root)` returns sorted index entries (newest first),
   one per directory, malformed entries degraded not dropped, empty-root and
   missing-root cases explicit.
4. `build_run_view(run_dir)` returns the detail view model: identity, policy
   allowlist, summary, steps with report availability, attempt history,
   lifecycle lease summary, and (verified only) step report text.
5. Boundary rule: this module returns plain data (dataclasses/dicts/strings);
   it never produces HTML.

## Task 2: Rendering and CLI

**Files:** `src/local_model_runtime_evaluation/results_browser_html.py`,
`tests/test_results_browser_html.py`, `tests/test_results_browser_cli.py`,
`managed_run_cli.py` (browse wiring only), `bin/lmre` (unchanged; subcommand
flows through existing dispatch).

1. `render_index(entries)` and `render_run(view)` produce self-contained
   HTML: inline CSS, no JavaScript, semantic tables, `html.escape` on every
   interpolated value, status labels verbatim.
2. Markdown pipe-table conversion is structural only; non-table report lines
   render as escaped text. No metric value is parsed, rounded, or replaced.
3. `write_browser(results_root, output_root)` writes `index.html` and
   `runs/<run-id>.html`, creating directories beneath the output root only.
4. `browse` subcommand: `--results-root` (default `results/runs`), `--output`
   (default `results/browser`); JSON result via `_emit`; failures use the
   existing sanitized error path.
5. Rendering tests cover fail-closed pages (corrupt, unsealed, unreadable,
   unsupported), label fidelity (`N/A`, `INCOMPARABLE`, `est.`, `—`),
   escaping of hostile strings in fixture data, and index/detail link
   round-trip. CLI tests use `main(argv)` with captured stdout JSON.

## Task 3: Documentation and reconciliation

**Files:** `docs/results-browser.md`, `README.md`, `docs/status.md`,
`docs/architecture.md`.

1. `docs/results-browser.md`: one-command usage, health states, honest-label
   guarantees, privacy posture, non-goals.
2. README: add the browse command row and doc link.
3. `docs/status.md`: record the managed live acceptance PASS
   (`run-20260731-051843-04302b`, `gemma-managed-acceptance-20260731-r4`,
   sealed attempt 4, OptiQ overhead pair `N/A`) replacing the stale
   "non-live validated only" claim, and record the results-browser slice
   status accurately.
4. `docs/architecture.md`: add the results-browser row to the component
   table and a short read-only evidence-presentation note.

## Verification Gate (before PR)

- New focused tests pass; full retained suite passes
  (`PYTHONPATH=src python3 -m unittest discover -s tests -v`).
- `git diff --check`; `git status --short` shows only intended files.
- Real exercise: `./bin/lmre browse` against `results/runs`, inspect the
  generated pages for the sealed acceptance bundle (attempts 2–3 preserved,
  OptiQ `N/A` intact), then re-verify the bundle checksum manifest
  byte-for-byte from inside the run directory.
- Confirm no runtime, provider, credential, vault, or archive contact; the
  browser binds no port and spawns no process.
- Graphify refresh via the repository hook after committed source changes;
  confirm ignored outputs are not ingested.

## Execution Topology

Two sequential implementation agents with disjoint file ownership (Task 1
then Task 2, contract frozen between), lead-owned integration, review wave
(correctness/evidence-integrity, privacy/path-safety, UI/accessibility), then
lead adjudication. Agents do not commit, push, or edit outside assignment.

## Commit Sequence

1. Handoff artifact + this plan + design spec.
2. Evidence boundary + fixtures + tests.
3. Rendering + CLI + tests.
4. Documentation + status reconciliation.

## Deferred (recorded, not implemented)

- Cross-run comparison views gated on comparison identity and suite/revision
  equality.
- Loopback server mode for interactive filtering.
- Raw response viewing behind a separate privacy design.
- Discovery/Approach 3 result browsing (non-managed layouts).
- Incremental verification caching keyed on manifest mtime.
