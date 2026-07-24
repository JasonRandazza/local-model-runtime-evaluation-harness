# Discovery MVP design (2026-07-24)

**Status:** APPROVED (Jason, 2026-07-24)  
**Parent vision:** `docs/superpowers/specs/2026-07-24-harness-north-star-vision.md`  
**Architecture:** Approach 2 — in-process orchestration over existing preference/RAG library APIs  
**Does not authorize:** live discovery against real servers, Stage 2 run IDs, provider edits, plugin rebuild, or silent model copies

## 1. Goals

### In scope
- Detect loopback reachability for Osaurus, oMLX, and OptiQ (health + inventory where applicable).
- Check pinned family cell artifacts exist and expected model identities can match.
- Treat a family as **ready** only when the full native triple matches (fail closed on partial).
- Write an auditable **proposal** artifact.
- `execute` runs **in-process**: preference (collect → review → judge → tally) plus RAG (oracle collect+score, keyword collect+score) via existing library APIs.
- One family per execute.
- Gate A: fake-only tests; no live contact; no new Stage 2 IDs; no provider edit.

### Out of scope (deferred north-star)
- Auto-run without explicit execute (`confirm_policy: auto_when_ready`).
- Setting to execute all ready families sequentially.
- Custom any-three-model mixes (Approach 3 ingredient).
- Osaurus CLI provider configure / OptiQ reconnect automation.
- UI shell; matrix measure as part of default execute.
- Silent or implied copy/move/relocate of model weights.

### Success criteria
- Competent local-stack user: discover → inspect proposal → execute one ready family → preference+RAG artifacts without hand-editing JSON.
- Partial triples never execute.
- Existing preference/RAG CLIs remain usable and unchanged in behavior.

### Confirm path (B now → C later)
- MVP confirm = two-step: `propose` then `execute` (no interactive `y/N` required).
- Same proposal object later supports `confirm_policy: auto_when_ready` without a new runner.

## 2. Architecture choice

**Approach 2 (chosen):** discovery owns a thin orchestration layer that calls existing library entrypoints (`run_collect`, `run_review`, `run_judge`, `run_tally`, `score_run`). It does not subprocess `lmre-preference` / `lmre-rag`, and does not fork scoring rules.

**Rejected for MVP:** Approach 1 (subprocess CLIs only) — smaller first PR, weaker path to auto-run, all-families, and custom mixes.

**Hard rule:** discovery **orchestrates**; it must not change preference/RAG suite pins, gold wording, or sealed scoring semantics.

## 3. Match rules

For each family present in both `config/preference/family-cells.json` and `config/rag/family-cells.json`:

1. Recipes must agree on the native triple; mismatch → discovery error.
2. **Artifact:** each cell’s `artifact_path` exists on disk.
3. **Reachability:** each distinct `native_server` in the triple has successful loopback health on the pinned port (`osaurus` 1337, `omlx` 8100, `optiq` 8080).
4. **Identity:** when the server is reachable, inventory/`list_models` must contain the cell’s exact `model_id` or at least one id from the family quant’s `model_ids`. Reachable-but-missing-id → not ready.
5. **Ready:** all three cells pass (2)–(4). Partial → `ready: false` with per-cell reasons; never listed in `executable_families`.

`propose` is **observe-only**: it does not start or stop servers. Execute may start/stop via existing preference/RAG collectors (lifecycle delegated).

## 4. Proposal schema

Written under `results/discovery/<proposal_id>/proposal.json`.

Sketch:

```json
{
  "schema_version": "1.0.0",
  "proposal_id": "discovery-YYYYMMDD-NNN",
  "created_at": "...",
  "confirm_policy": "explicit_execute",
  "content_hash": "...",
  "servers": {
    "osaurus": {"reachable": true, "port": 1337},
    "omlx": {"reachable": true, "port": 8100},
    "optiq": {"reachable": false, "port": 8080, "reason": "..."}
  },
  "families": {
    "gemma-4-12b-qat": {
      "ready": true,
      "cells": {
        "jang_4m__osaurus": {
          "artifact_ok": true,
          "identity_ok": true
        }
      },
      "suites": ["preference", "rag_oracle", "rag_keyword"]
    }
  },
  "executable_families": ["gemma-4-12b-qat"]
}
```

