# Current Status

## Product Direction

LMRE has a live-accepted managed-run foundation: standing local policy,
immutable plans, exact runtime ownership, retained collector orchestration,
checksummed evidence, and overhead-only resume after an operator-owned
provider reconnect. A read-only sealed-results browser (`lmre browse`)
renders that evidence as static local HTML; it grants no run, lifecycle,
provider, or credential authority.

A functional fixed-loopback run console (`lmre ui`) now presents existing
immutable plans, exact evidence state, and runtime ownership. Starting the
console grants no live authority; start or resume requires the complete plan
hash, explicit acknowledgement, and a fresh single-use action grant. The UI
delegates execution to the existing managed CLI and does not create policy,
plans, providers, endpoints, or commands.

The harness is now genuinely installable. `pip install` provides all seven
console scripts, `lmre init` scaffolds a workspace from configuration shipped
inside the wheel, and paths resolve from a workspace root rather than a fixed
repository checkout. A source checkout resolves exactly as before, which keeps
plan hashes and recorded input paths byte-identical and existing sealed runs
comparable with future ones. Installing grants no authority to run inference.

The harness now draws the conclusion its evidence supports. A **rubric** is
checked-in configuration naming the quality floors a cell must clear and the
single metric that orders whatever clears them; a **ruling** is the conclusion
drawn from one sealed run under one rubric, naming the cell to serve.
`lmre-managed ruling make` produces one and `ruling list` indexes what has been
concluded. Producing a ruling contacts no runtime, provider, credential store,
or model and requires no adopted policy: interpreting evidence is not an act of
running anything. A ruling names a cell and never a native server, because the
diagonal runs a different quant per server and the evidence cannot support a
server-level claim.

Rulings are derived, so they are never sealed. The rubric is hashed into the
ruling but never into the plan or `input_hashes`, which is what lets a change
of criteria re-rule old evidence instead of invalidating it. A later ruling
supersedes an earlier one by being a separate file; the earlier ruling is never
edited or removed.

Committed model configuration is now machine-portable. A strict, gitignored
`.lmre/machine-profile.json` supplies the two approved local artifact roots;
new managed plans checksum that profile so changed mappings fail before
inference. An offline `lmre doctor` command reports static local readiness
(profile, configuration, resolved artifacts, adopted policy) and labels
every runtime, provider, credential, memory, and inference fact
`NOT_CHECKED_LIVE`; it grants no live authority.

## Runtime Pins and Provenance (Non-Live Verified, 2026-09-03)

Four slices landed. 757 tests pass with no skips; all six `dry-config`
commands exit 0. Package version is still `0.4.0` and the work sits in
`Unreleased`.

**Volatile upstream defaults are pinned (ADR-0007).** Osaurus, oMLX and
mlx-optiq all shipped updates. No adapter rewrite was needed -- every
hardcoded flag still exists -- but three upstream *defaults* had begun to
decide what the harness measures. OptiQ's `--max-context auto` engages a
memory-safe KV cap only when the model's native context would not fit RAM,
making the same cell machine-dependent; oMLX's tiered `--memory-guard`,
concurrency default of 8, and on-by-default paged SSD cache each move TTFT
and throughput. They are pinned to `--max-context 8192`,
`--max-concurrent-requests 1`, `--memory-guard off` and `--no-cache`.

This changed the cell configs, so plans built before the pins read
`INCOMPARABLE` against plans built after. That is correct: the measurement
genuinely changed. Sealed evidence is untouched.

**Runtime versions are captured as provenance.** `runtime_versions.py` records
which build a result was produced against -- previously impossible, because
`osaurus version` prints `dev` and older `omlx --version` crashed. Osaurus is
read from `doctor --json --redact`, preferring the running bundle and recording
how many were installed, so a duplicate install cannot make the provenance
confidently wrong. The value is **written, never read** by ruling, rubric,
comparison or discovery code, and never enters `input_hashes` or the plan. It
is provenance, not the rejected runtime-version regression axis.

**Rulings render in the browser.** `lmre browse` now writes `rulings/index.html`
and one page per ruling, showing the named cell, rubric identity and hash, the
floors and which cells cleared them, and -- for `UNAVAILABLE` or
no-cell-qualifies outcomes -- the code and reason stated plainly. Superseded
rulings are marked, never hidden. `list_rulings` now shares `save_ruling`'s
bare-file-name guard, so a ruling whose file contents claim an id like
`../../evil` can no longer drive a write outside the output tree.

**A pinned linter exists.** `ruff==0.16.5`, rule set E/F/W/I/UP/B, line-length
79. The CI step is deliberately **advisory**: the tree carries 1444 existing
violations (87% `E501`, 186 auto-fixable), so a blocking gate would have red-lit
the build on day one. Clearing that backlog and making the gate blocking is
tracked as the next mechanical slice.

