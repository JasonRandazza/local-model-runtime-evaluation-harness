# LMRE continuation handoff — 2026-08-07

Written to be agent-agnostic. It assumes no memory of prior sessions and no
particular model or tool. Its first job is to get you oriented **without
scanning the repository or the Deep Wiki**.

Supersedes `2026-08-07-release-readiness-handoff.md` and
`2026-08-06-claude-code-continuation-handoff.md`. Those describe work that is
now merged and released; read them only for archaeology.

---

## 1. Read these, in this order, and stop

Do not explore beyond this list before you have a task. Six files is enough to
start work.

| # | File | Why |
|---|---|---|
| 1 | `AGENTS.md` | The rules that bind you: product boundary, non-live boundary, live boundary, credentials, retired configuration. Non-negotiable. |
| 2 | `docs/status.md` | What is true now, what evidence exists, and the open risks. The top sections are the most recent. |
| 3 | `docs/architecture.md` | Workspace boundary, component responsibilities, evidence boundary. |
| 4 | `CHANGELOG.md` | What changed in the current release and what it means for evidence. |
| 5 | `docs/release-checklist.md` | The gates any release must pass, including the plan-hash gate. |
| 6 | This file, section 4 onward | Current state, traps, and candidate next slices. |

**Do not read the whole `docs/` tree.** Read the one topic doc for the area you
are touching, when you touch it:

`managed-runs.md` (policy/plan/run/resume), `run-console.md` (`lmre ui`),
`results-browser.md` (`lmre browse` and comparisons), `doctor.md`,
`discovery.md`, `matrix.md`, `preference.md`, `rag.md`, `overhead.md`,
`omniroute-claude-code.md` (external delegation), `history.md` (retired lanes).

### Navigating code

This repository has a Graphify knowledge graph at `graphify-out/`. Use it before
grepping or reading source:

```bash
graphify query "<question>"     # scoped subgraph
graphify explain "<concept>"
graphify path "<A>" "<B>"
graphify update .               # after changing code (AST only, no API cost)
```

Read raw source when you need exact lines to change or debug. `GRAPH_REPORT.md`
is for broad architecture review only; prefer a scoped query.

### The Deep Wiki

The vault at `~/Documents/ObsidianNotes` holds durable intent and history. The
**repository is executable truth**; the vault is context. Relevant LMRE notes:

- `20 Records/Projects/Local Model Stack/Tier 5/` — session records and handoffs
- `10 Wiki/Projects/Local Model Benchmark Overhaul/` — durable project wiki

Before writing anything there, read
`00 System/Policies/Agent Onboarding Contract.md`. Vault policy also requires
disclosing that reading a sensitive note may transmit content to a cloud model,
and obtaining current-session permission.

---

## 2. Authority boundary

Begin read-only. This document grants **nothing**. Obtain explicit
current-session permission for any of: running a live model, adopting or
replacing policy, altering providers, transmitting project material to an
external model, staging, committing, pushing, opening a pull request, merging,
tagging, or writing to the Deep Wiki.

Never print or persist a credential. A previous session leaked an Osaurus MCP
token into a transcript by dumping a whole config blob — filter to the fields
you need.

Unit tests and dry-config commands must not contact Osaurus, oMLX, OptiQ, a
keychain, or a real model.

---

## 3. Verifying anything

```bash
.venv/bin/python -m pytest tests/ -q      # expect 626 passed
./bin/lmre-discover dry-config
./bin/lmre-approach3 dry-config config/approach3/gemma-freeform-native-triple-v1.json
./bin/lmre-matrix --dry-config --campaign config/matrix/gemma-4-12b-qat-campaign.json
./bin/lmre-preference collect --dry-config
./bin/lmre-rag collect --dry-config
./bin/lmre-overhead run --dry-config
```

CI runs the suite on Python 3.11 and 3.13, the six dry-config commands, and a
clean-environment install smoke test. It is the only automated gate; there is no
linter in CI.

**Re-run checks rather than quoting this file.** The filesystem may have changed.

---

## 4. Exact state at handoff

- branch `main`, released tag `v0.4.0`, package version `0.4.0`
- working tree clean; **626 tests pass**, no skips
- merged this cycle: PRs #32, #33, #34, #35
- GitHub release `v0.4.0` published with wheel and sdist attached
- MIT licensed; repository is public
- Graphify refreshed

Two untracked files must never be staged, edited, or deleted. They predate this
work and are unrelated:

- `docs/handoffs/2026-08-05-claude-fable-comparison-health-visibility-execution-prompt.md`
- `docs/handoffs/2026-08-05-claude-fable-sealed-cross-run-comparison-execution-prompt.md`

### What shipped in 0.4.0

