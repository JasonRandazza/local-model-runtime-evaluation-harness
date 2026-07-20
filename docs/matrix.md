# Gemma 4 12B QAT 3×3 Matrix

Direct native comparison of three control artifacts across Osaurus (`1337`), oMLX (`8100`), and OptiQ (`8080`). One cell at a time; unloadable cells become `N/A`. Stage 0–2B machinery stays frozen — this path does not use Gate B, plugin tools, or Stage 2B inference authority.

**Preference quality POC:** pairwise human preference on the three screen PASS cells — see [preference.md](preference.md).

**RAG oracle Phase 1:** oracle-injected gold context fact-hit scoring on the same three cells — see [rag.md](rag.md).

**Osaurus routing overhead:** direct native vs routed `:1337` tax for oQ4 and OptiQ screen winners — see [overhead.md](overhead.md).

## Prerequisites

- Artifact paths in `config/matrix/cells/` must exist on disk (JANG under `MLXModels/OsaurusAI/`, oQ4 and OptiQ-4bit under Hugging Face cache).
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
- JANG and oQ4 artifacts lack OptiQ’s `optiq_vision` sidecar, so `optiq serve` fails weight load on those cells (`vision_embedder… parameters not in model`) → expected N/A/FAIL until an OptiQ-packaged build exists.
- `report.md` includes Option A metric tables (median total, TTFT, exact decode tok/s, contract ratio) plus Option B estimated decode tok/s (`completion_tokens / (total − TTFT)`, labeled `est.`).

## Non-live check

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -name 'test_matrix_*' -v
```

Unit tests use fakes only — no live Osaurus, oMLX, or OptiQ contact.

## Validate config

```bash
./bin/lmre-matrix --dry-config \
  --campaign config/matrix/gemma-4-12b-qat-campaign.json
```

## Live screen (operator)

Run all nine cells in screen mode first:

```bash
./bin/lmre-matrix --mode screen \
  --campaign config/matrix/gemma-4-12b-qat-campaign.json
```

Subset example:

```bash
./bin/lmre-matrix --mode screen --cells jang_4m__osaurus,oq4_fp16__omlx \
  --campaign config/matrix/gemma-4-12b-qat-campaign.json
```

## Live finalist

After reviewing the screen report, rerun survivors at finalist depth:

```bash
./bin/lmre-matrix --mode finalist \
  --campaign config/matrix/gemma-4-12b-qat-campaign.json
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
