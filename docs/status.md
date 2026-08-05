# Current Status

## Product Direction

LMRE has a live-accepted managed-run foundation: standing local policy,
immutable plans, exact runtime ownership, retained collector orchestration,
checksummed evidence, and overhead-only resume after an operator-owned
provider reconnect. A read-only sealed-results browser (`lmre browse`)
renders that evidence as static local HTML; it grants no run, lifecycle,
provider, or credential authority.

Committed model configuration is now machine-portable. A strict, gitignored
`.lmre/machine-profile.json` supplies the two approved local artifact roots;
new managed plans checksum that profile so changed mappings fail before
inference. An offline `lmre doctor` command reports static local readiness
(profile, configuration, resolved artifacts, adopted policy) and labels
every runtime, provider, credential, memory, and inference fact
`NOT_CHECKED_LIVE`; it grants no live authority.

## Controlled Expansion Contract (Non-Live, 2026-08-05)

- `lmre plan --comparison-class <id>` binds a checked-in same-family class
  while preserving the ordered native baseline and baseline overhead pairs.
- Comparison-class plan schema `1.1.0` records the class and baseline identity;
  those fields remain in current schema `1.2.0`, while legacy `1.0.0` plans
  remain readable and hash-verifiable without rewriting.
- Expansion cells must be checked-in native-server cells. Arbitrary paths,
  cross-family mixes, custom endpoints, and automatic route generation remain
  refused.
- Class duration must meet a conservative request-count-scaled minimum and
  still pass the adopted policy's exact time and request ceilings.
- Verification: 488 retained tests passed with one environment skip; all six
  dry-config commands and a non-live class-bound managed plan passed. No live
  runtime, provider, credential, or model was contacted.

## Comparison-Class Inspection (Non-Live, 2026-08-05)

- `lmre comparison-class inspect <id>` reports class shape, selected cells,
  reviewed native candidate cells, and approved-root artifact availability.
- Candidate discovery is configuration-backed only; the command does not scan
  arbitrary model directories or guess family identity from names.
- The current `gemma-native-baseline-v1` inspection reports all three baseline
  artifacts present, no reviewed candidate cells, `BASELINE_ONLY`, and
  `NOT_CHECKED_LIVE`.
- The command writes nothing and grants no plan, policy, lifecycle, provider,
  credential, or inference authority.
- Verification: 495 retained tests passed with one environment skip, all six
  dry-config commands passed, and the real checked-in Gemma class inspection
  returned the truthful baseline-only result without live contact.

## Managed Free-Bind Declarations (Non-Live, 2026-08-05)

- `lmre binding propose|show|validate|adopt` creates and reviews immutable
  local declarations for an ordered selection of checked-in same-family cells.
- Bindings accept safe IDs only, require each quant's declared native server,
  and bind the family, selected cells, and fixed machine profile by SHA-256.
- Missing artifacts produce `ACTION_REQUIRED`, changed inputs produce
  `STALE_INPUTS`, and only a current `READY_FOR_ADOPTION` proposal can be
  explicitly adopted.
- Proposal and adoption records are create-only, gitignored, and explicitly
  carry `live_authority: false` and `NOT_CHECKED_LIVE`.
- Verification: 512 retained non-live tests passed, all six dry-config
  commands passed, and focused tripwires confirmed that the binding module
  imports no live runtime, transport, process, resource, or credential code.

## Managed Free-Bind Execution and Sealing (2026-08-05)

- `lmre plan --binding <id>` revalidates one explicitly adopted declaration
  and binds its ordered cells, provenance hashes, supported overhead pairs,
  selected runtimes, endpoints, request count, and duration into an immutable
  plan.
- Plan schema `1.2.0` adds binding identity while retaining read compatibility
  for sealed `1.0.0` and comparison-class `1.1.0` plans.
- Execution reuses the accepted one-lane runtime manager, retained collectors,
  provider-reconnect resume, exact cleanup, and checksummed evidence bundle.
  Binding adoption alone still grants no inference or lifecycle authority.
- The results browser exposes binding identity and treats its hashes as
  comparability dimensions.
