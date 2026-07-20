# Osaurus Routing Overhead Design

**Status:** Approved in conversation by Jason on 2026-07-20. This document authorizes implementation planning only. It does not authorize a live overhead run, Stage 2B Gate B, plugin rebuild, folding into `lmre-matrix --mode overhead`, equal-weight full metric pack expansion, Ornith/Qwen cells, or RAG/preference changes.

**Depends on:** Gemma 3×3 matrix on `main` (screen winners `oq4_fp16__omlx`, `optiq_4bit__optiq`). Reuses suite `gemma-matrix-v1` at screen depth.

**Approach:** Thin `bin/lmre-overhead` CLI (Approach 1). Approach 2 (`lmre-matrix --mode overhead`) is a documented later option only.

## Goal

Measure the **Osaurus router tax** for the two non-Osaurus screen winners: oQ4-fp16 and OptiQ-4bit. For each pair, compare **direct native** vs **the same model via Osaurus** (`http://127.0.0.1:1337/v1`).

Answer: how much median total latency (and secondarily TTFT) grows when daily traffic goes through Osaurus instead of the native port.

## Locked Decisions

| Topic | Choice |
| --- | --- |
| Comparison set | Only `oq4_fp16` and `optiq_4bit` (not JANG / Osaurus-native) |
| Lifecycle | Hybrid: harness owns backend start/stop for both legs; Jason owns Osaurus + providers |
| Depth | Matrix screen suite + screen-depth reps |
| Primary metric | Δ median total latency (routed − direct) |
| Secondary metric | Δ median TTFT |
| Later metrics | Equal-weight full pack (total + TTFT + estimated decode tok/s) — out of this phase |
| Structure | New `lmre-overhead` now; matrix `--mode overhead` later option |

## Scope

### In scope

- `bin/lmre-overhead` with `dry-config`, `run`, and report (report may be written by `run`)
- Two pairs:
  - `oq4_fp16`: direct cell `oq4_fp16__omlx` (`:8100`) vs routed via `:1337`
  - `optiq_4bit`: direct cell `optiq_4bit__optiq` (`:8080`) vs routed via `:1337`
- Pair configs that pin direct cell path, backend start cell, routed `base_url`, and exact routed `model_id`
- Reuse matrix measure/transport/credentials/RAM floor/screen depth
- Paired report: Δ median total (primary), Δ median TTFT (secondary)
- Fakes-only unit tests; live `run` requires Jason’s in-session authorization

### Out of scope

- JANG / `jang_4m__osaurus` pair
- Implementing Approach 2 (`lmre-matrix --mode overhead`) in this phase
- Equal-weight full metric pack (metrics option C)
- Starting, stopping, signaling, restarting, or configuring Osaurus or providers
- Stage 2B / plugin `0.3.0` rebuild / Gate B
- Ornith / Qwen wiring, RAG, preference/judge changes

## Operator Flow

Per pair (`oq4_fp16`, then `optiq_4bit`), in order:

1. **Prep (Jason)** — Osaurus listening on `:1337` with a provider exposing the target backend. Confirm the routed model id via inventory. Put that **exact** id in the pair config (often `omlx/...` for oMLX; OptiQ provider id as configured).
2. **Direct leg (harness)** — Start only the native backend; measure screen suite on `:8100` or `:8080`; stop backend; verify port free + RAM floor.
3. **Routed leg (harness)** — Leave Osaurus up. Start the **same** backend again (provider needs it); measure the same suite against `http://127.0.0.1:1337/v1` with the configured routed `model_id`; stop **only** the backend. Never touch Osaurus lifecycle or provider config.
4. **Next pair** — After ports free and RAM OK.

### Fail-closed

- Missing or incorrect routed `model_id` → fail that pair (do not invent ids)
- Backend start failure or port busy → fail/skip with reason
- Osaurus not listening on `1337` before routed leg → fail that leg early
- Live `run` without in-session authorization → not allowed

