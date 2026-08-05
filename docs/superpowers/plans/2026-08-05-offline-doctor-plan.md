# Offline Doctor Implementation Plan

**Design:** `docs/superpowers/specs/2026-08-05-offline-doctor-design.md`
**Branch:** `claude/lmre-doctor` from `main` at `f3269e5`.
**Method:** test-driven; failing tests establish each behavior first.

## Task 1: Diagnostic engine (implementation agent)

**Files:** `src/local_model_runtime_evaluation/doctor.py`,
`tests/test_doctor.py`.

1. `run_diagnostics(*, machine_profile_path, state_root, repository_root,
   which=shutil.which, now=None) -> dict` implementing the seven sections
   and the aggregation/action rules from the design, importing only the
   verified-clean module set.
2. `render_text(result) -> str`: pure checklist projection — overall
   readiness, per-section findings with status labels, actions list, fixed
   live-facts-not-checked disclaimer. No recomputation.
3. Tests per the design's testing contract, including the tripwire tests
   (monkeypatched `socket`/`subprocess`/`os.kill` + static import scan) and
   JSON/text parity. Fixtures reuse `tests/artifact_profile_fixtures.py`
   and `adopt_policy` into temp state roots; synthetic config trees live in
   temp dirs with fake family names and paths.

## Task 2: CLI wiring, CLI tests, documentation (lead)

**Files:** `managed_run_cli.py` (doctor subparser + dispatch only),
`tests/test_doctor_cli.py`, `docs/doctor.md`, `README.md`,
`docs/status.md`, `docs/architecture.md`.

1. `doctor` subcommand: `--format {json,text}` (default `json`),
   `--state-dir` (default `.lmre`); JSON via existing `_emit` as
   `{"ok": true, "diagnostic": ...}`; text prints the checklist alone; exit
   `0` for complete diagnostics, existing sanitized error path otherwise.
2. CLI tests: JSON happy path, text mode, exit codes, machine-profile
   keyword injection (mirror `tests/test_managed_run_cli.py`).
3. `docs/doctor.md`: what the doctor checks, what it deliberately cannot
   know, vocabulary, remediation reading. README command row + doc link;
   status/architecture reconciliation without overstating.

## Verification Gate

- New focused tests; full retained suite via
  `PYTHONPATH=src python3 -m unittest discover -s tests -v` (report fresh
  count).
- The six retained dry-config commands (discover, approach3, matrix,
  preference, rag, overhead) still pass.
- Real exercise: `./bin/lmre doctor` and `./bin/lmre doctor --format text`
  against actual static state only; confirm no live-readiness claim.
- `git diff --check`; `git status --short`; import/call-path inspection for
  live reachability; Graphify hook refresh without ignored-content
  ingestion.

## Review Wave (after integration)

- One correctness + non-live-boundary reviewer (primary).
- One operator-wording/privacy reviewer only for what the first does not
  cover. Verify every finding against code before changing anything.

## Commit Sequence

1. Handoff artifact + design spec + this plan.
2. Diagnostic engine + tests.
3. CLI wiring + CLI tests.
4. Documentation + status reconciliation (+ review fixes if any).

## Deferred (recorded, not implemented)

- Diagnostic snapshot export/persistence (needs its own design).
- Live readiness checks (endpoint/provider/inventory/memory) under a
  separately authorized live workflow.
- Doctor coverage of discovery/Approach 3 configuration surfaces.
- Machine-profile creation assistance beyond documented copy-example steps.
