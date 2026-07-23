# Cursor Continuation Prompt: Stage 2B-1 Gate A Remediation

> **ARCHIVE BANNER (2026-07-23):** Keep this handoff; do not delete. It is not
> current operator guidance. Stage 2B-1 findings closed; sealed PASS
> `stage2-20260721-005`. Prefer `docs/stage-2b1-gate-a.md` and AGENTS.md.
>
> **DEFERRED FUTURE LAB WORK - DO NOT USE FOR THE CURRENT HANDOFF.** This prompt
> preserves the five findings needed before any future automated Stage 2B-1 live
> run. Jason has intentionally frozen this lane because it is disproportionate
> to the current personal model-selection goal. Use
> `2026-07-15-cursor-personal-model-selection-mvp-handoff.md` instead.

Use the following prompt in Cursor with this repository open:

```text
You are the implementation agent continuing a tightly bounded safety-remediation
pass in Jason Randazza's local model runtime evaluation harness.

Repository root:
/Users/jrazz/Dev/active/local-model-runtime-evaluation-harness

Deep Wiki root:
/Users/jrazz/Documents/ObsidianNotes

PRIMARY OBJECTIVE

Close exactly five final architecture-review findings in the existing Stage
2B-1 Gate A implementation, add regression tests for them, run the complete
non-live verification set, and prepare the work for one clean final review.

This is not permission to redesign the harness, support new models or runtimes,
begin Gate B, create a live manifest or usable run ID, contact an endpoint, load
a model, start or stop a service, modify an Osaurus provider, reinstall the
plugin, or implement Stage 2B-2.

The user's real goal is modest: obtain trustworthy evidence for choosing local
models for a personal Deep Wiki workflow. Do not turn this into a definitive
cross-framework benchmark product. Preserve the useful harness, close the five
safety gaps, and then stop.

READ FIRST

Before editing, read these repository files in order:

1. AGENTS.md
2. docs/superpowers/specs/2026-07-15-stage-2b1-optiq-inference-acceptance-design.md
3. docs/superpowers/plans/2026-07-15-stage-2b1-optiq-inference-acceptance.md
4. .superpowers/sdd/progress.md
5. .superpowers/sdd/task-1-report.md through task-8-report.md
6. tests/test_stage_two_gate_a_e2e.py
7. The source and tests around transport, Stage 2B inference, cleanup, locking,
   lifecycle, and artifact sealing.

Then read the Deep Wiki for intent and durable history:

1. /Users/jrazz/Documents/ObsidianNotes/00 System/Policies/Agent Onboarding Contract.md
2. /Users/jrazz/Documents/ObsidianNotes/10 Wiki/Projects/Local Model Benchmark Overhaul/Local Model Benchmark Overhaul.md
3. /Users/jrazz/Documents/ObsidianNotes/20 Records/Projects/Local Model Stack/Tier 5/Local Model Runtime Evaluation Harness Stage 2B-1 Gate A Review - 2026-07-15.md
4. /Users/jrazz/Documents/ObsidianNotes/00 System/Audit/Agent Activity/2026-07-15.md

Follow the onboarding contract before any vault write. The repository defines
current executable truth. The Deep Wiki explains intent, decisions, and history.
When they disagree, inspect the repository, determine what changed, and update
the Deep Wiki rather than treating the Wiki as executable truth.

CURRENT VERIFIED BASELINE

- Stage 2A revision 3 is the accepted, preserved GET-only rollback baseline.
- Stage 2B-1 is a fixed non-benchmark smoke cohort: exactly eight serial POSTs,
  four excluded warm-ups, and four measured observations.
- The full non-live baseline passed 208 Python tests and 4 Swift plugin tests.
- Required JSON files parsed, static safety scans passed, and vault validation
  passed.
- Plugin 0.3.0 and its six one-time-approval tools are unchanged.
- No active Stage 2B manifest or usable run ID exists.
- Final decision is GATE_A_STOPPED. Passing tests do not authorize Gate B.

THE FIVE FINDINGS TO FIX

1. HARD WALL-CLOCK DEADLINE AND CANCELLATION
   Current transport timeout behavior is socket inactivity based. A trickling
   SSE stream can continue beyond the 120-second request contract, and blocking
   readline behavior can delay cancellation. Add an actual monotonic wall-clock
   deadline for the whole request and bounded/cancellation-aware stream reads.
   Preserve exact loopback allowlisting and credential-free request composition.

2. STRICT SSE FRAMING
   Current parsing can accept EOF without [DONE], ignore unexpected non-data
   lines, and still mark a stream valid. Fail closed on incomplete termination,
   malformed or unsupported framing, and any ambiguous stream state. Add tests
   for trickle, missing [DONE], malformed fields, unexpected lines, cancellation,
   and the normal valid stream.

3. CLEANUP LOCK AND SHUTDOWN TOCTOU
   Cleanup must prove the exact run owns the active lock throughout validation,
   sealing, and release. A missing lock is a failure, not an idempotent success.
   Recheck operator shutdown immediately before successful final sealing and
   lock release so a service restart cannot slip through. Add deterministic
   tests for lock removal, lock replacement, and service restart at each
   relevant boundary.

4. DURABLE POST-ATTEMPT ACCOUNTING
   A real POST must never disappear from evidence because persistence fails
   after transport. Implement a crash-consistent attempt journal or equivalent
   two-phase record that distinguishes prepared, dispatched, completed, and
   failed attempts without underreporting a possible POST. Partial summaries
   must derive conservative counts from durable evidence. Do not merely move a
   counter before the request if that can overstate a POST as definitely sent;
   represent uncertainty explicitly and fail closed. Add fault-injection tests
   around every persistence and transport boundary.

5. EXACT LIFECYCLE RECONCILIATION DURING RESEAL
   Resealing and cleaned-state recovery must verify the exact expected lifecycle
   history and reject unauthorized lifecycle changes. Do not allow a new
   checksum to legitimize altered lifecycle evidence. Add tampering and recovery
   tests for appended, removed, reordered, duplicated, and modified transitions.

IMPLEMENTATION METHOD

- Start by writing a concise fix plan mapping each finding to owned files and
  tests. Do not propose broader architecture work.
- Use test-driven development: create a failing regression test for a finding,
  implement the smallest fix, and rerun the focused test before moving on.
- Work one finding group at a time. Keep changes local to the established
  transport, Stage 2B engine, cleanup, lock, lifecycle, and artifact boundaries.
- Preserve Stage 0, Stage 1, and accepted Stage 2A behavior.
- Preserve the fixed eight-request limit, one-in-flight rule, RAM gates,
  route/model identity, credential separation, redaction, manual service
  lifecycle, and plugin 0.3.0 contract.
- Do not add a frontend, database, generic framework adapter layer, scheduler,
  remote provider support, framework auto-discovery, or product packaging.
- Do not chase later Osaurus, oMLX, or mlx-optiq releases in this pass. The
  current harness is version-pinned. Release changes belong in a separate impact
  review after this gate is closed.
- Do not use live endpoints or network access in tests. Use deterministic fakes
  and fault injection.
- Do not stage, commit, push, or alter Git history unless Jason explicitly asks.

ACCEPTANCE REQUIREMENTS

1. Every finding has at least one regression test that fails before its fix and
   passes after it.
2. The deterministic Stage 2B-1 end-to-end test still proves exactly eight
   serial fake POSTs, four warm-ups, four measured observations, independent
   decisions, redaction, checksum validation, and lock retention.
3. Stage 2A remains GET-only and all Stage 2A regression tests pass unchanged.
4. The complete Python suite passes, including all new tests.
5. The unchanged Swift plugin suite passes all four tests and remains 0.3.0.
6. Both schemas, the fixed suite, Stage 2B fixture, and non-authorizing template
   parse successfully.
7. Static scans confirm no active Stage 2B manifest or usable run ID, no new
   provider/service mutation, no credential serialization, and no Stage 2B-2
   authority.
8. A final independent architecture review reports no remaining Critical or
   blocking finding in this five-item scope.
9. Only after item 8 may the Deep Wiki decision move from GATE_A_STOPPED to
   READY_FOR_STAGE_2B1_GATE_B. Do not make that decision yourself based only on
   tests.

REQUIRED DELIVERABLES

- Minimal code and regression-test changes for the five findings.
- A focused verification log with exact commands and pass/fail counts.
- A short follow-up report beside .superpowers/sdd/task-8-report.md.
- After a clean independent review, bounded updates to the Stage 2B-1 Gate A
  Deep Wiki record, Local Model Benchmark Overhaul project note and board, and
  the Agent Activity audit. Follow vault authority and validation rules.
- A clear list of residual risks that require live observation rather than more
  Gate A code.

STOP CONDITIONS

Stop and report rather than improvising if:

- a fix requires live endpoint, model, service, provider, credential, or plugin
  activity;
- the scope begins expanding beyond the five findings;
- accepted Stage 2A behavior would need a broad rewrite;
- a test cannot be made deterministic;
- a framework-version change is required;
- any instruction would create a live manifest, usable run ID, or Stage 2B-2
  authority;
- the final review still finds a blocking safety gap.

When the five findings are closed and reviewed, recommend the smallest next
step: one read-only Gate B and then one explicitly authorized eight-request live
smoke run. Do not propose a broad benchmark matrix until that smoke run proves
the path and Jason decides the extra complexity is still useful.
```
