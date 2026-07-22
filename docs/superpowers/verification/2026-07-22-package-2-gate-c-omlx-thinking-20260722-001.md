# Package 2 Gate C — `omlx-thinking-20260722-001`

## Verdict

**Inference: PASS · Cleanup: FAIL** (overall recorded `FAIL` / treat as `FAIL_CLEANUP`)

Jason authorized this exact run ID on 2026-07-22. Preflight and both smoke
workloads returned `ok`. The cohort then failed because `omlX stop` did not free
port `8100` within the Slice 1a default **30s** wait (`LifecycleError: port 8100
did not free in time`). `service_lifecycle_actions` stayed at `1` because the
stop path raises before incrementing the stop action.

## Outcomes

| Phase | Result |
|---|---|
| Preflight | `ok` |
| `thinking-short-reason` | `ok` |
| `thinking-plan-and-answer` | `ok` |
| Cleanup / port free | **failed** (listener still up; ~23GB model loaded) |

Server log showed all three chat completions finishing (`finish_reason=stop`)
before cleanup.

## Root cause

Not a thinking-measure / transport / pin failure. **Stop-wait too short** for
unloading Qwen 35B OptiQ-4bit after dedicated serve. Live smoke now injects a
**180s** `wait_port_free` for the next authorized ID.

## Residual

Port `8100` remained busy after the run (healthy; default model
`Qwen3.6-35B-A3B-OptiQ-4bit`). Operator must run `omlX stop` in a host Terminal
before any retry.

## Next

1. Operator: `omlX stop` until `:8100` is free.
2. Jason authorizes a **new** unused ID (e.g. `omlx-thinking-20260722-002`) —
   `001` is consumed as FAIL_CLEANUP evidence.
3. Re-run live smoke with the longer stop wait for a sealed PASS.
