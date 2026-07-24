# Personal Selection Policy — Multi-Family Native Triples (2026-07-24)

**Date:** 2026-07-24  
**Status:** OPERATOR DECISION (Jason-authorized evidence window)  
**Evidence:**  
- Performance: `docs/superpowers/verification/2026-07-23-native-triple-overhead-live-evidence.md`  
- Quality + finalist: `docs/superpowers/verification/2026-07-24-multi-family-quality-live-evidence.md`

This note states an explicit selection policy. It does **not** invent new metrics.

## Decision rules

1. **Family first, then native cell.** Do not mix quants across families into one
   “best model” ranking.
2. **Preference outweighs RAG keyword** for interactive assistant quality (keyword
   R@k/P@k is suite-structural at `top_k=2`, not a cell discriminator).
3. **Finalist median latency is a veto**, not a primary score: reject cells that
   are too slow for interactive use even if preference is competitive.
4. **Self-judge bias is accepted** in the sealed preference tallies; treat
   OptiQ-as-judge / JANG-as-judge results as directional, not absolute.

## Per-family picks

### Gemma 4 12B QAT

| Role | Pick | Why |
|---|---|---|
| **Default interactive** | `optiq_4bit__optiq` | Preference win rate **0.727**; RAG oracle tied with oQ at **0.833**; finalist ~3.5s median (acceptable). |
| Latency-sensitive | `jang_4m__osaurus` | Fastest finalist (~2.3s) but preference last (0.300) — use only when speed dominates. |
| RAG / oMLX path | `oq4_fp16__omlx` | Ties OptiQ on RAG oracle; mid preference (0.444); ~2.6s. |

**Family verdict:** default **OptiQ-native**.

### Ornith 1.0 35B

| Role | Pick | Why |
|---|---|---|
| **Default interactive** | `ornith_oq4__omlx` | Preference **0.583**; finalist ~15s (heavy but usable). |
| RAG-led OptiQ path | `ornith_optiq_4bit__optiq` | Canonical full RAG oracle **0.833** (ahead of oQ/JANG at 0.500); fastest finalist (~1.3s); preference last (0.417). |
| **Reject for interactive** | `ornith_jang_4m__osaurus` | Preference mid (0.500) but finalist ~**30s** median — veto under rule 3. |

**Family verdict:** default **oQ-native** for preference-led chat; use **OptiQ-native** when RAG fact-hit or latency dominates.

### Qwen 3.6 35B-A3B

| Role | Pick | Why |
|---|---|---|
| **Default interactive** | `qwen_oq4__omlx` | Preference **0.667**; latency ~1.4s (clustered with peers). |
| Osaurus-native | `qwen_mxfp4__osaurus` | Preference 0.583; keyword RAG best (0.833); ~1.2s. |
| Avoid as default | `qwen_optiq_4bit__optiq` | Preference **0.250** under OptiQ self-judge; latency fine (~1.3s). |

**Family verdict:** default **oQ-native**.

## Cross-family reading

| Job | Prefer |
|---|---|
| Best sealed preference among defaults | Gemma OptiQ (0.727) over Ornith/Qwen oQ |
| Best sealed RAG oracle among defaults | Ornith OptiQ (0.833) on canonical full run; Gemma oQ/OptiQ tie at 0.833 |
| Best interactive latency among defaults | Qwen oQ / Gemma OptiQ cluster (~1–3.5s); avoid Ornith JANG |
| Routing overhead | Sealed four-leg deltas are small vs. model latency (see 2026-07-23 note) |

**There is no single global winner.** For personal use this session:

- **Primary daily stack:** Gemma **`optiq_4bit__optiq`** (quality-led).  
- **Heavy / RAG-heavy stack:** Ornith **`ornith_optiq_4bit__optiq`** (canonical RAG) or **`ornith_oq4__omlx`** (preference-led).  
- **Fast 35B alternate:** Qwen **`qwen_oq4__omlx`**.

## Out of scope

- Embedding / BM25 RAG, new preference judge protocol, Deep Wiki promotion
- Stage 2 route cohorts (separately evidenced)
- Changing sealed run artifacts; this policy only interprets them
