# Multi-Family Quality Live Evidence — Preference + RAG (2026-07-24)

**Date:** 2026-07-24  
**Decision:** quality follow-on **CLOSED** for native-triple preference and RAG  
**Prerequisite:** `docs/superpowers/verification/2026-07-23-native-triple-overhead-live-evidence.md`  
**RAG design:** `docs/superpowers/specs/2026-07-24-rag-native-triple-design.md`  
**Commit (config):** `fe93b16` — native RAG recipes + 2048 thinking budgets

Authorized by Jason in-session. Raw artifacts under `results/` are gitignored;
this note is the durable seal.

## Performance baseline (already sealed)

Native screens + four-leg overhead for Gemma / Ornith / Qwen: see the
2026-07-23 note. Do not re-derive those PASS counts here.

## Preference (native triples)

Suite `gemma-preference-v1` (Gemma collect on r1; Ornith/Qwen on r2 = all prompts
`max_tokens` 2048). Recipes trimmed to the native diagonal (`9a5f705`).
Self-judge bias accepted (judge is one of the three contestant cells).

| Family | Run dir | Suite | Judge | #1 | #2 | #3 |
|---|---|---|---|---|---|---|
| Gemma | `results/preference/gemma-preference-20260723-155133` | r1 | `jang_4m__osaurus` | OptiQ **0.727** (8–3–1) | oQ 0.444 (4–5–3) | JANG 0.300 (3–7–2) |
| Ornith | `results/preference/gemma-preference-20260723-160331` | r2 | `ornith_optiq_4bit__optiq` | oQ **0.583** (7–5) | JANG 0.500 (6–6) | OptiQ 0.417 (5–7) |
| Qwen | `results/preference/gemma-preference-20260724-102551` | r2 | `qwen_optiq_4bit__optiq` | oQ **0.667** (8–4) | mxfp4 0.583 (7–5) | OptiQ 0.250 (3–9) |

Win rates are pairwise tallies over 18 judgments (3 pairs × 6 prompts). Run
directory prefix remains `gemma-preference-*` because `suite_id` is still
`gemma-preference-v1` (naming polish deferred).

## RAG (native triples)

Suite `gemma-rag-oracle-v1`. Modes: oracle (gold chunks injected) and keyword
(`top_k=2`). Fact-hit = case-sensitive required-fact substring rate.

### Canonical scored runs

| Family | Mode | Run dir | Suite | Mean fact-hit by cell |
|---|---|---|---|---|
| Gemma | oracle | `results/rag/gemma-rag-20260724-103631` | r1 | oQ **0.833**, OptiQ **0.833**, JANG 0.667 |
| Gemma | keyword | `results/rag/gemma-rag-20260724-103809` | r1 | all **0.667** (R@k=1.0, P@k=0.5) |
| Ornith | oracle | composite (see note) | r1 + r2 | oQ **1.000**, OptiQ **0.833**, JANG **0.500** |
| Ornith | keyword | composite (see note) | r1 + r2 | oQ **1.000**, OptiQ **0.833**, JANG **0.500** |
| Qwen | oracle | `results/rag/gemma-rag-20260724-104524` | r1 | all **0.667** |
| Qwen | keyword | `results/rag/gemma-rag-20260724-104652` | r1 | mxfp4 **0.833**, others 0.667 (R@k=1.0, P@k=0.5) |

### Ornith JANG composite note

First Ornith full runs (`…-104019` oracle, `…-104250` keyword, suite r1 /
`max_tokens` 256): oQ + OptiQ scored as above; JANG **0.000** (6/6
`chat stream produced no content` — reasoning filled the budget).

After suite **r2** (`max_tokens` 2048), JANG-only re-runs:

| Mode | Run dir | Success | Mean hit |
|---|---|---|---|
| oracle | `results/rag/gemma-rag-20260724-112406` | 6/6, 0 empty | **0.500** |
| keyword | `results/rag/gemma-rag-20260724-112604` | 6/6, 0 empty | **0.500** |

Treat oQ/OptiQ from the r1 full runs and JANG from the r2 re-runs as the sealed
Ornith RAG native triple.

## Suite / budget lineage (thinking models)

| Artifact | Rev / value | Live role |
|---|---|---|
| `gemma-matrix-v1` | r3 freeform 2048; **r4** all workloads 2048 | Ornith JANG matrix; finalist uses r4 |
| `gemma-preference-v1` | r2 all prompts 2048 | Ornith + Qwen preference |
| `gemma-rag-oracle-v1` | **r2** all questions 2048 | Ornith JANG RAG re-run |
| `JUDGE_MAX_TOKENS` | **2048** | Preference judge (thinking-safe) |

Lesson: Ornith JANG (and similar Osaurus-native thinking builds) routinely fill
small completion budgets with `reasoning_content` and leave empty `content`.
Treat **2048** as the default ceiling for any suite those cells share.

## Cross-lane reading (not a ranking)

- **Gemma:** OptiQ leads preference; oQ ≈ OptiQ on RAG oracle.
- **Ornith / Qwen:** oQ leads preference; OptiQ trails even under OptiQ self-judge.
- **RAG keyword:** retrieval R@k=1.0 / P@k=0.5 at `top_k=2` is suite-structural
  (one gold chunk vs two retrieved), not a cell discriminator.
- Preference and RAG measure different jobs; do not collapse them into one
  “winner” without an explicit selection policy.

## Finalist matrix (suite r4)

Authorized in-session. Depth = 1 warm-up + 5 measured per workload (18 requests
per cell). All three native campaigns **3/3 PASS**.

| Family | Run dir | Suite | Result |
|---|---|---|---|
| Gemma | `results/matrix/gemma-4-12b-qat-native-finalist-20260724-114208` | r4 | **3/3 PASS** |
| Ornith | `results/matrix/ornith-35b-native-finalist-20260724-114548` | r4 | **3/3 PASS** |
| Qwen | `results/matrix/qwen36-35b-a3b-native-finalist-20260724-115919` | r4 | **3/3 PASS** |

Median total latency (from each `report.md`, indicative): Gemma JANG ≈ 2.3s /
oQ ≈ 2.6s / OptiQ ≈ 3.5s; Ornith JANG ≈ 29.8s / oQ ≈ 15.4s / OptiQ ≈ 1.3s;
Qwen mxfp4 ≈ 1.2s / oQ ≈ 1.4s / OptiQ ≈ 1.3s.

## Next lanes

1. ~~Finalist matrix~~ — sealed above.
2. ~~Polish~~ — run dirs use `<family_id>-preference-*` / `<family_id>-rag-*`
   (historical `gemma-preference-*` / `gemma-rag-*` remain valid).
3. Stage 2 harness-unattended Slice 1c — smoke Gate B–D sealed on
   `stage2-20260723-003` and re-evidenced **PASS** on `stage2-20260724-001`
   (`3.5.0` / profile r4; see
   `docs/superpowers/verification/2026-07-24-slice-1c-stage2-20260724-001-pass.md`).
   Design 2 harness benchmark sealed on `stage2-20260723-008` (`3.6.0` / r5).
   Do not reuse those IDs.
