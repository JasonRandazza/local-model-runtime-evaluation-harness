# Sealed Results Browser

The results browser turns managed evidence bundles under `results/runs/` into
static, read-only HTML pages so an operator can read sealed evidence without
opening raw JSON.

## Usage

```bash
./bin/lmre browse
open results/browser/index.html
```

Options: `--results-root` (default `results/runs`) and `--output`
(default `results/browser`). The command prints a JSON result and writes
`index.html` plus one `runs/<run-id>.html` page per discovered bundle. Pages
are self-contained: inline styling, no JavaScript, no network access, no
external assets. The default output lives beneath ignored `results/`, so
generated pages stay out of Git.

## What It Verifies

Every sealed bundle is re-verified with the harness's own checksum
verification (`EvidenceBundle.verify`) before it is presented as trusted.
Each run renders with exactly one health state:

| Health | Meaning |
| --- | --- |
| `SEALED_VERIFIED` | Sealed and the complete checksum manifest validated. Full detail, including step reports. |
| `SEALED_CORRUPT` | Sealed but verification failed (checksum mismatch, invalid manifest, missing file). Fails closed: no report content is shown. |
| `UNSEALED` | The bundle is not sealed. Step states are shown under an explicit not-accepted-evidence banner; report bodies are withheld. |
| `UNSUPPORTED_SCHEMA` | The plan schema version is not supported. Fails closed. |
| `UNREADABLE` | Required bundle files are missing or invalid. The row shows the error instead of metrics. |
| `UNRECOGNIZED` | A directory that is not a run bundle. Listed, not opened. |

A malformed bundle never hides other valid runs.

## What It Shows

- **Index:** run name, run ID, comparison ID, comparison scope, family or
  open-mix identity, suite contract, recipe, comparison class, attempt, run
  status, created timestamp, and health, newest first.
- **Run detail:** plan identity (no credentials exist in bundle files; the
  policy section renders a fixed allowlist of policy fields), run summary,
  per-step states with report availability, preserved attempt history
  (honest earlier failures and blocks stay visible), lifecycle ownership per
  attempt-scoped lease (`attached`/`owned`/`reclaimed` and
  `released`/`untouched`), and —
  for verified bundles only — each step's existing `report.md` rendered
  structurally.
- Status labels pass through verbatim: `PASS`, `FAIL`, `N/A` (with its
  recorded reason), `INCOMPARABLE`, `PARTIAL_BLOCKED`,
  `BLOCKED_PROVIDER_RECONNECT`, `est.`, and `—` are never converted,
  recomputed, or replaced. Missing reports render as unavailable, not as
  success.

## Cross-Run Comparisons

The browser also writes `comparisons/index.html` and one
`comparisons/<comparison-id>.html` page per group, linked from the main
index. The grouping and comparability baseline is preserved in
`docs/superpowers/specs/2026-08-05-sealed-cross-run-comparison.md`; the current
read-only presentation contract is:

- Groups form only from a persisted, non-empty `identity.comparison_id`
  matching the safe shape `[a-z0-9][a-z0-9-]{0,79}`. Missing or malformed
  identity never invents a group; `UNREADABLE`, `UNRECOGNIZED`, and
  `UNSUPPORTED_SCHEMA` bundles have no vetted identity and join no group
  (they stay visible in the run index).
- Two kinds of exclusion are distinct and never conflated. **In-group
  exclusions** are `UNSEALED`/`SEALED_CORRUPT` bundles with vetted identity:
  they appear as excluded members inside their comparison group. **Unattributed
  exclusions** are entries with no vetted identity at all — degraded health
  (`UNREADABLE`/`UNSUPPORTED_SCHEMA`/`UNRECOGNIZED`, including symlinked
  entries) or a present-but-malformed `comparison_id` — and are listed
  separately in the comparisons index under "Unattributed exclusions"; they
  contribute nothing and cannot be assigned to any group. A healthy solo run
  with no explicit `comparison_id` is neither: it keeps forming its own
  one-member `N/A` group as before.
- Only `SEALED_VERIFIED` members contribute accepted comparison data.
  `UNSEALED` and `SEALED_CORRUPT` members are listed with the group as
  excluded, with a deterministic reason, and never leak withheld report
  content.
- A shared comparison ID is necessary but not sufficient. Accepted members
  must agree on the portable immutable plan dimensions (schema version,
  comparison scope, family or open-mix definition and ordered members, suite
  contract, recipe, comparison class, managed binding ID and hashes, matrix
  mode, steps, cell IDs, pair IDs, and the `input_hashes` content identity).
  Machine paths are never compared as identities.
- Group verdicts: `COMPARABLE` (two or more accepted members, all
  dimensions agree), `INCOMPARABLE` with a stable
  `plan_dimension_mismatch: ...` reason (no metrics are aggregated or
  ranked), or `N/A (fewer than two accepted members)`. A mismatch never
  hides individual run pages.
- Ordering is deterministic: groups by comparison ID; members by created
  timestamp, then run ID, then directory name.
- A `COMPARABLE` page also shows the existing recorded matrix summary values
  for every exact plan cell and direct-versus-Osaurus overhead summary values
  for every exact plan pair. Values are read only from checksummed `raw.json`
  files inside sealed verified bundles and displayed verbatim, in immutable
  plan order. The browser never reads observations or response text for this
  view.
- Missing, malformed, duplicate, or plan-mismatched metric rows fail closed as
  `UNAVAILABLE`; plans with no overhead pairs show overhead as `N/A`. An
  unavailable run remains an accepted member when its bundle and plan are
  otherwise sealed, verified, and comparable, but contributes no metric rows.
- No metric section is exposed for `INCOMPARABLE` or one-member `N/A` groups.
  No winner, ranking, delta, confidence value, or new score is derived.
  Open-mix identity is understood and compared fail-closed.

The `browse` JSON output adds `comparison_index` and `comparisons`
alongside the existing keys, plus `unattributed_exclusions` (the count of
entries listed in the "Unattributed exclusions" section above).

## Boundaries

The browser is read-only presentation. It does not run, resume, or plan
evaluations; it does not contact Osaurus, oMLX, OptiQ, or any other service;
it binds no port; it never edits bundles, policies, providers, credentials,
or model weights. Raw model-response viewing and derived metric calculations
remain deliberately out of scope.
