# Package 2 oMLX 0.5.2 Pin-Confirm Checklist

Manual, operator-owned checklist. This document does **not** authorize Gate B, a
live manifest, a usable run ID, POST smoke, plugin rebuild, or harness lifecycle
control beyond what a later Gate B session explicitly authorizes. Agents must not
execute these steps unless Jason explicitly authorizes live contact in the
current session.

**Pin under confirmation:** `omlx-0.5.2-thinking` revision **`1`**  
**Pin file:** `config/omlx-pins/omlx-0.5.2-thinking-r1.json`  
**Suite file:** `suites/omlx-thinking-smoke-v1.json`  
**Comparison class:** `omlx-thinking-measure-v1`  
**Base URL:** `http://127.0.0.1:8100/v1`  
**Rollback:** Stage 2 OptiQ operator/harness lanes unchanged; sealed `005`/`006`
evidence on `mlx-optiq 0.3.3` / Gemma revision `2`.

Gate A landed revision `1` with a provisional `start_command` (host/port only).
Pin-confirm closes the gap between contract and disk after a separately
authorized oMLX `0.5.2` install probe. Stop on the first fail-closed mismatch.

Record answers in a dated note (or inline checkmarks below) before any later
Gate B session for `omlx-thinking-measure-v1`.

**Lab:** N/A — oMLX has no OptiQ Lab equivalent; port `8100` must be free before
launch (exactly one foreground `omlX serve` may own it).

---

## Preconditions

- [ ] Port `8100` is free before launch.
- [ ] Package 2 Gate A implementation is reviewed; this session is pin-confirm
      only — not Gate A code work.
- [ ] This checklist session will issue **GET only** (`/health`, `/v1/models`)
      until Jason separately opens Gate B for `omlx-thinking-measure-v1`.
- [ ] Do **not** retarget Stage 2 OptiQ schemas or mix sealed OptiQ evidence
      with oMLX thinking-measure claims.

---

## 1. Authorize and confirm oMLX `0.5.2`

**Not part of Gate A.** Gate A must not have changed the on-disk install.

- [ ] Jason explicitly authorizes confirming or upgrading the oMLX install in
      the current session.
- [ ] Confirm `omlX --version` reports exactly **`0.5.2`** (record path used).
- [ ] If upgrade is required, record the exact install command used.
- [ ] Confirm `huggingface-hub >= 1.19.0` in the oMLX host environment (oMLX
      `0.5.2` install requirement per implications note).
- [ ] Do **not** treat this checklist as authorization for live thinking-measure
      POSTs or Gate B cohorts — install + identity probe only.

```text
omlX_path:
omlX_version:
omlX_sha256:
upgrade_command:
upgrade_date:
authorized_by:
huggingface_hub_version:
```

**Observed on 2026-07-22 (planning capture — re-measure at pin-confirm):**

| Field | Provisional value |
|---|---|
| `omlX_path` | `/Users/jrazz/.omlx/bin/omlx` (Homebrew shim: `/opt/homebrew/bin/omlX`) |
| `omlX_version` | `0.5.2` |
| `huggingface_hub_version` | *(record at pin-confirm)* |

---

## 2. Record model identity and replace provisional `start_command`

Gate A pin JSON uses a host/port-only placeholder. Pin-confirm must pin a
thinking-capable model and refresh `start_command` in
`config/omlx-pins/omlx-0.5.2-thinking-r1.json`.

**Locked model (Jason, 2026-07-22 — re-measure dirs/hashes at pin-confirm):**

| Field | Locked value |
|---|---|
| Model id | `Qwen3.6-35B-A3B-OptiQ-4bit` |
| Model path | `/Users/jrazz/.cache/huggingface/hub/mlx-community/Qwen3.6-35B-A3B-OptiQ-4bit` |
| Ownership mode | `dedicated_serve` (port `8100` must be free before harness serve) |
| Rejected | `ThinkingCap-Qwen3.6-27B-OptiQ-4bit` (not comparable) |

