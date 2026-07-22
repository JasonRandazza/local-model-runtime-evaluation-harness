# Package 2 oMLX Thinking Gate D Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Land Package 2 Gate D documentation so Jason can manager-review sealed Gate C `omlx-thinking-20260722-004` and close the thinking-measure smoke lane — without live POSTs or new run IDs.

**Architecture:** Docs-only gate mirroring Stage 2 manager review. Status surface + checklist + design/plan cross-links. Follow-ons D2 (expanded suite) and D3 (external-bench) named but not implemented.

**Tech Stack:** Markdown only. Prefer `/opt/homebrew/bin/python3` only if a later task adds code (none in this plan). Plugin `0.3.0` unchanged.

## Global Constraints

- Design: `docs/superpowers/specs/2026-07-22-package-2-omlx-thinking-gate-d-design.md`
- Sealed PASS ID only: `omlx-thinking-20260722-004`
- No live oMLX/OptiQ contact, no new run IDs, no POSTs
- Do not commit `config/matrix/omlx-roots/**` or `.harness-lifecycle/**`
- Do not overwrite sealed Gate C evidence

## File map

| Area | Files |
|---|---|
| Status | Create `docs/package-2-omlx-thinking-gate-d.md` |
| Checklist | Create `docs/superpowers/notes/2026-07-22-package-2-gate-d-manager-review-checklist.md` |
| Cross-links | Update `docs/package-2-omlx-thinking-gate-b.md`, `docs/architecture.md`, queue design Package 2 section |

---

### Task 1: Gate D status surface

**Files:**
- Create: `docs/package-2-omlx-thinking-gate-d.md`

- [ ] **Step 1:** Write status `GATE_D_READY`, fixed contract table, gate boundaries (A–D), link to sealed `004`, state D2/D3 follow-ons, state that manager review is separately recorded.
- [ ] **Step 2:** Commit

```bash
git commit -m "$(cat <<'EOF'
Document Package 2 oMLX thinking Gate D manager-review surface.

EOF
)"
```

---

### Task 2: Manager-review checklist

**Files:**
- Create: `docs/superpowers/notes/2026-07-22-package-2-gate-d-manager-review-checklist.md`

- [ ] **Step 1:** Checklist covering all design-required checks; decision codes ACCEPT / ACCEPT_WITH_NOTES / REJECT; pointer to where Jason records the review.
- [ ] **Step 2:** Commit

```bash
git commit -m "$(cat <<'EOF'
Add Package 2 Gate D manager-review checklist for sealed smoke 004.

EOF
)"
```

---

### Task 3: Cross-link architecture and Gate B / queue

**Files:**
- Modify: `docs/package-2-omlx-thinking-gate-b.md` (Gate D row → Ready / reviewable)
- Modify: `docs/architecture.md` (Package 2 Gate D sentence)
- Modify: `docs/superpowers/specs/2026-07-21-stack-review-gate-a-queue-design.md` (Package 2 Gate D pointer)

- [ ] **Step 1:** Update status rows and related-doc tables only; no live authority language.
- [ ] **Step 2:** Commit

```bash
git commit -m "$(cat <<'EOF'
Wire Package 2 Gate D docs into architecture and queue status.

EOF
)"
```

---

## Verification

- [ ] Grep shows Gate D status + checklist + design linked from Gate B and architecture
- [ ] No new Python modules or live scripts in this plan
- [ ] Sealed `004` evidence untouched

## Out of scope (explicit)

- Filling the manager-review ACCEPT record (Jason / current-session review)
- D2 expanded suite, D3 external-bench
- Live re-smoke
