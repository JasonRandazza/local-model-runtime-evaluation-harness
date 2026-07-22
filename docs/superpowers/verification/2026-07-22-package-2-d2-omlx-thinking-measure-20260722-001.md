# Package 2 D2 Live — `omlx-thinking-measure-20260722-001`

## Verdict

**PASS** (sealed)

| Field | Value |
|---|---|
| Run ID | `omlx-thinking-measure-20260722-001` (authorized; consumed) |
| Pin | `omlx-0.5.3-thinking` revision `1` / oMLX `0.5.3` |
| Suite | `omlx-thinking-measure-v1` revision `1` (5 workloads) |
| Lifecycle actions | `2` |
| Port 8100 after | free |

## Outcomes

| Phase | Result |
|---|---|
| Preflight | `ok` |
| All 5 measure workloads | `ok` |
| Cleanup | `ok` |

## Qualification

| Label | Value |
|---|---|
| TTFT | `QUALIFIED_INCREMENTAL_DELIVERY` |
| Decode | `SUPPRESSED_AMBIGUOUS_TOKEN_ACCOUNTING` |

Decode suppression is **correct fail-closed behavior**: the stream did not provide
`reasoning_tokens` / `EXACT_VISIBLE` accounting (`reasoning_tokens: null` on all
requests). Cohort still PASS on outcomes + cleanup.

## Status

Live D2 cohort sealed. Manager review optional (mirror Gate D) if Jason wants an
explicit ACCEPT record; otherwise D2 live is closed on this PASS.
