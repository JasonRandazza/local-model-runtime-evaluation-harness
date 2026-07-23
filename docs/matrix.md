# Multi-Family Native Control Triple

Each family runs exactly **three cells** — one per quant on its only capable native server (Osaurus `1337`, oMLX `8100`, or OptiQ `8080`). Historical cross-server cell JSON may remain on disk but is not scheduled. Stage 0–2B machinery stays frozen — this path does not use Gate B, plugin tools, or Stage 2B inference authority. Do not run live campaigns without explicit operator authorization.

Campaigns are family-scoped. Each campaign JSON declares a `family_id` that loads an allowlist from `config/matrix/families/<family_id>.json`. Cells keep `quant__server` ids; Ornith and Qwen quants are prefixed so they do not collide with Gemma.

Family quant entries require `"native_server"` (`osaurus`, `omlx`, or `optiq`). Optional `"role": "osaurus_native"` marks curated Osaurus library artifacts (JANG or MXFP); when set, `native_server` must be `"osaurus"`. `Cell.load` rejects cells whose server does not match the quant's `native_server`. Cross-server cell JSON may remain on disk for history but campaigns schedule only the native triple.

| Campaign | Family | Command |
| --- | --- | --- |
| Gemma 4 12B QAT native | `gemma-4-12b-qat` | `config/matrix/gemma-4-12b-qat-campaign.json` |
| Ornith 1.0 35B native | `ornith-35b` | `config/matrix/ornith-35b-campaign.json` |
| Qwen 3.6 35B-A3B native | `qwen36-35b-a3b` | `config/matrix/qwen36-35b-a3b-campaign.json` |

All reuse suite `suites/gemma-matrix-v1.json` revision `2` and the same screen/finalist depth.
Revision `2` raises freeform `max_tokens` (`short-instruction` 512, `wiki-constraint-summary` 768) so
Osaurus-native builds that still emit a long `reasoning_content` preamble can reach visible `content`
within budget (Ornith/Qwen JANG–class). Revision `1` evidence remains historical. Free-form Approach 3
cells are a later goal — not implemented here.

**Multi-family quality/overhead (keep for later):** preference, RAG, and routing-overhead recipes for Ornith/Qwen are in-tree — see [preference.md](preference.md), [rag.md](rag.md), and [overhead.md](overhead.md). Live multi-family matrix screens and those follow-on campaigns wait until the Gemma harness frame is fully built out; then return here for proper cross-family testing.

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
- Non-OptiQ-packaged artifacts may fail `optiq serve` weight load → expected N/A/FAIL until an OptiQ-packaged build exists.
- `report.md` includes native-triple PASS/FAIL/N/A tables (one row per cell: quant, native server, result) plus Option A metric tables (median total, TTFT, exact decode tok/s, contract ratio) and Option B estimated decode tok/s (`completion_tokens / (total − TTFT)`, labeled `est.`). Quant rows follow campaign cell order.

## Non-live check

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_matrix_*.py' -v
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

Run all three campaign cells in screen mode first. Gemma:

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
- `report.md` — native-triple PASS / FAIL / N/A table
- `logs/` — server stdout/stderr for cells this run started

## Safety

- Pinned start argv only; harness starts and stops only what each cell defines.
- Verify port free before the next cell; stop on RAM floor breach.
- Attempt listed campaign cells; `on_cell_failure: continue` keeps going after `N/A` or `FAIL`.
  `osaurus_native` quants (JANG / MXFP) run only on Osaurus — not scheduled on oMLX/OptiQ.
- Do not run live campaigns without explicit operator authorization.
- Stage 2B sealed cohorts for this window remain historical evidence; this matrix path still does not use Gate B, plugin tools, or Stage 2B inference authority, and does not authorize a new Stage 2 run ID.
