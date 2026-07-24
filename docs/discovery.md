# Discovery MVP (Gate A)

Observe loopback servers and pinned native-triple artifacts, write an auditable proposal, and execute one ready family’s preference + RAG pipelines in-process. Gate A is fake-only; live propose/execute requires separate authorization after Gate A closes.

Design: `docs/superpowers/specs/2026-07-24-discovery-mvp-design.md`  
Gate A checklist: `docs/stage-discovery-gate-a.md`

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

Discovery **never** silently copies, moves, or relocates model weights. Match checks pinned `artifact_path` only. Missing paths → cell not ready; the proposal reports the expected path. Operators fix gaps manually or via future explicit `place` UX (not implemented in Gate A).

## Live authorization

Gate A tests and docs do not authorize live loopback contact, Stage 2 run IDs, provider edits, or plugin changes. Live `propose` / `execute` against real servers requires Jason’s separate current-session authorization after Gate A acceptance.

## Deferred (not in Gate A)

- `lmre-discover place`
- `confirm_policy: auto_when_ready`
- Execute all ready families in one command
- Custom any-three-model mixes
- Osaurus provider CLI automation
- Matrix measure in default execute
