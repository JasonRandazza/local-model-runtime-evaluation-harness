# Sealed Results Browser Design

**Status:** Current design for the read-only results-browser slice (2026-07-31).
**Baseline:** `main` at `3e17a2c` after the sealed managed acceptance run
`run-20260731-051843-04302b` (`gemma-managed-acceptance-20260731-r4`, PASS).

## Goal

Let an operator understand sealed local evaluation evidence under
`results/runs/` without opening raw JSON or Markdown files by hand. This slice
is read-only presentation over existing trusted evidence. It adds no run,
resume, lifecycle, provider, credential, or storage authority.

## Architecture Decision

Three shapes were compared:

| Shape | Verdict |
| --- | --- |
| Generated static HTML from verified bundles | **Chosen.** Stdlib-only, no server or port, read-only by construction, testable with the existing `unittest` conventions. |
| Loopback-only local server with browser UI | Rejected: adds process lifecycle, port handling, and harder tests. No requirement needs dynamic behavior at the current run count. |
| Separate frontend framework application | Rejected: a new dependency tree with no requirement the standard library cannot satisfy. |

The repository has zero third-party dependencies and no existing UI code; the
browser keeps it that way. If interactive filtering is ever needed, a loopback
server can be added later without discarding this slice.

## Command

```bash
./bin/lmre browse [--results-root results/runs] [--output results/browser]
```

`browse` is a new non-live subcommand of the managed CLI. It emits the usual
JSON result (`{"ok": true, "index": ..., "runs": N, ...}`) and writes:

```text
results/browser/
├── index.html          # run index
└── runs/<run-id>.html  # one detail page per discovered bundle
```

The output root defaults beneath ignored `results/`, so generated pages can
never be committed accidentally. The operator opens `index.html` in any
browser; pages are self-contained (inline CSS, no JavaScript, no external
assets, no network access).

## Module Boundaries

| Module | Responsibility |
| --- | --- |
| `results_browser.py` | Evidence interpretation: bundle discovery, health classification, view-model construction. No HTML. |
| `results_browser_html.py` | HTML rendering from view models. No evidence I/O, no JSON parsing. |
| `managed_run_cli.py` | `browse` argument wiring only. |

Evidence interpretation reuses the existing trusted APIs and never
reimplements them: `EvidenceBundle.load`, `EvidenceBundle.state`,
`EvidenceBundle.verify`, `ManagedRunPlan.from_dict`, and the `StepState` /
`RunSummaryState` / `ManagedStep` / `Ownership` enums. Checksum, state, and
metric semantics are not duplicated.

## Bundle Health Model

Every directory beneath the results root becomes exactly one index row with
one health value, evaluated in this order:

| Health | Detection | Presentation |
| --- | --- | --- |
| `UNREADABLE` | `plan.json`/`state.json` missing or invalid (`EvidenceError` codes `evidence_file_missing`, `evidence_plan_invalid`, `evidence_state_invalid`) | Fail closed: identity line plus the error code and message; no metrics, no report content. |
| `UNSUPPORTED_SCHEMA` | `plan.json` `schema_version` differs from the supported `1.0.0` | Fail closed with the observed version. `ManagedRunPlan.from_dict` does not enforce the version value, so the browser checks it explicitly before load. |
| `UNSEALED` | `state.sealed` is false | State and step table shown with an explicit "unsealed — not accepted evidence" banner; step report bodies withheld. |
| `SEALED_CORRUPT` | `state.sealed` true but `EvidenceBundle.verify()` raises (`evidence_checksum_mismatch`, `evidence_manifest_invalid`, `evidence_file_missing`) | Fail closed: banner with the error code; step report bodies withheld so tampered content is never presented. |
| `SEALED_VERIFIED` | `EvidenceBundle.verify()` passes | Full detail including step report bodies. |

A malformed bundle never aborts index generation; it renders as its own
degraded row while valid runs render normally. `verify()` re-hashes the whole
bundle; it runs once per sealed bundle per `browse` invocation.

## Run Index

Columns: run name, run ID, comparison ID, family, recipe, attempt, run status
(`RunSummaryState`), created timestamp (from `plan.json`), and health. Sorted
by created timestamp, newest first. Rows sharing a `comparison_id` are
adjacent within the same timestamp ordering. An empty results root renders an
explicit empty state, not a blank page.

No cross-run metric comparison is rendered in this slice. Legitimate
comparison requires comparison identity, suite revision, and qualification
checks that this MVP intentionally defers; the index provides navigation and
shared `comparison_id` visibility instead of charts.

