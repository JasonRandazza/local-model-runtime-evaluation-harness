# Claude Fable 5 execution prompt: LMRE offline doctor

Copy everything below the horizontal rule into a new Claude Code session
started from:

`/Users/jrazz/Dev/active/local-model-runtime-evaluation-harness`

Select **Fable 5** as the lead model before submitting it.

---

You are the lead architect, planner, orchestrator, implementer, and final
integrator for the Local Model Runtime Evaluation Harness (LMRE). You are
expected to be running as Claude Fable 5 in Claude Code. Confirm the active
model and working directory before spending usage credits. If the model is
not Fable 5, or the working directory is not exactly
`/Users/jrazz/Dev/active/local-model-runtime-evaluation-harness`, stop and
tell the user what must be corrected.

## Mission

Design and implement the smallest trustworthy **offline `lmre doctor`
readiness assistant** for LMRE. It should help a competent local-AI operator
understand whether the harness installation, active configuration, model
artifacts, and standing policy are prepared for a later live check—without
contacting, starting, stopping, inspecting, or configuring a model runtime.

Portable artifact roots are now current product behavior. The doctor must
validate the fixed ignored `.lmre/machine-profile.json`, reuse the merged
artifact resolver, and report readiness for the exact resolved artifacts. It
must not recreate token parsing, search for alternative models, or treat a
machine profile as live authority.

The doctor must distinguish static local readiness from live runtime
readiness. It may report that offline prerequisites are satisfied. It must
never infer that Osaurus, oMLX, OptiQ, their providers, their model inventory,
credentials, memory state, listeners, or inference are ready unless a future
separately authorized live workflow checks them.

You have authority to inspect the repository, create a feature branch, write
the design and implementation plan, implement this bounded slice, run
non-live tests and dry-config verification, commit logical changes, push the
feature branch, and open a reviewable pull request. Do not merge the pull
request.

## Credit and orchestration budget

The user allocated **$61.34 in usage credits** to this effort when this prompt
was approved.

- Treat **$50.00 as the hard working cap** for discovery, planning,
  implementation, testing, and review.
- Preserve **$11.34 as an untouched repair reserve**.
- Verify the currently displayed balance before dispatching paid work. If it
  is below $61.34, reduce the working allowance so at least $11.34 remains;
  never increase the $50.00 cap without new user approval.
- Before dispatching agents, use the available `claude-api` skill or current
  official Claude Code information to verify available model controls and
  cost telemetry. Do not rely on remembered pricing or obsolete model names.
- Use Fable for architecture, synthesis, integration decisions, difficult
  defects, and final adjudication. Use the cheapest adequate available model
  for bounded scouting, fixture, test, or focused review work.
- Limit concurrent subagents to **two**. Work in waves and terminate completed
  agents. Do not create a full agent team.
- Do not send the entire repository or identical long context to every agent.
  Give each agent exact files, a narrow question, an output schema, and a
  short shared brief.
- Keep a compact cost ledger after each wave. If exact dollar telemetry is
  unavailable, use conservative usage estimates and state the uncertainty.
  Stop before beginning any wave that could plausibly exceed the $50.00 cap.
- Suggested allocation, adjustable only with written justification:
  - onboarding, contract inspection, and planning: at most $8.00;
  - implementation and focused tests: at most $30.00;
  - verification, review, and repair: at most $12.00.

Cost efficiency is an acceptance requirement. The reserve is not permission
to exceed the working cap.

## Authority and stop conditions

This prompt authorizes safe repository-local implementation, tests, branch
creation, commits, push, and pull-request creation for the offline doctor
slice.

Stop and request current-session user authorization before any of the
following:

- contacting any loopback or remote endpoint;
- issuing a live model request, benchmark, proposal, or managed run;
- starting, stopping, signaling, reclaiming, attaching to, or inspecting a
  running Osaurus, oMLX, OptiQ, or other model-runtime process;
- polling or binding ports `1337`, `8100`, `8080`, or any other port;
- reading Keychain, environment secrets, credentials, API keys, or tokens;
- adopting, replacing, or writing an operator policy;
- creating a managed run plan or evidence bundle;
- editing or reconnecting an Osaurus provider;
- executing an external runtime CLI, even only with `--version`;
- downloading, copying, moving, linking, or deleting model weights;
- modifying or installing an external/native plugin;
- writing to the Obsidian vault or sibling archive;
- destructive cleanup, force kill, broad process matching, or Git history
  rewrite;
