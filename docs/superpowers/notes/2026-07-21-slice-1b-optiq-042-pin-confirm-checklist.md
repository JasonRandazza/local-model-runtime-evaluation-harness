# Slice 1b OptiQ 0.4.2 Pin-Confirm Checklist

Manual, operator-owned checklist. This document does **not** authorize Gate B, a
live manifest, a usable run ID, POST smoke/benchmark, plugin rebuild, or harness
lifecycle control of OptiQ/Osaurus. Agents must not execute these steps unless
Jason explicitly authorizes live contact in the current session.

**Profile under confirmation:** `gemma-4-12b-optiq-4bit` revision **`3`**  
**Profile file:** `config/runtime-profiles/gemma-4-12b-optiq-4bit-r3.json`  
**Provisional routed ID (clone of revision `2` — re-measure after upgrade):**
`optiq//Users/jrazz/.cache/huggingface/hub/mlx-community/gemma-4-12B-it-qat-OptiQ-4bit:no-think`  
**Rollback (unchanged):** revision `2` / `mlx-optiq 0.3.3` /
`bin/lmre-stage2-operator-serve-gemma`; sealed `005`/`006` evidence  
**Direct base:** `http://127.0.0.1:8080/v1`  
**Routed base:** `http://127.0.0.1:1337/v1`

Gate A landed revision `3` with provisional constants cloned from revision `2`.
Pin-confirm closes the gap between contract and disk after a separately
authorized `0.4.2` upgrade. Stop on the first fail-closed mismatch.

Record answers in a dated note (or inline checkmarks below) before any later
Gate B session for the **new** comparison classes (see step 6).

---

## Preconditions

- [ ] OptiQ Lab is closed.
- [ ] Port `8080` is free before launch (exactly one foreground `optiq serve`
      may own it).
- [ ] Osaurus is already running with the existing `Optiq` provider present
      (do not create or edit the provider).
- [ ] Slice 1b Gate A implementation is reviewed; this session is pin-confirm
      only — not Gate A code work.
- [ ] This checklist session will issue **GET only** (`/health`, `/v1/models`)
      until Jason separately opens Gate B for the `0.4.2` comparison classes.

---

## 1. Authorize and upgrade `mlx-optiq` to `0.4.2`

**Not part of Gate A.** Gate A must not have changed the on-disk venv.

- [ ] Jason explicitly authorizes upgrading the pinned venv
      (`/Users/jrazz/Dev/tools/mlx-optiq/.venv`) in the current session.
- [ ] Upgrade `mlx-optiq` / `optiq` to exactly **`0.4.2`** in that venv (record
      the exact install command used).
- [ ] Do **not** treat this checklist as authorization for live Stage 2 POSTs
      or revision `3` cohorts — upgrade + identity probe only.

```text
upgrade_command:
upgrade_date:
authorized_by:
```

---

## 2. Record executable path, file hash, and package versions

- [ ] Confirm `runtime_executable` path still matches profile expectation:
      `/Users/jrazz/Dev/tools/mlx-optiq/.venv/bin/optiq`
- [ ] Record SHA-256 of the `optiq` binary (or the resolved real path if
      symlinked).
- [ ] Record exact `package_versions` from the upgraded venv for all four pins:

```sh
/Users/jrazz/Dev/tools/mlx-optiq/.venv/bin/python3 - <<'PY'
import importlib.metadata as m
for pkg in ("mlx-optiq", "mlx", "mlx-lm", "transformers"):
    print(f"{pkg}={m.version(pkg)}")
PY
```

- [ ] Verify `mlx-optiq == 0.4.2`. If any sibling version differs from the
      provisional Gate A map (`mlx 0.32.0`, `mlx-lm 0.31.3`,
      `transformers 5.12.1`), plan a profile/parser constant update before
      Gate B.
- [ ] Update `config/runtime-profiles/gemma-4-12b-optiq-4bit-r3.json` and
      `_GEMMA_R3_PACKAGE_VERSIONS` in `stage_two_profiles.py` if measured
      versions drift.

```text
optiq_path:
optiq_sha256:
mlx-optiq:
mlx:
mlx-lm:
transformers:
profile_updated: yes / no
```

---

## 3. Start OptiQ; confirm Lab closed and `/health` ok

