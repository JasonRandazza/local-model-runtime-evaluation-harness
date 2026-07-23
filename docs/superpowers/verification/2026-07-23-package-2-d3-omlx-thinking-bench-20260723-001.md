# Package 2 D3 Live — `omlx-thinking-bench-20260723-001`

## Verdict

**PASS** (sealed)

| Field | Value |
|---|---|
| Run ID | `omlx-thinking-bench-20260723-001` (authorized; consumed) |
| Gate | `D3_LIVE` |
| Pin | `omlx-0.5.3-thinking` revision `2` / oMLX `0.5.3` |
| Bench | external mode → owned `http://127.0.0.1:8100/v1` |
| Bench status | `completed` (`bench-867066793803`) |
| Lifecycle actions | `2` |
| Port 8100 after | free |

## Informational metrics (single `pp=1024` / `tg=4096`)

| prompt_tokens | completion_tokens | ttft_ms | tpot_ms | gen_tps | e2e_latency_s |
|---:|---:|---:|---:|---:|---:|
| 990 | 512 | 2233.3 | 23.13 | 43.3 | 14.08 |

## Cross-check vs `omlx-thinking-measure-20260722-004`

- TTFT semantics diverge (oMLX first `content`|`reasoning_content` vs harness content-only) — do not equate.
- Viability: external warmup/preflight + single 1024 test completed without false thinking failure.
- Metric equality is **not** a PASS criterion.

## Machine report

See `2026-07-23-package-2-d3-omlx-thinking-bench-20260723-001.json`.
