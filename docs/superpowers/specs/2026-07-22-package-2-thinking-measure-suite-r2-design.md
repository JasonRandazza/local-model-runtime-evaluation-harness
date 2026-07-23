# Package 2 — Thinking Measure Suite Revision 2 Design

**Status:** Design accepted (Jason, 2026-07-22). Fake-only first.
Does **not** authorize live POSTs or run ID `omlx-thinking-measure-20260722-003`.

**Depends on:** Sealed request-pin live FAIL
`omlx-thinking-measure-20260722-002` (pin r2; all measure workloads
`token_capped` at suite r1 budgets).

## Goal

Raise thinking-aware `max_tokens` so pin-r2 request-pin cohorts can finish
visible answers (`finish_reason=stop` / outcome `ok`) instead of burning the
entire budget on reasoning.

## Locked decisions

1. **Approach:** Suite revision `2` — same suite id / prompts; higher budgets only.
2. **Do not** change live PASS semantics (`outcome == "ok"` still required).
3. **Do not** override budgets only in the live CLI.
4. **Pin:** Unchanged `omlx-0.5.3-thinking` revision `2`.
5. **Smoke suite:** Unchanged (`omlx-thinking-smoke-v1` revision `1`).
6. **Live:** Separately gated; next unused ID would be
   `omlx-thinking-measure-20260722-003` after Jason authorizes.

## Budget table (r2)

| Workload | r1 | r2 |
|---|---:|---:|
| thinking-short-reason | 512 | **2048** |
| thinking-plan-and-answer | 768 | **3072** |
| thinking-multi-step | 768 | **3072** |
| thinking-compare-tradeoffs | 768 | **3072** |
| thinking-token-pressure | 1024 | **4096** |

## Artifact shape

| Item | Value |
|---|---|
| Suite id | `omlx-thinking-measure-v1` |
| Revision | `2` |
| File | `suites/omlx-thinking-measure-v1-r2.json` |
| Historical r1 | keep `suites/omlx-thinking-measure-v1.json` (revision `1`) |
| Loader | `MEASURE_SUITE_REVISION = "2"`; `default_measure_suite_path()` → r2 |
| Workload count | still **5** (≤8 with preflight) |

## Non-goals

- Live `003` without separate authorization  
- D3 / D4  
- Accepting `token_capped` as PASS  
- Changing smoke suite or pin  

## Success (Gate A)

- r2 loads fail-closed; r1 file remains and is rejected by the r2 loader when
  pointed at that path (revision / contract mismatch).
- Fake-only tests cover load + budget floors.
- No live authority created.

## Related

- Request-pin design: `docs/superpowers/specs/2026-07-22-package-2-thinking-request-pin-design.md`
- Sealed FAIL `002`: `docs/superpowers/verification/2026-07-22-package-2-request-pin-omlx-thinking-measure-20260722-002.md`
