# Stage 2B-1 Gemma Pin Confirmation Checklist

Manual, operator-owned checklist. This document does **not** authorize Gate B,
a live manifest, a usable run ID, eight-POST smoke, plugin rebuild, or harness
lifecycle control of OptiQ/Osaurus. Agents must not execute these steps unless
Jason explicitly authorizes live contact in the current session.

**Profile under confirmation:** `gemma-4-12b-optiq-4bit` revision `2`  
**Profile file:** `config/runtime-profiles/gemma-4-12b-optiq-4bit-r2.json`  
**Expected routed ID (exact, case-sensitive):**
`optiq//Users/jrazz/.cache/huggingface/hub/mlx-community/gemma-4-12B-it-qat-OptiQ-4bit:no-think`  
**Rejected locals / substitutes:** `gemma-4-12b-optiq-4bit`,
`mlx-community/gemma-4-12B-it-qat-OptiQ-4bit`,
`optiq/mlx-community/gemma-4-12B-it-qat-OptiQ-4bit`,
`optiq//Users/jrazz/.cache/huggingface/hub/mlx-community/gemma-4-12B-it-qat-OptiQ-4bit`
(bare path without `:no-think`)  
**Chat POST direct identity:** absolute snapshot path with `:no-think`  
**Direct base:** `http://127.0.0.1:8080/v1`  
**Routed base:** `http://127.0.0.1:1337/v1`

Record answers in a dated note (or inline checkmarks below) before any Gate B
session. Stop on the first fail-closed mismatch.

---

## Preconditions

- [ ] OptiQ Lab is closed.
- [ ] Port `8080` is free before launch (exactly one future foreground `optiq
      serve` may own it).
- [ ] Osaurus is already running with the existing `Optiq` provider present
      (do not create or edit the provider).
- [ ] Slice 2 retarget review is complete or explicitly waived by Jason for
      this pin-confirmation-only session.
- [ ] This checklist session will issue **GET only** (`/health`, `/v1/models`).
      No POST, no Coordinator tools, no Gate B checker against live services
      unless Jason separately opens a Gate B session afterward.

---

## 1. Start the Gemma foreground launcher

- [ ] In a dedicated terminal, from the Stage 2B-1 worktree/repo root, start:

```sh
./bin/lmre-stage2-operator-serve-gemma
```

- [ ] Leave the process foreground. Do not daemonize, background, or hand
      lifecycle to the harness.
- [ ] Do **not** use `bin/lmre-stage2-operator-serve` (VibeThinker Stage 2A
      rollback) for this pin confirmation.
- [ ] Confirm the launched command matches the profile `serve_arguments`
      (pinned `mlx-optiq 0.3.3` executable, Gemma snapshot path, host
      `127.0.0.1`, port `8080`, single-model, max-concurrent `1`).

If a different launcher is chosen, record the exact binary path and argv here
and treat any argv/path drift as a pin failure until a new profile revision
lands:

```text
chosen_launcher:
argv_observed:
```

---

## 2. Reconnect existing `Optiq` without editing

- [ ] In Osaurus, use only the existing provider’s retry/reconnect control for
      provider id `Optiq`.
- [ ] Do **not** edit base URL, model list, headers, credentials, or provider
      name.
- [ ] Do **not** create a second OptiQ/Optiq provider.
- [ ] Harness / agents issue zero provider mutations
      (`service_lifecycle_actions` remains harness-owned `0` later).

---

## 3. GET `/health` and GET `/v1/models` on both ports

Issue only these four read-only GETs (no Authorization header, no body):

```sh
curl -sS http://127.0.0.1:8080/health
curl -sS http://127.0.0.1:8080/v1/models
curl -sS http://127.0.0.1:1337/health
curl -sS http://127.0.0.1:1337/v1/models
```

- [ ] Direct `GET /health` reports `status: ok`. If optional model diagnostics
      appear, they agree with the pinned Gemma identity; optional activity
      counters are zero.
- [ ] Routed `GET /health` is reachable and healthy enough for inventory
      (record status).