- deployment to an external service;
- merging the pull request;
- expanding into a setup wizard, package installer, runtime dashboard,
  provider editor, run-orchestration UI, or managed-runtime refactor.

If the worktree is dirty at onboarding, inspect the changes and stop if they
overlap this mission. One expected exception is this exact untracked handoff
artifact:

`docs/handoffs/2026-07-31-claude-fable-lmre-doctor-execution-prompt.md`

Preserve it and include it in the first documentation commit on your feature
branch. Do not treat that file by itself as a blocker. Never discard another
agent's or the user's work.

## Source precedence and baseline

Use this precedence when sources conflict:

1. Repository source, configuration, schemas, and tests define current
   executable behavior.
2. Current repository documentation explains supported operation.
3. Canonical verification records and sealed local evidence support claims.
4. The Deep Wiki preserves durable intent and project history.
5. The checksummed sibling archive preserves retired Stage 0–2, Package 2,
   personal-selection, and native-plugin history; it is not current authority.

PR #16, **Add read-only sealed-results browser (`lmre browse`)**, and PR #17,
**Add portable model artifact roots**, are both merged current behavior.
Before spending beyond a cheap baseline check, verify that `main` contains
merge commit `f3269e5` (or equivalent later history containing portability
commit `594d786`), that PR #17 is closed as merged, and that the worktree
contains no unexplained changes other than the handoff artifact above. If the
portability work is absent, stop and tell the user rather than recreating it or
building a stacked doctor branch.

The merged results browser is current product behavior, but the doctor is a
separate slice. Do not redesign its evidence model, HTML, or `browse` command.

## Required repository onboarding

Use progressive disclosure. Do not read the whole repository repeatedly.

1. Read `AGENTS.md` completely. Its current safety and Git boundaries govern
   this work.
2. Read `README.md`, `docs/status.md`, `docs/architecture.md`,
   `docs/managed-runs.md`, `docs/discovery.md`, and
   `docs/results-browser.md`. Read `docs/matrix.md` and `docs/overhead.md` only
   for their current artifact-resolution and dry-config contracts.
3. Read:
   - `docs/superpowers/specs/2026-07-24-harness-north-star-vision.md`
   - `docs/superpowers/specs/2026-07-30-managed-local-run-foundation-design.md`
   - `docs/superpowers/specs/2026-07-31-sealed-results-browser-design.md`
   - `docs/superpowers/specs/2026-07-31-portable-artifact-roots-design.md`
   - `docs/superpowers/plans/2026-07-31-portable-artifact-roots.md`
   - `schemas/operator-policy.schema.json`
   - `config/operator-policies/local-managed-v1.example.json`
4. Inspect current Git history, package metadata, `bin/lmre`, managed command
   dispatch, `artifact_profile.py`, matrix/config resolvers,
   operator-policy loading, plan input hashing, error conventions, test
   conventions, and ignored-output boundaries.
5. Use the installed `graphify` skill and existing
   `graphify-out/graph.json` as the first architecture map. Query it for
   `artifact_profile.py`, operator policy, config loaders,
   family/cell/recipe relationships, CLI dispatch, dry-config behavior,
   credentials, transports, process inspection, runtime adapters, and tests.
   Treat graph results as navigation pointers and verify every conclusion in
   current source. Do not rebuild Graphify during onboarding.
6. Do not inspect real result bodies, credentials, runtime state, the entire
   Obsidian vault, or the sibling archive. This slice should be answerable
   from active repository truth.

The sibling archive remains read-only at:

`/Users/jrazz/Dev/archive/local-model-runtime-evaluation-harness-history-2026-07-30`

Do not restore retired doctor/plugin/stage behavior from it.

## Approved product design

The user approved this product boundary before this prompt was written.

### Command surface

- Add `./bin/lmre doctor` to the normal managed CLI.
- Preserve the managed CLI's existing JSON output convention by default.
- Add `./bin/lmre doctor --format text` for a concise, readable operator
  checklist.
- Both formats must be projections of the same structured diagnostic result;
  rendering must not recompute readiness.
- The command writes nothing by default. It reports to stdout only.

### Readiness language

Use a small explicit vocabulary such as:

- `OFFLINE_READY`: every prerequisite that this offline command is authorized
  to check passed;
- `ACTION_REQUIRED`: a required local prerequisite is missing or invalid;
- `WARNING`: a non-blocking condition deserves attention;
- `NOT_CHECKED_LIVE`: the fact requires runtime, provider, credential,
  listener, process, memory, or inference contact and was intentionally not
  checked.

