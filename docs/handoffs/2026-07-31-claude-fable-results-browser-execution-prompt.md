# Claude Fable 5 execution prompt: LMRE sealed-results browser

Copy everything below the horizontal rule into a new Claude Code session started
from:

`/Users/jrazz/Dev/active/local-model-runtime-evaluation-harness`

Select **Fable 5** as the lead model before submitting it.

---

You are the lead architect, planner, orchestrator, and final integrator for the
Local Model Runtime Evaluation Harness (LMRE). You are expected to be running
as Claude Fable 5 in Claude Code. Confirm the active model and working
directory before spending usage credits. If you are not Fable 5, or the
working directory is not exactly
`/Users/jrazz/Dev/active/local-model-runtime-evaluation-harness`, stop and tell
the user what must be corrected.

## Mission

Design and implement the smallest trustworthy **read-only sealed-results
browser** vertical slice for LMRE. This is the next non-overlapping product
slice of the North Star: operators should be able to understand sealed local
evaluation evidence without opening raw JSON and Markdown files manually.

You have authority to inspect the repository, create a feature branch, write
the design and implementation plan, implement this bounded slice, run non-live
tests and local UI verification, commit logical changes, push the feature
branch, and open a reviewable pull request. Do not merge the pull request.

This mission is intentionally separate from the managed runtime work. Do not
extend, redesign, or opportunistically refactor runtime lifecycle, inference,
provider, credential, storage, or live-evaluation behavior.

## Credit and orchestration budget

The user has a total of **$90 in usage credits** available for this effort.

- Treat **$75 as the hard working cap** for discovery, planning,
  implementation, testing, and review.
- Preserve **$15 as an untouched repair reserve**.
- Before dispatching agents, use the available `claude-api` skill or current
  official Claude Code usage information to verify the models, subagent model
  controls, and cost telemetry actually available in this installation. Do
  not rely on remembered pricing or obsolete model names.
- Use Fable for architecture, synthesis, difficult integration decisions, and
  final adjudication. Use the cheapest adequate available model for bounded
  scouting, fixture, test, and review tasks.
- Limit concurrent subagents to **three**. Work in waves. Do not leave idle
  agents running, and do not create a full agent team unless you first show
  that ordinary bounded subagents cannot do the job more cheaply.
- Do not send the entire repository or the same long context to every agent.
  Give each agent exact files, a narrow question, an output schema, and a
  short shared brief.
- Require concise results: findings with file references, decisions,
  uncertainties, and recommended actions. Do not pay multiple agents to write
  overlapping narrative reports.
- Keep a compact cost ledger after every wave. If exact dollar telemetry is
  unavailable, use conservative token/usage estimates and state the
  uncertainty. Stop before starting a wave that could plausibly exceed the
  $75 working cap.
- Suggested allocation, adjustable only with written justification:
  - onboarding, evidence inspection, and planning: at most $12;
  - implementation: at most $48;
  - verification, review, and repair: at most $15.

Cost efficiency is an acceptance requirement, not an afterthought.

## Authority and stop conditions

This prompt explicitly authorizes safe repository-local implementation,
tests, branch creation, commits, push, and pull-request creation for the
results-browser slice.

Stop and request current-session user authorization before any of the
following:

- a live model request or benchmark;
- starting, stopping, signaling, reclaiming, or configuring Osaurus, oMLX,
  OptiQ, or another model runtime;
- adopting or replacing an LMRE operator policy;
- editing or reconnecting an Osaurus provider;
- reading, creating, moving, or exposing credentials or secrets;
- downloading, copying, moving, or deleting model weights;
- modifying or installing an external/native plugin;
- writing to the Obsidian vault or sibling archive;
- destructive cleanup, force kill, broad process-name kill, or repository
  history rewrite;
- deployment to any remote service;
- merging the pull request;
- expanding into run orchestration UI or changing the managed-runtime core.

If the worktree is dirty at onboarding, inspect the changes and stop if they
overlap this mission. One expected exception is this exact untracked handoff
artifact:

