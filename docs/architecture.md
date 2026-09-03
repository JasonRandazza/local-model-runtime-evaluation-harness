# Architecture

## Workspace Boundary

Every operator-owned tree the harness reads or writes lives under one
**workspace root**: `config/`, `suites/`, `corpora/`, `results/`, and `.lmre/`.
A source checkout is itself a workspace, which is why an installed copy behaves
the same as a checkout once `lmre init` has scaffolded one.

`workspace.py` resolves the root once per process, first match winning:

1. `LMRE_WORKSPACE`, when set. Set but not a directory is a hard error --
   silently substituting another root would let a run record evidence against
   configuration the operator never chose.
2. The nearest ancestor of the current directory holding a `.lmre-workspace`
   marker or a `config/managed-runs/` tree.
3. The directory two levels above the package, which is the repository root in
   a source checkout.

Resolution is cached because these are one-shot CLIs; without that, path
constants in different modules could disagree with each other.

The third rule is load-bearing, not a convenience. A checkout resolves exactly
as it did before workspaces existed, which is what keeps plan hashes and the
recorded `input_hashes` keys byte-identical and existing sealed runs comparable
with future ones. See the plan-hash gate in `docs/release-checklist.md` before
changing anything that affects where a plan input resolves.

Configuration is never read at import time. A module-scope read would crash
every command before argument parsing wherever configuration is absent, which
is exactly an installed copy's situation; `tests/test_import_purity.py` fails
if one is reintroduced.

## Product Flow

```text
lmre init (optional, installed copy) -> workspace root
adopted policy -> immutable plan -> runtime manager -> retained collectors
               -> evidence bundle -> blocked resume or sealed report
                                  -> rubric -> ruling (names the cell to serve)
```

The ruling arm is read-only and needs no authority: it consumes a sealed bundle
and a checked-in rubric, and contacts no runtime, provider, credential store, or
model. It is a separate act from running, deliberately — a run produces
measurements, a ruling interprets them.

Planning and preflight do not silently download, copy, relocate, or remap model
weights. A family is executable only when its complete native triple passes
artifact, policy, memory, configuration, and exact runtime checks.
Run and resume also require unchanged hashes for every bound executable input,
including the fixed local machine profile, the exact adopted-policy record
captured at planning time, and exclusive
ownership of the local active-run lock.

## Active Components

| Component | Responsibility |
| --- | --- |
| `workspace.py` | Workspace-root resolution and shipped-template location; the single source every path constant derives from |
| `workspace_init.py` | `lmre init` scaffolding: copies the shipped template, creates empty result and state directories, grants nothing |
| `artifact_profile.py` | Strict logical-root resolution from the fixed ignored machine profile |
| `operator_policy.py` | Standing local authority, exact limits, adoption record |
| `run_identity.py` / `managed_run_types.py` | Immutable plan, bound input hashes, name, ID, and state contracts |
| `runtime_versions.py` | Runtime CLI version capture for provenance; shells out to each runtime, never raises |
| `comparison_class.py` | Checked-in same-family expansion declarations that preserve the native baseline |
| `comparison_class_inspect.py` | Read-only class, candidate-cell, and approved-artifact readiness inspection |
| `free_bind.py` | Immutable offline proposals, validation, and non-authorizing local adoption for ordered same-family cells |
| `open_mix.py` / `open_mix_inspect.py` | Strict checked-in heterogeneous comparison identity, shared-suite validation, and static artifact readiness |
| `runtime_adapters/` / `runtime_manager.py` | Exact attach/start/reclaim/release ownership |
| `managed_run.py` / `managed_run_cli.py` | Fixed collector order, blocking, resume, JSON CLI |
| `evidence_bundle.py` | Atomic state, lifecycle journal, attempts, checksums, sealing |
| `omlx_catalog.py` | Per-run temporary oMLX model catalog |
| `discovery_*` | Proposal identity, matching, persistence, and bounded execution |
| `approach3*` | Explicit free-form recipe validation and collection routing |
| `matrix_*` | Family/cell validation, fixed server lifecycle, measurement, reports |
| `preference_*` | Pair generation, collection, human review, local judging, tally |
| `rag_*` | Oracle/keyword retrieval, prompting, collection, fact/retrieval scoring |
| `overhead_*` | Direct-versus-routed paired measurement and delta reports |
| `transport.py` | Loopback-only OpenAI-compatible streaming transport |
| `credentials.py` | Bounded local credential retrieval without value disclosure |
| `resources.py` | Host memory and resource-floor checks |
| `measurement.py` / `token_counter.py` | Qualified timing and token evidence |
| `rubric.py` | Strict rubric loading: closed metric vocabulary, ordered floors, exactly one ordering metric |
| `cell_metrics.py` | Per-cell matrix, preference, and RAG metric extraction from a sealed bundle |
| `ruling.py` | `build_ruling`: fail-closed interpretation of one sealed run under one rubric; never raises |
| `ruling_store.py` | One ruling per file, written once and never overwritten; superseding derived at read time |
| `ruling_cli.py` | `ruling make` and `ruling list` on the managed CLI; grants no authority |
| `results_browser.py` / `results_browser_html.py` | Read-only sealed-evidence interpretation and static HTML presentation |
| `run_console.py` / `run_console_html.py` / `run_console_server.py` | Fixed-loopback presentation, exact-plan authority form, and one fixed managed-CLI child |
| `doctor.py` | Offline static-readiness diagnostics over existing validators; no live contact |

## Native-Diagonal Contract

Each family has one curated cell per capable native server:

```text
Osaurus-native quant -> Osaurus
oQ quant             -> oMLX
OptiQ quant          -> OptiQ
```

Historical cross-server cells are archived. Discovery, matrix, preference, and
RAG share the same family and cell identities so incompatible mixes fail closed.

Controlled comparison classes may append reviewed same-family native cells to
that baseline. They cannot replace or reorder baseline cells, accept arbitrary
paths, select cross-family cells, relax native-server validation, or create new
overhead routes. The complete class definition and selected cells are bound by
the managed plan's input hashes; execution still holds one model lane at a time.

Before planning, `lmre comparison-class inspect <id>` can read the checked-in
class and approved machine roots to report its baseline/expansion shape,
reviewed extra native cells, and static artifact availability. It does not scan
arbitrary model directories, create configuration, inspect services, or grant
live authority.

`lmre binding propose|show|validate|adopt` provides a separate offline path for
an operator-selected order of existing same-family native cells. Its create-only
local records bind the family, cells, and fixed machine profile by hash and
never grant live authority. `lmre plan --binding <id>` explicitly consumes a
current adopted record, revalidates its provenance and artifacts, and persists
the binding identity and hashes in plan schema `1.2.0`. Execution materializes
the selected checked-in cells in their declared order and reuses the existing
runtime manager, collectors, resume behavior, and evidence seal.

Checked-in open mixes provide a separate heterogeneous identity. Each strict
definition binds two to six ordered native cells from at least two families to
one shared suite contract. `lmre open-mix inspect <id>` validates configuration
and approved-root artifact presence without runtime contact. Plan schema
`1.3.0` binds the definition, ordered members, suite contract, member-family
campaigns, executable inputs, request ceiling, and policy dimensions while
preserving the serialized shape and hash behavior of schemas `1.0.0` through
`1.2.0`. The managed adapter materializes those members in definition order,
reuses the single-lane runtime manager and collectors, qualifies collector
evidence by family, and permits only overhead-only resume after an
operator-owned provider reconnect. Members without a reviewed overhead pair
record `N/A`; they do not trigger route discovery.

Committed family, cell, and overhead configuration uses logical
`{LMRE_ROOT:...}` and `{artifact_path}` templates. Resolution happens only at
explicit runtime boundaries through `.lmre/machine-profile.json`; unresolved
tokens never reach runtime adapters. The resolver accepts exactly the two
declared root keys, never scans caches, and never takes arbitrary roots from a
CLI or environment variable.

## Lifecycle

Managed collection uses fixed commands from checked-in cell definitions.
When a configured backend port is already occupied:

- attach only when exact inventory identity matches the requested cell;
- otherwise notify the operator for 60 seconds, revalidate exact process
  identity, and use the policy-authorized bounded reclaim path;
- never stop an attached matching process during cleanup;
- verify owned or reclaimed processes stop and ports become free;
- never use broad process-name matching or force kill;
- never edit or reconnect an Osaurus provider.

An operator may press `Ctrl+C` during the notice or run. Cleanup records
attached leases as untouched and owned/reclaimed leases as released. Processes
that predated a run are not restored afterward.

## Evidence Boundary

Managed results are written beneath ignored `results/runs/` directories. Each
bundle preserves its immutable plan and policy snapshot, environment, append
journals, per-step attempt roots, state, summary, and checksum manifest.
Reports must preserve:

- family, cell, quant, and native-server identity;
- PASS/FAIL/N/A or `EXECUTED_UNSEALED`;
- exact versus estimated token qualification;
- timing and response-contract evidence;
- retrieval and fact-hit evidence for RAG;
- cleanup and resource failures.

Missing exact Osaurus routes produce sealed `PARTIAL_BLOCKED` evidence. After
the operator reconnects the existing provider in the UI, resume verifies the
sealed attempt and runs only a new overhead attempt.

Rulings are **derived, not measured**, so they are never sealed. They are
written beneath the results tree alongside the evidence they cite, one file per
ruling, and record the run id, plan hash, plan dimensions, and the rubric's id,
revision and hash. Because the rubric is hashed into the ruling and never into
the plan or `input_hashes`, changing a rubric leaves sealed evidence untouched
and still comparable, and old evidence can be re-ruled under new criteria
without re-running any model. A later ruling supersedes an earlier one by being
a separate file; nothing rewrites or removes the earlier conclusion, which was
honest under the rubric and evidence of its moment.

A ruling names a cell and never a native server: the native diagonal runs a
different quant per server, so stack and quant vary together and the evidence
cannot support a server-level claim.

Raw outputs do not automatically become durable decisions. Canonical current
evidence is indexed in [status.md](status.md).

The sealed-results browser ([results-browser.md](results-browser.md)) is
read-only presentation over this boundary: it re-verifies sealed checksums
through `evidence_bundle` before presenting a bundle as trusted, fails closed
for unsealed, corrupt, unsupported, or unreadable bundles, and never contacts
a runtime or mutates evidence.

The functional run console ([run-console.md](run-console.md)) remains a thin
local adapter over the same evidence and managed CLI. It binds only to the
fixed loopback origin, creates no plans or policy, requires an exact plan hash
and a fresh single-use action grant, permits one console-owned child, and
treats persisted evidence as the only run truth. Cancellation targets that
exact child with `SIGINT`; console shutdown may follow with bounded `SIGTERM`
but never force kill or broad process matching.

## Source Precedence

1. Repository source, config, and tests define current executable behavior.
2. Current repository docs explain supported operation.
3. Canonical verification records support current claims.
4. Deep Wiki records preserve durable decisions and project history.
5. The sibling archive preserves retired executable and documentation history.
