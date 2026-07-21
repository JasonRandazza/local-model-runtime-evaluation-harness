# Qwen RAG Recipe Design

**Status:** Approved in conversation by Jason on 2026-07-20 (proceed after Qwen preference). Authorizes RAG config/docs/tests and live oracle/keyword collect for family `qwen36-35b-a3b`. Does not authorize overhead recipes, Stage 2B, or plugin changes.

**Depends on:** Qwen matrix screen `…-201114` PASS cells; preference recipe for the same cell set.

## Goal

Add a checked-in RAG cell recipe for Qwen3.6-35B-A3B using the four screen PASS cells, via existing `--family` resolution.

## Locked Decisions

| Topic | Choice |
| --- | --- |
| Family id | `qwen36-35b-a3b` |
| Cells | `qwen_mxfp4__osaurus`, `qwen_oq4__omlx`, `qwen_optiq_4bit__omlx`, `qwen_optiq_4bit__optiq` |
| Default family | Unchanged (`gemma-4-12b-qat`) |
| Modes | Existing `oracle` + `keyword`; suite unchanged |
| Code | Config + docs + tests only |

## Non-goals

Overhead Qwen pairs; Stage 2B; changing RAG defaults.

## Definition Of Done

- `config/rag/family-cells.json` lists the four PASS ids
- Dry-config `--family qwen36-35b-a3b` OK
- Docs + unit tests updated
