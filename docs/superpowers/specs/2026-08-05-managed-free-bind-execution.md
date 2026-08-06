# Managed Free-Bind Execution and Sealing (2026-08-05)

**Status:** Implemented; authorized live acceptance blocked at the port 8100
identity boundary.
**Live authority:** An adopted binding is review intent, not inference
authority. A live run still requires an explicit current-session request and
an adopted operator policy authorizing the exact immutable plan.

## Purpose

This slice connects an explicitly adopted offline free-bind declaration to the
existing managed lifecycle, collectors, resume behavior, and sealed evidence.
It does not add a second process manager or a separate evidence format.

## Operator flow

```bash
./bin/lmre binding show gemma-curated-native-v1

./bin/lmre plan \
  --family gemma-4-12b-qat \
  --recipe config/managed-runs/complete-native-quality-v1.json \
  --binding gemma-curated-native-v1 \
  --name gemma-curated-managed-run

./bin/lmre status <run-id>
./bin/lmre run <run-id>
```

If routed models require an operator-owned Osaurus provider reconnect, the
native evidence seals as `PARTIAL_BLOCKED`. After reconnecting the existing
provider in the Osaurus UI, `lmre resume <run-id>` retries only overhead under
the original immutable plan.

## Frozen contract

1. `lmre plan` accepts either `--comparison-class <id>` or `--binding <id>`,
   never both. It does not accept an arbitrary cell list, endpoint, executable,
   server, model path, suite, pair, or artifact root.
2. Planning reloads the fixed local proposal and adoption records and verifies
   their canonical hashes, linkage, family, ordered cells, checked-in source
   hashes, fixed machine-profile hash, native-server mapping, and artifact
   readiness.
3. The complete managed recipe requires two to nine selected cells, including
   one Osaurus cell and at least one selected backend with an existing reviewed
   overhead pair. Unsupported overhead pairs are omitted rather than invented.
4. Plan schema `1.2.0` records the binding ID, revision, binding hash, proposal
   hash, ordered cells, filtered pairs, selected runtimes, endpoints, request
   count, duration, and all executable input hashes. Plan schemas `1.0.0` and
   `1.1.0` remain readable and hash-verifiable without rewriting.
5. Duration is conservatively request-scaled from the retained native baseline.
   The exact request, time, runtime, endpoint, memory-floor, reclaim, and
   single-model limits must pass the adopted operator policy before inference.
6. Execution uses only the fixed checked-in cell definitions already bound by
   the plan. It materializes an in-memory campaign in the adopted cell order;
   no repository configuration or adoption record is edited.
7. Runtime behavior remains sequential and exact: profile-approved loopback,
   one model lane, memory-floor checks, attach or fixed-command start, 60-second
   notice before exact reclaim, `SIGINT` then bounded `SIGTERM`, no force kill,
   and cleanup of harness-owned processes.
8. Preference, RAG, matrix, and supported overhead collectors reuse their
   retained implementations. Provider creation and reconnection remain
   operator-owned through the Osaurus UI.
9. The existing evidence bundle records the binding identity in the plan,
   preflight detail, and terminal summary, then preserves honest `PASS`,
   `FAIL`, `STOPPED`, or `PARTIAL_BLOCKED` states and checksum sealing.
10. The read-only results browser exposes binding identity and hashes and treats
    them as comparison dimensions. Different bindings are never silently
    comparable merely because a human supplied the same comparison ID.

## Still excluded

- cross-family or cross-size bindings;
- non-native runtime remapping;
- arbitrary or remote endpoints and commands;
- automatic provider edits or provider creation;
- model downloads, conversions, moves, or deletion;
- parallel model residency;
- heterogeneous/open-mix scheduling and comparison semantics.

## Live acceptance record

The first authorized acceptance window used binding
`gemma-osaurus-omlx-live-v1` (Osaurus JANG plus direct oMLX oQ4), 54 planned
requests, and one reviewed overhead pair. Four immutable attempts were created
and sealed as `FAIL`:

- `run-20260805-233948-4d5cf5` exposed an owned Osaurus child process that
  remained after `osaurus stop`. Exact-PID cleanup was repaired to use bounded
  `SIGINT` and policy-gated `SIGTERM`; the recorded process exited on `SIGINT`.
- `run-20260805-234409-41000e`, `run-20260805-234703-be6713`, and
  `run-20260805-235031-d2ba34` completed the Osaurus matrix lane and exact
  cleanup, then failed closed before oMLX start with
  `runtime executable lookup failed` while inspecting port 8100.

The process inspector now handles a process that demonstrably exits during
identity collection, and runtime adapters use a bounded three-observation
window for transient lookup races. Follow-up against installed oMLX `0.5.7`
also found that oMLX `0.5.4+` persists explicit non-secret serve settings. The
managed command previously supplied its temporary model catalog without an
isolated base directory, so an evidence-local catalog path could be persisted
into the user's normal oMLX settings. Managed starts now inject a fixed,
attempt-specific `--base-path` beneath `.lmre/runtime-state/`, reject recipe
overrides, and leave existing user settings untouched. No oMLX, preference,
RAG, or overhead result from this acceptance window is represented as PASS;
the repair still requires a new sealed live acceptance run before merge.

A fifth immutable attempt, `run-20260806-002938-b557ee`, attached to the
operator-owned Osaurus and oMLX applications. Both exact identities and model
inventories were compatible, and both matrix lanes completed before release.
The oMLX lease was correctly recorded `untouched`, but the retained matrix
collector then independently required port 8100 to become free and sealed the
attempt `FAIL`. Managed matrix runs now leave release verification to the
runtime manager, whose behavior is ownership-aware. The same boundary is
applied to managed overhead runs so their legacy oMLX pre-stop path cannot
bypass the managed adapter. Low-level collector port behavior remains intact.

Attempt `run-20260806-003419-0c7c3e` then passed the matrix but sealed `FAIL`
when the managed-only lifecycle flag was mistakenly forwarded to preference;
an integration-level hook test now fixes and guards that wiring. Attempt
`run-20260806-003703-52efe7` passed matrix, preference, RAG oracle, and RAG
keyword, including 9/9 successful and contract-valid oMLX matrix observations.
It correctly stopped at `BLOCKED_PROVIDER_RECONNECT` because the Osaurus oMLX
route was absent, but its final seal rejected repeated process-derived lease
IDs for repeated attachments to the same operator-owned app. That evidence is
preserved as `EXECUTED_UNSEALED`. Lease identity now adds a manager-local
acquisition sequence, so every acquire/terminal pair remains unique without
changing exact process identity. A further sealed run is still required.

Attempt `run-20260806-004836-920a93` provides the sealed acceptance for the
oMLX repair. Preflight, matrix, preference, RAG oracle, RAG keyword, cleanup,
and sealing are `PASS`; the direct oMLX matrix lane recorded 9/9 successful,
contract-valid observations. Every checksum verifies, and the attached
Osaurus and oMLX process identities remained unchanged. Attempt 1 sealed
`PARTIAL_BLOCKED` because Osaurus did not expose the routed model. After the
operator reconnected it, attempt 2 completed direct and routed overhead as
`PASS`, and the final run state is sealed `PASS`.

The initial attempt-2 seal failed because its manager-local lease sequence
reused process-derived IDs from attempt 1. Since lifecycle entries already
carry their attempt, evidence validation and browser summaries now key leases
by `(attempt, lease_id)`. The executed overhead output, complete cleanup, and
matching terminal lease records were reviewed before retrying only the seal.
The final checksum manifest verifies all attempt-1 and attempt-2 evidence.
