# Qwen Preference Recipe Design

**Status:** Approved in conversation by Jason on 2026-07-20. Authorizes preference config/docs/tests and, separately after implementation, live collect/judge for family `qwen36-35b-a3b`. Does not authorize RAG/overhead recipes, Stage 2B, or plugin changes.

**Depends on:** Qwen matrix screen evidence `results/matrix/qwen36-35b-a3b-3x3-screen-20260720-201114`.

## Goal

Add a checked-in preference cell recipe for Qwen3.6-35B-A3B using the four screen PASS cells, via existing `--family` resolution (same pattern as Ornith).

## Locked Decisions

| Topic | Choice |
| --- | --- |
| Family id | `qwen36-35b-a3b` |
| Cells | `qwen_mxfp4__osaurus`, `qwen_oq4__omlx`, `qwen_optiq_4bit__omlx`, `qwen_optiq_4bit__optiq` |
| Default family | Unchanged (`gemma-4-12b-qat`) |
| Code | Config + docs + tests only |
| Judge default | Unchanged Gemma `jang_4m__osaurus`; live Qwen judge uses an explicit `--judge-cell` from the PASS set |

## Non-goals

RAG/overhead Qwen recipes; changing checked-in preference defaults; Stage 2B.

## Definition Of Done

- `family-cells.json` lists the four PASS ids
- Dry-config `--family qwen36-35b-a3b` reports those cells
- Docs describe the recipe; unit tests cover resolve + dry-config
