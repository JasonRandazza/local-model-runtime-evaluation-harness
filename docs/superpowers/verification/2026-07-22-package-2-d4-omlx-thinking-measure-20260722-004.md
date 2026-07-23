# Package 2 D4 Live — `omlx-thinking-measure-20260722-004`

## Verdict

**PASS** (sealed)

| Field | Value |
|---|---|
| Run ID | `omlx-thinking-measure-20260722-004` (authorized; consumed) |
| Gate | `D4_LIVE` |
| Pin | `omlx-0.5.3-thinking` revision `2` / oMLX `0.5.3` |
| Request pin | `{"enable_thinking": true}` |
| Suite | `omlx-thinking-measure-v1` revision `2` (budgets 2048–4096) |
| Lifecycle actions | `2` |
| Port 8100 after | free |

## Outcomes

| Phase | Result |
|---|---|
| Preflight | `ok` (`DERIVED_REASONING_CONTENT`; 276 reasoning / 6 visible) |
| All 5 measure workloads | `ok` (`finish_reason=stop`; all `DERIVED_REASONING_CONTENT`) |
| Cleanup | `ok` |

## Qualification

| Label | Value |
|---|---|
| TTFT | `QUALIFIED_INCREMENTAL_DELIVERY` |
| Decode | `QUALIFIED_REASONING_CONTENT_SPLIT` |

Derived split from streamed `reasoning_content` + pinned-model `tokenizers`
encode; usage still lacked `completion_tokens_details.reasoning_tokens` (exact
path not claimed).

## Contrast

| Cohort | Decode |
|---|---|
| `003` (request-pin) | `SUPPRESSED_AMBIGUOUS_TOKEN_ACCOUNTING` |
| `004` (D4) | `QUALIFIED_REASONING_CONTENT_SPLIT` |

## Machine report

See `2026-07-22-package-2-d4-omlx-thinking-measure-20260722-004.json`.
