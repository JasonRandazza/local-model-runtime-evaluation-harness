# Managed Local Run Foundation Design

**Status:** Approved design (Jason, 2026-07-30)

## Goal

Move LMRE from individually authorized experimental lanes toward the North Star:
a competent local operator can run bounded, evidence-based evaluations with
minimal ceremony while the harness safely manages Osaurus, oMLX, and OptiQ.

This slice adds a managed-run layer above the proven collectors. It does not
rewrite matrix, preference, RAG, or overhead measurement behavior.

## Product Decisions

- Use a standing local policy instead of requesting permission for every
  compliant run.
- Support process lifecycle management for Osaurus, oMLX, and OptiQ.
- Ask users to shut down those runtimes before managed tests.
- If an incompatible runtime is still active, notify the user, wait 60 seconds,
  revalidate process identity, and safely reclaim it when standing policy
  permits.
- Never use an unqualified broad process kill.
- Provider creation and reconnection remain user-owned through the Osaurus UI.
- If an Osaurus route required by overhead is unavailable, preserve native
  results and make overhead resumably `BLOCKED_PROVIDER_RECONNECT`.
- Replace persistent repository-local oMLX model catalogs with temporary
  per-run catalogs.
- Separate readable run names from immutable run identifiers.

## Architecture

```text
lmre run
  -> load standing operator policy
  -> discover artifacts and runtime state
  -> construct and persist immutable run plan
  -> evaluate policy before lifecycle changes
  -> prepare, attach, or reclaim runtimes
  -> invoke existing collectors
  -> clean up harness-owned processes
  -> seal evidence and resumable state
```

### Components

| Component | Responsibility |
| --- | --- |
| `operator_policy.py` | Parse, validate, and evaluate standing local authority |
| `run_identity.py` | Allocate run names, IDs, attempts, comparison lineage, and plan hashes |
| `runtime_manager.py` | Coordinate runtime adapters and ownership records |
| `runtime_adapters/base.py` | Define the typed runtime lifecycle contract |
| `runtime_adapters/osaurus.py` | Inspect, attach, reclaim, start, verify, and stop Osaurus |
| `runtime_adapters/omlx.py` | Inspect, attach, reclaim, start, verify, and stop oMLX |
| `runtime_adapters/optiq.py` | Inspect, attach, reclaim, start, verify, and stop OptiQ |
| `omlx_catalog.py` | Build and clean temporary per-run model-directory views |
| `managed_run.py` | Execute immutable plans through existing collectors |
| `evidence_bundle.py` | Persist state, events, lifecycle evidence, summaries, and checksums |
| `managed_run_cli.py` | Expose `plan`, `run`, `resume`, `status`, and `report` |

Existing collectors remain the measurement authority. The managed layer owns
planning, policy, lifecycle, sequencing, resume, and evidence sealing.

## Standing Operator Policy

The first policy schema is `1.0.0`. A representative policy is:

```json
{
  "schema_version": "1.0.0",
  "policy_id": "local-managed-v1",
  "authorization_mode": "standing_local",
  "loopback_only": true,
  "allowed_runtimes": ["osaurus", "omlx", "optiq"],
  "allow_inference": true,
  "allow_start": true,
  "allow_exact_reclaim": true,
  "reclaim_grace_seconds": 60,
  "allow_terminate_after_interrupt": true,
  "allow_force_kill": false,
  "allow_provider_edits": false,
  "max_parallel_models": 1,
  "memory_floor_percent": 20,
  "max_run_minutes": 90,
  "max_requests_per_run": 250,
  "expires_at": null
}
```

Every managed run snapshots the policy into its evidence bundle. A plan is
rejected before process or inference activity when it exceeds any policy
limit.

The repository ships a policy schema and a non-authorizing example. Cloning
the repository does not grant standing authority. An operator adopts a policy
explicitly:

```bash
lmre policy adopt --from config/operator-policies/local-managed-v1.example.json
```

Adoption validates the policy, displays its lifecycle and inference authority,
and writes a gitignored local record beneath `.lmre/` containing the policy,
its hash, and `adopted_at`. `expires_at` is either `null` for a standing policy
or an RFC 3339 UTC timestamp. Editing the example does not change an adopted
policy; the operator must adopt the revised policy again.

Standing authority covers only the explicitly permitted local actions. It does
not cover provider edits, credential creation, model downloads, plugin changes,
remote endpoints, forced process killing, or model-weight deletion.

## Runtime Lifecycle

All three runtime adapters implement:

```text
inspect
  -> absent: start pinned process
  -> compatible: attach
  -> incompatible: notify and wait 60 seconds
       -> user stopped it: start pinned process
       -> still active: revalidate and reclaim under policy
  -> verify listener and exact model identity
  -> execute work
  -> stop only harness-owned process
  -> verify process and listener cleanup
```

### Process Identity

Before a reclaim, the harness records:

- PID and parent PID;
- executable path and argument array;
- process start time;
- listener port and loopback address;
- runtime inventory and model identity;
- incompatibility reason;
- policy clause authorizing reclaim;
- notification time and grace deadline.

At the deadline the adapter inspects the process again. PID, start time,
executable, arguments, and listener ownership must still match. Any unexpected
change cancels reclaim and fails closed.

Reclaim sends a graceful interrupt first. If the exact process remains after
the bounded interrupt wait, a normal termination signal is allowed only when
`allow_terminate_after_interrupt` is true. Forced kill is not permitted in this
slice.

### User Notice

The notice names the runtime, port, observed model, required model, PID,
60-second deadline, policy, and cancellation command. Documentation asks users
to shut down all three runtimes before managed tests to minimize reclaim.

### Ownership