The exact enum names may be refined in the design spec, but they must retain
these distinctions. Never use bare `READY`, `PASS`, or language implying the
machine is ready to run live evaluation when only static checks passed.

The command-level `ok` field should mean the diagnostic command completed
successfully, not that all prerequisites passed. Provide a separate overall
readiness field. Exit `0` whenever a complete structured diagnostic is
successfully emitted, including `ACTION_REQUIRED` or `WARNING` results. Exit
`1` only for malformed invocation or an unexpected failure that prevents a
complete diagnostic. Test both behaviors.

### Authorized offline checks

The implementation should inspect only static local state needed for a useful
first-run report:

1. **Harness and Python**
   - supported Python version;
   - package/import and repository-root integrity;
   - expected LMRE command wrappers and active documentation exist.
2. **External command presence**
   - resolve whether the fixed names `osaurus`, `omlx`, and `optiq` are
     discoverable through an injected `which`-style lookup;
   - do not execute them, inspect their processes, infer their versions, or
     accept user-selected executable paths.
3. **Active configuration integrity**
   - load the fixed `.lmre/machine-profile.json` through
     `load_artifact_roots`; report a missing, malformed, unsafe, or incomplete
     profile as action required without repairing it;
   - accept only the merged `local_models` and `huggingface_hub` root contract;
     do not add CLI overrides, environment interpolation, `~` expansion, or
     new root categories;
   - validate active families, cells, campaigns, managed recipes, suites,
     preference/RAG mappings, and overhead pairs through existing parsers and
     validation APIs wherever possible;
   - report cross-file mismatches without duplicating the business rules;
   - do not revive retired full-grid or archive configuration.
4. **Configured model artifacts**
   - resolve committed `{LMRE_ROOT:...}` templates through the validated
     `ArtifactRoots` value and existing matrix/config resolution APIs;
   - check only the exact resolved artifact paths selected by active config;
   - report missing, unreadable, broken-symlink, or wrong-kind paths honestly;
   - do not scan broad caches, follow unrelated roots, calculate large
     directory sizes, or mutate/link/copy/delete anything.
5. **Standing policy status**
   - if an adopted policy record exists, validate it and its hash/expiry using
     current policy APIs;
   - if it is absent or invalid, report manual action required;
   - never adopt, replace, rewrite, repair, or print secret material;
   - describe the reviewed example policy as a source for manual review, not
     as automatically authorized policy.
6. **Family/recipe offline readiness**
   - summarize which active family and managed recipe combinations satisfy
     the machine-profile, static config, command-presence, and resolved
     artifact prerequisites;
   - attach `NOT_CHECKED_LIVE` qualifications for endpoint reachability,
     provider inventory, process identity, credentials, memory, and actual
     model behavior;
   - do not create a proposal, immutable plan, run ID, evidence bundle, or
     authorization decision.
7. **Manual next actions**
   - produce deterministic, deduplicated remediation steps linked to current
     repository documentation;
   - suggest exact existing LMRE commands only when safe, but never execute
     them;
   - identify actions that still require explicit user authority, UI work, or
     live observation.

If a proposed check cannot be performed without crossing the non-live
boundary, classify it as `NOT_CHECKED_LIVE` instead of adding an exception.

## Architecture requirements

Do not immediately code. First compare these shapes:

1. a pure diagnostic engine plus structured result types and thin renderers
   wired into the existing managed CLI;
2. a separate `lmre-doctor` executable that duplicates some managed CLI
   conventions;
3. a broader interactive setup wizard or HTML application.

The approved default is shape 1 unless repository evidence reveals a concrete
conflict. Shape 2 must justify the duplicated command surface. Shape 3 is out
of scope. Enforce the smallest stdlib-first solution directly. If an optional
planning skill is available, it may assist but must not change this contract
or become a prerequisite. The repository currently has no third-party runtime
dependencies; any new dependency requires a specific unmet requirement and
explicit user approval.

Keep these boundaries explicit:

- diagnostic collection reads static inputs and returns typed/plain data;
- artifact/profile checks call `load_artifact_roots` and existing explicit
  config resolvers rather than parsing `{LMRE_ROOT:...}` or `{artifact_path}`
  again;
- extend the managed CLI's existing internal `machine_profile_path`
  dependency injection for doctor tests; do not expose a machine-profile path
  CLI option;
- readiness aggregation applies the vocabulary once;
- JSON and text renderers consume the same result without rechecking state;
- CLI wiring parses arguments and emits output only;
- no doctor module imports or constructs loopback transport, runtime manager,
  runtime adapters, process inspector, credentials, or evidence execution.

