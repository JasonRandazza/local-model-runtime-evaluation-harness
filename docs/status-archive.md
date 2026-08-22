# Status Archive

Dated status entries for cycles before 0.4.0, moved out of
[status.md](status.md) on 2026-08-22 so the live document stays readable.

**This file is history, not current state.** Nothing here is required reading.
It is append-only from the top as cycles age out: newest archived entry first,
matching status.md's own ordering. Current state -- accepted evidence, active
workflows, open risks, machine state -- lives only in status.md and is never
copied here, so the two can never disagree about what is true now.

Sealed run identifiers cited below remain valid; the runs themselves are local
and gitignored. The pre-cleanup repository tree is a separate concern, preserved
in the checksummed sibling archive described in [history.md](history.md).

---

## Qwen JANGTQ4 and Open-Mix Live Acceptance (2026-08-06)

- The prior `qwen_mxfp4__osaurus` cell remains preserved in sealed historical
  evidence but is retired from the active Qwen campaign. Run
  `run-20260806-151415-b64165` truthfully sealed `FAIL`: all 12 MXFP matrix
  observations and all six MXFP preference requests reached the corrected
  180-second request ceiling. A separately authorized one-request
  non-thinking probe also timed out at 60 seconds.
- The replacement `qwen_jangtq4__osaurus` cell uses the locally installed
  `Qwen3.6-35B-A3B-JANGTQ4` artifact and provider model ID
  `qwen3.6-35b-a3b-jangtq4`.
- A bounded live admission screen passed: the fixed non-thinking smoke request
  returned the exact expected marker in about 13.72 seconds, followed by 9/9
  successful, contract-valid matrix observations. Matrix median total latency
  was about 4.53 seconds, worst total latency about 6.86 seconds, and median
  TTFT about 1.07 seconds. The configured memory floor remained satisfied.
- Candidate evidence remains honestly `EXECUTED_UNSEALED`, while immutable run
  `run-20260806-194307-801b42` is the sealed full-workflow acceptance. It
  completed preflight, matrix, preference, both RAG modes, Ornith overhead,
  cleanup, and sealing as `PASS` on attempt 1. Qwen JANGTQ4 and Ornith oQ4 each
  produced 9/9 successful, contract-valid matrix observations; median total
  latency was about 1.08 seconds for JANGTQ4 and 11.24 seconds for Ornith.
- Ornith direct and Osaurus-routed overhead both produced 9/9 successful,
  contract-valid measured observations. Median total latency was about 14.74
  seconds direct and 14.45 seconds routed (about -0.29 seconds); median TTFT
  was about 13.79 seconds direct and 13.46 seconds routed (about -0.33 seconds).
  Qwen member-local overhead remains explicit `N/A` because no reviewed direct
  pair exists.
- The checksum manifest verifies in full. Six harness-owned oMLX worker PIDs
  were individually released, the operator-owned Osaurus PID was attached and
  recorded untouched across all six leases, cleanup completed, and the run
  lock was removed.

## OmniRoute-Assisted UI Slice (Recorded 2026-08-06)

- OmniRoute MCP `3.8.49` was reachable and healthy for this slice. Its named
  LMRE context skill remained unavailable and broader CLI/config skill coverage
  was incomplete, so no repository context integration was inferred.
- After explicit approval, only sanitized architecture and lifecycle packets
  were sent externally. They excluded credentials, source code, local paths,
  run identities, raw evidence, model responses, and machine configuration.
- Short bounded delegations covered information hierarchy, loopback server
  structure, route and session design, threat review, and offline test cases.
  Their proposals were treated as review input and reconciled against local
  repository rules; unsafe force-kill and UI-as-evidence suggestions were
  rejected.
- OmniRoute received no Git, filesystem, process, provider, evidence-write, or
  live-run authority. Improving its reusable LMRE context skill remains a
  separate slice owned by the concurrent OmniRoute workstream.

