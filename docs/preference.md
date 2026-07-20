# Gemma Preference Quality POC

Pairwise human preference on the three screen **PASS** cells (`jang_4m__osaurus`, `oq4_fp16__omlx`, `optiq_4bit__optiq`) using a six-prompt pack. Separate from `lmre-matrix` performance reports; Stage 0–2B machinery stays frozen.

**RAG oracle Phase 1:** oracle-injected gold context fact-hit scoring on the same three cells — see [rag.md](rag.md).

## Prerequisites

Same artifact paths, credentials, RAM floor, and server rules as the matrix campaign for these three cells — see [matrix.md](matrix.md) (Osaurus Keychain, oMLX loopback key, OptiQ `:no-think` ids, `20%` free RAM).

## Non-live check

```bash
PYTHONPATH=src python3 -m unittest \
  tests.test_preference_config \
  tests.test_preference_collect \
  tests.test_preference_review \
  tests.test_preference_tally \
  tests.test_preference_judge \
  tests.test_preference_cli -v
```

Unit tests use fakes only — no live Osaurus, oMLX, or OptiQ contact.

## Validate config

```bash
./bin/lmre-preference collect --dry-config
```

Prints JSON with `ok: true`, default cell ids, and `prompts: 6`. No network or server start.

Judge dry-config (after review):

```bash
./bin/lmre-preference judge --run results/preference/<run-id> --dry-config
```

Prints JSON with `ok: true`, default judge cell, run dir, and pair count. No network or server start.

## Workflow

1. **Collect** — one cell at a time; writes `answers/` under a timestamped run dir.
2. **Review** — builds blind `review.md`, `pairs.json`, and an empty `judgments.json` stub.
3. **Judge** — local Gemma cell scores each blind pair into `judgments.json` (or edit manually).
4. **Tally** — scores judgments and writes `report.md`.

```bash
./bin/lmre-preference collect

./bin/lmre-preference review --run results/preference/gemma-preference-<timestamp>

./bin/lmre-preference judge --run results/preference/gemma-preference-<timestamp>
# optional: inspect / edit judgments.json

./bin/lmre-preference tally --run results/preference/gemma-preference-<timestamp>
```

Default judge cell: `jang_4m__osaurus`. Override with `--judge-cell`:

```bash
./bin/lmre-preference judge --run results/preference/<run-id> \
  --judge-cell oq4_fp16__omlx
```

### Self-preference bias

Pairs that include the judge cell are still judged. For this POC, self-preference bias is accepted. To avoid a cell judging its own answers, override `--judge-cell` to a different candidate cell.

Human edit of `judgments.json` remains a valid fallback or override after judge.

Subset collect example:

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

Under `results/preference/gemma-preference-<timestamp>/`:

- `raw.json` — suite id, cell ids, timestamps; judge adds `judge_cell_id`, `judged_at`
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
- Pinned cell start argv only; harness starts and stops only what each cell defines.
- One cell at a time; verify port free and RAM floor between cells.

## Follow-ons

- **RAG oracle and keyword retrieval** — see [rag.md](rag.md)
- **Osaurus routing overhead** — direct vs routed latency tax for oQ4 and OptiQ — see [overhead.md](overhead.md)

This POC remains collect → review → judge (or human edit) → tally.