### CLI shape

```bash
./bin/lmre-overhead --dry-config
./bin/lmre-overhead run --pairs oq4_fp16,optiq_4bit
./bin/lmre-overhead report --run results/overhead/<id>
```

(`run` may write `report.md` in-place; a separate `report` subcommand is acceptable if simpler.)

## Architecture

| Piece | Role |
| --- | --- |
| `config/overhead/pairs/*.json` | Pair id, direct cell path, routed `base_url` (`http://127.0.0.1:1337/v1`), routed `model_id`, backend cell reference |
| `overhead_runner.py` | Orchestrate direct → routed; reuse `build_server`, matrix screen measure path, credentials, RAM floor |
| `overhead_report.py` | Paired deltas; primary Δ median total; secondary Δ median TTFT |
| `bin/lmre-overhead` | CLI entry |
| `docs/overhead.md` | Operator guide + live checklist |
| `tests/test_overhead_*.py` | Fakes only |

**Reuse, don’t fork:** matrix cells `oq4_fp16__omlx` / `optiq_4bit__optiq`, suite `gemma-matrix-v1`, screen depth, `LoopbackTransport`, auth/`--api-key`/`--no-auth` patterns, RAM floor.

**Harness must never:** start, stop, configure, or edit Osaurus or its providers. `service_lifecycle_actions` against Osaurus remain zero from this tool’s perspective (backend-only lifecycle).

## Outputs

Under `results/overhead/<run-id>/` (gitignored like other results):

- `raw.json` — pairs, legs, timestamps, cell refs, routed model ids
- Per-leg summaries / observations (matrix-shaped enough to compute medians)
- `report.md` — table: pair | direct median total | routed median total | **Δ total** | Δ TTFT | status

Latency deltas are the product answer. Quality/preference is out of scope.

## Later Options (Not This Phase)

### Approach 2 — `lmre-matrix --mode overhead`

Fold overhead pairs into the matrix campaign runner instead of a separate binary.

| | vs Approach 1 (chosen now) |
| --- | --- |
| **Pros** | Single operator entrypoint (`lmre-matrix`); shared campaign/report machinery; fewer docs surfaces |
| **Cons** | Mixes “native 3×3 science” with “router tax”; more conditionals in an already busy runner; harder to keep hybrid Osaurus-untouched lifecycle obvious; blurs matrix PASS/FAIL semantics with pair deltas |

Keep Approach 1 until overhead is proven useful; revisit Approach 2 only if maintaining two CLIs becomes the real cost.

### Metrics pack C — equal-weight full deltas

Later expansion: report Δ median total, Δ median TTFT, and Δ estimated decode tok/s with equal weight (still labeled when estimated / incomparable). This phase ships A (Δ total primary, Δ TTFT secondary) only.

## Stage 2B Boundary

- Do not run Gate B, authorize Stage 2B run IDs, or rebuild plugin `0.3.0`.
- Do not modify Stage 0–2A accepted evidence or Stage 2B-1 frozen paths.
- Overhead code lives beside matrix/preference/RAG, not inside Stage 2B inference authority.

## Definition Of Done

- Dry-config + fake unit tests green
- Under separate live authorization: both pairs run; `report.md` shows Δ median total and Δ median TTFT
- Docs cover hybrid lifecycle, routed model id pinning, and live smoke checklist
- This spec records Approach 2 and metrics pack C as later options only
- Stage 2B / plugin untouched

## Spec Self-Check

| Item | Covered |
| --- | --- |
| Two pairs only (oQ4, OptiQ) | Yes |
| Hybrid lifecycle; Osaurus operator-owned | Yes |
| Screen suite + depth | Yes |
| Δ total primary, Δ TTFT secondary | Yes |
| Approach 1 now; Approach 2 later with pros/cons | Yes |
| Metrics C later | Yes |
| No live authorize in this doc | Yes |
| Fakes only in unit tests | Yes |
