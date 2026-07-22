# Package 2 oMLX 0.5.2 Pin-Confirm Evidence — 2026-07-22

**Session:** Jason confirmed the oMLX `0.5.2` pin and asked to move toward Gate B
development. Host agent recorded GET-only probes. This note does **not**
authorize live thinking POSTs or a Package 2 run ID.

## Measured install

| Field | Value |
|---|---|
| `omlX_path` | `/Users/jrazz/.omlx/bin/omlx` (Homebrew shim `/opt/homebrew/bin/omlX`) |
| `omlX_version` | **`0.5.2`** (exact) |
| `omlX` script sha256 | `58b2d7aae13f8aefd3453860bbe151a56586e0ec9e62cc183a8a0e8867314bc8` |
| `huggingface-hub` | Not visible in system Python 3.14; record from oMLX app env at dedicated-serve confirm |
| Port `8100` at probe | **open** (existing multi-model server) |

## Health (GET)

```json
{"status":"healthy","default_model":"Qwen3.6-35B-A3B-oQ4-mtp","engine_pool":{"model_count":16,"loaded_count":0,...}}
```

## Models (GET `/v1/models` with matrix key `lmre-matrix-local`)

Unauthenticated → `API key required`. With matrix local key, inventory count **17**,
including (among others):

- `Qwen3.6-35B-A3B-OptiQ-4bit` (Gate A provisional target)
- `ThinkingCap-Qwen3.6-27B-OptiQ-4bit` (explicit thinking-capable candidate)
- `Qwen3.6-35B-A3B-oQ4-mtp` (current default_model)

## Model dir probe

Provisional path exists:

`/Users/jrazz/.cache/huggingface/hub/mlx-community/Qwen3.6-35B-A3B-OptiQ-4bit`

`config.json` sha256: `37b318461a236f8c190cf85ac97c4e5aa23f7bff6d3d0a463785c2f72ebf7767`

## Fail-closed implications for Gate B

1. **Version pin confirmed** — disk reports `0.5.2`.
2. **Current `:8100` is a multi-model pool**, not a single-model Gate A
   `start_command` serve. Harness `omlX stop` reclaim would stop the whole pool.
3. **Auth required** — live transport must use the matrix local key pattern
   (`lmre-matrix-local`) or a Keychain path; never serialize secrets into evidence.
4. **Model id locked for Gate B:** `Qwen3.6-35B-A3B-OptiQ-4bit` (Jason
   2026-07-22). `ThinkingCap-Qwen3.6-27B-OptiQ-4bit` rejected — OptiQ-specific
   variation, not comparable to the other Qwen models under test.
5. **Ownership mode locked:** `dedicated_serve` (harness-owned single-model
   serve on `:8100`; do not reclaim the observed multi-model pool without
   explicit in-session approval).
6. **Pin JSON `start_command` refreshed** — Gate B Task 1 locked argv with
   `--model-dir` for `Qwen3.6-35B-A3B-OptiQ-4bit` under `dedicated_serve`.

## Locked Gate B constants (Jason, 2026-07-22)

| Field | Value |
|---|---|
| `ownership_mode` | `dedicated_serve` |
| `model_id` | `Qwen3.6-35B-A3B-OptiQ-4bit` |
| Rejected | `ThinkingCap-Qwen3.6-27B-OptiQ-4bit` (OptiQ-specific; not comparable) |
| Pin JSON | Refreshed with `--model-dir` argv in `config/omlx-pins/omlx-0.5.2-thinking-r1.json` |
| Gate B CLI | `./bin/lmre-omlx-thinking-gate-b-check` (GET-only; no POSTs) |

## Checklist status

| Step | Status |
|---|---|
| 1. Confirm 0.5.2 | **PASS** (measured) |
| 2. Replace start_command / model id | **PASS** (locked `Qwen3.6-35B-A3B-OptiQ-4bit`; pin JSON + loader updated) |
| 3. Health ok | Partial — healthy multi-model pool observed at probe; dedicated pin serve not yet run |
| 4. Exact inventory id | **PASS** (auth probe lists exact id; bound in pin) |
| 5. Stop + port free | **NOT DONE** — foreign/multi-model process left running (do not reclaim without approval) |
| 6. Gate B separately gated | Gate B implementation **landed** (`GATE_B_READY`); live POSTs / run IDs still not authorized |