The harness became genuinely installable. Paths resolve from a **workspace
root** instead of a fixed checkout; `lmre init` scaffolds a workspace from
configuration shipped inside the wheel; all seven console scripts are declared
and work. Earlier, an installed copy crashed on `lmre --help`.

Also: the `lmre ui` run console, recorded metric visibility in sealed cross-run
comparisons, MIT licensing, and CI.

Full detail: `CHANGELOG.md` and `docs/releases/0.4.0-verification.md`.

---

## 5. Traps that will cost you time

**The plan-hash gate is the most important invariant in this repository.**
`input_hashes` is a cross-run comparison dimension and its keys are
workspace-relative path strings. Anything that changes where a plan input
resolves — moving `config/`, altering workspace resolution, renaming a suite
file — changes those keys, and runs planned before and after read
`INCOMPARABLE` despite byte-identical content. Sealed bundles are *not* at risk:
`EvidenceBundle.verify()` recomputes from the stored plan and never touches the
filesystem. The risk is strictly to future comparability.

Before any change touching path resolution or configuration layout, build the
plan for every checked-in recipe and open mix using the real machine profile,
record the plan hash and `input_hashes` keys, and confirm they are unchanged
afterwards. Script it; do not eyeball it. `docs/release-checklist.md` describes
the gate.

**Never read configuration at import time.** A module-scope read crashes every
command before argument parsing wherever configuration is absent, which is an
installed copy's normal state. `tests/test_import_purity.py` enforces this with
an AST guard and subprocess checks; if you add a module-scope call, add it to the
allowlist only with a tested justification.

**A checkout must keep resolving to the repository root.** That fallback in
`workspace.py` is what preserves hash stability. Do not "clean it up".

**Prove a new test actually fails without the fix.** Two defects in this cycle
were caught only because a passing-first-try test was deliberately broken to
confirm it bound to real behavior. When adding a security or evidence test,
disable the protection, watch it fail, restore.

**Do not use `git add -A docs/` or any broad add.** The two protected prompt
files in section 4 live under `docs/handoffs/` and are untracked, so a broad add
stages them. This happened while writing this very handoff and had to be undone
with `git reset --soft` before pushing. Stage files by name.

**Do not use `git checkout <file>` to undo a probe.** It silently discarded a
real fix during this cycle. Copy the file aside and copy it back.

**zsh does not word-split unquoted variables.** `ruff check $FILES` passes one
giant argument; `ruff check $(...)` works. This produced two false readings
before it was noticed.

**Check the real exit code, not a pipeline's.** `cmd | tail` reports `tail`'s
status. A dry-config failure was briefly misread as success this way.

---

## 6. Candidate next slices

Not ranked; pick with the owner. Each is bounded.

**Publish to a package index.** The last step for the open-source goal. Needs a
PyPI account, name reservation, and a release workflow using trusted publishing
so no token enters the repository. The README currently documents installing
from the git URL, which is verified working.

**Adopt a pinned linter configuration.** There is none, so CI runs no linter and
ruff defaults report 23 pre-existing findings across the files touched for
0.4.0. Pin a config, decide which rules apply, fix or explicitly ignore the
backlog, then enforce it in CI. Until then "new modules clean" is manual and
undocumented.

**Live acceptance under the installed path.** 0.4.0 is verified non-live. A
separately authorized run started from an installed copy in a scaffolded
workspace would close the loop. Requires explicit live authority and an adopted
policy authorizing the exact plan.

**`--workspace` as a CLI flag.** Deliberately omitted. Path constants resolve at
import, so a flag parsed later cannot affect them; supporting it means
converting 37 constants across 21 modules to lazy accessors.
`LMRE_WORKSPACE=/path lmre ...` covers the need today.

**A whitespace check in CI.** The whole-tree form fails on intentional Markdown
hard line breaks. Scoping it to a pull-request diff would work.

---

## 7. OmniRoute, if you use it

An OmniRoute MCP server can route work to zero-cost external models to conserve
subscription tokens. Read `docs/omniroute-claude-code.md` and
`.claude/skills/omniroute-offload/SKILL.md` first.

Measured behavior, so you do not rediscover it: routing with an explicit model
works and costs nothing on the free lanes; **no combos are configured**, so
combo-selection tools fail; the registered LMRE context skill is listed but
returns `Skill not found`; and **long generations time out** at the MCP call
boundary, so it is useful for short exchanges and web research but not bulk
drafting.

Obtain current-session approval before transmitting project context, and exclude
credentials, source code, local paths, run identities, raw evidence, model
outputs, and machine-specific configuration. Worker output is advisory discovery
evidence, never acceptance.

---

## 8. What the manager owns

Reading the actual diff, running verification locally, safety and boundary
decisions, integration, staging, and final acceptance. A subagent or external
worker report is discovery evidence, not acceptance. If you cannot verify a
claim, say so plainly rather than repeating it.
