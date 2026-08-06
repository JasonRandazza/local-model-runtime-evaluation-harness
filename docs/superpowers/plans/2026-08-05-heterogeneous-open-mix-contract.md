# Heterogeneous Open-Mix Contract Implementation Plan (2026-08-05)

**Status:** Managed execution adapter implemented and offline-verified; live
acceptance pending.
**Scope:** Contract, immutable identity, sequential execution adapter, resume,
evidence, and documentation. No runtime contact, credentials, provider changes,
process actions, model loading, or real evidence creation occurred during the
adapter implementation.

## Objective

Add a fail-closed heterogeneous comparison-set identity without weakening or
rewriting the existing native baseline, comparison-class, or same-family
binding paths.

## Slice sequence

### 1. Strict open-mix definitions and inspection — complete

- Add `config/open-mixes/` and a strict loader for the frozen definition shape.
- Validate safe IDs, regular-file containment, two-to-six ordered unique
  members, exact family/cell ownership, native-server mapping, approved
  artifact resolution, and conservative duration.
- Add `lmre open-mix inspect <id>` as a read-only command.
- Tripwire the command against transport, process, credential, subprocess,
  runtime-adapter, provider, and inference imports or calls.

### 2. Shared suite contract — complete

- Add one checked-in suite-contract schema that binds exact preference, RAG,
  matrix, response, and generation inputs shared by every member.
- Reject per-family substitutions and unsupported members before plan creation.
- Keep overhead pairs member-local and optional; unsupported pairs remain
  explicit `N/A`.

### 3. Backward-compatible managed plan identity — complete

- Add a new plan schema version with `comparison_scope`, open-mix identity,
  ordered member identities, suite-contract identity, and all executable input
  hashes.
- Make `lmre plan --open-mix <id>` mutually exclusive with `--family`,
  `--comparison-class`, and `--binding`.
- Preserve byte-for-byte loading and hash verification for schemas `1.0.0`
  through `1.2.0`.
- Calculate request and duration ceilings conservatively across all members and
  route the exact immutable plan through the existing policy evaluator.

### 4. Managed execution adapter — complete, offline-verified

- Materialize per-member campaigns in definition order without editing
  checked-in configuration.
- Reuse the existing runtime manager, resource checks, collectors, resume
  behavior, provider-reconnect boundary, cleanup, journals, and evidence seal.
- Keep one configured member lane at a time. Never add a second process manager
  or evidence format.
- Record per-member family/cell/quant/server identity on every collector output.

### 5. Honest browser comparison — identity complete

- Expose open-mix and suite-contract identity in index and run views.
- Group only sealed-verified runs with identical ordered members and executable
  dimensions.
- Present matrix and overhead metrics as qualified member-local observations;
  do not derive cross-family performance rankings or composite winners.
- Fail closed on degraded, malformed, stale-schema, or dimension-mismatched
  evidence without leaking unverified plan details.

### 6. Verification and documentation — complete

- Add loader, CLI, tripwire, plan identity, backward-compatibility, policy,
  execution-hook, evidence, resume, and browser tests using temporary fixtures.
- Run the full retained Python suite and all six existing dry-config commands.
- Add a seventh open-mix inspection/plan dry check only if it remains entirely
  offline and uses approved local configuration.
- Run `git diff --check`, verify Graphify refresh, and reconcile `README.md`,
  architecture, managed-run, browser, status, and durable Deep Wiki status.

Verification completed with 546 retained tests, all six established dry-config
commands, and the checked-in open-mix inspection. The inspection reported both
artifacts present and `NOT_CHECKED_LIVE`; no real service or model was
contacted.

## Review gates

1. Approve the comparison semantics before implementation: capability evidence,
   member-local performance metrics, and no automatic overall winner.
2. Approve the schema and CLI boundary before adding code.
3. Review the managed adapter and offline tests before any live proposal.
4. Require a separate explicit authorization and adopted exact-plan policy for
   live acceptance; do not infer it from implementation or prior runs.

## Manual preparation

None for offline implementation verification. Osaurus, oMLX, and OptiQ may
remain shut down. Before live acceptance, the operator must confirm the
checked-in member artifacts and reconnect only the exact required Osaurus
providers through the UI. The harness will report a missing supported route as
`PARTIAL_BLOCKED` and preserve already completed native evidence.
