# Package 2 D2: Expanded Thinking Measure

## Current Decision

`D2_LIVE_PASSED` — sealed live PASS on
`omlx-thinking-measure-20260722-001` (2026-07-22).

**Evidence:**
`docs/superpowers/verification/2026-07-22-package-2-d2-omlx-thinking-measure-20260722-001.md`

## Fixed Contract (sealed)

| Item | Value |
|---|---|
| Run ID | `omlx-thinking-measure-20260722-001` |
| Pin | `omlx-0.5.3-thinking` revision `1` |
| Suite | `omlx-thinking-measure-v1` revision `1` |
| Decision | `PASS` (`inference_ok` + `cleanup_ok`) |
| TTFT | `QUALIFIED_INCREMENTAL_DELIVERY` |
| Decode | `SUPPRESSED_AMBIGUOUS_TOKEN_ACCOUNTING` (no `reasoning_tokens` in stream usage) |

## Residual / follow-on

Exact visible-token decode qualification needs oMLX to emit
`completion_tokens_details.reasoning_tokens` (or equivalent) on the chat stream.
That is a measurement-depth follow-on, not a reopen of this PASS.

**D3** (external-bench) remains deferred.

## Related

| Item | Location |
|---|---|
| Design | `docs/superpowers/specs/2026-07-22-package-2-d2-expanded-thinking-measure-design.md` |
| Plan | `docs/superpowers/plans/2026-07-22-package-2-d2-expanded-thinking-measure.md` |
| Live CLI | `bin/lmre-omlx-thinking-live-measure` |
| Gate D smoke ACCEPT | `docs/superpowers/verification/2026-07-22-package-2-gate-d-manager-review-004.md` |