`docs/handoffs/2026-07-31-claude-fable-results-browser-execution-prompt.md`

Preserve it and include it in the first documentation commit on your feature
branch. Do not treat that file by itself as a blocker. Never discard another
agent's or the user's work.

## Source precedence and reading discipline

Use this precedence when sources conflict:

1. Repository source, config, schemas, and tests define current executable
   behavior.
2. Current repository documentation explains supported operation.
3. Canonical verification records and sealed local evidence support claims.
4. The Deep Wiki preserves durable intent and project history.
5. The sibling archive preserves retired executable and documentation
   history; it is not current authority.

Do not read everything indiscriminately. Use progressive disclosure and
Graphify to avoid paying Fable prices for repeated file traversal.

### Required repository onboarding order

1. Read `AGENTS.md` completely. Its safety and Git boundaries apply even if
   another document is older or more permissive.
2. Read `README.md`, `docs/status.md`, `docs/architecture.md`, and
   `docs/history.md`.
3. Read:
   - `docs/superpowers/specs/2026-07-24-harness-north-star-vision.md`
   - `docs/superpowers/specs/2026-07-30-managed-local-run-foundation-design.md`
   - `docs/managed-runs.md`
   - `docs/documentation-triage-inventory.md`
4. Inspect the current branch, recent Git history, package metadata, source
   tree, tests, and ignored-output boundaries.
5. Use the installed `graphify` skill and existing
   `graphify-out/graph.json` as the first architecture map. Query it for the
   evidence bundle, managed run state, reports, comparison identities,
   attempts, and existing rendering/report code. Do not rebuild Graphify at
   onboarding.
6. Inspect the sealed acceptance bundle identified below. Prefer summaries,
   state, manifests, and reports. Do not ingest raw model response bodies into
   prompts unless a specific implementation question truly requires them.

### Targeted historical context only

If a product decision remains unresolved after repository onboarding, consult
the Obsidian vault read-only. Follow `Deep Wiki Home` to the
`Deep Wiki Retrieval Guide` before targeted retrieval. Relevant roots are:

- `/Users/jrazz/Documents/ObsidianNotes/10 Wiki/Projects/Local Model Benchmark Overhaul`
- `/Users/jrazz/Documents/ObsidianNotes/20 Records/Projects/Local Model Stack/Tier 5`

Do not scan the entire vault, configuration, archives, audit activity, or
unrelated projects. Do not write to the vault.

The retired repository history is checksummed at:

`/Users/jrazz/Dev/archive/local-model-runtime-evaluation-harness-history-2026-07-30`

Do not read it wholesale. Open a historical file only when an active source
explicitly points there and the current repository cannot answer the question.
Do not modify it or restore retired Stage 0–2 code.

## Confirmed handoff state

Treat the following as a handoff claim that must be cheaply verified before
planning, not blindly repeated:

- Repository: `/Users/jrazz/Dev/active/local-model-runtime-evaluation-harness`
- Baseline branch: `main`
- Baseline commit at handoff:
  `3e17a2c42674768d16cdcf36ccd2b08c77b5eaa5`
- Working tree was clean after PR #15 merged.
- The managed local-run foundation is implemented and live-accepted.
- Accepted run:
  `results/runs/run-20260731-051843-04302b`
- Run name and comparison ID:
  `gemma-managed-acceptance-20260731-r4`
- Final state: sealed `PASS`, attempt `4`.
- The complete checksum manifest validated after sealing.
- The retained Python suite passed **372 tests** after the lifecycle fix.
- Attempt 1 preserved PASS evidence for preflight, native matrix, preference,
  RAG oracle, and RAG keyword.
- Attempts 2 and 3 preserve honest overhead recovery failures/blocks.
- Attempt 4 completed the oMLX direct-versus-Osaurus screen overhead step:
  direct median total approximately `2.001s`, routed approximately `1.991s`,
  delta approximately `-0.011s`, TTFT delta approximately `+0.020s`, with
  both response-contract paths `PASS`.