- Verification: 525 retained tests and all six dry-config commands pass.
- Authorized two-cell Gemma acceptance is currently **blocked**, not accepted.
  Four sealed attempts (`run-20260805-233948-4d5cf5`,
  `run-20260805-234409-41000e`, `run-20260805-234703-be6713`, and
  `run-20260805-235031-d2ba34`) preserved PASS preflight and Osaurus matrix
  evidence but failed before the direct oMLX lane. The first exposed an
  Osaurus child-process cleanup gap, which is fixed and covered by exact-PID
  lifecycle tests. The next three failed closed on `runtime executable lookup
  failed` while observing port 8100 after verified Osaurus release, including
  after a bounded identity reinspection window.
- Each attempt sealed honestly as `FAIL`; no oMLX, preference, RAG, or overhead
  PASS is claimed. Post-run inspection found no matching listener or model
  server process. Further live retries are paused pending a deterministic port
  8100 identity trace.

## Managed Live Acceptance (2026-07-31)

The managed path was accepted with a sealed local run:

- Run `run-20260731-051843-04302b`, name and comparison ID
  `gemma-managed-acceptance-20260731-r4`, sealed `PASS` at attempt 4; the
  complete checksum manifest validated after sealing. The retained Python
  suite (372 tests) passed at acceptance.
- Attempt 1 preserved PASS evidence for preflight, the native matrix screen,
  preference, RAG oracle, and RAG keyword. Attempts 2 and 3 preserve honest
  overhead recovery failures and provider-reconnect blocks.
- Attempt 4 completed the oMLX direct-versus-Osaurus screen overhead step:
  direct median total ~2.001s, routed ~1.991s (delta ~-0.011s), TTFT delta
  ~+0.020s, with both response-contract paths PASS.
- The OptiQ overhead pair was `N/A` in this screen attempt. It was not
  measured and is not a PASS.
- Osaurus was attached and recorded untouched; harness-owned oMLX workers
  were sequentially released and absent after cleanup; the operator-owned
  OptiQ process remained untouched.

The sealed bundle is machine-local evidence under ignored `results/runs/`
and is intentionally not committed.

## Accepted Current Evidence

| Area | Status | Evidence |
| --- | --- | --- |
| Managed local-run foundation | Sealed live acceptance `PASS` | `results/runs/run-20260731-051843-04302b` (local, gitignored) |
| Native triple and routing overhead | Closed for the accepted window | `superpowers/verification/2026-07-23-native-triple-overhead-live-evidence.md` |
| Multi-family preference and RAG | Closed for the accepted window | `superpowers/verification/2026-07-24-multi-family-quality-live-evidence.md` |
| Personal selection policy | Operator decision | `superpowers/verification/2026-07-24-personal-selection-policy.md` |
| Discovery Gemma execution | Sealed PASS | `superpowers/verification/2026-07-24-discovery-20260725-004-pass.md` |
| Approach 3 Gemma collections | `EXECUTED_UNSEALED` | Historical run directories remain local; no product PASS claimed |

## Active Workflows

- managed `policy` / `plan` / `run` / `resume` / `status` / `report` / `browse`
- Discovery proposal/show/execute
- Approach 3 explicit recipes
- native matrix
- pairwise preference
- oracle and keyword RAG
- direct-versus-Osaurus overhead
- read-only sealed-results browser with sealed cross-run comparison
  ([results-browser.md](results-browser.md))
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

## Open Risks

- The OptiQ overhead pair remains unmeasured (`N/A`) in the accepted screen
  attempt.
- Approach 3 evidence still needs a separate review/seal decision.
- Backend attach/reclaim behavior is powerful and requires an adopted policy
  authorizing the exact plan.
- Resolved artifacts remain machine-local and may be missing even when the
  portable committed templates and machine profile are structurally valid.
- The results browser now includes read-only sealed cross-run comparison
  pages (metadata and verbatim statuses only, sealed verified members
  only). Richer metric comparison and open-mix comparison remain deferred.
- No external plugin lifecycle is managed by this repository cleanup.
- The controlled-expansion mechanism is shipped, but the only checked-in
  class currently declares the existing Gemma native baseline. No additional
  model build is claimed available or validated yet.
- Managed free-bind execution remains same-family and native-server-only;
  heterogeneous/open-mix scheduling is still deferred.

## Machine State

This file does not claim current runtime availability. Check actual loopback
services and artifacts only during a separately authorized local run.
