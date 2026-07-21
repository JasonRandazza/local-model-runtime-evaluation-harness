# Stage 2B-1 Gemma OptiQ Retarget Design

**Status:** Approved in conversation by Jason on 2026-07-20. This document authorizes implementation planning only. It does not authorize Gate B, a manifest, a usable run ID, live inference, provider changes, plugin rebuild/reinstall, or Stage 2B-2.

**Program shape:** Approach 1 (two slices) — close Gate A findings first; then schema `3.3.0` Gemma retarget. Smoke implementation plus a roadmap annex for later absorption of matrix / preference / RAG / overhead lanes.

## Goal

Reopen Stage 2B as a **Gemma OptiQ direct↔routed inference-path acceptance** program: prove the operator-owned OptiQ service and the Osaurus Optiq route can execute a fixed eight-POST smoke under fail-closed gates, then leave a clear ladder for later Stage-gated cohorts that absorb today’s measurement lanes.

Stage 2B-1 remains an inference-path acceptance check. It is not a statistically meaningful benchmark. It does not produce stable medians, quality rankings, or route-cost conclusions.

## Boundaries

### In scope

1. **Slice 1 — Gate A remediation:** close the five architecture-review findings on the existing Stage 2B-1 engine; independent review; leave `GATE_A_STOPPED` only after that review for the findings scope.
2. **Slice 2 — Gemma retarget:** add schema `3.3.0` pinned to Gemma OptiQ-4bit native (direct `:8080`, routed `:1337`), new runtime profile and suite; live work only after Gate B and Jason’s unused run-ID authorization.
3. **Roadmap annex (design only):** how matrix / preference / RAG / overhead become later Stage-gated cohorts. No implementation in slices 1–2.

### Out of scope

- Live Gate B, manifests, POSTs, provider edits, or plugin rebuild/reinstall until separately approved after the relevant reviews
- Changing Stage 2A revision-3 VibeThinker baseline or reusing consumed historical run IDs
- Folding matrix / preference / RAG / overhead into the eight-POST smoke
- Stage 2B-2 benchmark authority or statistical claims from Stage 2B-1
- Expanding the smoke to oMLX, JANG, or multi-quant cells
- Replacing VibeThinker pins in place under the old profile name

### Hard inherits

- Jason owns the foreground OptiQ lifecycle; the harness never starts, stops, signals, restarts, or configures OptiQ or Osaurus
- Plugin `0.3.0` and its six one-time-approval tools remain unchanged
- Every Stage summary reports `service_lifecycle_actions: 0`
- Stage 2A run `stage2-20260715-003` and runtime profile `vibethinker-3b-optiq-4bit` revision `3` remain the immutable accepted rollback/reference baseline for operator-owned GET observation

## Implementation sequencing

1. Write a focused fix plan mapping each Gate A finding to owned files and tests.
2. Close findings with TDD (deterministic fakes only).
3. Independent architecture review of the five findings.
4. Add schema `3.3.0`, Gemma profile, suite, fixtures, checkers, prompt, and runbook updates.
5. Capture live pin values (hashes, exact routed ID, serve argv) under Jason’s explicit session approval; write them into the profile.
6. Independent retarget review.
7. Separately: Gate B → unused run ID → eight-POST Gemma smoke → manager review.

Do not mix finding remediation and Gemma live authorization into one review gate.

## Exact Gemma contract pins (schema `3.3.0`)

New authorizing shape only. Schema `3.2.0` VibeThinker manifests remain parseable for evidence review and must not authorize new live runs.

| Item | Value |
|---|---|
| Schema | `3.3.0` |
| Mode | `operator_inference_probe` |
| Comparison class | `gemma-optiq-operator-route-smoke` |
| Runtime profile | `gemma-4-12b-optiq-4bit` revision `1` (new file) |
| Suite | `gemma-optiq-route-smoke-v1` revision `1` |
| Direct route | `http://127.0.0.1:8080/v1` |
| Routed route | `http://127.0.0.1:1337/v1` |
| Request timeout | `120` seconds |
| Memory stop level | `warning` |
| Maximum in-flight requests | `1` |
| Total request limit | `8` |
| Plugin | `local.jrazz.model-runtime-evaluation-harness` `0.3.0` |
| Coordinator model | `gemma-4-12b-it-qat-jang_4m` |
| OptiQ runtime | pinned `mlx-optiq 0.3.3` executable family (confirm against inventory; do not chase newer releases in this program) |
| Expected routed ID form | `optiq/mlx-community/gemma-4-12B-it-qat-OptiQ-4bit` (exact match from live inventory; case-sensitive; local and unprefixed IDs rejected) |
| Osaurus provider | existing `Optiq` provider; reconnect without editing |
| Smoke schedule | same two-workload / eight-request counterbalanced schedule as Stage 2B-1 (short-chat + exact JSON text contract); retarget identity only unless dry review shows the JSON contract must change for Gemma |