- The OptiQ overhead pair was `N/A` in this screen attempt. Do not convert that
  into a PASS or claim it was measured.
- Osaurus was attached and recorded untouched. The planned oMLX workers were
  harness-owned, sequentially released, and absent after cleanup. The
  operator-owned OptiQ process remained untouched.
- `docs/status.md` still says the managed implementation lacks live acceptance.
  That statement became stale after the sealed PASS and must be reconciled
  accurately as part of this work.

Recent fixes that must not be regressed include macOS executable inspection,
rewritten oMLX process identity, symlinked executable handling, writable sealed
resume ordering, attempt-specific oMLX catalogs, overhead-only retry rules,
and waiting for the exact managed PID to exit before evidence sealing. Inspect
PRs/commits #10 through #15 if a browser decision touches their contracts;
otherwise leave them alone.

## Product direction

The North Star is a local-first harness that lets competent local-AI operators
discover compatible models, run bounded fail-closed evaluations, and read the
results with minimal ceremony. The repository has reached the managed CLI
foundation. The next isolated slice is **read sealed evidence easily**.

The browser comes before run orchestration UI. This slice must remain
read-only. It should make existing trusted evidence understandable; it must
not become a second execution authority.

## Required planning behavior

Do not immediately code.

1. Verify the handoff state and authoritative contracts.
2. Dispatch at most three inexpensive, read-only scouts in one bounded wave:
   - **Evidence-contract scout:** map sealed bundle structure, verification
     APIs, attempts, comparison identity, metrics, and safe reusable code.
   - **Product/UX scout:** derive the smallest useful operator journeys and
     accessibility expectations from the North Star and existing reports.
   - **Implementation-risk scout:** inspect packaging, current dependencies,
     test conventions, privacy boundaries, and the cheapest viable delivery
     architecture.
3. Give scouts disjoint files and questions. Require file/line evidence and a
   compact structured answer. Do not allow edits in this wave.
4. Synthesize the findings yourself. Explicitly compare at least these three
   architecture shapes:
   - generated static HTML from verified sealed bundles;
   - a small loopback-only local server with a minimal browser UI;
   - a separate frontend framework/application.
5. Prefer the smallest architecture that meets the product requirements.
   Invoke the available `ponytail:ponytail` skill for simplicity pressure.
   Any new runtime dependency or framework must earn its cost with a concrete
   requirement that the standard library or existing dependencies cannot
   satisfy.
6. Write one current design spec under `docs/superpowers/specs/` and one
   executable implementation plan under `docs/superpowers/plans/`. Mark older
   relevant plans as historical only when necessary; do not delete history.
7. Self-review the design and plan for placeholders, contradictions, ambiguous
   evidence claims, scope creep, privacy leakage, unowned files, and work that
   cannot be tested.
8. Because the user approved autonomous safe execution in this prompt, proceed
   without waiting for another approval only if the final design stays inside
   every boundary here and the projected spend stays within the working cap.
   Otherwise stop and present the decision needed.

## Product requirements for the vertical slice

The design may refine presentation details, but it must satisfy these
behaviors:

1. **Local and read-only**
   - No telemetry, cloud service, remote API, CDN dependency, or account.
   - No mutation of evidence bundles.
   - No runtime or inference contact.
   - Bind only to loopback if a server is used.

2. **Verification before presentation**
   - Reuse the repository's evidence loading and checksum validation rather
     than reimplementing a weaker verifier.
   - Never present an unverified bundle as accepted evidence.
   - Display sealed, unsealed, corrupt, unsupported, and incomplete states
     distinctly and honestly.

3. **Run index**
   - Discover bundles beneath a configurable local results root with a safe
     default.
   - Show run name, run ID, comparison ID, family/recipe when available,
     attempt, terminal state, timestamp, and verification status.
   - Default to useful sorting and clear empty/error states.

4. **Run detail**
   - Show immutable plan identity and policy identity without displaying
     credentials.
   - Show step states, output/report availability, attempt history, preserved
     failures/blocks, and final summary.
   - Show lifecycle ownership as attached, owned, reclaimed, released, or
     untouched using precise language.

