# Slice 1c Harness-Unattended Gate B Readiness

**Date:** 2026-07-23  
**Decision:** **READY_FOR_MANIFEST_AUTHORIZATION**  
**Authorized by:** Jason (current session — OptiQ `0.4.2` upgrade + pin-confirm, then Gate B readiness)

Does **not** authorize a run ID, live `3.5.0` manifest, eight POSTs, provider
edits, or plugin rebuild.

Machine evidence:
`docs/superpowers/verification/2026-07-23-slice-1c-harness-unattended-gate-b.json`

## Prerequisites

| Item | Result |
|---|---|
| Slice 1b pin-confirm | PASS — `2026-07-23-slice-1b-optiq-042-pin-confirm.md` |
| Disk `mlx-optiq` | `0.4.2` (`optiq` sha256 `d61c2f888d5066ff1a7d0fc969e0768213325a61f81c3346b1df14614d17978e`) |
| Profile | `gemma-4-12b-optiq-4bit` revision `4` |
| Osaurus `:1337` | up (observe-only) |
| OptiQ Lab | closed |
| Port `8080` before | free |

## Harness-owned lifecycle

| Step | Result |
|---|---|
| Start via `HarnessOptiQController.capture()` | pid `41008`, `lifecycle_actions` → `1` |
| Direct `GET /health` | `{"status":"ok"}` |
| Direct `:no-think` inventory | present |
| Routed required ID | present (no reconnect tap) |
| Stop via process-group SIGTERM | `lifecycle_actions` → `2`; port `8080` free twice |

Required routed ID:

`optiq//Users/jrazz/.cache/huggingface/hub/mlx-community/gemma-4-12B-it-qat-OptiQ-4bit:no-think`

Counters: `http_post_attempts: 0`, `inference_request_attempts: 0`,
`reconnect_tap_used: false`.

## Stop-command fix (live finding)

mlx-optiq `0.4.2` has **no** `optiq stop` CLI (`optiq --help` lists serve/lab/… only).
Gate B first attempt failed cleanup because `optiq_server_pin_from_profile`
set `stop_command=(executable, "stop")`. Pin now uses empty `stop_command` so
`LifecycleController` stops the owned process group via `ManagedProcess.stop()`.

## Next gate

> **Supersession (2026-07-23):** Gate C/D for harness-unattended smoke sealed
> **PASS** on `stage2-20260723-003`. See
> `docs/superpowers/verification/2026-07-23-slice-1c-stage2-20260723-003-pass.md`
> and `docs/stage-2-harness-unattended-gate-a.md`. Point-in-time text below
> preserved.

Gate C: Jason authorizes one unused Stage 2 run ID + short-lived schema
`3.5.0` / mode `harness_inference_probe` manifest. Gate D (eight POSTs) remains
separately gated after that.
