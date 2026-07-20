# Gemma Preference Quality POC Design

**Status:** Approved in conversation by Jason on 2026-07-19. This document authorizes implementation planning only. It does not authorize a live preference collect, Stage 2B Gate B, plugin rebuild, local judge automation, RAG corpora, or Osaurus routing-overhead measurement.

**Depends on:** completed Gemma 3×3 performance screen + Option A/B metrics (`docs/superpowers/specs/2026-07-19-gemma-3x3-matrix-design.md`).

## Goal

Run a thin **LMSYS-style pairwise preference** POC on the three screen **PASS** cells only, with **human judgment first** and a clean seam for a local judge later. Answer which of the three winners humans prefer on a small preference pack, independent of latency.

Default cells:

- `jang_4m__osaurus`
- `oq4_fp16__omlx`
- `optiq_4bit__optiq`

## Approach

**Collect-then-review** via a separate CLI (`bin/lmre-preference`), not folded into `lmre-matrix` performance reports.

1. **Collect** — one cell at a time; reuse matrix cell configs + lifecycle; save answers.
2. **Review** — emit a blind pairwise pack (A/B shuffled; cell ids hidden from the checklist body).
3. **Judge (human)** — fill `judgments.json` with `A` | `B` | `tie`.
4. **Tally** — win/tie/loss rates per cell; write `report.md`.

Later (out of this POC): `review --judge local` writes the same `judgments.json` shape.

## Operator Flow

```bash
./bin/lmre-preference collect \
  --cells jang_4m__osaurus,oq4_fp16__omlx,optiq_4bit__optiq

./bin/lmre-preference review --run results/preference/<run-id>
# human edits judgments.json (or checklist → judgments)

./bin/lmre-preference tally --run results/preference/<run-id>
```

`--cells` override is allowed; default is the three PASS cells above.

### Collect

- Reuse matrix cell JSON, server adapters, auth (Osaurus Keychain), OptiQ `--no-auth`, oMLX loopback `--api-key`, RAM floor, one-at-a-time start/stop.
- For each cell: start → wait ready → run preference pack → stop/teardown.
- Optional single warm-up per prompt is allowed but not required for the POC; measured answers are the ones used for pairs.
- Persist per-cell answer files under the run directory.

### Review

- Round-robin pairs on collected cells (3 cells → 3 pairs).
- For each preference prompt × pair: one blind judgment item.
- Shuffle which cell is A vs B per item; store mapping only in `pairs.json`.
- Write human-facing `review.md` plus machine `pairs.json`.

### Tally

- Read `judgments.json` + `pairs.json`.
- Report wins / ties / losses and win-rate (ties ignored in win-rate denominator).
- Write `report.md`. Latency fields remain metadata only — not the preference criterion.

## Preference Pack

**Suite:** `suites/gemma-preference-v1.json`, revision `1`  
**Size:** 6 prompts (text quality; not JSON contract workloads)

Themes:

1. Clear explanation of a tradeoff  
2. Practical local-ops advice  
3. Concise multi-step plan  
4. Careful “I don’t know / uncertain” handling  
5. Rewrite for clarity without losing meaning  
6. Short comparison with a recommendation  

**Judgment volume:** 3 pairs × 6 prompts = **18** human labels.

**Per answer record:** prompt id, cell id, model id, full answer text, success/error, total latency, TTFT when incremental streaming evidence exists.

**Labels:** `A` | `B` | `tie` only.

## Artifacts

Under `results/preference/<run-id>/` (gitignored like other results):

| Path | Role |
|------|------|
| `answers/<cell_id>.json` | Collected responses per cell |
| `pairs.json` | Blind pair definitions + A/B mapping |
| `review.md` | Human-facing blind checklist |
| `judgments.json` | Human (later: judge) labels |
| `report.md` | Tally summary |
| `raw.json` | Run metadata (cells, suite, timestamps) |

## Non-goals (this POC)

- Rubric / absolute quality scores from a judge model  
- Longer RAG / grounded corpora  
- Osaurus routing overhead  
- Folding preference results into the performance 3×3 matrix report  
- Stage 2B Gate B, plugin rebuild, vault writes  
- Live unit tests against real endpoints  

## Follow-ons (separate designs after this POC)

1. Local judge automation filling the same `judgments.json`  
2. Longer RAG / grounded corpus tasks  
3. Osaurus routing overhead on winners  

## Likely Files

- `bin/lmre-preference`
- `suites/gemma-preference-v1.json`
- `src/local_model_runtime_evaluation/preference_*.py`
- `tests/test_preference_*.py` (fakes only)
- `docs/preference.md`
- Pointer from `docs/matrix.md` to the preference POC

## Definition Of Done

- Collect → blind review pack → human judgments → tally works on fakes in CI.
- Live collect of the three PASS cells works when Jason explicitly authorizes it in-session.
- Jason can answer which of the three winners humans prefer on `gemma-preference-v1`, independent of latency.

## Effort And Uncertainties

- Effort: small–medium  
- Uncertainties: preference prompt wording quality; whether OptiQ cells must keep `:no-think` model ids (yes — reuse matrix cell configs as-is)

## Explicit Confirmations

- Separate CLI (`lmre-preference`), not a `lmre-matrix` mode  
- Human-first hybrid; local judge is a later seam only  
- New 6-prompt preference pack; not the performance contract suite  
- Default cells = three screen PASS cells; round-robin pairwise  
- Deferred after POC: local judge, RAG, Osaurus overhead  
