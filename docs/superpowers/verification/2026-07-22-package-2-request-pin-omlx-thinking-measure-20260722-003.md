# Package 2 Request-Pin Live — `omlx-thinking-measure-20260722-003`

## Verdict

**PASS** (sealed)

| Field | Value |
|---|---|
| Run ID | `omlx-thinking-measure-20260722-003` (authorized; consumed) |
| Pin | `omlx-0.5.3-thinking` revision `2` / oMLX `0.5.3` |
| Request pin | `{"enable_thinking": true}` |
| Suite | `omlx-thinking-measure-v1` revision `2` (budgets 2048–4096) |
| Lifecycle actions | `2` |
| Port 8100 after | free |

## Outcomes

| Phase | Result |
|---|---|
| Preflight | `ok` (`finish_reason=stop`) |
| All 5 measure workloads | `ok` (`finish_reason=stop`) |
| Cleanup | `ok` |

## Qualification

| Label | Value |
|---|---|
| TTFT | `QUALIFIED_INCREMENTAL_DELIVERY` |
| Decode | `SUPPRESSED_AMBIGUOUS_TOKEN_ACCOUNTING` |

Decode suppression remains correct fail-closed behavior (no stream
`reasoning_tokens`); tracked as deferred **D4**, not a reopen of this PASS.

## Contrast

| Cohort | Pin / suite | Measure outcomes |
|---|---|---|
| `001` (D2) | pin r1 / suite r1 | all `ok` / `stop` (thinking not request-pinned) |
| `002` | pin r2 / suite r1 | all `token_capped` / `length` |
| `003` | pin r2 / suite r2 | all `ok` / `stop` |

Request-pin + higher thinking budgets close the path for this measure lane.

## Evidence

JSON: `docs/superpowers/verification/2026-07-22-package-2-request-pin-omlx-thinking-measure-20260722-003.json`
