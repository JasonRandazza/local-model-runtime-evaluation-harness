# Multi-Family 3×3 Matrix

Direct native comparison of control artifacts across Osaurus (`1337`), oMLX (`8100`), and OptiQ (`8080`). One cell at a time; unloadable cells become `N/A`. Stage 0–2B machinery stays frozen — this path does not use Gate B, plugin tools, or Stage 2B inference authority. Do not run live campaigns without explicit operator authorization.

Campaigns are family-scoped. Each campaign JSON declares a `family_id` that loads an allowlist from `config/matrix/families/<family_id>.json`. Cells keep `quant__server` ids; Ornith and Qwen quants are prefixed so they do not collide with Gemma.

Family quant entries may set optional `"role": "osaurus_native"` for curated Osaurus library artifacts. That role covers **JANG or MXFP** — nativeness is not JANG-only.

| Campaign | Family | Command |
| --- | --- | --- |
| Gemma 4 12B QAT 3×3 | `gemma-4-12b-qat` | `config/matrix/gemma-4-12b-qat-campaign.json` |
| Ornith 1.0 35B 3×3 | `ornith-35b` | `config/matrix/ornith-35b-campaign.json` |
| Qwen 3.6 35B-A3B 3×3 | `qwen36-35b-a3b` | `config/matrix/qwen36-35b-a3b-campaign.json` |

All reuse suite `suites/gemma-matrix-v1.json` and the same screen/finalist depth. Free-form Approach 3 cells are a later goal — not implemented here.

**Later follow-ons:** preference quality, RAG oracle, and Osaurus routing overhead recipes for Ornith/Qwen PASS cells ship in separate plans after matrix screen evidence — see [preference.md](preference.md), [rag.md](rag.md), and [overhead.md](overhead.md).

## Prerequisites

- Artifact paths in `config/matrix/cells/` must exist on disk before live runs. Osaurus-native builds (JANG or MXFP) live under `MLXModels/OsaurusAI/`; oQ4 and OptiQ-4bit live under the Hugging Face cache (flat hub paths or operator symlinks).
- **Ornith / Qwen prep:** download and complete HF snapshots before live screen. Hub dirs may be refs-only (no `snapshots/`) until `huggingface-cli download` finishes; flat paths may need a local symlink. Dry-config lists missing paths in `artifact_missing`; live cells with missing weights become `N/A`.
- Restore `optiq` on `PATH` before OptiQ cells (`which optiq`).
- Unload other heavy models; keep RAM above the campaign floor (`20%` free).
- **Osaurus Keychain item** (required for Osaurus cells). In Osaurus: `⌘⇧M` → Identity → Create Access Key. Copy the **full** string once — it must look like `osk-v1.<payload>.<signature>` (**two** dots; the trailing signature segment is easy to miss). Then store it privately in Terminal (do **not** paste the key into chat):

```bash
/usr/bin/security add-generic-password \
  -a benchmark-harness \
  -s local.jrazz.lmre.osaurus \
  -l "LMRE Osaurus Matrix" \
  -j "Dedicated local matrix credential; do not export" \
  -U -w
```

  `-w` last: paste the key only into the hidden password prompt.

  Confirm with a local inventory probe (must return HTTP 200). If you still get 401, delete and recreate the Keychain item with a freshly minted access key:

```bash
/usr/bin/security delete-generic-password -a benchmark-harness -s local.jrazz.lmre.osaurus
# then re-run the add-generic-password command above
```

  Model exposure (routing oMLX into Osaurus) is separate from auth — inventory can list models and still reject a bad key. Osaurus may list routed ids such as `omlx/...` that differ from direct native ids.
