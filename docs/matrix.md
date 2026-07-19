# Gemma 4 12B QAT 3×3 Matrix

Direct native comparison of three control artifacts across Osaurus (`1337`), oMLX (`8100`), and OptiQ (`8080`). One cell at a time; unloadable cells become `N/A`. Stage 0–2B machinery stays frozen — this path does not use Gate B, plugin tools, or Stage 2B inference authority.

## Prerequisites

- Artifact paths in `config/matrix/cells/` must exist on disk (JANG under `MLXModels/OsaurusAI/`, oQ4 and OptiQ-4bit under Hugging Face cache).
- Restore `optiq` on `PATH` before OptiQ cells (`which optiq`).
- Unload other heavy models; keep RAM above the campaign floor (`20%` free).

## Non-live check

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -name 'test_matrix_*' -v
```

Unit tests use fakes only — no live Osaurus, oMLX, or OptiQ contact.

## Validate config

```bash
./bin/lmre-matrix --dry-config \
  --campaign config/matrix/gemma-4-12b-qat-campaign.json
```

## Live screen (operator)

Run all nine cells in screen mode first:

```bash
./bin/lmre-matrix --mode screen \
  --campaign config/matrix/gemma-4-12b-qat-campaign.json
```

Subset example:

```bash
./bin/lmre-matrix --mode screen --cells jang_4m__osaurus,oq4_fp16__omlx \
  --campaign config/matrix/gemma-4-12b-qat-campaign.json
```

## Live finalist

After reviewing the screen report, rerun survivors at finalist depth:

```bash
./bin/lmre-matrix --mode finalist \
  --campaign config/matrix/gemma-4-12b-qat-campaign.json
```

Screen = 1 warm-up + 3 measured per workload (12 requests per timed cell).  
Finalist = 1 + 5 (18 requests).

## Outputs

Under `results/matrix/<campaign_id>-<mode>-<timestamp>/`:

- `raw.json` — per-cell observations and summaries
- `report.md` — 3×3 PASS / FAIL / N/A table
- `logs/` — server stdout/stderr for cells this run started

## Safety

- Pinned start argv only; harness starts and stops only what each cell defines.
- Verify port free before the next cell; stop on RAM floor breach.
- Attempt all nine cells; `on_cell_failure: continue` keeps going after `N/A` or `FAIL`.
- Do not run live campaigns without explicit operator authorization.
