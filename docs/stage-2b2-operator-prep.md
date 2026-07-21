# Stage 2B-2 Manual Operator Prep (Every Run)

**Status:** Checklist stub only. Gate B/C/D are blocked. No active run ID.

Canonical vault copy (preferred after Gate A review and before first live run):

`10 Wiki/Projects/Local Model Benchmark Overhaul/Stage 2B-2 Manual Operator Prep.md`

When the vault note and this file drift, **prefer the vault note** and update this
mirror in the same change when practical.

## Active run

| Field | Value |
|---|---|
| Run ID | **none** — no Stage 2B-2 run authorized |
| Prerequisite PASS | `stage2-20260721-005` — Stage 2B-1 Gemma OptiQ inference-path acceptance (consumed) |
| Profile | `gemma-4-12b-optiq-4bit` revision `2` |
| Schema / mode | `3.4.0` / `operator_route_benchmark` |
| Suite | `gemma-optiq-route-benchmark-v1` revision `1` |
| Launcher | `bin/lmre-stage2-operator-serve-gemma` |
| Template | `manifests/stage-2-optiq-route-benchmark.json.template` (non-authorizing until Gate C) |

Ask the host agent for a new unused ID only after Gate B reports ready and Jason
authorizes one exact ID in the current session. Do not reuse consumed IDs
(`001`–`005` or any prior Stage 2 run).

## Minimal command strip (placeholders — not live)

```zsh
# Terminal A — Gemma OptiQ (foreground, no args)
/Users/jrazz/Dev/active/local-model-runtime-evaluation-harness/bin/lmre-stage2-operator-serve-gemma

# Terminal B — mandatory warm-up BEFORE run_scenario (same direct model as 2B-1)
curl -sS --max-time 180 -N -X POST http://127.0.0.1:8080/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"model":"/Users/jrazz/.cache/huggingface/hub/mlx-community/gemma-4-12B-it-qat-OptiQ-4bit:no-think","messages":[{"role":"user","content":"Reply with the single word: ready"}],"max_tokens":8,"temperature":0,"stream":true}'

# Gate B (read-only; no POST from harness)
cd /Users/jrazz/Dev/active/local-model-runtime-evaluation-harness
./bin/lmre-stage2-gate-b-check

# Terminal B — after Coordinator run_scenario (replace <run-id> only after Gate C)
/Users/jrazz/Dev/active/local-model-runtime-evaluation-harness/bin/lmre-stage2-wait <run-id>

# After waiter: Ctrl+C on Terminal A, confirm port free, then Coordinator status + cleanup
lsof -nP -iTCP:8080 -sTCP:LISTEN
```

Osaurus: reconnect existing `Optiq` (no edits); load only
`gemma-4-12b-it-qat-jang_4m` (or idle); install the **reviewed** Stage 2B-2
Coordinator prompt for schema `3.4.0` / profile revision `2` (repo draft at
`docs/stage-2b2-coordinator-prompt.md` is not installed); fresh chat.

**Stage 2B-1 consumed:** `001`–`004` STOPPED; `005` PASS.

Full copy-paste Coordinator prompts and post-run checks will live in the vault note
after Gate A review. Until then, use `docs/stage-2b2-gate-a.md` for the operator
sequence and contract table.