Prefer existing config and policy validators over a second implementation.
Avoid speculative plugin systems, generic check frameworks, async execution,
dynamic discovery, caching, persistence, and extension points.

## Planning and subagent protocol

1. Verify the baseline and authoritative contracts.
2. Dispatch at most two inexpensive read-only scouts in one bounded wave:
   - **contract scout:** map reusable config/policy validation APIs and identify
     imports that could accidentally cross into live behavior;
   - **operator-journey scout:** map the minimum useful first-run questions,
     output wording, remediation links, and missing test fixtures.
3. Give scouts disjoint files and require a compact response with file/line
   evidence, proposed checks, forbidden dependencies, and uncertainties. No
   edits in the scouting wave.
4. Synthesize the findings yourself and finalize the smallest architecture.
5. Write one current design spec under `docs/superpowers/specs/` and one
   executable implementation plan under `docs/superpowers/plans/`.
6. Self-review both for placeholders, contradictions, ambiguous readiness
   claims, accidental live authority, privacy leakage, duplicated validators,
   and untestable work.
7. Proceed autonomously only if the design remains inside every boundary and
   projected spend stays within the $50.00 cap. Otherwise stop and present the
   exact user decision required.

After the contract is frozen, use the smallest useful implementation
topology. One inexpensive implementation agent may own the pure diagnostic
engine and focused tests. A second agent is optional for CLI rendering,
fixtures, and documentation only if file ownership is disjoint and the cost
is justified. Fable owns integration and every Git action. Subagents must not
commit, push, merge, alter plans, touch live state, or edit outside their
assignment.

Use focused independent review only after integration:

- one correctness/non-live-boundary review;
- one operator-wording/privacy review if the first review does not cover it.

Do not pay two agents for generic overlapping review. Verify every reported
finding against the code before changing anything.

## Error and privacy behavior

- One failed check must not hide unrelated results.
- Expected missing prerequisites are structured findings, not stack traces.
- Invalid active configuration must fail closed for the affected
  family/recipe while leaving other diagnostic sections visible.
- Unexpected internal errors use the existing sanitized CLI error path.
- Never print environment variables, credential values, Keychain data,
  provider configuration bodies, raw model responses, or arbitrary command
  output.
- Configured artifact paths may be shown locally when needed for remediation,
  but committed fixtures and documentation must use sanitized synthetic paths.
- Do not persist a diagnostic snapshot, because machine readiness becomes
  stale quickly. A future export feature requires a separate design.

## Explicit non-goals

Do not implement any of these in this pull request:

- installing Python, LMRE, Osaurus, oMLX, OptiQ, models, or plugins;
- executing external CLIs or querying their versions;
- port, process, listener, provider, inventory, memory, or inference checks;
- credential presence checks or Keychain access;
- provider creation, edits, reconnects, or UI automation;
- policy adoption or repair;
- plan creation, proposal creation, run creation, execution, or resume;
- model search, download, placement, symlinking, cleanup, or storage analysis;
- arbitrary path or executable selection;
- results-browser redesign or cross-run comparison;
- run-orchestration UI, setup wizard, server, JavaScript frontend, or remote
  service;
- external telemetry, analytics, deployment, authentication, or sync;
- sibling archive or Obsidian vault changes;
- unrelated refactoring of lifecycle, transport, evidence, or collector code.

Record attractive ideas outside these boundaries as concise deferred work;
do not implement them.

## Testing contract

Use test-driven development for behavior changes. Tests must establish the
missing behavior before implementation and pass afterward.

Create sanitized temporary fixtures covering at least:

- fully satisfied offline prerequisites with every live fact qualified as
  `NOT_CHECKED_LIVE`;
- missing external command names;
- missing artifact, unreadable artifact, and broken symlink;
- valid, absent, expired, hash-mismatched, and malformed adopted policy;
- valid, missing, malformed, wrong-schema, wrong-root-key, nonexistent-root,
  and broken-link machine profiles, using only sanitized temporary roots;
- exact artifact-template resolution and an unresolved/escaping-template
  failure surfaced through existing portability APIs rather than duplicate
  parser logic;
- one malformed family/config mapping that does not hide unrelated checks;
- mixed family readiness with deterministic ordering and deduplicated actions;
- JSON/text projection parity;
- hostile or secret-looking fixture strings that are not leaked through an
  unsafe error path;
- stable exit behavior for completed diagnostics with action items versus
  internal failure.

