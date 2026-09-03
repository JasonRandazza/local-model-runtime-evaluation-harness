# LMRE continuation handoff — 2026-09-03

Agent-agnostic. Assumes no memory of prior sessions. **Supersedes
`2026-08-22-continuation-handoff.md`** (its "exact state" is stale: branch,
test count, and next slices all moved) and **closes
`2026-08-29-runtime-updates-research-handoff.md`** (its Phase 0, 1 and 2
questions are all answered below — do not re-run that investigation).

---

## 1. Read these, in this order, and stop

| # | File | Why |
|---|------|-----|
| 1 | `AGENTS.md` | The rules that bind you: product boundary, non-live boundary, credentials. Non-negotiable. |
| 2 | `CONTEXT.md` | Domain vocabulary. Ruling, rubric, supersede, cell, family, workspace. |
| 3 | `docs/adr/` | Seven decision records. 0004–0006 govern rulings; **0007 is new** and governs runtime pins. |
| 4 | This file, section 3 onward | Current state and what is actually next. |

`docs/status.md` and `docs/architecture.md` describe the rulings cycle and are
current except for this cycle's four merges. The two superseded handoffs named
above are history; do not read them for state.

Navigate code with `graphify query "<question>"` before grepping.

## 2. Authority boundary

Begin read-only. This document grants **nothing**. Obtain explicit
current-session permission for: running a live model, adopting policy, altering
providers, staging, committing, pushing, opening a PR, merging, or tagging.

Never print or persist a credential.

## 3. Exact state

- branch `main` at `6726d02`, pushed, **working tree has three loose items** —
  see section 6 before you do anything else
- **757 tests pass**, no skips (was 706 at the start of this cycle)
- all six `dry-config` commands exit 0
- package version still `0.4.0`; this cycle's work is in `Unreleased`
- issue #37 (GUI / testing-suite direction) is the **only** open issue, still
  `needs-triage`, still captured intent rather than a spec

### What shipped this cycle (four worker tickets, all merged)

1. **Pinned volatile upstream runtime defaults** (ADR-0007). OptiQ
   `--max-context 8192`; oMLX `--max-concurrent-requests 1`,
   `--memory-guard off`, `--no-cache`. Adapter tuples and the six cell configs
   must stay in exact sync or every affected cell fails validation.
2. **Runtime version provenance.** New `runtime_versions.py` plus a
   `runtime-versions` managed CLI command.
3. **Rulings in the results browser.** `rulings/index.html` plus one page per
   ruling, linked from the main index; supersession shown, never hidden.
4. **Pinned linter configuration.** `ruff==0.16.5`, rule set E/F/W/I/UP/B,
   line-length 79, **advisory** (`continue-on-error: true`) in CI.

### The one consequence that matters

Pinning changed the cell configs, so **plans built before `e3bf4af` read
`INCOMPARABLE` against plans built after**. That is correct and intended: with
`--max-context auto`, a 64GB and a 32GB Mac were silently measuring different
things. Existing sealed evidence is untouched and still readable; only forward
comparability is cut. ADR-0007 states this.

## 4. Runtime ground truth (verified 2026-09-03 — do not re-verify)

| Runtime | Version | Notes |
|---|---|---|
| osaurus | app `0.24.4` | `osaurus version` prints the literal string `dev`. Use `osaurus doctor --json --redact`, whose `apps` array carries the real version. |
| oMLX | `0.6.4` | `--version` now works; it used to traceback. |
| mlx-optiq | `0.4.2` | `--version` works. |

Every flag the adapters hardcode still exists. **No adapter rewrite is needed.**

Two closed questions from the 2026-08-29 research, so nobody re-opens them:

- **`optiq --single-model` default.** The worry was that a test asserting a 404
  on a wrong model id had gone silently green. **No such test exists**, so
  nothing was lying. Closed.
- **`osaurus serve --help` starts the server** instead of printing help. Use
  `osaurus --help`. If you trip it, `osaurus stop`.

Phase 2 of that research — whether `osaurus bench`, `osaurus doctor`,
`optiq benchmark|eval|latency` or `omlx diagnose` make parts of this harness
redundant — is **still unexamined**. It is a comparison study, not a config
change, and deserves its own session. The honest question for each: does it
measure what we measure, under conditions we control?

