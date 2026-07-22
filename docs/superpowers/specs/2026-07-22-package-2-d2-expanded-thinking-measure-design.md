# Package 2 D2 — Expanded Thinking Measure Suite Design

**Status:** Design accepted (Jason, 2026-07-22). Fake-only / docs first.
Does **not** authorize live POSTs, new run IDs, or D3 external-bench.

**Depends on:** Package 2 Gate D ACCEPT on sealed smoke `omlx-thinking-20260722-004`.

## Goal

Expand the thinking-measure lane beyond smoke: a larger suite (still ≤8 serial
requests) and evidence that records reasoning-token accounting plus TTFT/decode
qualification labels via existing `qualify_thinking_metrics`.

## Locked decisions

1. **Scope:** Docs + Gate-A-style fake-only implementation; live separately gated.
2. **Comparison class:** Keep `omlx-thinking-measure-v1`.
3. **Pin:** Unchanged `omlx-0.5.3-thinking` revision `1`.
4. **Smoke suite:** Keep `omlx-thinking-smoke-v1` for sealed Gate C path.
5. **Measure suite:** New `omlx-thinking-measure-v1` revision `1` with **5**
   workloads (all `max_tokens ≥ 512`); with 1 preflight → 6 total ≤ 8.
6. **Transport/runner:** Plumb `reasoning_tokens`, `visible_output_tokens`,
   `token_accounting_status`, `content_span_seconds`, and streaming semantics
   into request outcomes; expose cohort `qualification_labels`.

## Non-goals

- Live D2 cohort  
- D3 external-bench  
- Overwriting sealed `004` / Gate D ACCEPT  
- Plugin changes  

## Success

- Measure suite loads fail-closed; smoke suite still loads.
- Fake-only tests cover loader, metric plumbing, and qualification rollup.
- Status `D2_GATE_A_READY` (not live).
