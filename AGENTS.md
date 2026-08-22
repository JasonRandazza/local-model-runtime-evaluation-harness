# Repository Agent Rules

The repository defines current executable reality. The Deep Wiki preserves
durable intent and history. The checksummed sibling archive preserves the
retired Stage 0–2, Package 2, personal-selection, and native-plugin repository
state from commit `ea600e0`.

## Active Product Boundary

The active project contains:

- managed policy/plan/run/resume/status/report
- managed free-bind proposal/show/validate/adopt/plan/run/resume/seal
- heterogeneous open-mix inspect/plan/run/resume/seal
- Discovery proposal/show/execute
- Approach 3 explicit recipes
- native-diagonal matrix measurement
- preference collection/review/judging/tally
- oracle and keyword RAG
- direct-versus-Osaurus routing overhead

Historical stage runners, consumed manifests, plugin tools, and operator-window
instructions are not active commands.

## Retired Model Configuration

- MXFP quantization is retired from LMRE and must not be reintroduced into any
  active family, cell, campaign, suite map, open mix, or comparison class.
  Operator decision, 2026-08-07: it runs far longer than the Gemma and Ornith
  lanes and did not produce correct comparable results.
- For the `qwen36-35b-a3b` family, the Osaurus-native cell is
  `qwen_jangtq4__osaurus`. Do not propose an MXFP replacement or a "retry MXFP"
  investigation.
- The sealed MXFP failure evidence stays preserved and must not be deleted,
  retroactively sealed, or reinterpreted. Retirement means "not selectable for
  future runs", never "erase the record".
- Removing MXFP model weights from disk and removing an MXFP entry from an
  Osaurus provider are operator actions outside agent authority. Do not perform
  them; report them instead.

## Non-Live Boundary

- Unit tests and dry-config use fakes or configuration reads only.
- They must not contact Osaurus, oMLX, OptiQ, Keychain, or a real model.
- They must not start, stop, signal, reconnect, or configure a service.
- They must not create live proposals by default or write outside temporary
  test directories.

## Live Boundary

- Do not adopt or replace a local operator policy unless the user explicitly
  requests that action in the current session.
- Do not initiate a live managed run unless the user explicitly requests live
  execution. Once requested, the adopted policy must authorize the exact
  immutable plan; matching runs do not require a second per-request manifest.
- Contact is limited to profile-approved loopback routes.
- Run one configured model/server lane at a time.
- Enforce the configured memory floor before and between lanes.
- Start/stop behavior is limited to fixed configured commands and exact
  process identity. Give the policy-defined 60-second notice before reclaim,
  honor `Ctrl+C`, use `SIGINT` then bounded `SIGTERM`, and never use broad
  process matching or force kill.
- Do not accept arbitrary shell, executable, endpoint, model, or output paths.
- Do not edit Osaurus providers or install, replace, rebuild, or uninstall an
  external plugin.
- Never infer live authority from historical manifests, evidence, or prior
  sessions.
- Open-mix execution must preserve definition order, one configured member
  lane at a time, family-qualified evidence, and honest `N/A` for unsupported
  member-local overhead. Inspection and planning remain non-live and grant no
  execution authority.

## Credentials and Evidence

- Credentials remain in approved local stores.
- Never print, serialize, log, commit, or place credentials in prompts or
  artifacts.
- Keep generated raw results out of Git.
- Preserve honest `PASS`/`FAIL`/`N/A`/`INCOMPARABLE` step states,
  `PARTIAL_BLOCKED` run states, and `EXECUTED_UNSEALED`. `N/A` means the
  step did not apply; `INCOMPARABLE` means it ran but its evidence cannot
  be set beside the other cells'. Never collapse one into the other.
  See `CONTEXT.md` for the full vocabulary.
- Do not promote generated output into durable conclusions without review.

## Repository Hygiene

- Keep current operator documentation under `docs/`.
- Keep retired project history in the sibling archive, not the active Graphify
  corpus.
- Run the retained Python suite and all dry-config commands after relevant
  changes.
- Do not stage, commit, push, add remotes, or run live evaluation unless
  explicitly requested.
- Do not delete external model weights or caches as part of catalog or
  documentation cleanup. Storage reclamation is a separately authorized task.

## Agent skills

### Issue tracker

Issues live in GitHub Issues for `JasonRandazza/local-model-runtime-evaluation-harness`, via the `gh` CLI. See `docs/agents/issue-tracker.md`.

### Triage labels

Default five-role vocabulary, label strings unchanged. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: `CONTEXT.md` and `docs/adr/` at the repo root. See `docs/agents/domain.md`.