## Rulings (Non-Live Verified, 2026-08-22)

Closed issue #36 via PR #38; documentation in PR #39.

- `rubric.py` loads and validates a rubric: identity, an ordered list of
  `{metric, comparator, value}` floors, and exactly one `{metric, direction}`
  ordering. Metric names come from a closed vocabulary; an unknown name, a
  missing or duplicated ordering, or an id disagreeing with the file name is a
  load error.
- `cell_metrics.py` extracts per-cell metrics from a sealed bundle for matrix,
  preference and RAG. Preference and RAG were previously computed and written
  but never read back out through any metric layer.
- `ruling.py` provides `build_ruling`, which **never raises**: an unsealed,
  corrupt or incomplete run, or a rubric naming a metric the run cannot supply,
  each yields an `UNAVAILABLE` outcome carrying a code and a reason. When no
  cell clears every floor the outcome says so rather than naming the least-bad
  candidate.
- `ruling_store.py` writes one ruling per file, atomically, and never
  overwrites; superseding is derived when the directory is read, so the earlier
  file is untouched. Rulings live under the results tree, not version control.
- `ruling_cli.py` adds `ruling make` and `ruling list` to the managed CLI,
  emitting JSON on stdout like every other managed command.

Metric names now carry the step that produced them: `rag.fact_hit_rate` became
`rag_oracle.fact_hit_rate` and `rag_keyword.fact_hit_rate`, and retrieval
recall and precision are keyword-only, because two steps produce RAG scores and
an unprefixed name could not say which one a floor gated on. No sealed evidence
changes meaning.

Verified non-live: 706 tests pass with no skips, all six `dry-config` commands
exit 0, and CI is green on 3.11 and 3.13. The plan-hash gate is unaffected —
nothing under `config/`, no workspace resolution and no plan types were touched,
so `input_hashes` keys cannot have moved. Every non-trivial protection was
proven to bind by disabling it and confirming the corresponding test fails.

Aggregating repeat runs, and rendering rulings in the browser or run console,
are deliberately out of scope.

## Release 0.4.0 (Non-Live Verified, 2026-08-07)

First tagged release: `v0.4.0`, MIT licensed, with wheel and sdist attached.
Verification record: `docs/releases/0.4.0-verification.md`.

- Installability was measured, not assumed. The published wheel was downloaded
  from the release, installed into a clean virtualenv, and driven through the
  documented first-run path from outside any checkout: all seven console
  scripts run, `lmre init` scaffolds a workspace, and `lmre doctor` reports
  `harness.entry_points` and the recipe check `OFFLINE_READY`. The sdist was
  verified the same way.
- Five defects found and fixed that were not in any task description: the
  comparisons page crashed entirely on a state read that failed after
  classification; the run console index could be taken down by one racing
  bundle; every CLI crashed before argument parsing when configuration was
  absent; `lmre doctor` demanded checkout-only files from installed operators;
  and the README documented an install command that could not work.
- CI exists and is meaningful. Its first run failed and caught that the test
  suite only ran where the package had been installed editable by hand, so a
  fresh checkout could not run it at all.
- **Evidence compatibility holds.** Plan hashes and recorded `input_hashes`
  keys are unchanged, so `run-20260806-194307-801b42` stays comparable with
  future runs and existing sealed bundles still verify. Gated on a reproducible
  plan-hash oracle over the managed and open-mix planning paths, checked on
  every commit of the packaging work.
- Verification: 626 retained tests pass on Python 3.11 and 3.13; all six
  retained dry-config commands pass. No runtime, provider, credential store, or
  model was contacted; no managed run was started; no policy was adopted.
## Earlier cycles

Dated entries for cycles before 0.4.0 -- live acceptance on 2026-07-31, the
free-bind and open-mix work through 2026-08-05, and the run-console and
Qwen/open-mix cycles on 2026-08-06 -- moved to
[status-archive.md](status-archive.md) on 2026-08-22. The evidence they cite is
still summarised in Accepted Current Evidence below.

## Accepted Current Evidence