- [ ] Model directory exists and matches expected artifact identity (record
      SHA-256 of `config.json` or agreed hash set).
- [x] Replace provisional `start_command` with measured argv:

```json
[
  "omlX",
  "serve",
  "--model-dir",
  "/Users/jrazz/.cache/huggingface/hub/mlx-community/Qwen3.6-35B-A3B-OptiQ-4bit",
  "--host",
  "127.0.0.1",
  "--port",
  "8100"
]
```

- [ ] Confirm launched argv matches pin JSON after update.
- [ ] Record thinking extras / `extra_body_allowlist` if the identity probe
      requires pinned provider params (Gate A allowlist starts empty).

```text
model_path:
model_config_sha256:
argv_observed:
extra_body_allowlist_updated: yes / no
pin_json_updated: yes / no
```

---

## 3. Start oMLX; confirm `/health` ok

- [ ] Start oMLX with updated `start_command` from the pin JSON.
- [ ] Leave the process foreground unless a later harness-owned lifecycle path
      explicitly replaces this step (Slice 1a `LifecycleController` for Gate B).
- [ ] Confirm exactly one listener on port `8100`.

```sh
curl -sS http://127.0.0.1:8100/health
```

- [ ] Direct `GET /health` reports `status: ok`. If optional model diagnostics
      appear, they agree with the pinned model identity.

```text
health_response:
```

---

## 4. Capture exact `GET /v1/models` inventory

```sh
curl -sS http://127.0.0.1:8100/v1/models
```

- [ ] Inventory includes the expected model id for the pinned `--model-dir`.
- [ ] Record exact id string for later suite/runner binding (case-sensitive).
- [ ] Do **not** assume hub-shaped vs path-shaped ids — measure from live
      inventory.

```text
model_ids_observed:
expected_model_id:
matches_provisional: yes / no
```

---

## 5. Stop oMLX; confirm port free

- [ ] Stop foreground oMLX (`Ctrl+C` or `omlX stop` as appropriate).
- [ ] Confirm port `8100` is free twice (same proof pattern as Slice 1a).

```text
port_8100_free_after_stop: yes / no
```

---

## 6. Gate B remains separately gated

- [ ] Pin-confirm complete — profile/pin constants refreshed if measured values
      drifted from Gate A provisional map.
- [ ] Do **not** add `omlx-thinking-measure-v1` to policy allowlists during
      pin-confirm.
- [ ] Do **not** create run IDs, manifests, or POST smoke until Jason
      separately authorizes Package 2 live Gate C+ in the current session.
- [ ] Live thinking-measure cohort uses harness `ThinkingMeasureRunner` +
      Slice 1a lifecycle; records honest `service_lifecycle_actions > 0`.
- [x] Gate B readiness implementation landed — read-only check only:

```sh
./bin/lmre-omlx-thinking-gate-b-check
```

See `docs/package-2-omlx-thinking-gate-b.md`. `READY_FOR_LIVE_AUTHORIZATION`
requires port `8100` free under `dedicated_serve`; observing a foreign pool is
diagnostic only.

---

## Related documents

| Item | Location |
|---|---|
| Design | `docs/superpowers/specs/2026-07-22-package-2-omlx-thinking-measure-design.md` |
| Gate A plan | `docs/superpowers/plans/2026-07-22-package-2-omlx-thinking-measure-gate-a.md` |
| Gate B surface | `docs/package-2-omlx-thinking-gate-b.md` |
| Gate B plan | `docs/superpowers/plans/2026-07-22-package-2-omlx-thinking-gate-b.md` |
| Pin-confirm evidence | `docs/superpowers/notes/2026-07-22-package-2-omlx-052-pin-confirm-evidence.md` |
| oMLX 0.5.2 implications | `docs/superpowers/notes/2026-07-21-omlx-0.5.2-implications.md` |
| Slice 1a lifecycle | `src/local_model_runtime_evaluation/harness_lifecycle.py` |
