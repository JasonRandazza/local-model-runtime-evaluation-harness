# Discovery

> **Documentation role:** Retained low-level discovery and proposal reference.
> For normal live evaluation, use [managed-runs.md](managed-runs.md). Direct
> `propose` or `execute` use must be explicitly requested and does not inherit
> the managed evidence coordinator.

Observe loopback servers and pinned native-triple artifacts, write an auditable
proposal, and execute one ready family’s preference and RAG pipelines
in-process.

Fake-only Gate A passed on 2026-07-24. A later separately authorized Gemma
execution, `discovery-20260725-004`, sealed PASS across preference, RAG oracle,
and RAG keyword. That consumed authorization does not grant future live access.

Design: `docs/superpowers/specs/2026-07-24-discovery-mvp-design.md`  
Historical accepted evidence: `docs/superpowers/verification/2026-07-24-discovery-20260725-004-pass.md`

## Flow: propose → show → execute

1. **`propose`** (default) — observe Osaurus (`1337`), oMLX (`8100`), and OptiQ (`8080`); match pinned family recipes against on-disk artifacts and server inventory; write `results/discovery/<proposal_id>/proposal.json`; print summary, `proposal_id`, and `executable_families`. Observe-only: does not start or stop servers.
2. **`show <proposal_id>`** — reload and verify the proposal hash; reprint status.
3. **`execute <proposal_id> --family <family_id>`** — run suites for one family listed in `executable_families`. Confirm = invoking `execute` (no interactive `y/N` in MVP).

```bash
./bin/lmre-discover propose
./bin/lmre-discover show discovery-YYYYMMDD-NNN
./bin/lmre-discover execute discovery-YYYYMMDD-NNN --family gemma-4-12b-qat
```

**`dry-config`** validates config wiring and cell JSON without network (Gate A safe):

```bash
./bin/lmre-discover dry-config
```

## Fail-closed partial triples

A family is **ready** only when all three native cells pass: artifact exists, server reachable, and identity matches inventory. Partial triples get `ready: false` with per-cell reasons and never appear in `executable_families`. Execute rejects `--family` values not in that list.

Preference and RAG recipes must agree on the same native triple; mismatch is a discovery error.

## Judge cell

On execute, preference uses the family’s recipe from `config/preference/family-cells.json`. The **judge cell** is the first cell in that recipe (Osaurus-native for each family), not the global `jang_4m__osaurus` default — so Ornith and Qwen are judged by their own Osaurus-native builds.

## Execute pipeline (one family)

Sequential in-process steps (Approach 2 — no subprocess CLIs):

1. Preference: collect → review → judge → tally (`suites/multi-family-preference-v1.json`)
2. RAG oracle: collect + score
3. RAG keyword: collect + score

Matrix measure is **not** part of default execute. First hard failure stops remaining steps; `execution.json` records each step honestly.

## Model placement

Discovery **never** silently copies, moves, scans for, or relocates model
weights. It resolves the checked-in logical artifact template through the
fixed `.lmre/machine-profile.json`, then checks only that exact path. Missing
paths make the cell not ready and the proposal reports the resolved expected
path. Operators correct the profile or placement manually; there is no
automatic `place` behavior.

## Live authorization

Dry-config is non-live. `propose` contacts configured loopback inventories and
`execute` is retained as a low-level diagnostic surface. Use `./bin/lmre` for
normal managed live execution. Policy adoption and initiating live execution
each require an explicit user request; the adopted policy then governs exact
matching plans. Historical PASS evidence is not reusable authority.

## OptiQ lifecycle on execute (A+C)

During low-level preference/RAG collection, OptiQ handling is:

- **Attach (A):** if `:8080` is busy and inventory already lists the cell’s exact `model_id`, reuse that serve and do not kill it on cleanup.
- **Incompatible listener:** fail closed and direct the operator to the managed
  `lmre` path. Managed execution gives the 60-second notice, revalidates exact
  process identity, and uses only exact `SIGINT` then bounded `SIGTERM`.

`--allow-model-switch` (pathway B) is not part of the active baseline. Its
investigation record is preserved in the sibling archive.

## Deferred (not in Gate A)

- `lmre-discover place`
- `confirm_policy: auto_when_ready`
- Execute all ready families in one command
- Custom any-three-model mixes
- Osaurus provider CLI automation
- Matrix measure in default execute
