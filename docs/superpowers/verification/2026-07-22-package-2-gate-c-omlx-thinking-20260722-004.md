# Package 2 Gate C — `omlx-thinking-20260722-004`

## Verdict

**PASS** (sealed)

| Field | Value |
|---|---|
| Run ID | `omlx-thinking-20260722-004` (authorized; consumed) |
| Pin | `omlx-0.5.3-thinking` revision `1` |
| oMLX | `0.5.3` |
| Model | `Qwen3.6-35B-A3B-OptiQ-4bit` |
| Suite | `omlx-thinking-smoke-v1` revision `1` |
| Ownership | `dedicated_serve` |
| Lifecycle actions | `2` (start + stop) |
| Port 8100 after | free |

## Outcomes

| Phase | Result |
|---|---|
| Preflight | `ok` |
| `thinking-short-reason` | `ok` |
| `thinking-plan-and-answer` | `ok` |
| Cleanup | `ok` (`cleanup_ok: true`) |

## Prior IDs (do not reuse)

| ID | Result |
|---|---|
| `omlx-thinking-20260722-001` | `FAIL_CLEANUP` (inference ok) |
| `omlx-thinking-20260722-002` | `FAIL` (port stuck before start) |
| `omlx-thinking-20260722-003` | `FAIL_CLEANUP` (inference ok) |

## Cleanup note

Sealed with the force-free stop path (`omlX stop`, then SIGTERM/SIGKILL on
listeners). `LifecycleController` also escalates to owned `process.stop()` when
the port stays busy after the CLI stop command.
