# Package 2 D4: Reasoning-Content Decode Accounting

## Current Decision

`D4_LIVE_PASSED` — sealed live PASS on
`omlx-thinking-measure-20260722-004` (2026-07-22).

**Evidence:**
`docs/superpowers/verification/2026-07-22-package-2-d4-omlx-thinking-measure-20260722-004.md`

## Fixed Contract (sealed)

| Item | Value |
|---|---|
| Run ID | `omlx-thinking-measure-20260722-004` |
| Pin | `omlx-0.5.3-thinking` revision `2` |
| Suite | `omlx-thinking-measure-v1` revision `2` |
| Decision | `PASS` (`inference_ok` + `cleanup_ok`) |
| TTFT | `QUALIFIED_INCREMENTAL_DELIVERY` |
| Decode | `QUALIFIED_REASONING_CONTENT_SPLIT` |
| Token status | `DERIVED_REASONING_CONTENT` (all ok samples) |

## What landed

| Item | Detail |
|---|---|
| Token accounting | `token_counter.py` + `resolve_token_accounting` |
| Transport | Accumulate `delta.reasoning_content`; injectable `TokenCounter` |
| Status | `DERIVED_REASONING_CONTENT` (exact usage still wins → `EXACT_VISIBLE`) |
| Decode label | `QUALIFIED_REASONING_CONTENT_SPLIT` |
| Live wire | `OmlxThinkingTransport.for_pin` best-effort model-dir counter (`tokenizers` preferred) |

## Next

**D3** (external-bench) Gate A ready — fake-only runner and docs landed; live
cohort separately gated. Do not reuse run ID `004`.

## Related

| Item | Location |
|---|---|
| Design | `docs/superpowers/specs/2026-07-22-package-2-d4-reasoning-content-decode-design.md` |
| Gate A plan | `docs/superpowers/plans/2026-07-22-package-2-d4-reasoning-content-decode-gate-a.md` |
| Sealed request-pin PASS | `omlx-thinking-measure-20260722-003` |
| Live JSON | `docs/superpowers/verification/2026-07-22-package-2-d4-omlx-thinking-measure-20260722-004.json` |