5. **Results presentation**
   - Render the most useful existing summary metrics for matrix, preference,
     RAG, and overhead without inventing comparability.
   - Preserve `PASS`, `FAIL`, `N/A`, `INCOMPARABLE`, `PARTIAL_BLOCKED`, and
     qualification labels exactly where their distinction matters.
   - Do not turn missing OptiQ overhead data into zero, PASS, or an inferred
     result.
   - Prefer existing report structures and shared parsing code over duplicated
     business logic.

6. **Comparison honesty**
   - Compare runs only when comparison identity, suite/revision, family/cell
     contract, and metric qualification make the comparison legitimate.
   - If the MVP cannot safely compare runs, provide navigation and explicitly
     defer comparison rather than shipping misleading charts.

7. **Privacy and fixture discipline**
   - `results/` is gitignored and raw local evidence must remain uncommitted.
   - Create small synthetic, sanitized fixtures that exercise PASS, blocked,
     failed/corrupt, missing, and multi-attempt behavior.
   - Do not copy real prompts, model responses, credentials, machine secrets,
     or unnecessary absolute paths into committed fixtures or screenshots.
   - Treat raw response viewing as out of scope unless the user separately
     approves a privacy design.

8. **Operator experience**
   - Provide one documented command to build/open or serve the browser.
   - Make the primary path understandable without knowledge of internal JSON
     filenames.
   - Provide keyboard-usable, readable, responsive output with basic
     accessibility semantics.
   - Favor clear tables and compact visuals over decorative dashboard chrome.

9. **Failure behavior**
   - A malformed bundle must not crash or hide other valid runs.
   - Unsupported schema versions and checksum failures must fail closed and
     explain what is wrong without leaking raw content.
   - Missing optional step reports must render as unavailable, not success.

10. **Maintainability**
    - Keep evidence interpretation in a tested boundary separate from
      rendering.
    - Keep modules small and interfaces explicit.
    - Avoid a second copy of state transitions, checksum rules, or metric
      semantics.

## Explicit non-goals

Do not implement any of these in this pull request:

- buttons or APIs that plan, run, resume, cancel, start, stop, or reclaim;
- provider setup, provider reconnect, credential entry, or Keychain access;
- live service discovery or polling of ports 1337, 8100, or 8080;
- model download, placement, cache cleanup, or storage management;
- editing policies, plans, sealed bundles, reports, or run names;
- arbitrary filesystem browsing or user-selected executable paths;
- open heterogeneous comparison scheduling;
- Approach 3 sealing or evidence-schema redesign;
- raw model-response exploration;
- authentication, multi-user hosting, remote deployment, analytics, or sync;
- native plugin work;
- changes to the sibling archive or Obsidian vault;
- unrelated refactoring of the managed runtime foundation.

Record attractive ideas outside these boundaries as concise deferred work;
do not implement them.

## Subagent execution protocol

After the design and plan pass self-review, choose the smallest useful
implementation topology. Do not spawn agents merely to satisfy the phrase
"subagent driven."

Recommended waves:

### Wave 1: contract and skeleton

- One implementation agent may own the evidence-index/view-model boundary and
  its tests.
- One implementation agent may own the presentation shell and sanitized
  fixture-driven UI tests, but only after the lead freezes the view-model
  contract.
- A third agent is optional for documentation/fixture work only if its files
  are disjoint and the cost is justified.

Use isolated worktrees for parallel writing, or execute sequentially if
worktree setup and integration would cost more than it saves. Assign exact
file ownership. Subagents must not commit, push, merge, change plans, or edit
files outside their assignment. The Fable lead owns integration and Git.

### Wave 2: focused review

After integration and local tests, use inexpensive independent reviewers with
non-overlapping mandates:

- correctness and evidence-integrity review;
- privacy/security and path-safety review;
- UI usability/accessibility review, only if a real browser UI exists.

