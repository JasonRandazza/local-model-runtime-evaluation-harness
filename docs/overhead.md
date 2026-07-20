# Osaurus Routing Overhead

Measure the **Osaurus router tax** for the two non-Osaurus screen winners: oQ4-fp16 and OptiQ-4bit. For each pair, compare **direct native** (`:8100` or `:8080`) vs **the same model via Osaurus** (`http://127.0.0.1:1337/v1`). Separate from `lmre-matrix` 3×3 science and `lmre-preference`; Stage 0–2B machinery stays frozen.

**Related:** matrix campaign — see [matrix.md](matrix.md); preference POC — see [preference.md](preference.md); RAG oracle — see [rag.md](rag.md).

## Hybrid lifecycle

The harness **starts and stops only the native backend** for both legs. Jason owns Osaurus and provider configuration throughout:

1. **Prep (operator)** — Osaurus listening on `:1337` with a provider exposing the target backend. Confirm the routed model id via inventory; pin that **exact** id in `config/overhead/pairs/*.json`.
2. **Direct leg (harness)** — Start only the native backend; measure the screen suite on the direct port; stop backend; verify port free and RAM floor.
3. **Routed leg (harness)** — Leave Osaurus up. Start the **same** backend again (provider needs it); measure the same suite against `http://127.0.0.1:1337/v1` with the configured routed `model_id`; stop **only** the backend. Never start, stop, or configure Osaurus.
4. **Next pair** — After ports free and RAM OK.

If `:8100` is already busy, the harness matches matrix behavior and runs `omlX stop` before owning the serve. OptiQ still requires `:8080` free (stop Lab/`optiq serve` yourself first).

The harness never starts, stops, signals, or configures Osaurus or its providers.

## Live prep checklist

Before `./bin/lmre-overhead run`:

- [ ] Osaurus listening on `:1337` (`GET /health` or inventory probe succeeds).
- [ ] Provider for oQ4 and/or OptiQ backend is connected and exposes the target model.
- [ ] Routed model ids in `config/overhead/pairs/oq4_fp16.json` and `optiq_4bit.json` match live inventory **exactly** (often `omlx/...` for oMLX; OptiQ provider id as configured).
- [ ] Artifact paths in `config/matrix/cells/` exist; `optiq` on `PATH` for OptiQ pair.
- [ ] Osaurus Keychain credential stored (see [matrix.md](matrix.md)).
- [ ] Other heavy models unloaded; RAM above the campaign floor (`20%` free).
- [ ] **Live run requires Jason's in-session authorization.** Do not run without explicit operator approval.

## Non-live check

```bash
PYTHONPATH=src python3 -m unittest \
  tests.test_overhead_config \
  tests.test_overhead_runner \
  tests.test_overhead_report \
  tests.test_overhead_cli -v
```

Unit tests use fakes only — no live Osaurus, oMLX, or OptiQ contact.

## Validate config

```bash
./bin/lmre-overhead --dry-config
./bin/lmre-overhead run --dry-config
```

Prints JSON with `ok: true`, default pair ids (`oq4_fp16`, `optiq_4bit`), per-pair `direct_cell_id` / `routed_model_id` / `routed_base_url`, `suite_id: gemma-matrix-v1`, and `mode: screen`. No network or server start.

## Workflow

```bash
./bin/lmre-overhead run --pairs oq4_fp16,optiq_4bit
./bin/lmre-overhead report --run results/overhead/overhead-<timestamp>
```

`run` writes `raw.json` and `report.md` under `results/overhead/overhead-<timestamp>/`. Use `report` to regenerate `report.md` from an existing run.

Optional filters: `--pairs id,id`, `--pairs-root PATH`, `--cells-root PATH`, `--suite PATH`, `--results-dir PATH`. Depth is fixed to matrix `screen`.

## Metrics

Primary: **Δ median total latency** (routed − direct). Secondary: **Δ median TTFT**.

Report table columns: pair | direct median total | routed median total | Δ total | Δ TTFT | direct status | routed status.

A full equal-weight metric pack (including estimated decode tok/s) is a **later expansion** (metrics pack C). This phase ships Δ total primary and Δ TTFT secondary only.

## Outputs

Under `results/overhead/overhead-<timestamp>/`:

- `raw.json` — pairs, legs, timestamps, cell refs, routed model ids, summaries
- `report.md` — paired delta table
- `logs/` — backend server stdout/stderr for legs this run started

## Later options (not this phase)

### Approach 2 — `lmre-matrix --mode overhead`

Fold overhead pairs into the matrix campaign runner instead of a separate binary.

| | vs Approach 1 (chosen now) |
| --- | --- |
| **Pros** | Single operator entrypoint (`lmre-matrix`); shared campaign/report machinery; fewer docs surfaces |
| **Cons** | Mixes "native 3×3 science" with "router tax"; more conditionals in an already busy runner; harder to keep hybrid Osaurus-untouched lifecycle obvious; blurs matrix PASS/FAIL semantics with pair deltas |

Keep Approach 1 until overhead is proven useful; revisit Approach 2 only if maintaining two CLIs becomes the real cost.

### Metrics pack C — equal-weight full deltas

Later expansion: report Δ median total, Δ median TTFT, and Δ estimated decode tok/s with equal weight (still labeled when estimated / incomparable).

## Safety

- Pinned backend start argv only; harness lifecycle touches backend cells only.
- One pair at a time (direct then routed); verify port free and RAM floor between legs.
- Osaurus not listening on `:1337` before the routed leg → fail that leg early.
- Do not run live overhead without explicit operator authorization.
