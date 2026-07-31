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

- **Index:** run name, run ID, comparison ID, family, recipe, attempt, run
  status, created timestamp, and health, newest first.
- **Run detail:** plan identity (no credentials exist in bundle files; the
  policy section renders a fixed allowlist of policy fields), run summary,
  per-step states with report availability, preserved attempt history
  (honest earlier failures and blocks stay visible), lifecycle ownership per
  lease (`attached`/`owned`/`reclaimed` and `released`/`untouched`), and —
  for verified bundles only — each step's existing `report.md` rendered
  structurally.
- Status labels pass through verbatim: `PASS`, `FAIL`, `N/A` (with its
  recorded reason), `INCOMPARABLE`, `PARTIAL_BLOCKED`,
  `BLOCKED_PROVIDER_RECONNECT`, `est.`, and `—` are never converted,
  recomputed, or replaced. Missing reports render as unavailable, not as
  success.

## Boundaries

The browser is read-only presentation. It does not run, resume, or plan
evaluations; it does not contact Osaurus, oMLX, OptiQ, or any other service;
it binds no port; it never edits bundles, policies, providers, credentials,
or model weights. Cross-run comparison views and raw model-response viewing
are deliberately out of scope.