## Run-Orchestration UI MVP (Non-Live Verified, 2026-08-06)

- `lmre ui` binds only `127.0.0.1:8765`, renders server-side HTML with no
  JavaScript, and reads existing managed bundles through the retained evidence
  and results-browser boundaries.
- A start or overhead-only resume is shown only when persisted evidence allows
  it. The full plan hash, explicit acknowledgement, same-origin CSRF proof, and
  a fresh ten-minute single-use action grant are all required.
- One fixed managed-CLI child may run at a time. UI memory is presentation-only;
  persisted evidence remains truth. Cancel sends exact-child `SIGINT`; console
  shutdown may follow with bounded exact-child `SIGTERM`, never force kill.
- Host, Origin/Referer, CSRF, safe-run-ID, HTML escaping, action replay,
  expiry, concurrency, cancellation, and fixed command-vector behavior have
  offline fake-process coverage. Desktop and phone-width browser reviews
  passed without horizontal page overflow.
- Verification at review: 566 retained tests passed (environment-dependent
  transport tests skip while a local Osaurus holds its port); all six
  retained dry-config commands passed. No runtime, provider, credential, or
  model was contacted and no live run was initiated.

## Heterogeneous Open-Mix Managed Execution (Offline-Verified, 2026-08-05)

- `lmre open-mix inspect <id>` strictly validates a checked-in ordered set of
  two to six native cells from at least two families, one shared suite
  contract, and approved-root artifact presence without live contact.
- `lmre plan --open-mix <id>` writes plan schema `1.3.0`, binding the definition,
  ordered members, suite contract, all executable input hashes, request and
  duration ceilings, loopback routes, and policy-relevant lifecycle bounds.
- Plan schemas `1.0.0` through `1.2.0` retain their original serialized shape
  and hash behavior. The sealed-results browser exposes open-mix and suite
  identity as exact comparability dimensions and derives no winner or score.
- The checked-in `qwen-ornith-capability-v1` inspection reports its two local
  artifacts as present and labels all live facts `NOT_CHECKED_LIVE`.
- `run` now materializes the exact ordered members through the existing
  single-lane runtime manager and retained collectors. Collector artifacts
  preserve family-qualified identity, member-family campaign inputs are bound
  by plan hash, and unsupported overhead is explicit `N/A` without route
  discovery.
- A supported missing Osaurus route seals `PARTIAL_BLOCKED`; `resume` verifies
  the original bundle and retries overhead only after the operator reconnects
  the existing provider.
- The implementation adapter was first verified with fakes and configuration
  reads only; live acceptance is now supplied by
  `run-20260806-194307-801b42` as recorded above.
- Verification: 546 retained tests passed, all six established dry-config
  commands passed, and the checked-in open-mix inspection returned
  `READY_FOR_PLAN` with both artifacts present and `NOT_CHECKED_LIVE`.

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
  server process.
- Follow-up against installed oMLX `0.5.7` identified a release-compatibility
  boundary introduced in oMLX `0.5.4`: explicit non-secret serve settings are
  persisted. The prior managed command passed its temporary model catalog but
  did not isolate oMLX's base directory, allowing a run-specific catalog path
  to enter the user's normal oMLX settings. Managed starts now use a fixed,
  attempt-specific base under `.lmre/runtime-state/`; recipes cannot override
  it, credentials remain memory-only, and existing user settings are not
  modified by the repair. Non-live verification is complete; live oMLX
  acceptance remains required before this branch can be merged.
- A fifth sealed attempt, `run-20260806-002938-b557ee`, proved that installed
  oMLX `0.5.7` passed exact process identity, authentication, model inventory,
  readiness, and matrix inference while attached as operator-owned. It then
  failed after the oMLX lane because the retained matrix collector required
  port 8100 to become free even after the managed runtime layer correctly
  recorded the attached oMLX process as `untouched`. Managed matrix execution
  now delegates release verification solely to the exact-ownership runtime
  manager. Managed overhead execution likewise bypasses the legacy pre-start
  `omlX stop` and port-free checks; low-level collector behavior is unchanged.
  A new sealed end-to-end acceptance attempt remains required.