The harness distinguishes:

- `attached`: compatible process existed before the run and remains untouched;
- `owned`: harness started the process and stops it during cleanup;
- `reclaimed`: harness stopped an incompatible process, then started and owns
  the replacement.

The first slice does not restore a reclaimed pre-run process. The report states
what was replaced.

## Temporary oMLX Catalogs

Persistent `config/matrix/omlx-roots` catalogs are retired to the sibling
archive. They are small symbolic-link collections rather than copied weights,
but they encode obsolete cross-server topology and machine-specific paths.

For an oMLX step, `omlx_catalog.py` creates a private directory beneath the
run's working area. It links only the artifacts authorized by the immutable
plan and passes that directory to oMLX. Cleanup removes the catalog links but
never deletes their model targets.

Model-weight cleanup remains a separate storage operation requiring an
explicit inventory and deletion decision.

## Run Identity

Each run records:

| Field | Meaning |
| --- | --- |
| `run_name` | Readable user- or agent-selected name |
| `run_id` | Immutable collision-safe identifier |
| `attempt` | Monotonic attempt number for resume or retry |
| `comparison_id` | Stable group for comparable runs |
| `parent_run_id` | Lineage pointer for derived runs |
| `plan_hash` | Hash of the immutable executable plan |

An example run ID is `run-20260730-173812-a1b2c3`. A generated name derives
from family, recipe, and purpose, such as
`qwen-native-quality-baseline`. Names are sanitized, never overwrite an
existing run, and never grant authority.

## Managed Execution

The complete native-quality recipe orders:

```text
preflight
-> native screen or finalist matrix
-> preference
-> RAG oracle
-> RAG keyword
-> routed overhead
-> seal
```

Other recipes may select a bounded subset. Execution cannot add steps after
the plan hash is persisted.

The managed coordinator invokes the existing collector interfaces. It does not
duplicate measurement, scoring, or reporting implementations.

## Evidence Bundle

Each managed run writes:

```text
results/runs/<run-id>/
├── plan.json
├── policy-snapshot.json
├── environment.json
├── state.json
├── events.jsonl
├── lifecycle.jsonl
├── steps/
│   ├── matrix/
│   ├── preference/
│   ├── rag-oracle/
│   ├── rag-keyword/
│   └── overhead/
├── summary.json
├── report.md
└── checksums.sha256
```

Step states are:

- `PENDING`
- `RUNNING`
- `PASS`
- `FAIL`
- `BLOCKED_PROVIDER_RECONNECT`
- `STOPPED`
- `INCOMPARABLE`

Run summaries may additionally use `PARTIAL_BLOCKED` when all completed native
evidence is valid but a required routed step is blocked.

Raw model responses remain local and gitignored. Reports retain qualified
metrics, hashes, exact runtime versions and arguments, lifecycle ownership,
policy decisions, failures, and cleanup results. Secrets are excluded from
every persisted artifact.

Checksums are written only after owned-process cleanup completes or attached
processes are explicitly recorded as untouched.

## Provider-Reconnect Resume

Starting Osaurus does not prove its oMLX or OptiQ provider route is connected.
Before routed overhead, the coordinator validates the exact routed model ID.

If it is absent:

1. Seal completed native steps.
2. Set overhead to `BLOCKED_PROVIDER_RECONNECT`.
3. Set the run summary to `PARTIAL_BLOCKED`.
4. Record the exact missing routed ID and operator UI instruction.
5. Exit without discarding completed evidence.

After the operator reconnects the provider:

```bash
lmre resume <run-id>
```

Resume verifies the prior checksums, plan hash, policy, current process
identity, and exact route. It creates the next attempt record and executes only
the blocked overhead step. Prior evidence is never overwritten.

## Failure Handling

The run fails before inference when:

- the local adopted policy is missing, invalid, past a non-null `expires_at`,
  or exceeded;
- an executable or process cannot be identified exactly;
- a required listener is not loopback-only;
- process identity changes during the reclaim grace period;
- available memory is below the policy floor;
- a required model artifact or inventory ID is absent;
- resume evidence fails checksum or plan-hash validation.

During execution:

- a collector failure stops dependent later steps and preserves completed
  evidence;
- `Ctrl+C` records `STOPPED`, cleans up owned processes, and seals the partial
  bundle;
- cleanup failure prevents a `PASS`;
- attached compatible processes remain untouched;
- secrets never enter errors, logs, plans, or reports.

## Validation Strategy

1. Pure unit tests for policy, identity, plan hashing, state transitions, and
   evidence persistence.
2. Fake-process tests for notification, 60-second grace timing, PID
   revalidation, interrupt, termination, and cleanup.
3. Fake-runtime integration tests for all three adapters.
4. Fake provider-route tests for `BLOCKED_PROVIDER_RECONNECT` and resume.
5. The complete retained active-product suite as regression coverage.
6. One separately reviewed local acceptance run after non-live validation.

After the standing policy is deliberately adopted, subsequent compliant runs
do not require individual permission prompts.

## Out of Scope

- Provider creation or editing
- Credential creation
- Model downloading or deletion
- Forced process killing
- Scheduled or recurring runs
- Remote endpoints
- Plugin changes
- GUI work
- Heterogeneous cross-family comparisons
- Restoration of a reclaimed pre-run process

## Delivery Sequence

1. Policy and immutable run identity.
2. Evidence bundle and state transitions.
3. Typed runtime adapters and ownership ledger.
4. Temporary oMLX catalogs and retirement of persistent catalogs.
5. Managed run planning and execution.
6. Provider-blocked resume.
7. CLI, documentation, and non-live regression validation.
8. Separately reviewed local acceptance and standing-policy adoption.
