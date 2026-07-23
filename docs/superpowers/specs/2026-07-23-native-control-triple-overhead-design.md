# Native Control Triple + Routing Overhead Redesign

**Status:** Design approved (Jason, 2026-07-23). Gate A landed on `main`. Live
native-triple + four-leg overhead follow-on **CLOSED** — see
`docs/superpowers/verification/2026-07-23-native-triple-overhead-live-evidence.md`.
Does **not** authorize preference/RAG, Stage 2 POSTs, provider edits, or plugin rebuild.

**Context:** Full 3×3 quant×server matrices hang or FAIL for invalid pairings
(JANG/MXFP on OptiQ/oMLX; oQ on OptiQ; etc.). Live Gemma screen
`20260723-130012` / `131429` confirmed this. Retire the cross-product; keep
native capability cells + Osaurus router-tax pairs.

## Goal

1. **Native control screen** — exactly **three** cells per family (not nine):
   each quant on its only capable native server.
2. **Routing overhead** — exactly **four** legs per family (two pairs):
   oQ native ↔ oQ via Osaurus; OptiQ native ↔ OptiQ via Osaurus.
3. Apply to **Gemma, Ornith, and Qwen** with the same fail-closed rules.

## Locked native map

| Quant class | Family examples | Native server only |
|---|---|---|
| Osaurus-native (JANG / MXFP) | `jang_4m`, `ornith_jang_4m`, `qwen_mxfp4` | `osaurus` (`:1337`) |
| oQ / oQ4 | `oq4_fp16`, `ornith_oq4`, `qwen_oq4` | `omlx` (`:8100`) |
| OptiQ-4bit | `optiq_4bit`, `ornith_optiq_4bit`, `qwen_optiq_4bit` | `optiq` (`:8080`) |

No other quant×server pairs are scheduled for the native control screen.

## Family / loader policy (Approach 2)

Extend family quant metadata so every quant has an explicit native server:

- Keep `role: "osaurus_native"` for JANG/MXFP (implies `native_server: osaurus`), **or**
  add required `native_server` ∈ `{osaurus, omlx, optiq}` for all quants (preferred
  single field; `osaurus_native` may remain as a synonym / display hint).
- `Cell.load` / `validate_for_family`: reject any cell whose `server` ≠ the
  quant’s native server.
- `Campaign.load`: for native-control campaigns, require **exactly three**
  cells — one per family quant — each on that quant’s native server. Reject
  duplicates and missing quants.

Historical cross-server cell JSON may remain on disk unused. Loading them
against the family must fail closed.

## Campaign shape (per family)

| Family | Campaign cells (only) |
|---|---|
| `gemma-4-12b-qat` | `jang_4m__osaurus`, `oq4_fp16__omlx`, `optiq_4bit__optiq` |
| `ornith-35b` | `ornith_jang_4m__osaurus`, `ornith_oq4__omlx`, `ornith_optiq_4bit__optiq` |
| `qwen36-35b-a3b` | `qwen_mxfp4__osaurus`, `qwen_oq4__omlx`, `qwen_optiq_4bit__optiq` |

Reporting: replace 3×3 grid expectation with a **native triple** table (one
row or one column of three native results). CLI name `lmre-matrix` may stay
for now (YAGNI rename); docs must stop calling this a full 3×3 science matrix.

## Overhead (four legs)

`lmre-overhead` already targets two pairs × (direct, routed) = four measurements.
Align docs and recipes explicitly:

| Pair | Direct | Routed |
|---|---|---|
| oQ | native oMLX cell (`:8100`) | same model via Osaurus (`:1337`) |
| OptiQ-4bit | native OptiQ cell (`:8080`) | same model via Osaurus (`:1337`) |

No overhead pair for Osaurus-native JANG/MXFP. Family recipes in
`config/overhead/family-pairs.json` already match this for Gemma/Ornith/Qwen —
verify and update docs only unless a pair file still points at a retired cell.

## Explicitly out of scope

- Live native-triple or overhead runs without Jason’s current-session authorization
- Deleting historical cross-server cell JSON or old result trees
- Renaming `lmre-matrix` binary (optional follow-on)
- Plugin rebuild; Stage 2 contract changes
- Preference / RAG campaign redesign (still consume native-triple PASS cells later)

## Success criteria (implementation Gate A)

1. All three family campaigns load with exactly three native cells; dry-config OK.
2. Loader rejects wrong-server cells for every quant class (not only `osaurus_native`).
3. Report/docs describe native triple + four-leg overhead; no “must run nine cells”.
4. Fake-only unit tests green; no live contact in Gate A.

## Follow-on (live, separately gated)

1. Authorize Gemma native-triple screen.
2. Authorize Gemma overhead four-leg run (pin live routed inventory ids first).
3. Repeat for Ornith/Qwen when artifacts and authorization allow.
