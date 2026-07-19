# Stage 2 Gate A Implementation Plan

**Goal:** Add a deterministic, fail-closed Stage 2A OptiQ lifecycle and route-discovery path without starting OptiQ Lab, loading a model, or issuing inference requests during Gate A.

**Boundary:** Stage 2A may validate an approved pinned runtime profile, own one API-only `optiq serve` process, perform GET-only health/model discovery on exact loopback routes, stop only the process it started, and preserve checksummed evidence. Stage 2B generation and benchmarking remain unauthorized.

## Task 1: Stage 2 manifest and policy

- Add a strict Stage 2 fixture and manifest tests.
- Add schema version `3.0.0`, `stage2-YYYYMMDD-NNN`, mode `lifecycle_probe`, exact route and limit contracts, and runtime-profile references.
- Add a Stage 2 policy that authorizes only the existing six operations for the exact lifecycle-probe class.
- Verify Stage 0 and Stage 1 behavior remains unchanged.

## Task 2: Pinned OptiQ runtime profile

- Add a strict runtime-profile schema, configuration, registry, and tests.
- Pin the canonical mlx-optiq executable/version, package versions, model snapshot, artifact hashes, exact serve arguments, provider identity, and base-model route identity.
- Reject unknown fields, mutable model references, alternate variants, and launch-argument drift.

## Task 3: Owned lifecycle and GET-only discovery

- Add protocols for host inspection, owned process control, and loopback discovery so tests can use fakes.
- Preflight must reject occupied port 8080, OptiQ Lab, an unowned OptiQ process, runtime/hash drift, provider headers, route ambiguity, and failed resource policy.
- The run must start only the fixed API-only command, record PID/PGID/command identity, issue only GET health/models calls, and stop only the matching owned process.
- Cleanup must be bounded and fail closed while preserving diagnostic evidence.

## Task 4: Lifecycle, worker, and runner integration

- Add Stage 2A lifecycle states and legal transitions without changing valid Stage 0/1 paths.
- Add a fixed `_stage2-worker` command and exact Stage 2 run-ID validation.
- Route Stage 2 operations through the new engine while keeping the six-tool surface unchanged.
- Add cancellation and partial-cleanup tests for ownership mismatch and worker failure.

## Task 5: Evidence contract

- Require runtime identity, artifact identity, process ownership, service events, endpoint inventory, memory samples, lifecycle, redacted logs, summary, and checksums.
- Record zero model-load and zero inference-request attempts.
- Validate artifact completeness and tamper detection.

## Task 6: Native plugin contract

- Keep exactly six permission-gated tools and only the `run_id` argument.
- Allow Stage 2 run IDs, update descriptions/version, and add Swift contract tests.
- Do not install the plugin during Gate A.

## Task 7: Deterministic verification and documentation

- Run the Python suite and Swift plugin suite with OptiQ Lab closed.
- Scan the code and test output for accidental POST/inference paths and credential exposure.
- Update the repository runbook and DeepWiki closeout with the Gate A result, remaining Gate B manual steps, and rollback boundary.