Do not ask three agents for generic code review. Deduplicate findings, verify
each against the code, and fix only validated issues.

### Wave 3: final adjudication

Fable must inspect the final diff, run the complete verification commands,
exercise the real local UI against sanitized fixtures and the sealed PASS
bundle, and decide whether the result meets every acceptance criterion.

If an agent fails, times out, or returns an ambiguous result, do not blindly
repeat the whole task. Narrow the missing question and use the cheapest
recovery path.

## Git workflow

1. Verify the `main` baseline and fetch current remote state without
   discarding local work. The one expected untracked handoff artifact named
   above is allowed; any other overlapping change remains a stop condition.
2. Create a branch such as `claude/results-browser-mvp`.
3. Keep commits small and coherent: design/plan, evidence boundary, UI,
   documentation/verification as appropriate.
4. The lead reviews every diff before committing it.
5. Never commit `results/`, `.lmre/`, credentials, caches, generated Graphify
   outputs, local screenshots containing sensitive paths, or dependency build
   output.
6. Push the branch and create a pull request only after verification passes.
7. Do not merge. Hand the PR to the user with risks, deferred work, cost
   accounting, and exact verification evidence.

## Required verification

Use test-driven development for behavior changes. Tests must fail for the
expected missing behavior before implementation and pass afterward.

At minimum, before claiming completion:

- run all new focused tests;
- run `PYTHONPATH=src python3 -m unittest discover -s tests -v` with whatever
  local loopback permission the test fixtures require, but no model runtimes;
- run any chosen frontend build, type, lint, and test commands;
- run `git diff --check` and inspect `git status --short`;
- verify the browser against sanitized fixtures;
- verify it read-only against
  `results/runs/run-20260731-051843-04302b`;
- independently confirm that the evidence bundle remains byte-for-byte valid
  by checking its existing checksum manifest from inside the run directory;
- confirm no runtime was contacted, started, stopped, or signaled;
- confirm no provider, credential, policy, model weight, vault note, archive
  file, or external system changed;
- inspect the process/listener state only if necessary to prove the browser did
  not contact runtimes; do not alter that state;
- update `docs/status.md` so it accurately records the managed acceptance PASS
  and the actual results-browser status without overstating either;
- refresh/query Graphify after committed source changes using the repository's
  existing hook/workflow, and verify it did not ingest ignored evidence,
  archive, cache, or generated output.

Do not claim success based only on subagent reports or a passing unit test.
Read the full command output and verify the real user-visible behavior.

## Acceptance criteria

The pull request is ready only when:

- the result is a useful read-only browser, not merely a design or mockup;
- sealed bundles are verified before being represented as trusted;
- invalid/unsealed/corrupt evidence is visibly distinct and fail-closed;
- the accepted attempt-4 bundle renders accurately, including its preserved
  earlier attempts and OptiQ overhead `N/A`;
- no raw local evidence or sensitive content is committed;
- the implementation introduces no live/runtime/provider authority;
- the architecture is the smallest justified option;
- focused tests and the full retained suite pass;
- the real UI path was exercised and documented;
- current status documentation is reconciled;
- the working cap was respected and the $15 reserve remains untouched;
- the branch is pushed and a non-draft PR is open, but unmerged.

## Final report format

Return a compact handoff with:

1. outcome and PR link;
2. architecture chosen and why the cheaper alternatives did or did not meet
   requirements;
3. user-visible functionality;
4. files and commits created;
5. tests, build, browser exercise, checksum, and Graphify verification;
6. explicit confirmation of every non-live/non-destructive boundary;
7. subagent wave ledger: task, model, result, and whether reused;
8. usage-cost ledger: known spend or conservative estimate by phase, total,
   uncertainty, and reserve remaining;
9. validated risks and deferred work;
10. exact next action for the user.

Lead with the outcome. Do not bury failures, `N/A` states, budget uncertainty,
or work that remains.

Begin now with model/cwd verification, repository onboarding, Graphify query,
and the bounded three-scout planning wave. Do not perform live evaluation or
runtime actions.
