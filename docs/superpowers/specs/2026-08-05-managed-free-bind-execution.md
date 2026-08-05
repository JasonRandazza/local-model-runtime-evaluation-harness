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
window for transient lookup races. The failure remained after both changes,
so further live retries are paused until a deterministic trace can identify
the port 8100 listener without weakening exact identity checks. No oMLX,
preference, RAG, or overhead result from this acceptance window is represented
as PASS. Post-run listener and process inspection was clean.
