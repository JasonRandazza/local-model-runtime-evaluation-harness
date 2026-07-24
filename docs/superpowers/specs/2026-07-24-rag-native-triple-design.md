# RAG native-triple recipes (design)

**Status:** APPROVED (Jason, 2026-07-24)  
**Scope:** Align RAG cell recipes with preference native triples; live oracle + keyword for Gemma, Ornith, Qwen.

## Decision

RAG uses exactly the same native diagonal cells as preference:

| Family | Cells |
| --- | --- |
| `gemma-4-12b-qat` | `jang_4m__osaurus`, `oq4_fp16__omlx`, `optiq_4bit__optiq` |
| `ornith-35b` | `ornith_jang_4m__osaurus`, `ornith_oq4__omlx`, `ornith_optiq_4bit__optiq` |
| `qwen36-35b-a3b` | `qwen_mxfp4__osaurus`, `qwen_oq4__omlx`, `qwen_optiq_4bit__optiq` |

Drop cross-server cells (`*_optiq_*__omlx`, `ornith_jang_4m__omlx`, etc.).

## Live sequence

For each family (Gemma → Ornith → Qwen): oracle collect + score, then keyword `--top-k 2` collect + score.

## Out of scope

New corpus/suite, BM25/embeddings, RAG pairwise judge, Stage 2 / plugin changes.

## Follow-on (2026-07-24)

Suite `gemma-rag-oracle-v1` revision `2` raises all question `max_tokens` to `2048` after Ornith JANG empty-content failures at `256`. Matrix suite revision `4` raises `strict-tool-json` to `2048` for the same reason. Preference suite already at `2048`; preference judge budget raised to `2048`.
