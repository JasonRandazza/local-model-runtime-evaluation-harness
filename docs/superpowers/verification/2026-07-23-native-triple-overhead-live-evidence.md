# Native Control Triple + Four-Leg Overhead — Live Evidence (2026-07-23)

**Date:** 2026-07-23  
**Decision:** live follow-on **CLOSED** for the native-triple redesign  
**Spec:** `docs/superpowers/specs/2026-07-23-native-control-triple-overhead-design.md`  
**Gate A:** `docs/superpowers/plans/2026-07-23-native-control-triple-overhead-gate-a.md` (merged on `main`)

Authorized by Jason in-session. Suite `gemma-matrix-v1` revision `3` (freeform
`max_tokens` 2048) landed after Ornith JANG exhausted smaller budgets with
`reasoning_content`-only streams.

## Native control screens

| Family | Canonical run dir | Suite rev | Result |
|---|---|---|---|
| Gemma | `results/matrix/gemma-4-12b-qat-native-screen-20260723-141202` | `1` | **3/3 PASS** |
| Ornith | composite (see note) | `1` + `3` | **3/3 PASS** |
| Qwen | `results/matrix/qwen36-35b-a3b-native-screen-20260723-152828` | `3` | **3/3 PASS** |

### Ornith composite note

First full screen (`…-144057`, suite r1): oQ + OptiQ **PASS**; JANG **FAIL**
(empty `content` after reasoning filled low `max_tokens`). After suite r3,
JANG-only retry (`…-151902`) **PASS** 9/9. No single directory holds all three
Ornith cells under r3; treat oQ/OptiQ from `…-144057` and JANG from `…-151902`
as the sealed native triple. Optional later: one clean Ornith full screen on r3.

## Four-leg overhead

| Family | Run dir | Suite rev | Result | Δ median total (routed − direct) |
|---|---|---|---|---|
| Gemma | `results/overhead/overhead-20260723-143449` | `1` | **4/4 PASS** | oQ ≈ +0.00s; OptiQ ≈ +0.06s |
| Ornith | `results/overhead/overhead-20260723-150411` | `1` | **4/4 PASS** | oQ ≈ +0.04s; OptiQ ≈ +0.12s |
| Qwen | `results/overhead/overhead-20260723-153636` | `3` | **4/4 PASS** | oQ ≈ +0.08s; OptiQ ≈ +0.19s |

## Suite lineage

| Rev | Freeform budgets | Live role |
|---|---|---|
| `1` | 128 / 256 | Gemma native+overhead; Ornith oQ/OptiQ + overhead |
| `2` | 512 / 768 | Insufficient for Ornith JANG short-instruction (still reasoning-only) |
| `3` | 2048 / 2048 | Ornith JANG PASS; Qwen native+overhead |

## Next lane (quality)

Preference → RAG on native PASS cells. Preference `config/preference/family-cells.json`
still lists some non-native cells (e.g. `optiq_4bit__omlx`) — trim to the native
diagonal before live preference collect.