### Pin discipline

Before Gate B, freeze into `gemma-4-12b-optiq-4bit` revision `1`:

- runtime executable path and package versions
- model repository, revision, snapshot path
- artifact hashes
- approved `serve` argument array
- direct and routed base URLs
- exact `routed_model_id` and rejected local IDs
- direct model identity allowlist

Provisional matrix/personal-selection paths (including `:no-think` for streaming into `delta.content`) inform the draft profile. They are not live authority until hashed and inventory-confirmed.

### Acceptance outputs

Only `inference_path_acceptance` and `behavioral_contract_acceptance`. Evidence stays sanitized: no prompts, generated output, request payloads, headers, credentials, or process details in the Coordinator-facing report.

## Slice 1 — Gate A remediation

### Purpose

Make the existing Stage 2B-1 engine fail-closed on the five reviewed gaps. This slice does not authorize Gate B, create a run ID, or change the live model pin to Gemma.

### Findings (exclusive scope)

1. **Hard wall-clock deadline and cancellation** — whole-request monotonic 120s deadline; cancellation-aware stream reads (not socket-inactivity-only). Preserve loopback allowlisting and credential-free request composition.
2. **Strict SSE framing** — fail closed on missing `[DONE]`, malformed or unsupported framing, and ambiguous EOF. Cover trickle, cancellation, and valid streams in tests.
3. **Cleanup lock and shutdown TOCTOU** — prove the exact run owns the active lock through validation, sealing, and release; missing lock is failure; recheck operator shutdown immediately before successful final sealing and lock release.
4. **Durable POST-attempt accounting** — crash-consistent attempt journal (prepared → dispatched → completed/failed); conservative counts from durable evidence; never silently drop a possible POST; represent uncertainty explicitly and fail closed.
5. **Exact lifecycle reconciliation during reseal** — verify exact expected lifecycle history; reject appended, removed, reordered, duplicated, or modified transitions; a new checksum must not legitimize altered lifecycle evidence.

### Method

- Map each finding to owned files and tests before coding.
- TDD per finding; deterministic fakes and fault injection only; no live endpoints in tests.
- Preserve Stage 0, Stage 1, and accepted Stage 2A behavior.
- Preserve eight-request limit, one-in-flight, RAM gates, route/model identity, credential separation, redaction, manual service lifecycle, and plugin `0.3.0`.

### Slice 1 exit criteria

1. Every finding has at least one regression test that failed before its fix and passes after.
2. Deterministic Stage 2B-1 end-to-end test still proves exactly eight serial fake POSTs, four warm-ups, four measured observations, independent decisions, redaction, checksum validation, and lock retention.
3. Stage 2A remains GET-only; Stage 2A regression tests pass unchanged.
4. Complete Python suite passes; Swift plugin suite remains `0.3.0` and green.
5. Static scans confirm no active Stage 2B manifest or usable run ID, no new provider/service mutation, no credential serialization, and no Stage 2B-2 authority.
6. Independent architecture review reports no remaining Critical or blocking finding in this five-item scope.

Passing tests alone do not authorize Gate B. For this Gemma program, Gate B also waits on slice 2 pins and retarget review.

## Slice 2 — Gemma `3.3.0` retarget

### Prerequisite

Slice 1 findings closed and independently reviewed.

### Deliverables

1. Schema branch `3.3.0` with policy that authorizes only the Gemma pins above.
2. Runtime profile `gemma-4-12b-optiq-4bit` revision `1`.
3. Suite `gemma-optiq-route-smoke-v1` revision `1`.
4. Fixtures, non-authorizing template, Gate A/B checkers, Coordinator prompt, and runbook updated for Gemma pins (plugin tool surface unchanged).
5. Operator sequence unchanged in ownership: Jason starts the pinned foreground launcher, reconnects existing `Optiq` without editing, Gate B, authorizes one unused ID, inventory → preflight → run_scenario, waiter, Ctrl+C, status + cleanup, manager review.

### Second review

Retarget-only architecture review covering identity allowlists, no accidental VibeThinker live authorization path, no Stage 2B-2 creep, and preserved operator lifecycle.

### Live authorization (separate session steps)