## 5. Traps

Everything in the 2026-08-22 handoff's traps section still holds. The plan-hash
gate is still the most important invariant; never read configuration at import
time (`tests/test_import_purity.py` enforces it with an AST guard); prove a new
test fails without its fix; do not use `git checkout <file>` to undo a probe;
check the real exit code, not a pipeline's.

Two more, both learned the hard way this cycle:

**A worker started osaurus on port 1337 and quietly degraded every baseline.**
Five tests turned into skips and each worker reported "706" as though nothing
had happened. Runtimes are **shared singletons and belong to the orchestrator
alone**. Before trusting any test count, check `osaurus status` and
`lsof -nP -iTCP:1337 -sTCP:LISTEN`.

**A green worker test suite is not a review.** Four real defects passed the
workers' own tests this cycle, including a path traversal and a
double-escaping bug that the existing hostile-input test masked by asserting on
a different field. Read the diff; write the test the worker did not.

## 6. Working tree

Clean apart from one deliberate open question:

`uv.lock` is untracked and **not gitignored**. Decide: commit it, or add it to
`.gitignore`. `pyproject.toml` now carries a `[dependency-groups] dev` group
pinning `ruff==0.16.5` and `pytest`, so a committed lock is defensible. It was
left for you rather than decided unilaterally.

The 2026-08-22 handoff's side-track pointer was discarded (this document
replaces it), and the 2026-08-29 research handoff is committed as history --
its conclusions are preserved in section 4, so it is reference, not required
reading.

## 7. What is actually next

**Discovery-as-proposer.** Discovery today only *checks* cells; it never
authors them. This is the north star's one unkept promise and the stated gate
for moving from published artifact to real product. It was deliberately **not**
dispatched to a worker this cycle: the design is not settled, and a ticket
whose artifact cannot be stated in one sentence is the wrong shape for a
worker. **Design it in conversation first.** Largest and most valuable slice.

**Grill #37 before building anything from it.** It collides with the wiki's
"not chartered to become a compatibility suite." Also not dispatched, for the
same reason.

**Clear the ruff backlog and make the gate blocking.** 1444 violations, 87% of
them `E501` line-too-long, 186 auto-fixable. This is the single best worker
ticket available right now: mechanical, verifiable, and it converts an advisory
gate into a real one. **Do it in one worker on a quiet tree** — a repo-wide
autofix conflicts with every concurrent branch.

**Phase 2 of the runtime-tooling study** (section 4). Needs its own session.

**Aggregating repeat runs.** A ruling consumes exactly one sealed run.
Combining several needs an aggregation rule the codebase does not define.
Deferred deliberately.

**Publish to a package index.** Gated on discovery-as-proposer.

### Explicitly rejected — do not resurrect

**Runtime-version regression.** Measuring one family across successive builds
of one stack was ruled out as the wrong question. Note that `runtime_versions.py`
shipped this cycle is **not** that: it is write-only provenance, never read by
ruling, rubric, comparison or discovery code, and never enters `input_hashes`
or the plan. If work on it starts to look like a comparison axis, stop.

## 8. Orchestration notes

Workers ran as LongCat-2.0 through `opencode-go` in Termic worktrees. Two
things cost real time and will again:

- **The global `~/.config/opencode/opencode.json` pins `build`, `general` and
  `plan` to `deepseek-v4-flash`** while only the top-level model is LongCat. A
  worktree-local `opencode.json` pinning the model in all four places is what
  actually gets you LongCat. Confirm from the log, not the file:
  `grep -o 'modelID=[^ ]*' ~/.local/share/opencode/log/opencode.log | tail -3`.
- **`--dangerously-skip-permissions` is a Claude Code flag and does nothing for
  opencode workers.** Permissions come from config: set
  `{"edit":"allow","bash":"allow","webfetch":"allow"}` at top level and per
  agent.

Bonsai (`prism-ml/Bonsai-8B-AWQ-4-bit`, 64K context) was down at dispatch time
and came back mid-session; it is reachable on both `127.0.0.1:1234` and
`100.73.137.9:1234`, and `pi-bonsai-direct -p "..."` answers. It is the right
worker for the ruff backlog if that ticket is cut small enough.
