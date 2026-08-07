# Claude Code continuation handoff — 2026-08-06

This is the bounded continuation brief for the Local Model Runtime Evaluation
Harness (LMRE). It is written for Fable as the initial manager/reviewer, with
Anthropic subagents available for contained work.

## Manager and cost policy

- Start with Fable as the orchestrator and reviewer. Approximately $11 of
  Fable credit remained when this handoff was written.
- Spend Fable tokens on task decomposition, safety decisions, integration
  review, and final acceptance—not broad repository reading or routine edits.
- Delegate bounded discovery, focused tests, and independent review to the
  cheapest adequate subscription-backed Anthropic subagents. Give each agent
  exact files, questions, and output limits.
- Do not let parallel agents edit the shared worktree concurrently. Parallel
  work should be read-only; serialize implementation and integration.
- If Fable credit becomes unavailable, write a short checkpoint and switch the
  primary manager/advisor to Opus 5 under Jason's Anthropic subscription. Do
  not buy more credits, silently use paid API billing, or stop merely because
  the Fable allowance ended.
- The manager owns the final diff, test evidence, scope control, and truthful
  handoff. Subagent self-reports are discovery evidence, not acceptance.

## Authority boundary

Begin read-only. This document does not grant permission to run a live model,
adopt or replace policy, alter providers, transmit project material to an
external model, stage, commit, push, open a pull request, merge, or write to the
Deep Wiki. Obtain explicit current-session authority for whichever of those
actions is needed.

Never print or persist credentials. Unit tests and dry-config commands must not
contact or control Osaurus, oMLX, OptiQ, Keychain, or a real model. Live work is
one configured lane at a time and is governed by `AGENTS.md` and the exact
adopted policy and immutable plan.

## Sources of truth and first read

Repository executable truth wins over summaries. Read, in this order:

1. `AGENTS.md`
2. `README.md`
3. `docs/status.md`
4. `docs/architecture.md`
5. `docs/managed-runs.md`
6. `docs/results-browser.md`
7. `docs/run-console.md`
8. `docs/superpowers/specs/2026-07-24-harness-north-star-vision.md`
9. `docs/superpowers/specs/2026-08-06-run-orchestration-ui-mvp.md`
10. `docs/omniroute-claude-code.md` if OmniRoute will be used

Use Graphify for navigation only and verify conclusions against files and
tests. The retired Stage 0–2, Package 2, personal-selection, and native-plugin
repository state is preserved in the checksummed sibling archive; do not move
it back into the active project.

## Merged product history

The active project was reduced to the CLI-first North Star and then advanced in
bounded slices:

| Slice | Merged result |
|---|---|
| Foundation and cleanup | Managed policy/plan/run/resume/status/report became the active execution path; retired code and history moved to the sibling archive. PR #9 reconciled active documentation and code. |
| Runtime ownership hardening | PRs #10–#15 fixed macOS executable identity, oMLX process-title rewriting, symlink inspection, provider-resume sealing, retry catalogs, and process-exit sealing. |
| Readable evidence | PR #16 added the read-only sealed-results browser. |
| Portability | PR #17 added strict machine-local artifact roots and plan-bound machine profiles. |
| Readiness | PR #18 added the offline, non-authorizing `lmre doctor`. |
| Cross-run comparison | PRs #19–#22 added sealed comparison, degraded/unattributed exclusion visibility, controlled same-family expansion, and comparison-class inspection. |
| Flexible binding | PRs #23–#24 added managed free-bind declarations, immutable planning, execution, sealing, lifecycle fixes, and live acceptance. |
| Approach 3 closure | PR #25 preserved the historical collector result honestly as `REVIEWED_UNSEALED`; it was not retroactively sealed. |
| Heterogeneous open mixes | PRs #26–#27 added the ordered open-mix contract and managed execution/resume/seal path. |
| Operator reliability | PRs #28–#30 documented manual Osaurus provider reconnection, fixed a cleanup identity race, and corrected request-timeout wiring. |
| Current Qwen lane | PR #31 retired MXFP4 from the active Qwen campaign and promoted `Qwen3.6-35B-A3B-JANGTQ4`. The sealed Qwen/Ornith open-mix workflow passed; MXFP4 failure evidence remains preserved. |

Accepted current evidence includes the managed native foundation, oMLX and
OptiQ direct-versus-Osaurus overhead paths, and the sealed Qwen JANGTQ4 plus
Ornith heterogeneous run. See `docs/status.md` for exact evidence facts and
qualifications. Generated raw results remain outside Git.

## Exact current repository state

At handoff time:

- branch: `main`
- merged `HEAD` and `origin/main`: `63e9a8c` (merge of PR #31)
- package version: `0.3.0`
- the working tree is intentionally dirty with two completed, non-live slices
  that have not been committed or published

### Completed working-tree slice A: recorded metrics visibility

This extends sealed cross-run comparison with recorded metric visibility. Its
scope is currently in:

- `docs/results-browser.md`
- `docs/status.md`
- `src/local_model_runtime_evaluation/results_browser.py`
- `src/local_model_runtime_evaluation/results_browser_html.py`
- `tests/results_browser_fixtures.py`
- `tests/test_results_browser_comparisons.py`

### Completed working-tree slice B: functional run console

This adds a fixed-loopback, server-rendered operator console that delegates to
the existing managed CLI and evidence contracts. Its scope is currently in:

- `README.md`
- `docs/architecture.md`
- `docs/managed-runs.md`
- `docs/status.md`
- `docs/run-console.md`
- `docs/superpowers/specs/2026-08-06-run-orchestration-ui-mvp.md`
- `docs/ui/run-console-functional-concept.png`
- `docs/ui/run-console-fidelity-ledger.md`
- `src/local_model_runtime_evaluation/managed_run_cli.py`
- `src/local_model_runtime_evaluation/run_console.py`
- `src/local_model_runtime_evaluation/run_console_html.py`
- `src/local_model_runtime_evaluation/run_console_server.py`
- `tests/results_browser_fixtures.py`
- `tests/test_run_console.py`

The shared fixture file means the two slices must be staged carefully.

Two unrelated, untracked Fable prompt documents predate this continuation and
must not be edited, deleted, or accidentally staged:

- `docs/handoffs/2026-08-05-claude-fable-comparison-health-visibility-execution-prompt.md`
- `docs/handoffs/2026-08-05-claude-fable-sealed-cross-run-comparison-execution-prompt.md`

## Verification already completed

After the final run-console patch:

- 563 retained tests passed; one environment-dependent test skipped
- all six retained dry-config commands passed
- Ruff passed for the new UI modules and tests
- `git diff --check` and Python byte-compilation passed
- the UI was reviewed at 1280×900 and 390×844 with no horizontal page overflow
- Graphify was refreshed to 2,812 nodes, 8,995 edges, and 151 communities
- no live evaluation was started; temporary UI/browser processes were closed

Do not merely quote this evidence. Re-run the relevant checks before
publication because the filesystem may have changed after handoff.

## Immediate continuation sequence

1. Inspect `git status`, `git diff --stat`, and the complete diff against
   `main`. Confirm the two protected prompt files are still unrelated.
2. Review slice A for evidence honesty, checksum/schema failure behavior, HTML
   escaping, and compatibility with older sealed bundles.
3. Review slice B for fixed loopback/command vectors, Host and origin checks,
   CSRF, expiring single-use action grants, one-child concurrency, exact-child
   cancellation, and the rule that UI state never becomes evidence truth.
4. Run focused tests, the full retained suite, the six commands below,
   `git diff --check`, and the relevant formatter/linter checks.
5. With current explicit Git authorization, publish the work as either two
   sequential pull requests or one pull request with two logical commits.
   Prefer two commits: recorded metrics visibility first, run console second.
   Use selective staging because `tests/results_browser_fixtures.py` and
   `docs/status.md` contain shared work. Never stage the two protected prompts.
6. Independently review the pull request diff and checks before merging. Do not
   merge if evidence states, lifecycle ownership, or non-live boundaries have
   regressed.

Retained dry-config commands:

```bash
./bin/lmre-discover dry-config
./bin/lmre-approach3 dry-config config/approach3/gemma-freeform-native-triple-v1.json
./bin/lmre-matrix --dry-config --campaign config/matrix/gemma-4-12b-qat-campaign.json
./bin/lmre-preference collect --dry-config
./bin/lmre-rag collect --dry-config
./bin/lmre-overhead run --dry-config
```

## Next new bounded slice

After the dirty work lands, start **release-readiness hardening**. The North
Star feature chain—discovery, guided managed runs, controlled expansion,
free-binding, heterogeneous mixes, readable results, and run orchestration—is
functionally implemented. The next job is to make the first public release
credible and repeatable:

1. audit installation and packaging from a clean environment;
2. define the supported first-run path from install through offline doctor and
   read-only browsing;
3. add HTTP-handler-level run-console integration coverage where the present
   tests do not exercise the real local server boundary;
4. reconcile version, changelog/release notes, support boundary, and known
   limitations;
5. create a release checklist covering non-live verification, optional
   separately authorized live acceptance, artifacts, and rollback.

Keep this as a bounded release slice. Do not add cloud services, automatic
provider editing, arbitrary commands/endpoints, installer-driven model
downloads, or a generalized plugin system.

## OmniRoute boundary

OmniRoute may reduce manager-token use, but it is an external routing boundary.
Follow `docs/omniroute-claude-code.md`. Do not assume the named LMRE context
skill works: it was registered but its fixed wrapper returned `Skill not
found` during the latest check. Direct, minimal sanitized packets remain the
fallback. Obtain current-session approval before transmitting project context,
and exclude credentials, local paths, raw evidence, run identities, model
responses, and machine-specific configuration unless Jason explicitly changes
that boundary.

