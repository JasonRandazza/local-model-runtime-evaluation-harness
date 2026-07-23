# Package 2 D4: Reasoning-Content Decode Accounting

## Current Decision

`D4_GATE_A_READY` — fake-only implementation landed (2026-07-22).

Does **not** authorize live POSTs or a new measure run ID.

## What landed

| Item | Detail |
|---|---|
| Token accounting | `token_counter.py` + `resolve_token_accounting` |
| Transport | Accumulate `delta.reasoning_content`; injectable `TokenCounter` |
| Status | `DERIVED_REASONING_CONTENT` (exact usage still wins → `EXACT_VISIBLE`) |
| Decode label | `QUALIFIED_REASONING_CONTENT_SPLIT` |
| Live wire | `OmlxThinkingTransport.for_pin` best-effort `ModelDirTokenCounter` |

## Next (separately gated)

1. Gate B readiness (pin r2).
2. Jason authorizes one unused measure ID (e.g. `omlx-thinking-measure-20260722-004`).
3. Live cohort expects decode `QUALIFIED_REASONING_CONTENT_SPLIT` when thinking streams reasoning content.

## Related

| Item | Location |
|---|---|
| Design | `docs/superpowers/specs/2026-07-22-package-2-d4-reasoning-content-decode-design.md` |
| Gate A plan | `docs/superpowers/plans/2026-07-22-package-2-d4-reasoning-content-decode-gate-a.md` |
| Sealed request-pin PASS | `omlx-thinking-measure-20260722-003` |
| D3 | Deferred until after D4 live |
