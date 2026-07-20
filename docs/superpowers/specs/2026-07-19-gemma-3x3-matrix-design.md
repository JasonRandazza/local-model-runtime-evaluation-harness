# Gemma 4 12B QAT 3×3 Native Matrix Design

**Status:** Approved in conversation by Jason on 2026-07-19. This document authorizes implementation planning only. It does not authorize a live campaign, Stage 2B Gate B, plugin rebuild, vault write, or Osaurus-overhead / quality-judge add-ons.

**Approach:** Matrix-first, thin OptiQ Stage 2B-1 proof second (Approach 1).

## Goal

Measure performance of one control base model — **Gemma 4 12B IT QAT** — across three quantization artifacts and three native servers (full 3×3 = nine cells). Prefer automation with safe one-at-a-time lifecycle. Answer which native server+quant pairs are competitive on latency, reliability, and contract success.

This restores the project's original performance-science goal. It is not a day-to-day model-selection product and not a research-grade Stage 2B hardening program.

## Control Artifacts

| Quant label | Artifact |
|---|---|
| JANG_4M | `OsaurusAI/gemma-4-12B-it-qat-JANG_4M` |
| oQ4-fp16 | `avneetsb/gemma-4-12B-it-qat-oQ4-fp16` |
| OptiQ-4bit | `mlx-community/gemma-4-12B-it-qat-OptiQ-4bit` |

## Servers (direct only)

| Server | Direct base URL |
|---|---|
| Osaurus native | `http://127.0.0.1:1337/v1` |
| oMLX | `http://127.0.0.1:8100/v1` |
| OptiQ | `http://127.0.0.1:8080/v1` |

Osaurus-as-router overhead is a **later add-on**, not part of this matrix.

## Cell Policy

Attempt all nine combinations. If a server cannot load an artifact, record the cell as `N/A` with a clear reason, tear down anything started for that cell, and continue.

## Architecture

Two products, one shared measurement core:

| Piece | Role |
|---|---|
| Gemma 3×3 Matrix (primary) | Automated direct-to-native performance campaign |
| Stage 2B-1 Gemma OptiQ smoke (secondary, later) | Thin governed OptiQ path proof; not the matrix engine |
| Stage 2B VibeThinker lane | Frozen historical capital — keep code/tests; do not delete or broaden |

```text
config/matrix/gemma-4-12b-qat-campaign.json
config/matrix/cells/*.json          → 9 cell definitions
suites/gemma-matrix-v1.json         → 3 workloads
matrix runner + server adapters     → start/stop/health + measure
bin/lmre-matrix
results/matrix/...                  → raw.json + report.md (gitignored)
```

### Non-goals (this phase)

- Nine Gate B / Coordinator ceremonies for matrix cells
- Plugin rebuild or contract change
- Full Stage 2B-1 five-finding closeout as a gate for the matrix
- Osaurus routing overhead measurement
- LMSYS-style quality scores, judge models, long RAG corpora
- Dashboards, databases, product packaging
- Concurrent multi-model residency

## Automation And Safety

The matrix CLI owns service lifecycle for the campaign.

Hard rules:

1. One cell at a time — never two model servers resident.
2. Preflight RAM gate — refuse to start if free memory is below a configured floor.
3. Pinned commands only — exact executable + argument arrays from cell/campaign config; no arbitrary shell.
4. Post-stop verify — process absent and target port free before the next cell.
5. Fail closed — load/serve failure → `N/A`, stop what this cell started, continue or halt per campaign flag.

Human role: restore binaries/artifacts once, approve campaign config, review reports, pick finalists, approve any Deep Wiki write, intervene on fail-closed stops.

## Operator / Campaign Flow

```bash
./bin/lmre-matrix --mode screen --campaign config/matrix/gemma-4-12b-qat-campaign.json
# after human finalist selection:
./bin/lmre-matrix --mode finalist --cells <cell-id>,...
```

Per cell the CLI:

