# Package 2 D2: Expanded Thinking Measure (Gate A)

## Current Decision

`D2_GATE_A_READY` — fake-only expanded measure suite + qualification wiring.
**Not live.** Live D2 cohort remains separately gated.

**Prerequisite:** Package 2 Gate D ACCEPT on sealed smoke `omlx-thinking-20260722-004`.

## Fixed Contract

| Item | Value |
|---|---|
| Comparison class | `omlx-thinking-measure-v1` |
| Pin | `omlx-0.5.3-thinking` revision `1` (unchanged) |
| Smoke suite (Gate C) | `omlx-thinking-smoke-v1` revision `1` — unchanged |
| Measure suite (D2) | `omlx-thinking-measure-v1` revision `1` — **5** workloads |
| Request budget | ≤8 serial including preflight |
| Qualification | `ThinkingMeasureRunner.qualification_labels` via `qualify_thinking_metrics` |

## What landed

- Suite: `suites/omlx-thinking-measure-v1.json`
- Loader accepts smoke (2) or measure (5) by `suite_id`
- Transport/runner plumb reasoning / visible token accounting + streaming semantics
- Fake-only tests for loader, plumbing, and qualification rollup

## Non-goals (this status)

- Live D2 POSTs / new run IDs  
- D3 external-bench  

## Related

| Item | Location |
|---|---|
| Design | `docs/superpowers/specs/2026-07-22-package-2-d2-expanded-thinking-measure-design.md` |
| Plan | `docs/superpowers/plans/2026-07-22-package-2-d2-expanded-thinking-measure.md` |
| Gate D | `docs/package-2-omlx-thinking-gate-d.md` |
