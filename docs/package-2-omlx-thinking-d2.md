# Package 2 D2: Expanded Thinking Measure

## Current Decision

`D2_LIVE_READY` — live measure path prepared; **awaiting Jason’s exact run-ID
authorization** before POSTs.

**Prerequisite:** `D2_GATE_A_READY` (fake-only) + Package 2 Gate D ACCEPT on smoke
`omlx-thinking-20260722-004`.

## Fixed Contract (live)

| Item | Value |
|---|---|
| Proposed run ID | `omlx-thinking-measure-20260722-001` (unused until authorized) |
| Pin | `omlx-0.5.3-thinking` revision `1` |
| Suite | `omlx-thinking-measure-v1` revision `1` (5 workloads) |
| Requests | 1 preflight + 5 measure ≤ 8 |
| Ownership | `dedicated_serve` + force-free cleanup |
| CLI | `bin/lmre-omlx-thinking-live-measure` |

## Preflight (host)

Gate B currently reports `READY_FOR_LIVE_AUTHORIZATION` with `:8100` free (checked
2026-07-22). Re-check immediately before live:

```sh
./bin/lmre-omlx-thinking-gate-b-check
# expect decision READY_FOR_LIVE_AUTHORIZATION and port_8100_free true
```

## Operator sequence (after exact-ID authorization)

```sh
cd /Users/jrazz/Dev/active/local-model-runtime-evaluation-harness
./bin/lmre-omlx-thinking-gate-b-check
PYTHONPATH=src /opt/homebrew/bin/python3 bin/lmre-omlx-thinking-live-measure
```

Run in **Terminal.app** (Metal). Do not start the oMLX menu-bar pool first.

## Related

| Item | Location |
|---|---|
| Design | `docs/superpowers/specs/2026-07-22-package-2-d2-expanded-thinking-measure-design.md` |
| Plan | `docs/superpowers/plans/2026-07-22-package-2-d2-expanded-thinking-measure.md` |
| Gate A status (prior) | Fake-only measure suite + qualification wiring |
