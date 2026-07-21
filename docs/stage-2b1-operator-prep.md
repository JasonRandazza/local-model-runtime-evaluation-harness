# Stage 2B-1 Manual Operator Prep (Every Run)

Canonical vault copy (preferred for day-to-day use):

`10 Wiki/Projects/Local Model Benchmark Overhaul/Stage 2B-1 Manual Operator Prep.md`

in the Obsidian vault (`[[Stage 2B-1 Manual Operator Prep]]`).

Keep that note as the live checklist (active run ID, copy-paste prompts, OptiQ launcher, Gate B handoff, waiter, shutdown, cleanup). When the vault note and this file drift, **prefer the vault note** and update this mirror in the same change when practical.

## Active run (2026-07-21)

| Field | Value |
|---|---|
| Run ID | none — `stage2-20260721-005` sealed **PASS** (consumed) |
| Last PASS | `stage2-20260721-005` — Gemma OptiQ Stage 2B-1 inference-path acceptance |
| Profile | `gemma-4-12b-optiq-4bit` revision `2` |
| Launcher | `bin/lmre-stage2-operator-serve-gemma` |

Ask Cursor for a new unused ID only if repeating the cohort or moving to a separately gated stage.

## Minimal command strip

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

# Terminal B — after Coordinator run_scenario (use the active authorized run ID)
/Users/jrazz/Dev/active/local-model-runtime-evaluation-harness/bin/lmre-stage2-wait <run-id>

# After waiter: Ctrl+C on Terminal A, confirm port free, then Coordinator status + cleanup
lsof -nP -iTCP:8080 -sTCP:LISTEN
```

Osaurus: reconnect existing `Optiq` (no edits); load only `gemma-4-12b-it-qat-jang_4m` (or idle); Stage 2B-1 Coordinator prompt for schema `3.3.0` / profile revision `2`; fresh chat.

**Consumed STOPPED:** `001`–`004`. **Consumed PASS:** `005`.

Full copy-paste prompts and checks live in the vault note.
