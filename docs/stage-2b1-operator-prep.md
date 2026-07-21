# Stage 2B-1 Manual Operator Prep (Every Run)

Canonical vault copy (preferred for day-to-day use):

`10 Wiki/Projects/Local Model Benchmark Overhaul/Stage 2B-1 Manual Operator Prep.md`

in the Obsidian vault (`[[Stage 2B-1 Manual Operator Prep]]`).

Keep that note as the live checklist (active run ID, copy-paste prompts, OptiQ launcher, Gate B handoff, waiter, shutdown, cleanup). When the vault note and this file drift, **prefer the vault note** and update this mirror in the same change when practical.

## Active run (2026-07-21)

| Field | Value |
|---|---|
| Run ID | `stage2-20260721-004` |
| Manifest | `manifests/stage-2-optiq-inference-004.json` |
| Profile | `gemma-4-12b-optiq-4bit` revision `2` |
| Launcher | `bin/lmre-stage2-operator-serve-gemma` |
| Expires | end of `2026-07-21` Eastern |
| Transport | SSE 1s-timeout fix (`256b78e`) required — already on `main` |

## Minimal command strip

```zsh
# Terminal A — Gemma OptiQ (foreground, no args)
/Users/jrazz/Dev/active/local-model-runtime-evaluation-harness/bin/lmre-stage2-operator-serve-gemma

# Terminal B — mandatory warm-up BEFORE run_scenario
curl -sS --max-time 180 -N -X POST http://127.0.0.1:8080/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"model":"/Users/jrazz/.cache/huggingface/hub/mlx-community/gemma-4-12B-it-qat-OptiQ-4bit:no-think","messages":[{"role":"user","content":"Reply with the single word: ready"}],"max_tokens":8,"temperature":0,"stream":true}'

# Gate B (must be READY_FOR_MANIFEST_AUTHORIZATION before Coordinator run_scenario)
cd /Users/jrazz/Dev/active/local-model-runtime-evaluation-harness
./bin/lmre-stage2-gate-b-check

# Terminal B — after Coordinator run_scenario
/Users/jrazz/Dev/active/local-model-runtime-evaluation-harness/bin/lmre-stage2-wait stage2-20260721-004

# After waiter: Ctrl+C on Terminal A, then Coordinator status + cleanup
```

Osaurus: reconnect existing `Optiq` (no edits); load only `gemma-4-12b-it-qat-jang_4m` (or idle); Stage 2B-1 Coordinator prompt for schema `3.3.0` / profile revision `2`; fresh chat; one-time approvals for `inventory` → `preflight` → `run_scenario` → (after OptiQ stop) `status` → `cleanup`.

**Consumed:** `001`–`003` (STOPPED — SSE timeout poison). **Active:** `stage2-20260721-004`.

Full copy-paste prompts and checks live in the vault note.
