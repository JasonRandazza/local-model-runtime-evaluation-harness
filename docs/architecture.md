# Architecture

## Product Flow

```text
adopted policy -> immutable plan -> runtime manager -> retained collectors
               -> evidence bundle -> blocked resume or sealed report
```

Planning and preflight do not silently download, copy, relocate, or remap model
weights. A family is executable only when its complete native triple passes
artifact, policy, memory, configuration, and exact runtime checks.
Run and resume also require unchanged hashes for every bound executable input,
the exact adopted-policy record captured at planning time, and exclusive
ownership of the local active-run lock.

## Active Components

| Component | Responsibility |
| --- | --- |
| `operator_policy.py` | Standing local authority, exact limits, adoption record |
| `run_identity.py` / `managed_run_types.py` | Immutable plan, bound input hashes, name, ID, and state contracts |
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
| `results_browser.py` / `results_browser_html.py` | Read-only sealed-evidence interpretation and static HTML presentation |

## Native-Diagonal Contract

Each family has one curated cell per capable native server:

```text
Osaurus-native quant -> Osaurus
oQ quant             -> oMLX
OptiQ quant          -> OptiQ
```

Historical cross-server cells are archived. Discovery, matrix, preference, and
RAG share the same family and cell identities so incompatible mixes fail closed.

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

Raw outputs do not automatically become durable decisions. Canonical current
evidence is indexed in [status.md](status.md).

The sealed-results browser ([results-browser.md](results-browser.md)) is
read-only presentation over this boundary: it re-verifies sealed checksums
through `evidence_bundle` before presenting a bundle as trusted, fails closed
for unsealed, corrupt, unsupported, or unreadable bundles, and never contacts
a runtime or mutates evidence.

## Source Precedence

1. Repository source, config, and tests define current executable behavior.
2. Current repository docs explain supported operation.
3. Canonical verification records support current claims.
4. Deep Wiki records preserve durable decisions and project history.
5. The sibling archive preserves retired executable and documentation history.