- `confirm_policy` remains `explicit_execute` for MVP.
- Execute requires proposal on disk and recomputes `content_hash` over the proposal body excluding the hash field; mismatch → reject.
- `--family` must appear in `executable_families`.

## 5. CLI

Prog: `lmre-discover`

| Command | Behavior |
|---|---|
| `propose` (default) | Observe + match; write proposal; print summary, `proposal_id`, `executable_families`. |
| `show <proposal_id>` | Reprint proposal status. |
| `execute <proposal_id> --family <family_id>` | Run suites for one ready family. |
| `dry-config` | Validate config + fakeable wiring; no network (Gate A). |

No interactive prompt in MVP; confirm = invoking `execute`.

## 6. Execute pipeline

For `--family F`, sequential in-process steps:

1. **Preference:** `run_collect` → `run_review` → `run_judge` → `run_tally`
   - Cells: family recipe from `config/preference/family-cells.json`
   - Suite: `suites/multi-family-preference-v1.json`
   - **Judge cell:** family’s Osaurus-native cell (first recipe cell), not the global `jang_4m__osaurus` default — so Ornith/Qwen are not judged by Gemma.
2. **RAG oracle:** `run_collect(..., mode=oracle)` → `score_run`
3. **RAG keyword:** `run_collect(..., mode=keyword)` → `score_run`
   - Cells/suite/corpus: existing RAG defaults + family recipe

Record each step in `execution.json` as `{step, status, run_dir?, error?}`. First hard failure stops remaining steps for that execute; do not pretend PASS.

Lifecycle remains inside collectors. Discovery does not become a new OptiQ/Osaurus lifecycle owner in this slice.

## 7. Model placement (explicit operator choice)

Discovery must **never** silently copy, move, or duplicate model weights.

1. **Default:** match against pinned `artifact_path` only. Missing path → cell not ready; report the expected path; no auto-place.
2. **Future optional command** (designable in Gate A, implementable after core propose/execute): e.g. `lmre-discover place --family … --mode symlink|copy|relocate` that:
   - prints what will happen (source → destination, size if known),
   - explains why (harness pin / oMLX root / HF cache layout),
   - requires explicit confirm (`--yes` with printed plan hash),
   - never runs as a side effect of `propose` or `execute`.
3. Until that command exists, operators use existing relocate tools or manual paths; discovery only reports gaps.

## 8. Gate A boundaries

- Fake transport + fake filesystem for reachability and artifact checks.
- Fake or injected collector hooks prove execute order and stop-on-failure.
- Unit tests must not contact real loopback servers, Keychain, or live OptiQ/oMLX/Osaurus.
- No Stage 2 manifests or run IDs.
- Plugin `0.3.0` unchanged.
- Live propose/execute against Jason’s machine requires separate current-session authorization after Gate A.

## 9. Deferred north-star tracks

| Track | Intent |
|---|---|
| `confirm_policy: auto_when_ready` | Move B → C on the same proposal/runner |
| Setting: execute all ready families | Sequential loop over `executable_families` |
| Custom any-3 mix | New proposal kind; separate fail-closed rules |
| Osaurus CLI provider prep | One-time / automated OptiQ provider so reconnect stops being a persistent tap |
| Explicit `place` / relocate UX | Informed consent for disk operations (§7) |
| Matrix measure in default execute | Optional suite slot later |

## 10. Likely implementation touch list (non-binding)

- `src/local_model_runtime_evaluation/discovery*.py` (match, proposal, execute orchestration)
- `tests/test_discovery_*.py` (Gate A fake-only)
- `bin/lmre-discover` + package entry point
- Docs: Gate A checklist; pointer from north-star vision
- Reuse: `matrix_config`, cell/family pins, `LoopbackTransport` patterns, preference/RAG library APIs, credential fakes

## 11. Decisions locked in brainstorming

- Propose-and-run (B), designed for auto (C) later.
- Fail closed on partial native triples.
- Two-step propose → execute.
- Suites on execute: preference + RAG oracle + RAG keyword (not matrix measure).
- Lifecycle: delegate to existing collectors.
- One family per execute.
- Approach 2 in-process orchestration.
- Model copy/relocate only via explicit future `place` UX, never silent.