| Area | Status | Evidence |
| --- | --- | --- |
| Managed local-run foundation | Sealed live acceptance `PASS` | `results/runs/run-20260731-051843-04302b` (local, gitignored) |
| Native triple and routing overhead | Closed for the accepted window | `superpowers/verification/2026-07-23-native-triple-overhead-live-evidence.md` |
| Multi-family preference and RAG | Closed for the accepted window | `superpowers/verification/2026-07-24-multi-family-quality-live-evidence.md` |
| Personal selection policy | Operator decision | `superpowers/verification/2026-07-24-personal-selection-policy.md` |
| Discovery Gemma execution | Sealed PASS | `superpowers/verification/2026-07-24-discovery-20260725-004-pass.md` |
| Managed OptiQ free-binding overhead | Sealed live acceptance `PASS` | `results/runs/run-20260806-012734-936521` (local, gitignored) |
| Approach 3 Gemma collections | `REVIEWED_UNSEALED` | Historical collector directories reviewed; negative seal decision recorded, no product PASS claimed |

## Active Workflows

- managed `init` / `policy` / `plan` / `run` / `resume` / `status` / `report` /
  `browse` / `ui` / `ruling`
- Discovery proposal/show/execute
- Approach 3 explicit recipes
- native matrix
- pairwise preference
- oracle and keyword RAG
- direct-versus-Osaurus overhead
- read-only sealed-results browser with sealed cross-run comparison
  ([results-browser.md](results-browser.md))
- rulings over sealed evidence under a checked-in rubric
  ([ADR-0004](adr/0004-rulings-name-cells-not-servers.md),
  [ADR-0005](adr/0005-constraint-then-order.md),
  [ADR-0006](adr/0006-rubric-stays-out-of-the-plan-hash.md))
- offline readiness doctor ([doctor.md](doctor.md))
- checked-in controlled comparison classes bound into immutable managed plans
  ([controlled-expansion contract](superpowers/specs/2026-08-05-controlled-expansion-comparison-class.md))
- offline comparison-class readiness inspection
  ([inspection contract](superpowers/specs/2026-08-05-comparison-class-offline-inspection.md))
- offline managed free-bind declaration, validation, and non-authorizing
  adoption
  ([free-bind contract](superpowers/specs/2026-08-05-managed-free-bind-declarations.md))
- managed free-bind planning, execution, resume, and sealing
  ([execution contract](superpowers/specs/2026-08-05-managed-free-bind-execution.md))
- heterogeneous open-mix inspection, immutable planning, sequential managed
  execution, overhead-only resume, and sealing
  ([open-mix contract](superpowers/specs/2026-08-05-heterogeneous-open-mix-contract.md))

## Open Risks

- Not published to a package index. The README documents installing from the
  repository git URL, which is verified; `pip install
  local-model-runtime-evaluation-harness` will not resolve until the project is
  uploaded.
- No pinned linter configuration, so CI runs no linter. The files changed for 0.4.0
  carry 23 pre-existing findings under ruff defaults; later cycles, including
  rulings, have not been measured against a pinned config at all. The "new
  modules clean" convention remains manual and undocumented.
- 0.4.0 has no live acceptance run of its own. It is verified non-live, and the
  most recent sealed live evidence predates it. That is sound because plan
  hashes are unchanged, but a live run under the installed path has not been
  exercised.
- There is no earlier working release to roll back to. An installed copy of
  pre-0.4.0 code could not start, so rollback means checking out an earlier
  commit and using the `./bin/` wrappers.
- The original three-cell managed acceptance still preserves its honest OptiQ
  overhead `N/A`; the missing path is superseded by the separate sealed OptiQ
  binding run rather than by rewriting that bundle.
- Historical Approach 3 collector output remains permanently unsealed by
  review decision; use the managed binding path for future sealable evidence.
- Backend attach/reclaim behavior is powerful and requires an adopted policy
  authorizing the exact plan.
- Resolved artifacts remain machine-local and may be missing even when the
  portable committed templates and machine profile are structurally valid.
- The results browser now includes read-only sealed cross-run comparison
  pages for sealed verified members only. `COMPARABLE` groups additionally
  expose recorded matrix and direct-versus-Osaurus summary values from exact,
  checksummed plan rows. Missing or malformed metric payloads fail closed as
  `UNAVAILABLE`; no winner, ranking, delta, confidence value, or new score is
  derived. A state read that fails after classification keeps the member
  visible with `UNAVAILABLE` metrics instead of failing the build.
  Verification at review: 566 retained tests passed (environment-dependent
  transport tests skip while a local Osaurus holds its port), and all six
  retained dry-config commands passed.
- No external plugin lifecycle is managed by this repository cleanup.
- The controlled-expansion mechanism is shipped, but the only checked-in
  class currently declares the existing Gemma native baseline. No additional
  model build is claimed available or validated yet.
- Managed free-bind execution remains same-family and native-server-only.
  Heterogeneous open-mix scheduling and collection now have sealed live
  acceptance; additional definitions and future runs remain behind the exact
  adopted-plan policy gate.

## Machine State

This file does not claim current runtime availability. Check actual loopback
services and artifacts only during a separately authorized local run.
