# Non-live backlog after 2026-07-24 night session

**Audience:** next agent / Jason returning to keyboard.  
**Living companion:** `docs/superpowers/notes/2026-07-24-discovery-session-handoff.md`

## Done (tested or sealed)

| Item | Status |
|------|--------|
| Discovery MVP Gate A + Gemma live execute | Sealed earlier |
| OptiQ A+C attach/reclaim | In tree; reclaim live thin |
| Stage 2 smoke `stage2-20260724-004` | Sealed PASS |
| Stage 2 inventory-wait request-evidence bloat | Fixed + unit tested (`a0495b1`) |
| Approach 3 Gate A scaffold + RAG CLI wiring | Unit tested; live UNTESTED |
| Plugin `0.4.0` Discovery surface | Source + parked dylib; **not installed** (`0.3.0` live) |

## Still open (prefer this order)

1. **Live Approach 3** — preference + RAG with `--i-understand-live` when stack available (needs oMLX + OptiQ; harness A+C). Mark seal only after evidence.
2. **Future harness smoke: prefer profile revision `5`** (`verify_routed_id_only_no_tap`) over r4 when authorizing new IDs — reduces reconnect-tap risk after OptiQ restart. Design 2 benchmark already uses r5 / schema `3.6.0`.
3. **Plugin `0.4.0` install** — explicit Jason approval + Osaurus full restart; Gate B still expects installed `0.3.0` until that changes.
4. **Approach 3 overhead collector** — not started.
5. **Eliminate remaining reconnect dependency** — prove auto-attach after harness OptiQ start without human tap on smoke lane.
6. **Ornith / Qwen OptiQ live** — blocked on operator OptiQ availability tonight.
7. **Deep Wiki** — deferred (Jason: repo handoff only for this session).

## Operator away constraints

Jason may not start/stop OptiQ or sit at the keyboard. Non-live coding may continue. Live inference / plugin install / new Stage 2 IDs require fresh authorization when he returns.
