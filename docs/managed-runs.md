# Managed Local Runs

`lmre` is the normal operator path for a complete, evidence-producing local
evaluation. It applies one deliberately adopted policy to an immutable plan,
runs the retained collectors in a fixed order, and seals the resulting
evidence.

## Safe Operator Sequence

Start from an idle machine when practical:

```bash
osaurus stop
omlx stop
# Stop any foreground `optiq serve` with Ctrl+C.
```

Create the fixed local artifact-root profile once if it is not already
present:

```bash
mkdir -p .lmre
cp config/machine-profile.example.json .lmre/machine-profile.json
```

Edit `.lmre/machine-profile.json` so `local_models` and `huggingface_hub`
contain absolute paths to existing directories on this machine. The profile is
gitignored and has no CLI override. LMRE does not download, discover, copy, or
move weights while resolving it.

Adopt the reviewed standing-local policy once:

```bash
./bin/lmre policy adopt \
  --from config/operator-policies/local-managed-v1.example.json
```

The `policy adopt` command is the explicit adoption action. It writes a
gitignored `.lmre/operator-policy.json` record containing the exact policy,
its hash, and its adoption time. Review a replacement policy before adopting
it; adoption atomically replaces the prior local record.

Plan, inspect, and execute:

```bash
./bin/lmre plan \
  --family gemma-4-12b-qat \
  --recipe config/managed-runs/complete-native-quality-v1.json \
  --name gemma-managed-baseline
./bin/lmre status <run-id>
./bin/lmre run <run-id>
```

The plan is non-live but writes an immutable run bundle under
`results/runs/<run-id>/`. Execution runs preflight, matrix, preference, RAG
oracle, RAG keyword, routing overhead, cleanup, and seal in that order.
The plan binds SHA-256 hashes for its recipe, campaign, selected cells, suites,
pair definitions, family mappings, RAG corpus, and the exact bytes of the fixed
`.lmre/machine-profile.json`. If any bound input or root mapping changes, create
a new plan; execution and resume reject the stale plan before inference.
Existing sealed plans that predate the profile hash remain readable, while a
new run still requires the current local profile to resolve artifacts.

### Controlled comparison classes

An optional checked-in comparison class can append reviewed native cells while
preserving the family's native triple:

```bash
./bin/lmre plan \
  --family gemma-4-12b-qat \
  --recipe config/managed-runs/complete-native-quality-v1.json \
  --comparison-class gemma-native-baseline-v1 \
  --name gemma-declared-native-baseline
```

The CLI accepts a class ID only. Definitions are loaded from
`config/comparison-classes/`; there is no arbitrary cell, path, endpoint,
suite, or pair override. Every class preserves the three baseline cells in
order, permits only same-family cells on their declared native server, and
keeps overhead on the existing baseline pairs. Plan schema `1.1.0` binds the
class and selected cells by hash. Legacy `1.0.0` plans remain readable without
changing their original serialized shape or hash.

The checked-in `gemma-native-baseline-v1` class intentionally has no extra
cells. It validates the product boundary without claiming that an additional
artifact is installed or comparable. See the
[controlled-expansion contract](superpowers/specs/2026-08-05-controlled-expansion-comparison-class.md).

Only one managed `run` or `resume` may hold `.lmre/active-run.lock` at a time.
If a host crash leaves that file behind, first verify that its recorded PID is
no longer active before removing the stale lock.

If the native steps pass but Osaurus does not expose every exact routed model,
the run seals as `PARTIAL_BLOCKED`. Reconnect the existing provider in the
Osaurus UI; the harness does not edit providers. Then resume:

```bash
./bin/lmre resume <run-id>
./bin/lmre report <run-id>
```

Resume verifies the original checksums, plan hash, policy hash, terminal state,
and exact routed IDs before creating only
`steps/overhead/attempt-002/`. It never repeats or overwrites the completed
native evidence.

The route check starts or attaches the planned Osaurus runtime and holds that
lease through overhead. Cleanup uses the fixed `osaurus stop` command only for
a harness-owned or reclaimed Osaurus lease; a matching attached Osaurus
process remains untouched.

## Runtime Ownership

A managed lease has one of three ownership states:

- `attached`: an already-running process exactly matches the required runtime,
  command identity, listener, and model inventory. Cleanup records it as
  untouched.
- `owned`: the required port was free and the harness started the fixed,
  configured process. Cleanup stops that exact process.
- `reclaimed`: an incompatible process occupied the required port, survived
  the notice period, and was stopped by exact verified identity before the
  harness started its replacement. Cleanup stops the replacement.

For an incompatible process, LMRE identifies the PID, observed models, required
model, and policy, then gives the operator 60 seconds to shut it down or press
`Ctrl+C`. After the grace period it revalidates the full process identity.
Only then may policy-authorized reclaim send `SIGINT`, followed by bounded
`SIGTERM` if needed. It never uses `SIGKILL`, broad process-name matching, or
arbitrary shell commands.

Pressing `Ctrl+C` records a terminal `STOPPED` state and still attempts exact
cleanup and evidence sealing. LMRE does not restore processes that were running
before a run; the documented safe posture is to stop them before starting.

## oMLX Catalogs and Credentials

oMLX receives a per-run temporary catalog containing only the planned model.
The catalog lives beneath the ignored run evidence, and is removed when the
owned oMLX lease is released. The credential is injected in memory and redacted
from lifecycle evidence. Persistent model-root catalogs are not part of the
active workflow.

Credentials stay in approved local stores. They must not be copied into policy,
plan, configuration, logs, reports, or prompts.

## Evidence States

- `PENDING`: planned but not started.
- `RUNNING`: at least one step is active.
- `PASS`: all requested work and cleanup completed, and the bundle sealed.
- `FAIL`: execution or validation failed; cleanup succeeded and evidence
  sealed unless cleanup itself failed.
- `STOPPED`: operator interruption was recorded and cleanup completed.
- `PARTIAL_BLOCKED`: native evidence is valid, but routing overhead awaits an
  operator-owned provider reconnect.

`report` verifies the sealed checksum manifest before returning the summary.
A cleanup failure prevents both `PASS` and sealing.

## Separate Storage Decisions

Managed runs never delete model caches or external weights. Removing a
repository catalog link is not the same as deleting its target. Any future
model-cache cleanup is a separate storage task requiring exact path,
process-use, symlink, and recoverability checks plus explicit authorization.
