# Slice 1b OptiQ 0.4.2 Pin-Confirm Evidence

**Date:** 2026-07-23  
**Decision:** **PASS**  
**Authorized by:** Jason (current session — venv upgrade + GET-only pin-confirm)

Does **not** authorize Stage 2 POSTs, a harness-unattended run ID, provider
edits, or plugin rebuild.

## Upgrade

| Field | Value |
|---|---|
| Command | `uv pip install --python /Users/jrazz/Dev/tools/mlx-optiq/.venv/bin/python3 'mlx-optiq==0.4.2'` |
| Prior | `mlx-optiq==0.3.3` |
| Result | `mlx-optiq==0.4.2` |

## Executable + packages

| Field | Value |
|---|---|
| `optiq_path` | `/Users/jrazz/Dev/tools/mlx-optiq/.venv/bin/optiq` |
| `optiq_sha256` | `d61c2f888d5066ff1a7d0fc969e0768213325a61f81c3346b1df14614d17978e` |
| mlx-optiq | `0.4.2` |
| mlx | `0.32.0` |
| mlx-lm | `0.31.3` |
| transformers | `5.12.1` |
| profile_updated | no (matches provisional r3 package map) |

## Serve + health

| Field | Value |
|---|---|
| Lab | closed (no Lab on `:8080`) |
| Port `8080` before | free |
| Argv | profile r3 `serve_arguments` (pinned `0.4.2` optiq, Gemma snapshot, `127.0.0.1:8080`, single-model, max-concurrent 1) |
| `GET /health` | `{"status":"ok"}` |

## Inventories (GET only)

**Direct** (`http://127.0.0.1:8080/v1/models`) includes:

- `.../gemma-4-12B-it-qat-OptiQ-4bit`
- `.../gemma-4-12B-it-qat-OptiQ-4bit:think`
- `.../gemma-4-12B-it-qat-OptiQ-4bit:no-think`
- `.../gemma-4-12B-it-qat-OptiQ-4bit:precise` (new diagnostic variant)
- `.../gemma-4-12B-it-qat-OptiQ-4bit:creative` (new diagnostic variant)

**Routed** required id present:

`optiq//Users/jrazz/.cache/huggingface/hub/mlx-community/gemma-4-12B-it-qat-OptiQ-4bit:no-think`

| Field | Value |
|---|---|
| matches_provisional_r3 | yes (required routed + direct `:no-think` / path / hub allowlist) |
| profile_identity_updated | no |
| parser_r3_constants_added | n/a |

## Artifact hashes

All five profile `artifact_hashes` re-measured — **unchanged** vs provisional r3 / revision `2` shared map.

| Field | Value |
|---|---|
| model_revision | `083d338ef60c7ce2b47b27e1447ed92e729c4150` (unchanged) |
| hashes_changed | no |
| profile_hash_updated | no |

## Exit

Pin-confirm exit criteria 1–4 met. Separate Gate A/B plans for
`gemma-optiq-042-operator-route-*` comparison classes remain queued (checklist
step 6) — not opened by this note.

Rollback for sealed `005`/`006` remains revision `2` / `0.3.3` launchers and
evidence. Disk venv is now `0.4.2` for Slice 1c / revision `3`–`4` work.

## Related

| Item | Location |
|---|---|
| Checklist | `docs/superpowers/notes/2026-07-21-slice-1b-optiq-042-pin-confirm-checklist.md` |
| Profile r3 | `config/runtime-profiles/gemma-4-12b-optiq-4bit-r3.json` |
| Slice 1c Gate A | `docs/stage-2-harness-unattended-gate-a.md` |
