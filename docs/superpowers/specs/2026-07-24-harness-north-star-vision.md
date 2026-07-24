# Harness north-star vision (2026-07-24)

**Status:** APPROVED direction (Jason, 2026-07-24) — vision only; does not authorize implementation  
**Next bounded slice (agreed):** Discovery MVP (detect servers + catalog artifacts; still schedule curated native triples under the hood)  
**Not next:** free-form cell scheduling, cross-family free mixes, or UI shell

## North star

A harness that competent local-AI operators can use with minimal ceremony:

1. **Install** the harness.
2. **Connect** Osaurus, oMLX, and OptiQ (credentials / loopback already understood by the user).
3. **Discover** matching model families and on-disk paths automatically.
4. **Run** sealed, fail-closed evaluations with little hand-editing of JSON.
5. **Read** results easily (eventually a UI over sealed reports).
6. **Later:** compare richer sets — multiple JANG builds, same family at different sizes, or deliberate mixes across family / size / quant / server — under explicit, safe scheduling rules.

The product goal is **hands-off for people who already know how to run these stacks**, not a beginner cloud console.

## What we already proved (do not throw away)

The 2026-07 reopen sealed a **lab baseline**, not the north star itself:

- **Native control triples** (one quant per capable server) for Gemma / Ornith / Qwen
- Preference + RAG quality, finalists, selection policy
- Harness-unattended Stage 2 smoke + Design 2 benchmark on OptiQ `0.4.2`
- Thinking-budget and Osaurus-residency lessons

Evidence: `docs/superpowers/verification/2026-07-24-multi-family-quality-live-evidence.md`,  
`docs/superpowers/verification/2026-07-24-personal-selection-policy.md`,  
Deep Wiki reopen note (Tier 5, 2026-07-24).

## Reframe: Approach 1 / “3×3” is not the product end-state

| Concept | Role going forward |
|---|---|
| Historical **3×3** (quant × server full grid) | **Lab history.** Full-grid passes are rare and often uninteresting; cross-server cells are weak evidence for “which serving stack to use.” |
| Current **native diagonal** (Approach 1, three cells) | **Sealed baseline + regression kit.** Keep for fail-closed proofs and personal picks. Not the destination UX. |
| Original **Approach 3** (free-form user-defined cells) | **One ingredient** of the north star (flexible binding), not the whole meal. |
| **Discovery + guided connect** | **Next product slice.** Makes Approach 1 (and later freer schedules) usable without hand-maintained path JSON. |
| **Cross-model / cross-size mixes** | **Later.** Needs new scheduling, RAM, identity, and comparability rules before it is honest science. |
| **UI** | **Later.** Browse sealed artifacts first; then drive runs. |

Jason’s judgment (2026-07-24): chasing a filled 3×3 as the *goal* is the wrong product bet. Prefer discovery and guided runs; keep native triples as trustworthy machinery underneath.

## Phased path (careful)

1. **Discovery MVP** — detect Osaurus / oMLX / OptiQ reachability; scan known roots for artifacts; propose family/cell matches; still execute today’s native-triple campaigns (or an explicit subset). No free-form schedule yet.
2. **Guided run UX (CLI first)** — one command path: discover → confirm → screen/finalist/preference/RAG with less JSON editing.
3. **Controlled expansion** — optional extra cells *within* a declared comparison class (e.g. two JANG builds), still fail-closed.
4. **Approach 3–style free bind** — user-defined cells when discovery + policy can still refuse unsafe configs.
5. **Open mix comparisons** — Qwen-27B vs 35B-A3B vs Nemotron-class mixes only after identity, RAM, and suite contracts are defined for heterogeneous sets.
6. **UI** — results browser, then run orchestration.

## Anti-goals (this phase)

- Boiling the ocean into “one app that is everything”
- Weakening fail-closed identity / one-cell-at-a-time / residency rules to look more flexible
- Rewriting sealed Stage 0–2 or multi-family evidence
- Plugin rebuild without explicit session approval

## Definition of done for *this document*

- North star and phased path are written and linked from Deep Wiki + repo
- Next implementation target is explicitly **Discovery MVP**, separately designed before code
