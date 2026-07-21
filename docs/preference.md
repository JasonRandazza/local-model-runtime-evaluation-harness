# Multi-Family Preference Quality POC

Family-first pairwise human preference on matrix **PASS** cells using a six-prompt pack. Separate from `lmre-matrix` performance reports; Stage 0–2B machinery stays frozen.

**RAG oracle Phase 1:** oracle-injected gold context fact-hit scoring — see [rag.md](rag.md).

## Family selection

Preference resolves a matrix **family** first, then that family’s cell recipe:

1. `--family <family_id>` if set
2. Else `config/preference/defaults.json` → `family_id` (checked-in default: **`gemma-4-12b-qat`**)
3. Else fail closed — family is required

Cell ids come from `--cells` or the selected family’s recipe in `config/preference/family-cells.json`. Every cell must load for the selected matrix family; mixed-family lists are rejected.

### Default family (Gemma)

`config/preference/defaults.json` names the repo default explicitly (not a silent Python constant):

```json
{
  "family_id": "gemma-4-12b-qat",
  "cells": [
    "jang_4m__osaurus",
    "oq4_fp16__omlx",
    "optiq_4bit__omlx",
    "optiq_4bit__optiq"
  ]
}
```

### Ornith override

```bash
./bin/lmre-preference collect --dry-config --family ornith-35b
```

Ornith recipe (four screen 12/12 cells): `ornith_jang_4m__omlx`, `ornith_oq4__omlx`, `ornith_optiq_4bit__omlx`, `ornith_optiq_4bit__optiq`.

### Qwen override

```bash
./bin/lmre-preference collect --dry-config --family qwen36-35b-a3b
```

Qwen recipe (four screen PASS cells from `qwen36-35b-a3b-3x3-screen-20260720-201114`): `qwen_mxfp4__osaurus`, `qwen_oq4__omlx`, `qwen_optiq_4bit__omlx`, `qwen_optiq_4bit__optiq`.

### Pair count

Four cells → **6 unordered pairs per prompt** (**36** judgments across the six-prompt suite). Historical **3-cell** Gemma preference runs remain valid artifacts; review and tally read `cell_ids` from each run’s `raw.json`.

## Prerequisites

Same artifact paths, credentials, RAM floor, and server rules as the matrix campaign for the selected family’s cells — see [matrix.md](matrix.md) (Osaurus Keychain, oMLX loopback key, OptiQ `:no-think` ids, `20%` free RAM).

## Non-live check

```bash
PYTHONPATH=src /opt/homebrew/bin/python3 -m unittest \
  tests.test_preference_config \
  tests.test_preference_collect \
  tests.test_preference_review \
  tests.test_preference_tally \
  tests.test_preference_judge \
  tests.test_preference_cli -v
```

Unit tests use fakes only — no live Osaurus, oMLX, or OptiQ contact.

## Validate config (dry-config)

Gemma default (four cells):

```bash
./bin/lmre-preference collect --dry-config
```

Prints JSON with `ok: true`, `"family_id": "gemma-4-12b-qat"`, four default cell ids (including `optiq_4bit__omlx`), and `prompts: 6`. No network or server start.

Ornith four-cell recipe:

```bash
./bin/lmre-preference collect --dry-config --family ornith-35b
```

Prints JSON with `ok: true`, `"family_id": "ornith-35b"`, four `ornith_*` cell ids, and `prompts: 6`.

Qwen four-cell recipe:

```bash
./bin/lmre-preference collect --dry-config --family qwen36-35b-a3b
```

Prints JSON with `ok: true`, `"family_id": "qwen36-35b-a3b"`, four `qwen_*` cell ids, and `prompts: 6`.

Judge dry-config (after review):

```bash
./bin/lmre-preference judge --run results/preference/<run-id> --dry-config
```

Prints JSON with `ok: true`, default judge cell, run dir, and pair count. No network or server start.

## Workflow

1. **Collect** — one cell at a time; writes `answers/` under a timestamped run dir.
2. **Review** — builds blind `review.md`, `pairs.json`, and an empty `judgments.json` stub.
3. **Judge** — local judge cell scores each blind pair into `judgments.json` (or edit manually).
4. **Tally** — scores judgments and writes `report.md`.

```bash
./bin/lmre-preference collect

./bin/lmre-preference review --run results/preference/gemma-preference-<timestamp>

./bin/lmre-preference judge --run results/preference/gemma-preference-<timestamp>
# optional: inspect / edit judgments.json

./bin/lmre-preference tally --run results/preference/gemma-preference-<timestamp>
```

Ornith live collect (only after separate operator authorize):

```bash
./bin/lmre-preference collect --family ornith-35b
```

Qwen live collect (only after separate operator authorize):

```bash
./bin/lmre-preference collect --family qwen36-35b-a3b
```

For Qwen judging, prefer a PASS cell that is not under test self-bias pressure if desired, e.g. `--judge-cell qwen_optiq_4bit__optiq` or `qwen_mxfp4__osaurus`.

Default judge cell: `jang_4m__osaurus`. Override with `--judge-cell`:

```bash
./bin/lmre-preference judge --run results/preference/<run-id> \
  --judge-cell oq4_fp16__omlx
```

### Self-preference bias

Pairs that include the judge cell are still judged. For this POC, self-preference bias is accepted. To avoid a cell judging its own answers, override `--judge-cell` to a different candidate cell.

Human edit of `judgments.json` remains a valid fallback or override after judge.

Subset collect example (must belong to the selected family):

```bash
./bin/lmre-preference collect \
  --cells jang_4m__osaurus,oq4_fp16__omlx
```

Review shuffle seed (default `0`):

```bash
./bin/lmre-preference review --run results/preference/<run-id> --seed 42
```

## Judgment labels

| Label | Meaning |
| --- | --- |
| `A` | First answer in the pair wins |
| `B` | Second answer wins |
| `tie` | No preference |

Do not look up cell ids while judging; the review pack hides them in the markdown body. Local judge prompts are also blind (no cell ids). Optional `reason` fields in `judgments.json` are ignored by tally.

## Outputs

Under `results/preference/<family>-preference-<timestamp>/` (or historical `gemma-preference-*` dirs):

- `raw.json` — `family_id`, suite id, cell ids, timestamps; judge adds `judge_cell_id`, `judged_at`
- `answers/<cell_id>.json` — per-cell model answers
- `review.md` — blind pairwise checklist
- `pairs.json` — pair mapping (cell ids for tally only)
- `judgments.json` — winners (`A`, `B`, or `tie`); judge may add optional `reason`
- `judge_raw.json` — per-pair raw model text and parse status (after judge)
- `report.md` — per-cell wins, losses, ties, win rate (after tally)

Latency is not used for preference scoring.

## Safety

- **Live collect requires Jason's in-session authorization.** Do not run collect without explicit operator approval.
- **Live judge requires Jason's in-session authorization.** Do not run `judge` without explicit operator approval.
- **Stage 2B remains frozen.** These docs do not authorize Gate B, Stage 2B run IDs, or plugin changes.
- Pinned cell start argv only; harness starts and stops only what each cell defines.
- One cell at a time; verify port free and RAM floor between cells.

## Follow-ons

- **RAG oracle and keyword retrieval** — see [rag.md](rag.md)
- **Osaurus routing overhead** — direct vs routed latency tax for oQ4 and OptiQ — see [overhead.md](overhead.md)

This POC remains collect → review → judge (or human edit) → tally.