- Attempt `run-20260806-003419-0c7c3e` sealed `FAIL` after its matrix step
  passed because a managed-only lifecycle argument was wired to the preference
  collector. That argument placement is corrected and covered by an
  integration-level hook test.
- Attempt `run-20260806-003703-52efe7` completed matrix, preference, RAG oracle,
  and RAG keyword as `PASS`, including 9/9 successful, contract-valid oMLX
  matrix observations. It reached the expected provider-reconnect boundary
  because Osaurus did not expose the routed oMLX model. Final sealing then
  failed closed because repeated attachments to the same app reused a
  process-derived lease ID. The run remains truthfully `EXECUTED_UNSEALED`.
  Runtime-manager lease IDs now include a unique acquisition sequence, with
  matching evidence tests. A new run must prove sealed `PARTIAL_BLOCKED` or
  `PASS`; the unsealed attempt will not be promoted.
- Attempt `run-20260806-004836-920a93` is the sealed acceptance for this repair.
  Preflight, matrix, preference, RAG oracle, RAG keyword, cleanup, and sealing
  are `PASS`; oMLX produced 9/9 successful and contract-valid matrix
  observations. The checksum manifest verifies in full, and the originally
  attached Osaurus and oMLX PIDs remained unchanged. Attempt 1 sealed
  `PARTIAL_BLOCKED` because Osaurus did not expose the routed oMLX model.
  After the operator reconnected that provider, attempt 2 completed both
  direct and routed overhead as `PASS` and the run sealed with terminal
  `PASS`. Direct median total latency was about `1.769s`; routed was about
  `1.910s` (`+0.140s`), with median TTFT about `0.682s` direct and `0.730s`
  routed (`+0.048s`).
- The first attempt-2 seal exposed that process-derived lease IDs can repeat
  across resume attempts even though each attempt's acquire/terminal pairs are
  complete. Evidence validation and browser summaries now scope lease IDs by
  recorded attempt. The completed overhead evidence was reviewed, cleanup was
  complete, both app identities were unchanged, and only the failed seal
  operation was retried before the final checksum verification.

## OptiQ and Approach 3 Evidence Closure (2026-08-05)

- Managed run `run-20260806-012734-936521` used the reviewed two-cell binding
  `gemma-osaurus-optiq-evidence-v1` and sealed terminal `PASS` on its first
  attempt. Preflight, matrix, preference, both RAG modes, OptiQ overhead,
  cleanup, and evidence verification all passed.
- Direct and Osaurus-routed OptiQ each recorded 9/9 successful,
  contract-valid measured observations. Median total latency was about
  `1.988s` direct and `2.084s` routed (`+0.095s`); median TTFT was about
  `0.284s` direct and `0.307s` routed (`+0.023s`). The attached Osaurus and
  OptiQ process identities were recorded `untouched` and remained unchanged.
- The four historical 2026-07-24 Approach 3 collector directories were
  reviewed without modification. They contain complete collector-level
  preference and RAG requests, direct oMLX `PASS`, routed oMLX `N/A`, and
  direct/routed OptiQ `PASS`, but no immutable plan, policy linkage, lifecycle
  journal, cleanup proof, input hashes, or execution-time checksum manifest.
- The seal decision is `REVIEWED_UNSEALED`: retroactive sealing would invent
  provenance, so the old directories remain excluded from product PASS and
  the sealed-results browser. The exact three-cell managed acceptance plus
  the sealed oMLX and OptiQ binding runs are the current product evidence.
  See the [Approach 3 closure review](superpowers/verification/2026-08-05-approach3-evidence-closure-review.md).

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
