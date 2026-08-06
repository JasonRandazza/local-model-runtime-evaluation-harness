# Approach 3 — Free-form cell binding

**Status:** Retained low-level/experimental product surface, not the normal
managed execution path.
**Shipped baseline:** `gemma-freeform-native-triple-v1`.
**Current authority:** `AGENTS.md` and `docs/managed-runs.md`.
**Direct live boundary:** Direct Approach 3 collection requires an explicit
user request and `--i-understand-live`. A managed run does not use this design
as a separate per-collector approval gate.

## Intent

Let an operator bind an ordered list of existing matrix `cell_id`s for a family
without changing the matrix scheduler. The shipped recipe is the native-triple
baseline; operators may add explicitly reviewed recipes from retained cells.

## Contract

1. Recipe JSON under `config/approach3/` with `family_id`, ordered `cell_ids`,
   and `require_native_server` (default `false` for Approach 3).
2. Cells still load from `config/matrix/cells/{cell_id}.json` and must pass
   family quant / artifact validation. No silent model copy or `place`.
3. Lifecycle stays on collector A+C / server builders — Approach 3 does not
   spawn OptiQ itself.
4. CLI: `bin/lmre-approach3 dry-config|show|collect-preference`.
5. `collect-preference` reuses `preference_collect.run_collect`; live requires
   explicit `--i-understand-live`.
6. Fail-closed on missing cells, wrong family quants, empty lists, duplicate
   cell ids, or unknown recipe fields.

## Boundaries

- One recipe cannot mix families.
- Recipes can reference only retained matrix cells.
- The archived cross-server demonstration recipe is not an active baseline.
- No plugin or vault write is part of Approach 3.

## Collectors

| Command | Status |
|---------|--------|
| `collect-preference` | Wired; passes `require_native_server` from recipe |
| `collect-rag --mode oracle\|keyword` | Wired; same native-server flag |
| `collect-overhead` | Wired for supported native pairs |

The active non-live baseline is `dry-config` plus the unit suite. Historical
experiments and unsealed remap recipes are in the sibling archive.

## Historical Evidence Closure (2026-08-05)

The four 2026-07-24 Gemma collector directories were reviewed separately.
Their request records are internally complete at the collector level, but the
directories predate immutable plans, policy linkage, lifecycle journals,
cleanup proof, input hashes, and execution-time checksum manifests. They are
therefore classified `REVIEWED_UNSEALED` and will not be retroactively
promoted to product `PASS`.

The current sealed successor is managed free binding through `lmre plan
--binding` and `lmre run|resume`. Sealed managed evidence now covers the exact
native triple plus both oMLX and OptiQ direct-versus-Osaurus overhead paths.
See the [closure review](../verification/2026-08-05-approach3-evidence-closure-review.md).
