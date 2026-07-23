# Stage 2B-2 Manual Operator Prep (Every Run)

Canonical vault copy (preferred for day-to-day use):

`10 Wiki/Projects/Local Model Benchmark Overhaul/Stage 2B-2 Manual Operator Prep.md`

Coordinator system prompt (paste Primary System Prompt block into Osaurus):

`00 System/Templates/Prompts/Benchmark Coordinator/Benchmark Coordinator Stage 2B-2 Agent System Prompt.md`

When the vault note and this file drift, **prefer the vault note** and update this
mirror in the same change when practical.

## Active run (2026-07-21)

| Field | Value |
|---|---|
| Run ID | none — `stage2-20260721-006` sealed **PASS** (consumed) |
| Last PASS | `stage2-20260721-006` — Gemma OptiQ Stage 2B-2 route benchmark |
| Manager review | `docs/superpowers/verification/2026-07-21-stage-2b2-manager-review-006.md` |
| Prerequisite PASS | `stage2-20260721-005` — Stage 2B-1 smoke (consumed) |
| Profile | `gemma-4-12b-optiq-4bit` revision `2` |
| Schema / mode | `3.4.0` / `operator_route_benchmark` |
| Suite | `gemma-optiq-route-benchmark-v1` revision `1` |
| Launcher | `bin/lmre-stage2-operator-serve-gemma` |

Ask the host agent for a new unused ID only after a separately gated Gate B and Jason's exact-ID authorization. Do not reuse `001`–`006`.

## Minimal command strip (placeholders — not live)

```zsh
# Terminal A — Gemma OptiQ (foreground, no args)
/Users/jrazz/Dev/active/local-model-runtime-evaluation-harness/bin/lmre-stage2-operator-serve-gemma

# Terminal B — mandatory warm-up BEFORE run_scenario
curl -sS --max-time 180 -N -X POST http://127.0.0.1:8080/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"model":"/Users/jrazz/.cache/huggingface/hub/mlx-community/gemma-4-12B-it-qat-OptiQ-4bit:no-think","messages":[{"role":"user","content":"Reply with the single word: ready"}],"max_tokens":8,"temperature":0,"stream":true}'

# Gate B
cd /Users/jrazz/Dev/active/local-model-runtime-evaluation-harness
./bin/lmre-stage2-gate-b-check

# Terminal B — after Coordinator run_scenario (replace <run-id> only after Gate C)
/Users/jrazz/Dev/active/local-model-runtime-evaluation-harness/bin/lmre-stage2-wait <run-id>

# After waiter: Ctrl+C on Terminal A, confirm port free, then Coordinator status + cleanup
lsof -nP -iTCP:8080 -sTCP:LISTEN
```

**Stage 2B-1 consumed:** `001`–`004` STOPPED; `005` PASS.  
**Stage 2B-2 consumed:** `006` PASS.
