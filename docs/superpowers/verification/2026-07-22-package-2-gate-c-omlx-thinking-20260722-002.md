# Package 2 Gate C — `omlx-thinking-20260722-002`

## Verdict

**FAIL** before inference. Port `8100` never freed.

## What happened

1. `omlX stop` printed `oMLX stopped`.
2. `curl` still got healthy JSON — same listener **PID 32761** left from run
   `001` (Qwen still loaded, `model_count: 16`).
3. Gate B correctly returned `port_busy_foreign_pool`.
4. Live smoke tried reclaim via `omlX stop` + 180s wait, then failed:
   `LifecycleError: port 8100 did not free in time`.
5. `service_lifecycle_actions: 0` — no owned start, no smoke POSTs.

## Root cause

`omlX stop` is **not killing** the python listener on `:8100`. The process is an
orphaned / app-backed server from the prior cohort, not a clean dedicated-serve
child the CLI stop can tear down in this state.

## Operator recovery (host Terminal)

```sh
# Prefer: quit oMLX entirely from the menu bar (Quit), then confirm:
lsof -nP -iTCP:8100 -sTCP:LISTEN || echo "8100 free"

# If still listening after Quit:
kill 32761
# wait a few seconds; if needed:
kill -9 32761
lsof -nP -iTCP:8100 -sTCP:LISTEN || echo "8100 free"
```

Do **not** start the multi-model pool again before the next smoke.

## Next

Jason authorizes a new unused ID (e.g. `omlx-thinking-20260722-003`) only after
`:8100` is confirmed free, then re-run Gate B + live smoke.