- oMLX: campaign stops a busy managed `omlX` on `:8100` before spawning a cell-owned serve with a fixed loopback `--api-key` (`lmre-matrix-local`).
- OptiQ cells start with `--no-auth`. OptiQ inventory ids are the absolute `--model` paths; use the `:no-think` variant so streams put visible text in `delta.content` (default/`:think` stream into `delta.reasoning`, which the harness treats as empty).
- Non-OptiQ-packaged artifacts may fail `optiq serve` weight load → expected N/A/FAIL until an OptiQ-packaged build exists. MXFP on oMLX/OptiQ may likewise N/A; full 3×3 still records that evidence.
- `report.md` includes Option A metric tables (median total, TTFT, exact decode tok/s, contract ratio) plus Option B estimated decode tok/s (`completion_tokens / (total − TTFT)`, labeled `est.`). Quant rows follow campaign cell order.

## Non-live check

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -name 'test_matrix_*' -v
```

Unit tests use fakes only — no live Osaurus, oMLX, or OptiQ contact.

## Validate config

Gemma:

```bash
./bin/lmre-matrix --dry-config \
  --campaign config/matrix/gemma-4-12b-qat-campaign.json
```

Ornith:

```bash
./bin/lmre-matrix --dry-config \
  --campaign config/matrix/ornith-35b-campaign.json
```

Qwen:

```bash
./bin/lmre-matrix --dry-config \
  --campaign config/matrix/qwen36-35b-a3b-campaign.json
```

Dry-config JSON includes `family_id`, `cell_count`, cell ids, and `artifact_missing` (artifact paths referenced by the campaign that are not on disk). Resolve any listed paths before live screen.

## Live screen (operator)

Run all nine cells in screen mode first. Gemma:

```bash
./bin/lmre-matrix --mode screen \
  --campaign config/matrix/gemma-4-12b-qat-campaign.json
```

Ornith (after artifacts complete and explicit authorization):

```bash
./bin/lmre-matrix --mode screen \
  --campaign config/matrix/ornith-35b-campaign.json
```

Qwen (after artifacts complete and explicit authorization):

```bash
./bin/lmre-matrix --mode screen \
  --campaign config/matrix/qwen36-35b-a3b-campaign.json
```

Subset example:

```bash
./bin/lmre-matrix --mode screen --cells jang_4m__osaurus,oq4_fp16__omlx \
  --campaign config/matrix/gemma-4-12b-qat-campaign.json
```

Ornith subset:

```bash
./bin/lmre-matrix --mode screen --cells ornith_jang_4m__osaurus,ornith_oq4__omlx \
  --campaign config/matrix/ornith-35b-campaign.json
```

Qwen subset:

```bash
./bin/lmre-matrix --mode screen --cells qwen_mxfp4__osaurus,qwen_optiq_4bit__optiq \
  --campaign config/matrix/qwen36-35b-a3b-campaign.json
```

## Live finalist

After reviewing the screen report, rerun survivors at finalist depth:

```bash
./bin/lmre-matrix --mode finalist \
  --campaign config/matrix/gemma-4-12b-qat-campaign.json
```

Ornith:

```bash
./bin/lmre-matrix --mode finalist \
  --campaign config/matrix/ornith-35b-campaign.json
```

Qwen:

```bash
./bin/lmre-matrix --mode finalist \
  --campaign config/matrix/qwen36-35b-a3b-campaign.json
```

Screen = 1 warm-up + 3 measured per workload (12 requests per timed cell).  
Finalist = 1 + 5 (18 requests).

## Outputs

Under `results/matrix/<campaign_id>-<mode>-<timestamp>/`:

- `raw.json` — per-cell observations and summaries
- `report.md` — 3×3 PASS / FAIL / N/A table
- `logs/` — server stdout/stderr for cells this run started

## Safety

- Pinned start argv only; harness starts and stops only what each cell defines.
- Verify port free before the next cell; stop on RAM floor breach.
- Attempt all nine cells; `on_cell_failure: continue` keeps going after `N/A` or `FAIL`.
- Do not run live campaigns without explicit operator authorization.
- Stage 2B remains frozen (`GATE_A_STOPPED`); this path does not authorize Gate B or live inference authority.