- [ ] OptiQ Lab remains closed (no Lab UI owning port `8080`).
- [ ] Start OptiQ with argv from `config/runtime-profiles/gemma-4-12b-optiq-4bit-r3.json`
      `serve_arguments` — not `bin/lmre-stage2-operator-serve-gemma` (rollback
      launcher; stays on `0.3.3` for historical manifests).
- [ ] Leave the process foreground unless a later Slice 1c unattended path
      explicitly replaces this step.
- [ ] Confirm launched argv matches profile `serve_arguments` (pinned `0.4.2`
      executable, Gemma snapshot path, host `127.0.0.1`, port `8080`,
      single-model, max-concurrent `1`).

```sh
curl -sS http://127.0.0.1:8080/health
```

- [ ] Direct `GET /health` reports `status: ok`. If optional model diagnostics
      appear, they agree with the pinned Gemma identity; optional activity
      counters are zero.

```text
argv_observed:
health_response:
```

---

## 4. Capture exact `GET /v1/models` IDs (direct + routed)

After OptiQ is up, reconnect the existing Osaurus `Optiq` provider **without
editing** (retry/reconnect only — no URL, header, credential, or provider-name
changes).

Issue read-only GETs:

```sh
curl -sS http://127.0.0.1:8080/v1/models
curl -sS http://127.0.0.1:1337/v1/models
```

- [ ] Direct inventory includes an approved direct identity from the profile
      allowlist (absolute snapshot path with optional `:no-think` / `:think`
      variants as advertised, and/or hub-shaped repository id).
- [ ] Routed inventory exposes the **exact** required routed id (case-sensitive).
- [ ] Compare against provisional revision `3` values. Google chat-template sync
      in OptiQ `0.4.1`+ may change `:no-think` handling or inventory strings —
      do not assume revision `2` IDs survived.
- [ ] If any ID drifted from revision `2` shared parser values, update
      `routed_model_id`, `direct_model_identities`, and
      `rejected_local_model_ids` in `gemma-4-12b-optiq-4bit-r3.json` **and**
      add revision-3-only parser constants (e.g. `_GEMMA_R3_ROUTED_NO_THINK`,
      `_GEMMA_R3_DIRECT_NO_THINK`, `_GEMMA_R3_ROUTED_BARE_PATH`,
      `_GEMMA_R3_REJECTED_LOCAL_MODEL_IDS`) wired **only** in
      `_parse_gemma_revision_three`.
- [ ] **Do not** mutate shared symbols still used by `_parse_gemma_revision_two`:
      `_GEMMA_ROUTED_NO_THINK`, `_GEMMA_DIRECT_NO_THINK`, `_GEMMA_ROUTED_BARE_PATH`,
      or `_GEMMA_ARTIFACT_HASHES`. Revision `2` / sealed `005`–`006` rollback
      depends on those values remaining unchanged.
- [ ] If measured IDs match revision `2` shared constants, profile JSON may stay
      provisional; no parser change required before Gate B authorization.

```text
direct_ids_observed:
routed_id_observed:
matches_provisional_r3: yes / no
profile_identity_updated: yes / no
parser_r3_constants_added: yes / no / n/a
```

**Rejected locals / substitutes (update if inventory shape changed):**

- `gemma-4-12b-optiq-4bit`
- `mlx-community/gemma-4-12B-it-qat-OptiQ-4bit`
- `optiq/mlx-community/gemma-4-12B-it-qat-OptiQ-4bit`
- bare path without `:no-think` variant if routed requires `:no-think`

---

## 5. Re-hash model artifacts; update profile if drift

Weights may be unchanged; template sync is OptiQ-side. Still re-measure.

- [ ] Confirm snapshot path unchanged:
      `/Users/jrazz/.cache/huggingface/hub/mlx-community/gemma-4-12B-it-qat-OptiQ-4bit`
- [ ] Re-check Hub `model_revision` if the snapshot was refreshed.
- [ ] Re-hash all five artifact files in profile `artifact_hashes`:

```sh
shasum -a 256 \
  "/Users/jrazz/.cache/huggingface/hub/mlx-community/gemma-4-12B-it-qat-OptiQ-4bit/config.json" \
  "/Users/jrazz/.cache/huggingface/hub/mlx-community/gemma-4-12B-it-qat-OptiQ-4bit/optiq_metadata.json" \
  "/Users/jrazz/.cache/huggingface/hub/mlx-community/gemma-4-12B-it-qat-OptiQ-4bit/model.safetensors.index.json" \
  "/Users/jrazz/.cache/huggingface/hub/mlx-community/gemma-4-12B-it-qat-OptiQ-4bit/model-00001-of-00002.safetensors" \
  "/Users/jrazz/.cache/huggingface/hub/mlx-community/gemma-4-12B-it-qat-OptiQ-4bit/model-00002-of-00002.safetensors"
```

- [ ] If any hash differs from revision `2` shared values, update
      `artifact_hashes` in `gemma-4-12b-optiq-4bit-r3.json` **and** add
      `_GEMMA_R3_ARTIFACT_HASHES` in `stage_two_profiles.py`, wired **only** in
      `_parse_gemma_revision_three`.
- [ ] **Do not** mutate `_GEMMA_ARTIFACT_HASHES` — `_parse_gemma_revision_two`
      and sealed `005`–`006` rollback still pin the revision `2` hash map.
- [ ] If measured hashes match revision `2` shared values, profile JSON may stay
      provisional; no parser change required.
- [ ] Re-run non-live profile tests after any revision-3-only constant update.

```text
model_revision:
hashes_changed: yes / no
profile_hash_updated: yes / no
parser_r3_constants_added: yes / no / n/a
```

---

## 6. Open separate Gate A/B plan for new comparison classes

Pin-confirm alone does **not** authorize live smoke or benchmark cohorts.
Sealed `005`/`006` remain bound to revision `2` comparison classes:

- `gemma-optiq-operator-route-smoke` (schema `3.3.0`)
- `gemma-optiq-operator-route-benchmark` (schema `3.4.0`)

Only after steps 1–5 pass, open a **separate** Gate A/B design and
authorization for the distinct post–template-sync evidence names:

- Smoke: `gemma-optiq-042-operator-route-smoke`
- Benchmark: `gemma-optiq-042-operator-route-benchmark`

- [x] Do **not** add these classes to policy allowlists during pin-confirm.
- [x] Do **not** reuse sealed `005`/`006` run IDs or mix revision `2` manifests
      with `0.4.2` lifecycle.
- [x] Do **not** authorize live inference under revision `3` until that
      separate plan passes Gate A review and Jason authorizes Gate B+ with a
      fresh unused run ID and short-lived manifest.

**Update (2026-07-23):** Gate A for these comparison classes is landed
(fake-only) — design
`docs/superpowers/specs/2026-07-23-operator-042-route-lanes-design.md`,
plan `docs/superpowers/plans/2026-07-23-operator-042-route-lanes-gate-a.md`,
launcher `bin/lmre-stage2-operator-serve-gemma-042`.

**Update (2026-07-23, later):** Operator **smoke** live Gate B–D accepted —
manager review
`docs/superpowers/verification/2026-07-23-operator-042-smoke-manager-review.md`
(canonical sealed PASS `stage2-20260723-006`; prior `005` PASS; `004` STOPPED).
Operator **benchmark** Gate B–D remain separately gated.

---

## Exit criteria

Pin-confirm is complete when all of the following hold:

1. Disk reports `mlx-optiq 0.4.2` with recorded path, hash, and package map.
2. Foreground OptiQ serves revision `3` argv; Lab closed; direct `/health` ok.
3. Direct and routed `/v1/models` IDs match updated profile constants (or
   provisional clones were verified unchanged).
4. Artifact hashes and Hub revision match profile constants.
5. A separate Gate A/B plan for `gemma-optiq-042-*` comparison classes is
   queued — not started from this checklist.

Until then, rollback remains revision `2` / `0.3.3` / `005`–`006`.

## Related documents

| Item | Location |
|---|---|
| Slice 1b Gate A plan | `docs/superpowers/plans/2026-07-21-slice-1b-optiq-042-pin-gate-a.md` |
| Queue design | `docs/superpowers/specs/2026-07-21-stack-review-gate-a-queue-design.md` |
| OptiQ release implications | `docs/superpowers/notes/2026-07-21-mlx-optiq-0.3.3-to-0.4.2-implications.md` |
| Revision `2` pin confirm (historical) | `docs/superpowers/verification/2026-07-20-stage-2b1-gemma-pin-confirmation.md` |
