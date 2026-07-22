# Package 2 Gate D — Manager Review Design

**Status:** Design accepted (Jason, 2026-07-22). Docs/plan only in this gate.
Does **not** authorize new live POSTs, run IDs, oMLX lifecycle, expanded suites,
or external-bench.

**Depends on:** Sealed Package 2 Gate C PASS
`omlx-thinking-20260722-004`.

## Goal

Close the Package 2 thinking-measure **smoke** lane with a Stage-2-style manager
review of sealed Gate C evidence. Gate D is review and documentation — not a
new inference cohort.

## Locked product decisions

1. **Scope:** Manager-review only (Jason approved option 1, 2026-07-22).
2. **Sealed input:** Exact run ID `omlx-thinking-20260722-004` only for ACCEPT.
3. **Historical IDs:** `001` FAIL_CLEANUP, `002` FAIL, `003` FAIL_CLEANUP — never
   promote to PASS.
4. **No live contact** from Gate D implementation or review checklist execution
   beyond reading sealed evidence files already in-repo.
5. **Follow-ons (named, out of Gate D):**
   - **D2** — Expanded harness measure suite + qualification / reasoning-token
     accounting (docs/plan + later live).
   - **D3** — Optional oMLX external-bench lane (docs/plan + later live).

## Fixed contract under review

| Item | Required value |
|---|---|
| Comparison class | `omlx-thinking-measure-v1` |
| Pin | `omlx-0.5.3-thinking` revision `1` |
| oMLX version | `0.5.3` |
| Suite | `omlx-thinking-smoke-v1` revision `1` |
| Model | `Qwen3.6-35B-A3B-OptiQ-4bit` |
| Ownership | `dedicated_serve` |
| Sealed PASS ID | `omlx-thinking-20260722-004` |
| Lifecycle actions (PASS) | `2` |
| Cleanup | `cleanup_ok: true`, port `8100` free after |

## Manager-review outcomes

| Decision | Meaning |
|---|---|
| `ACCEPT` | Sealed `004` satisfies contract; Package 2 smoke lane closed |
| `ACCEPT_WITH_NOTES` | Accept with documented residual (e.g. force-free stop path) |
| `REJECT` | Evidence incomplete, wrong ID, or contract mismatch — do not close |

## Required review checks

1. Evidence files exist for `004` (JSON + markdown) and match each other.
2. `decision: PASS`, `inference_ok: true`, `cleanup_ok: true`.
3. Preflight + both smoke workloads `ok`.
4. `service_lifecycle_actions: 2`.
5. `port_8100_free_after: true`.
6. Pin / version / model / suite / ownership match the fixed contract.
7. Authorization text names exact ID `omlx-thinking-20260722-004`.
8. No API keys or secrets in evidence bodies.
9. Prior IDs `001`–`003` are labeled non-PASS and not reused as success.

## Non-goals

- New thinking POSTs or a new run ID  
- Expanded suite or qualification label work (→ **D2**)  
- External-bench wiring (→ **D3**)  
- OptiQ↔oMLX same-artifact matrix  
- Plugin `0.3.0` rebuild  
- Mixing Stage 2 OptiQ sealed `005`/`006` into this comparison class  

## Deliverables

| Artifact | Path |
|---|---|
| This design | `docs/superpowers/specs/2026-07-22-package-2-omlx-thinking-gate-d-design.md` |
| Implementation plan | `docs/superpowers/plans/2026-07-22-package-2-omlx-thinking-gate-d.md` |
| Status surface | `docs/package-2-omlx-thinking-gate-d.md` |
| Manager-review checklist | `docs/superpowers/notes/2026-07-22-package-2-gate-d-manager-review-checklist.md` |
| Manager-review record (filled at review time) | `docs/superpowers/verification/2026-07-22-package-2-gate-d-manager-review-004.md` (created when Jason records a decision) |

## Success criteria

- Gate D status is `GATE_D_READY` (reviewable; not auto-accepted).
- Jason can execute the checklist against sealed `004` and record
  ACCEPT / ACCEPT_WITH_NOTES / REJECT without further inference.
- D2 and D3 are named follow-ons with clear deferral language.

## Related

- Gate C seal: `docs/superpowers/verification/2026-07-22-package-2-gate-c-omlx-thinking-20260722-004.md`
- Gate B status: `docs/package-2-omlx-thinking-gate-b.md`
- Package 2 design: `docs/superpowers/specs/2026-07-22-package-2-omlx-thinking-measure-design.md`
- Stage 2B-2 manager-review pattern: `docs/superpowers/verification/2026-07-21-stage-2b2-manager-review-006.md`