Inject or monkeypatch filesystem lookup, command resolution, machine-profile
location, and time so tests do not depend on the developer's installed
runtimes, model paths, or policy. Add explicit tripwire tests proving the
doctor does not invoke socket/network APIs,
`subprocess`, `os.kill`, process inspection, Keychain/credential loaders,
runtime adapters, runtime manager, discovery proposal, plan construction, or
evidence execution.

At minimum, before claiming completion:

- run every new focused test;
- run `PYTHONPATH=src python3 -m unittest discover -s tests -v` and report the
  fresh test count and failures;
- run these six retained non-live dry-config commands:
  - `./bin/lmre-discover dry-config`
  - `./bin/lmre-approach3 dry-config config/approach3/gemma-freeform-native-triple-v1.json`
  - `./bin/lmre-matrix --dry-config --campaign config/matrix/gemma-4-12b-qat-campaign.json`
  - `./bin/lmre-preference collect --dry-config`
  - `./bin/lmre-rag collect --dry-config`
  - `./bin/lmre-overhead run --dry-config`
- run the real doctor only against static local state, once in JSON and once
  in text mode, without executing any suggested remediation;
- confirm its results do not claim live readiness;
- run `git diff --check` and inspect `git status --short`;
- inspect imports and call paths to confirm no live subsystem is reachable;
- confirm no runtime, listener, process, provider, credential, policy,
  evidence bundle, model weight, vault note, archive file, or external system
  was contacted or changed;
- update `README.md`, `docs/status.md`, `docs/architecture.md`, and add a
  concise operator guide such as `docs/doctor.md` without overstating the
  command;
- refresh/query Graphify after committed source changes using the existing
  repository hook/workflow and verify ignored/generated evidence was not
  ingested.

Do not claim success from subagent reports or focused tests alone. Read the
full verification output and exercise the actual command.

## Acceptance criteria

The pull request is ready only when:

- `lmre doctor` provides useful deterministic offline readiness information;
- default JSON and `--format text` agree on the same structured result;
- every live-only fact is explicitly `NOT_CHECKED_LIVE` or equivalent;
- missing prerequisites produce actionable, deduplicated remediation without
  mutation;
- configuration and policy checks reuse current validators;
- machine-profile and artifact checks reuse `artifact_profile.py` and current
  matrix/config resolution APIs; no second token parser, broad cache scan, or
  user-selected root override exists;
- the command performs no network, subprocess, process, Keychain, credential,
  runtime, provider, plan, or evidence action;
- no raw local evidence, credential, machine secret, or real home path is
  committed in fixtures;
- no third-party dependency or speculative framework is added;
- focused tests, the full retained suite, and all dry-config checks pass;
- current documentation accurately describes both what doctor checks and what
  it deliberately cannot know;
- total working spend remains at or below $50.00 and the $11.34 reserve is
  untouched;
- the feature branch is pushed and a non-draft PR is open but unmerged.

## Git workflow

1. Verify PR #16 and PR #17 are merged and update clean `main` from its remote
   without discarding local work. Preserve the one expected untracked handoff
   artifact named above.
2. Create `claude/lmre-doctor` from the updated `main`.
3. Keep commits coherent: design/plan/handoff, diagnostic engine/tests, CLI
   rendering/tests, documentation/verification as appropriate.
4. Fable reviews every diff before committing it.
5. Never commit `.lmre/`, `results/`, credentials, caches, generated Graphify
   outputs, machine-local reports, real model paths, or build output.
6. Push and create a non-draft pull request only after all verification passes.
7. Do not merge. Hand the PR to the user with exact evidence, limitations,
   cost accounting, and deferred work.

## Final report format

Return a compact handoff with:

1. outcome and PR link;
2. architecture chosen and why;
3. exact checks implemented and their readiness semantics;
4. user-visible JSON and text workflows;
5. files and commits created;
6. focused tests, full-suite count, dry-config results, real command exercise,
   and Graphify verification;
7. explicit confirmation of every non-live/non-mutating boundary;
8. subagent ledger: task, model, spend/estimate, result, and reuse;
9. total usage-cost ledger, uncertainty, and reserve remaining;
10. validated risks, deferred work, and the exact next action for the user.

Lead with the outcome. Do not bury failures, action-required states,
`NOT_CHECKED_LIVE` qualifications, budget uncertainty, or remaining work.

Begin now with model/cwd verification, PR #17/main baseline verification,
repository onboarding, a targeted Graphify query beginning at
`artifact_profile.py`, and the bounded two-scout planning wave. Do not perform
live checks or runtime actions.