Gate B, unused run-ID authorization, eight POSTs, and manager review are not granted by this design document.

## Roadmap annex — measurement lanes into Stage 2

Design-only. Not built in slices 1–2.

After Gemma Stage 2B-1 smoke is manager-accepted, today’s personal measurement lanes become later Stage-gated cohorts. They do not rewrite the eight-POST probe.

| Later stage (indicative names) | Absorbs | Proves under Stage gates | Explicitly not |
|---|---|---|---|
| **2B-2** (route benchmark) | Overhead pairs + bounded wall-clock/SSE timing | Direct vs routed latency under a pinned profile, larger N than smoke, same identity/lock/evidence rules | Preference winners, RAG quality |
| **2C matrix** | Family 3×3 screen/finalist | Cell PASS/FAIL/N/A under Stage auth + sealed evidence; family recipes stay config-driven | Silently replacing operator OptiQ ownership with harness lifecycle without a separate proposal |
| **2D preference** | Preference collect/judge/tally | Blind pairwise quality under pinned cells + declared judge cell; self-judge bias disclosed in evidence | Treating win rate as Stage 2B-1 path proof |
| **2E RAG** | Oracle + keyword RAG | Fact-hit / recall under pinned retrieval mode | Expanding corpus or tools inside 2B-1 |

### Annex rules

- Each lane gets its own schema/mode/comparison class and unused run ID; no piggybacking on a 2B-1 manifest.
- Reuse today’s config recipes and CLIs (`lmre-matrix`, `lmre-preference`, `lmre-rag`, `lmre-overhead`) behind Stage policy wrappers rather than forking parallel implementations.
- Operator OptiQ ownership and plugin `0.3.0` remain the default; any harness-started OptiQ for matrix cells requires a separate lifecycle proposal.
- Historical personal-lane result directories remain evidence, not Stage-authorized bundles, until re-run under a Stage manifest.

### Suggested order

Gemma 2B-1 smoke → 2B-2 overhead/timing on the same Gemma OptiQ pin → optional matrix / preference / RAG expansions when Stage-sealed multi-cell evidence is wanted.

## Tests and verification

### Slice 1

- Per-finding failing regression → fix → focused pass
- Deterministic Stage 2B-1 e2e invariants listed under exit criteria
- Stage 2A suite green and GET-only
- Full Python suite + Swift plugin `0.3.0` suite green
- Static scans for manifests, IDs, mutation, credentials, and 2B-2 authority

### Slice 2

- Schema/policy tests: only Gemma pins authorize; `3.2.0` VibeThinker cannot start a new live run
- Profile fixture tests: exact routed ID, rejected locals, hash/argv allowlists
- Suite schedule tests: eight-request counterbalanced order preserved
- Gate B checker dry tests against Gemma profile fixtures (no network)
- Second independent retarget review before any Gate B session

### Live residual risks

SSE under real load, provider reconnect flakiness, and similar observation-only risks stay on a residual-risk list. They are not default justification for more Gate A code.

## Rollback

- **Before live:** revert or disable the `3.3.0` authorization path and/or slice 1 changes if review fails; leave Stage 2A revision 3 untouched.
- **After a bad live attempt:** do not reuse the run ID; keep sealed evidence; authorize a new unused ID only after re-review if the contract changed.
- **Program abandonment:** remove Stage 2B-1 Gemma authorization materials; accepted Stage 2A artifacts, plugin `0.3.0`, and provider settings remain.

## Non-goals (permanent for this program)

- Deriving Stage 2B-2 statistics from eight POSTs
- Silent plugin version bumps or reinstalls
- Harness starting or stopping OptiQ during Stage 2B-1
- Committing local weight trees or `omlx-roots` symlinks
- Overwriting consumed Stage 2 run IDs

## References

- `docs/stage-2b1-gate-a.md` — current `GATE_A_STOPPED` decision and VibeThinker `3.2.0` contract
- `docs/handoffs/2026-07-15-stage-2b1-cursor-continuation-prompt.md` — five findings and acceptance method
- `docs/superpowers/specs/2026-07-15-stage-2b1-optiq-inference-acceptance-design.md` — original VibeThinker Stage 2B-1 design (historical authorizing shape)
- `docs/architecture.md` — Stage 2A/2B-1 architecture narrative
- `config/personal-selection/lanes/gemma-4-12b-optiq-via-osaurus.json` — provisional routed ID form
- `config/matrix/cells/optiq_4bit__optiq.json` — provisional Gemma OptiQ serve path / `:no-think` note
