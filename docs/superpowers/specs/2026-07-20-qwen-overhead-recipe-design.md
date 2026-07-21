# Qwen Overhead Recipe Design

**Status:** Approved in conversation by Jason on 2026-07-20 (proceed after Qwen RAG). Authorizes overhead pair config/docs/tests and live overhead run for family `qwen36-35b-a3b`. Does not authorize Stage 2B or plugin changes.

**Depends on:** Qwen matrix screen `…-201114` PASS cells (non-Osaurus-native winners).

## Goal

Add two Osaurus routing-overhead pairs for Qwen screen PASS backends (oQ4 oMLX + OptiQ native), mirroring Ornith.

## Locked Decisions

| Topic | Choice |
| --- | --- |
| Family | `qwen36-35b-a3b` |
| Pairs | `qwen_oq4`, `qwen_optiq_4bit` |
| MXFP / Osaurus-native | No overhead pair (same as JANG exclusion) |
| Third pair (`qwen_optiq_4bit__omlx`) | Out of scope |
| Routed ids (live-pinned) | `omlx/Qwen3.6-35B-A3B-oQ4-mtp`; `optiq//…/Qwen3.6-35B-A3B-OptiQ-4bit:no-think` |

## Non-goals

Stage 2B; changing Gemma/Ornith defaults; measuring MXFP via Osaurus.

## Definition Of Done

- Pair JSON + `family-pairs.json` + docs + tests
- Dry-config `--family qwen36-35b-a3b` OK