- [ ] Direct `GET /v1/models` includes an approved direct identity from the
      profile allowlist (absolute snapshot path, optional `:no-think` /
      `:think` variants as advertised, and/or the hub-shaped repository id).
- [ ] Routed `GET /v1/models` exposes the exact required routed id:

```text
optiq//Users/jrazz/.cache/huggingface/hub/mlx-community/gemma-4-12B-it-qat-OptiQ-4bit:no-think
```

- [ ] No accepted substitute: reject hub-shaped
      `optiq/mlx-community/gemma-4-12B-it-qat-OptiQ-4bit`, bare path routed id
      without `:no-think`, local slug `gemma-4-12b-optiq-4bit`, and
      `:think` as the required Stage 2B chat route.
- [ ] Record the exact routed `id` string observed (copy/paste, do not
      normalize):

```text
routed_id_observed:
direct_ids_observed:
direct_health:
routed_health:
observation_timestamp:
```

Stop here if the routed id is missing, ambiguous, or not an exact match.

---

## 4. Confirm artifact hashes still match the profile

Against `config/runtime-profiles/gemma-4-12b-optiq-4bit-r2.json`:

- [ ] Snapshot path still resolves to the pinned model directory.
- [ ] `model_revision` / repository identity still match live artifacts.
- [ ] Re-hash each `artifact_hashes` entry (SHA-256 of file bytes) and compare
      to the profile. Example:

```sh
PROFILE=config/runtime-profiles/gemma-4-12b-optiq-4bit-r2.json
SNAP=$(python3 -c "import json; print(json.load(open('$PROFILE'))['model_snapshot'])")
python3 - <<'PY'
import hashlib, json
from pathlib import Path
profile = json.loads(Path("config/runtime-profiles/gemma-4-12b-optiq-4bit-r2.json").read_text())
snap = Path(profile["model_snapshot"])
mismatches = []
for name, expected in profile["artifact_hashes"].items():
    path = snap / name
    if not path.is_file():
        mismatches.append((name, "MISSING", expected))
        continue
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != expected:
        mismatches.append((name, digest, expected))
print("ok" if not mismatches else mismatches)
PY
```

- [ ] Runtime executable path and `mlx-optiq` / package versions still match
      the profile pins (`0.3.3` family; do not chase newer releases in this
      program).
- [ ] `serve_arguments` still match the running launcher argv.

### Drift policy (fail-closed)

- [ ] If any hash, revision, snapshot path, executable, package version,
      argv, base URL, or routed id drifts: **do not silently overwrite**
      revision `2`.
- [ ] Land a **new profile revision** (e.g. revision `3` in a new file /
      coordinated loader bump), update Gate B / template / suite pins in a
      separate change, and re-run this checklist against the new revision.
- [ ] Historical revision `1` (hub-shaped guess) and Stage 2A VibeThinker
      revision `3` remain untouched evidence / rollback.

```text
hash_check_result: ok | drift
drift_notes:
new_revision_required: yes | no
```

---

## 5. Gate B only in a separate session (after pins freeze)

Only after steps 1–4 all pass with frozen pins:

- [ ] Stop considering this checklist session as Gate B authority — it is not.
- [ ] Open a **separate** session with Jason’s explicit current-session
      authorization to run read-only Gate B
      (`bin/lmre-stage2-gate-b-check`) against the live Gemma service.
- [ ] Gate B still does not create a run ID. After Gate B reports ready, Jason
      must separately authorize **one exact unused** run ID and a short-lived
      schema `3.3.0` manifest before any eight-POST smoke.
- [ ] Until that separate authorization, remain at pin-confirmed / Gate-B-ready
      candidate only.

```text
pin_confirmation_result: PASS | FAIL
blocker:
next_allowed_step: none | separate Gate B session after Jason auth
```

---

## Explicit non-goals

- Do not run Gate B from this checklist alone.
- Do not create or authorize a usable run ID or live manifest.
- Do not issue inference POSTs or install a Coordinator prompt.
- Do not start/stop/signal OptiQ or Osaurus from the harness.
- Do not rebuild or reinstall plugin `0.3.0`.
- Do not mutate Stage 2A VibeThinker revision-3 evidence or launcher.
