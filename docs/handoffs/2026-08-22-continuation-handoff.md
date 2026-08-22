# LMRE continuation handoff — 2026-08-22

Agent-agnostic. Assumes no memory of prior sessions. Supersedes
`2026-08-07-continuation-handoff.md`, which describes work now merged and whose
"exact state" section is stale in three ways: the branch, the test count, and
the candidate next slices.

---

## 1. Read these, in this order, and stop

| # | File | Why |
|---|------|-----|
| 1 | `AGENTS.md` | The rules that bind you: product boundary, non-live boundary, credentials. Non-negotiable. |
| 2 | `CONTEXT.md` | The domain vocabulary. Ruling, rubric, supersede, cell, family, workspace. |
| 3 | `docs/adr/` | Six decision records. 0004–0006 govern rulings and are short. |
| 4 | `CHANGELOG.md` | What changed and what it means for evidence. |
| 5 | This file, section 3 onward | Current state and what is actually next. |

`docs/status.md` and `docs/architecture.md` are current as of this cycle and
both describe rulings. `status.md` keeps only the recent dated cycles; earlier
ones live in `docs/status-archive.md`, which is history and not required
reading.

Navigate code with the Graphify graph (`graphify query "<question>"`) before
grepping. Read raw source when you need exact lines.

## 2. Authority boundary

Begin read-only. This document grants **nothing**. Obtain explicit
current-session permission for: running a live model, adopting policy, altering
providers, staging, committing, pushing, opening a PR, merging, tagging, or
writing to the Deep Wiki.

Never print or persist a credential.

## 3. Exact state

- branch `main` at the merge of PR #38; working tree clean
- **706 tests pass**, no skips; CI green on 3.11 and 3.13
- all six `dry-config` commands exit 0
- issue #36 (rulings) is **closed**; #37 (GUI / testing-suite direction) is open
  and labelled `needs-triage` — it is captured intent, not a spec, and needs
  grilling before anyone builds from it
- package version is still `0.4.0`; rulings are in `Unreleased`

### What shipped this cycle

The harness now **draws the conclusion its evidence supports**. Previously it
collected per-cell latency, preference and RAG scores, sealed them, and stopped
— leaving the operator to read three tables and apply criteria that lived in a
prose document.

- `rubric.py` — the criteria: quality floors, then one ordering metric
- `cell_metrics.py` — per-cell readers for matrix, preference and RAG. Preference
  and RAG were computed and written but never read back out
- `ruling.py` — `build_ruling`, which **never raises**
- `ruling_store.py` — one ruling per file, never overwritten
- `ruling_cli.py` — `lmre-managed ruling make` / `ruling list`

## 4. Traps

**The plan-hash gate is still the most important invariant.** `input_hashes`
keys are workspace-relative path strings; anything that changes where a plan
input resolves makes runs planned before and after read `INCOMPARABLE` despite
identical content. Rulings deliberately sit outside it — the rubric is hashed
into the ruling and never into the plan (ADR-0006) — so this cycle did not touch
it, but the next one might. Before any change to path resolution or config
layout, build the plan for every checked-in recipe and open mix and confirm the
hashes are unchanged. Script it.

**Never read configuration at import time.** `tests/test_import_purity.py`
enforces this with an AST guard. A module-scope read crashes every command
before argument parsing, which is an installed copy's normal state.

**Prove a new test actually fails without the fix.** This is not ceremony. This
cycle it caught a tie-break test that passed with the tie-break deleted, because
`sorted` is stable and the input order happened to give the same answer — the
test asserted determinism without binding the code providing it. Disable the
protection, watch the test fail, restore.

**Do not use `git checkout <file>` to undo a probe.** It silently discarded a
real fix in an earlier cycle. Copy the file aside and copy it back.

**Check the real exit code, not a pipeline's.** `cmd | tail` reports `tail`'s
status.

## 5. What is actually next

**Discovery-as-proposer.** Discovery today only *checks* cells; it never authors
them. This is the north star's one unkept promise and the stated gate for moving
from published artifact to real product. Largest and most valuable slice.

**Rulings in the browser and run console.** Rendering a ruling as HTML adds no
decision-making capability but closes the loop for anyone reading results
without a terminal. Explicitly out of scope in #36.

**Aggregating repeat runs.** A ruling consumes exactly one sealed run.
Combining several runs of the same plan needs an aggregation rule the codebase
does not define. Deferred deliberately.

**Grill #37 before building anything from it.** It collides with the wiki's
"not chartered to become a compatibility suite."

**Publish to a package index.** Gated on discovery-as-proposer, not on rulings.

**Adopt a pinned linter configuration.** There is still none, so "new modules
clean" remains manual and undocumented.

### Explicitly rejected — do not resurrect

**Runtime-version regression.** Measuring one family across successive builds of
one stack was ruled out as the wrong question; the goal is a family across the
three stacks. The version-capture subtree was built and then dropped.

## 6. Working with local-model workers

Much of this cycle was implemented by **Ornith 1.5 9B** running locally through
OpenCode at no token cost, with the orchestrator specifying, reviewing and
integrating. It produced code needing no correctness fixes across five tickets.

Its constraint is a **~64K context window**, which the orchestrator must manage:
one artifact per ticket, ticket plus required reading under ~30K, facts inlined
rather than looked up, and every inlined fact verified first. Exhaustion looks
exactly like working — pinned context indicator, advancing timer, static
worktree, no error.

Full guidance is in the user-level `orchestrate` skill. Do not take any Termic
dispatch signal as proof: `termic send` reports "prompt delivered" for dropped
prompts and `termic wait` reports "agent finished" mid-generation. A file
appearing in the worktree is the only reliable evidence.

## 7. What the manager owns

Reading the actual diff, running verification locally, safety and boundary
decisions, integration, and final acceptance. A worker report is discovery
evidence, not acceptance. If you cannot verify a claim, say so plainly rather
than repeating it.
