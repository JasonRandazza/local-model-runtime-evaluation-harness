# Personal Model Selection — Phase A

Jumping-off comparison for **Gemma 4 12B IT QAT**: native Osaurus JANG versus OptiQ served through Osaurus. This is `native-best-stack` / cross-quant data, not same-artifact lab science.

Stage 0–2B lab machinery stays frozen. This path talks only to `http://127.0.0.1:1337/v1`.

## Non-live check

```bash
PYTHONPATH=src python3 -m unittest tests.test_personal_selection -v
```

## Live screen (operator)

One heavy target at a time.

### Lane 1 — native

1. Unload other big models.
2. Load `gemma-4-12b-it-qat-jang_4m` in Osaurus.
3. Confirm inventory, then screen:

```bash
./bin/lmre-personal-select --dry-inventory \
  --lane config/personal-selection/lanes/gemma-4-12b-native-osaurus.json

./bin/lmre-personal-select --mode screen \
  --lane config/personal-selection/lanes/gemma-4-12b-native-osaurus.json
```

### Lane 2 — OptiQ via Osaurus

1. Unload the native Gemma (or leave only what OptiQ needs).
2. Start OptiQ with `mlx-community/gemma-4-12B-it-qat-OptiQ-4bit`.
3. Reconnect the existing Osaurus `Optiq` provider.
4. Confirm the exact routed id matches the lane file (edit the lane if Osaurus shows a different exact string):

```bash
./bin/lmre-personal-select --dry-inventory \
  --lane config/personal-selection/lanes/gemma-4-12b-optiq-via-osaurus.json

./bin/lmre-personal-select --mode screen \
  --lane config/personal-selection/lanes/gemma-4-12b-optiq-via-osaurus.json
```

## Outputs

Under `results/personal-selection/<lane>-<mode>-<timestamp>/`:

- `raw.json` — sanitized observations and summary
- `report.md` — draft for human review before any Deep Wiki update

Screen = 1 warm-up + 3 measured per workload (12 requests).  
Finalist = 1 + 5 (18 requests) via `--mode finalist`.

## Coordinator

Optional: paste `docs/personal-selection-phase-a-coordinator-prompt.md` into a dedicated Osaurus agent so it can remind you of the steps and help compare the two draft reports. The measurable work is the CLI above; the Coordinator does not need Stage 2B plugin tools for Phase A.