1. Ensure ports clear / stop leftover from prior cell.
2. Start that cell’s native server with the pinned artifact.
3. Wait for health + exact model id (else `N/A`).
4. Run screen or finalist requests.
5. Stop that server and verify teardown.
6. Next cell.

## Workloads And Metrics

Suite `gemma-matrix-v1` reuses the three personal-selection workload classes:

1. Short instruction following
2. Strict structured JSON
3. Wiki-style constraint summary

Depth:

- Screen: 1 warm-up + 3 measured per workload
- Finalist: 1 warm-up + 5 measured per workload
- Warm-ups excluded from aggregates
- Two-pass: screen all loadable cells, then finalist only human-picked cells

Per request:

- success / finish reason / error class
- wall-clock total latency
- response-contract pass/fail
- completion and visible token counts when provided; else null
- streaming class: `incremental` | `buffered` | `unknown`
- TTFT and decode tok/s only when streaming is incremental and token evidence is trustworthy; otherwise null
- memory free % before start and after teardown

Per-cell and campaign summaries: success rate, contract pass rate, median/min/max latency (p95 on finalist only), median TTFT (incremental only), median decode tok/s (`EXACT_VISIBLE` only — Option A), median **estimated** decode tok/s from `completion_tokens / (total − TTFT)` (Option B, labeled `est.`), and a 3×3 status table (`PASS` / `FAIL` / `N/A`) plus metric tables in `report.md`.

## Stage 2B Boundary

### Matrix phase (now)

- Do not delete or rewrite accepted Stage 0–2A evidence or Stage 2B-1 VibeThinker implementation/tests.
- Do not run Gate B, authorize Stage 2B run IDs, or require the full five-finding closeout before matrix work.
- New matrix code lives beside Stage 2B; reuse transport/measurement where simpler.
- Plugin `0.3.0` remains unchanged unless Jason explicitly approves a rebuild.

### After first matrix screen works

- Bounded Stage 2B-1 retarget: Gemma OptiQ profile + small governed smoke.
- Fix only findings that block that smoke (likely wall-clock deadline + strict SSE).
- Leave cleanup-lock / durable journal / reseal reconciliation as labeled lab debt unless they block the smoke.

### Later add-ons (separate proposals)

1. Osaurus routing overhead on winning or all loadable cells
2. Quality evaluation: LMSYS-style / judge models / longer RAG corpora

Keep those after the performance matrix (including Option A latency/throughput breakdown) is useful. Do not fold quality judges into the first native 3×3 comparison.

## Likely Files

- `config/matrix/gemma-4-12b-qat-campaign.json`
- `config/matrix/cells/*.json` (nine cells)
- `suites/gemma-matrix-v1.json` (or reference personal-selection suite)
- `src/local_model_runtime_evaluation/matrix_runner.py`
- Small server adapters for Osaurus / oMLX / OptiQ start-stop-health
- `bin/lmre-matrix`
- `tests/test_matrix_*.py` (deterministic fakes only; no live endpoints in unit tests)
- Short docs pointer; Stage 2B-1 Gemma retarget note when that phase starts

## Definition Of Done

- Automated screen of all nine cells with safe one-at-a-time lifecycle
- Clear `PASS` / `FAIL` / `N/A` matrix plus per-cell reports under `results/matrix/`
- Finalist re-run for human-picked cells
- Jason can answer which loadable Gemma QAT native pairs are competitive on latency, reliability, and contract success — without Osaurus routing or quality judges yet

## Effort And Uncertainties

- Effort: medium
- Uncertainties: OptiQ binary availability on PATH; which off-diagonal cells load; exact Osaurus load/unload automation surface

## Explicit Confirmations

- Stage 2B-1 VibeThinker path and its five findings remain deferred lab capital, not deleted.
- Stage 2B-1 is not the measurement system for the 3×3 matrix.
- This design does not authorize live runs until Jason approves an implementation plan and a live campaign.
