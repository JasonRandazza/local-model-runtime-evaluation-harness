# Gemma Preference Local Judge Design

**Status:** Approved in conversation by Jason on 2026-07-19. This document authorizes implementation planning only. It does not authorize a live judge run, Stage 2B Gate B, plugin rebuild, RAG corpora, or Osaurus routing-overhead measurement.

**Depends on:** Gemma preference quality POC (`docs/superpowers/specs/2026-07-19-gemma-preference-quality-poc-design.md`) and an existing preference run with `pairs.json` + `answers/`.

## Goal

Automate pairwise preference labels by asking one local Gemma cell to choose `A` | `B` | `tie` for each blind pair, writing the same `judgments.json` shape humans edit so `tally` stays unchanged.

Default judge cell: `jang_4m__osaurus`.

## Approach

**Thin `judge` subcommand** (not folded into `review`):

```bash
./bin/lmre-preference judge --run results/preference/<run-id> \
  [--judge-cell jang_4m__osaurus]
```

1. **Collect** (existing) — answers for candidate cells.
2. **Review** (existing) — blind pack + `pairs.json` + empty `judgments.json` stub.
3. **Judge (local)** — start judge cell once; score each pair; write judgments + raw log.
4. **Tally** (existing) — operator still runs `tally` after judgments are complete.

Human edit of `judgments.json` remains a valid fallback or override.

## Operator Flow

```bash
./bin/lmre-preference collect
./bin/lmre-preference review --run results/preference/<run-id>
./bin/lmre-preference judge --run results/preference/<run-id>
# optional: inspect / edit judgments.json
./bin/lmre-preference tally --run results/preference/<run-id>
```

`--dry-config` on judge: load judge cell JSON + verify run dir has `pairs.json` and `answers/`; print `{"ok": true, ...}`; no network or server start.

**Live judge requires Jason’s in-session authorization.**

## Judge Protocol

For each pair, send prompt text + answer A + answer B with **no cell ids**. Require JSON:

```json
{"winner": "A"|"B"|"tie", "reason": "<one short sentence>"}
```

- `winner` must be exactly `A`, `B`, or `tie` (case-sensitive).
- `reason` is optional; if present, store it; truncate to 500 characters.
- Fail closed on bad JSON or invalid `winner`.
- **One automatic retry** on parse failure for that pair; then leave `winner: null` and record the error.

### Self-preference

Pairs that include the judge cell are still judged. Document that self-preference bias is accepted for this POC. Operators who want an unbiased judge for Osaurus answers should override `--judge-cell` to another cell.

## Lifecycle

Reuse matrix cell configs, `build_server`, credentials (Osaurus Keychain), RAM floor awareness as in preference collect:

1. Resolve credential for judge cell server.
2. Start judge cell; wait ready.
3. For each pair in `pairs.json` order: chat → parse → optional retry.
4. Stop judge cell in `finally`.

One in-flight request; serial pairs only.

## Artifacts

Under the existing run directory:

| Path | Role |
|------|------|
| `judgments.json` | `{ "judgments": [ { "pair_id", "winner", "reason"? } ] }` — tally uses `pair_id` + `winner` only |
| `judge_raw.json` | Per-pair raw model text, parse status, errors, retry count |
| `raw.json` | Append / update `judge_cell_id`, `judged_at` (and related metadata) |

`review.md` and `pairs.json` are not rewritten by judge.

## Testing

Fakes only in unit tests:

- Happy-path parse; invalid winner; malformed JSON → retry once → null.
- Judge writer produces `judgments.json` / `judge_raw.json` without live endpoints.
- CLI dry-config; live path mocked.
- Tally still succeeds when optional `reason` fields are present.

## Non-goals

- RAG / grounded corpora
- Osaurus routing-overhead measurement
- Multi-judge ensembles or absolute rubric scores
- Auto-tally after judge
- Changing preference suite or default collect cells
- Stage 2B / plugin work
- Ornith / Qwen (or other non-Gemma) cells in this slice

## Likely Files

- `src/local_model_runtime_evaluation/preference_judge.py`
- `tests/test_preference_judge.py`
- Modify: `preference_cli.py`, `docs/preference.md`
- Spec / plan under `docs/superpowers/`

## Definition Of Done

- Fake unit tests green; dry-config works.
- On Jason’s authorize: live `judge` on an existing Gemma preference run fills judgments; `tally` produces `report.md`.
- Docs state self-preference bias and live-auth rule.

## Explicit Confirmations

- Separate `judge` subcommand (Approach 1), not `review --judge local`
- Default judge cell: `jang_4m__osaurus`; override via `--judge-cell`
- JSON + optional `reason`; fail closed; one retry
- Self-pairs involving the judge cell are judged (bias documented)
- Tally unchanged; human edit still allowed