## Run Detail

Sections, in order:

1. **Health banner** — one of the five states above, with exact language.
2. **Identity** — run name, run ID, comparison ID, parent run ID, family,
   recipe, matrix mode, plan schema version, plan hash, created timestamp,
   request count, estimated minutes, runtimes, endpoints, cell IDs, pair IDs.
   All values come from `plan.json`; paths are repo-relative by construction.
3. **Policy identity** — allowlisted fields from `policy-snapshot.json`:
   `policy_id`, `schema_version`, `authorization_mode`, lifecycle booleans,
   and numeric limits. The policy schema contains no credentials; the browser
   still renders only this allowlist.
4. **Summary** — `summary.json` verbatim fields: status, attempt, error
   (if any), `completed_native_steps_valid` and `missing_routed_model_ids`
   (if present). Absent summary renders as "not written", never as success.
5. **Steps** — one row per `state.json` step record: step, state, attempt,
   output directory (present/absent), and which report files exist. A missing
   optional report renders as "unavailable", not success.
6. **Attempt history** — one entry per `attempts/attempt-00N.json` snapshot:
   attempt number, its summary status, per-step states, and whether the
   snapshot carried a checksum manifest. Preserved failures and blocks stay
   visible; e.g. the acceptance run shows attempts 2–3 as honest
   `PARTIAL_BLOCKED` overhead history under final attempt 4.
7. **Lifecycle ownership** — per lease from `lifecycle.jsonl`: runtime,
   ownership (`attached` / `owned` / `reclaimed`), and terminal action
   (`released` / `untouched`), using exactly those words. Unknown or
   unterminated leases render as "unresolved", never as released.
8. **Step reports** — for `SEALED_VERIFIED` bundles only, the latest
   attempt's existing `report.md` per step, rendered structurally: Markdown
   pipe tables become HTML tables cell-for-cell; every other line renders as
   escaped text. Values, labels (`PASS`, `FAIL`, `N/A`, `INCOMPARABLE`,
   `est.`, `—`), and reasons pass through verbatim — no reformatting,
   no recomputation, no substitution of missing values. The OptiQ overhead
   `N/A` therefore renders as `N/A` with its recorded reason.

## Privacy and Safety

- The browser opens bundle files read-only and writes only beneath the
  `--output` root. Re-running `EvidenceBundle.verify()` after generation must
  still pass for sealed bundles.
- No telemetry, network access, runtime contact, port binding, or process
  inspection.
- All interpolated text is HTML-escaped; report content is never emitted as
  raw HTML.
- Run directory names must match the safe run-ID pattern; other directories
  are listed as unrecognized entries without being opened deeply.
- Committed fixtures are synthetic. Tests build bundles through the real
  `EvidenceBundle` API in temporary directories: sealed PASS (including an
  overhead `N/A` report), `PARTIAL_BLOCKED` with preserved attempts, unsealed,
  checksum-corrupt, missing-file, and unsupported-schema cases. No real
  prompts, responses, credentials, or machine-specific absolute paths are
  committed.
- Raw model response viewing is out of scope; the browser renders only step
  `report.md` files and bundle metadata, not `raw.json` response bodies.

## Accessibility and Presentation

Semantic HTML (`<table>` with header scope, `<h1>`–`<h3>` hierarchy, `lang`
attribute, viewport meta), readable defaults at standard and small widths,
status conveyed by text labels (never color alone), and keyboard-reachable
navigation links between index and detail pages. Compact tables over
dashboard chrome.

## Explicit Non-Goals

Run orchestration UI, comparison charts, raw response viewing, provider or
credential surfaces, live service discovery or polling, arbitrary filesystem
browsing, schema redesign, authentication, remote hosting, and managed-runtime
refactoring. Deferred ideas are recorded in the implementation plan, not
implemented.

## Testing Contract

- View-model tests: health classification for all five states, index
  ordering, empty root, attempt history extraction, lifecycle summarization,
  step-report availability.
- Rendering tests: escaping, honest labels preserved verbatim, fail-closed
  pages for corrupt/unsealed/unreadable, table conversion fidelity.
- CLI tests: `browse` happy path and failure paths through the existing
  `main(argv)` + captured-stdout JSON convention.
- Full retained suite must pass unchanged.
- Manual verification renders the real sealed acceptance bundle read-only and
  re-validates its checksum manifest afterward.
