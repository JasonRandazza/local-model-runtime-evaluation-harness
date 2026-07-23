# Package 2 Gate D Manager-Review Checklist

**Sealed cohort under review:** `omlx-thinking-20260722-004`  
**Evidence:**  
- `docs/superpowers/verification/2026-07-22-package-2-gate-c-omlx-thinking-20260722-004.md`  
- `docs/superpowers/verification/2026-07-22-package-2-gate-c-omlx-thinking-20260722-004.json`  

**Design:** `docs/superpowers/specs/2026-07-22-package-2-omlx-thinking-gate-d-design.md`  

This checklist is **read-only**. Do not start oMLX, issue POSTs, or create a new
run ID while executing it.

---

## 1. Identity

- [ ] Exact run ID is `omlx-thinking-20260722-004` (not `001`–`003`)
- [ ] Markdown and JSON evidence agree on decision and outcomes
- [ ] Authorization text names this exact ID

## 2. PASS fields

- [ ] `decision: PASS`
- [ ] `inference_ok: true`
- [ ] `cleanup_ok: true`
- [ ] `error: null` (or absent)
- [ ] Preflight outcome `ok`
- [ ] `thinking-short-reason` outcome `ok`
- [ ] `thinking-plan-and-answer` outcome `ok`
- [ ] `service_lifecycle_actions: 2`
- [ ] `port_8100_free_after: true`

## 3. Contract match

- [ ] `pin_id: omlx-0.5.3-thinking`, `pin_revision: 1`
- [ ] `version: 0.5.3`
- [ ] `model_id: Qwen3.6-35B-A3B-OptiQ-4bit`
- [ ] `suite_id: omlx-thinking-smoke-v1`, `suite_revision: 1`
- [ ] `ownership_mode: dedicated_serve`
- [ ] Comparison class remains `omlx-thinking-measure-v1`

## 4. Hygiene

- [ ] No API keys, Bearer tokens, or credentials in evidence bodies
- [ ] Prior IDs `001`–`003` documented as non-PASS only
- [ ] Gate C evidence files not modified during this review

## 5. Residuals (notes, not automatic REJECT)

- [ ] Force-free stop path (`omlX stop` + listener SIGTERM/SIGKILL) acknowledged
- [ ] D2 / D3 follow-ons explicitly out of this review

---

## Decision

Record exactly one:

| Code | Use when |
|---|---|
| `ACCEPT` | All required checks pass |
| `ACCEPT_WITH_NOTES` | Accept; residual notes (e.g. force-free cleanup) |
| `REJECT` | Missing evidence, wrong ID, or contract mismatch |

**Write the record to:**  
`docs/superpowers/verification/2026-07-22-package-2-gate-d-manager-review-004.md`

Suggested body:

```markdown
# Package 2 Gate D Manager Review — omlx-thinking-20260722-004

**Date:** YYYY-MM-DD
**Decision:** ACCEPT | ACCEPT_WITH_NOTES | REJECT
**Reviewer:** Jason

## Checklist
All sections 1–4: PASS / FAIL (summarize)

## Notes
…

## Follow-ons
- D2 (expanded suite): deferred
- D3 (external-bench): deferred
```

> **Supersession (2026-07-23):** Template follow-ons above are historical.
> D2 / D3 / D4 live PASSED — see `docs/package-2-omlx-thinking-d{2,3,4}.md`.
