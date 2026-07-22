# Package 2 Gate C — `omlx-thinking-20260722-003`

## Verdict

**Inference: PASS · Cleanup: FAIL** (`FAIL_CLEANUP`)

Same pattern as `001`: preflight + both smoke workloads `ok`; `omlX stop` left
the listener up for the full 180s wait (that hang). New PID **43145**.

## Root cause (confirmed)

`LifecycleController` ran pin `stop_command` only and did not escalate to killing
the owned process group / port listeners when `omlX stop` lied.

## Fix landed for next ID

- Escalate `process.stop()` when port stays busy after stop_command.
- Live smoke uses force-free: `omlX stop` → SIGTERM listeners → SIGKILL.
- Next authorized ID: `omlx-thinking-20260722-004` (pending port free).
