# Current Status

## Product Direction

LMRE has a live-accepted managed-run foundation: standing local policy,
immutable plans, exact runtime ownership, retained collector orchestration,
checksummed evidence, and overhead-only resume after an operator-owned
provider reconnect. A read-only sealed-results browser (`lmre browse`)
renders that evidence as static local HTML; it grants no run, lifecycle,
provider, or credential authority.

Committed model configuration is now machine-portable. A strict, gitignored
`.lmre/machine-profile.json` supplies the two approved local artifact roots;
new managed plans checksum that profile so changed mappings fail before
inference. Fable's separate `lmre doctor` work is not part of this slice.

## Managed Live Acceptance (2026-07-31)

The managed path was accepted with a sealed local run:

- Run `run-20260731-051843-04302b`, name and comparison ID
  `gemma-managed-acceptance-20260731-r4`, sealed `PASS` at attempt 4; the
  complete checksum manifest validated after sealing. The retained Python
  suite (372 tests) passed at acceptance.
- Attempt 1 preserved PASS evidence for preflight, the native matrix screen,
  preference, RAG oracle, and RAG keyword. Attempts 2 and 3 preserve honest
  overhead recovery failures and provider-reconnect blocks.
- Attempt 4 completed the oMLX direct-versus-Osaurus screen overhead step:
  direct median total ~2.001s, routed ~1.991s (delta ~-0.011s), TTFT delta
  ~+0.020s, with both response-contract paths PASS.
- The OptiQ overhead pair was `N/A` in this screen attempt. It was not
  measured and is not a PASS.
- Osaurus was attached and recorded untouched; harness-owned oMLX workers
  were sequentially released and absent after cleanup; the operator-owned
  OptiQ process remained untouched.

The sealed bundle is machine-local evidence under ignored `results/runs/`
and is intentionally not committed.

## Accepted Current Evidence

| Area | Status | Evidence |
| --- | --- | --- |
| Managed local-run foundation | Sealed live acceptance `PASS` | `results/runs/run-20260731-051843-04302b` (local, gitignored) |
| Native triple and routing overhead | Closed for the accepted window | `superpowers/verification/2026-07-23-native-triple-overhead-live-evidence.md` |
| Multi-family preference and RAG | Closed for the accepted window | `superpowers/verification/2026-07-24-multi-family-quality-live-evidence.md` |
| Personal selection policy | Operator decision | `superpowers/verification/2026-07-24-personal-selection-policy.md` |
| Discovery Gemma execution | Sealed PASS | `superpowers/verification/2026-07-24-discovery-20260725-004-pass.md` |
| Approach 3 Gemma collections | `EXECUTED_UNSEALED` | Historical run directories remain local; no product PASS claimed |

## Active Workflows

- managed `policy` / `plan` / `run` / `resume` / `status` / `report` / `browse`
- Discovery proposal/show/execute
- Approach 3 explicit recipes
- native matrix
- pairwise preference
- oracle and keyword RAG
- direct-versus-Osaurus overhead
- read-only sealed-results browser ([results-browser.md](results-browser.md))

## Open Risks

- The OptiQ overhead pair remains unmeasured (`N/A`) in the accepted screen
  attempt.
- Approach 3 evidence still needs a separate review/seal decision.
- Backend attach/reclaim behavior is powerful and requires an adopted policy
  authorizing the exact plan.
- Resolved artifacts remain machine-local and may be missing even when the
  portable committed templates and machine profile are structurally valid.
- The results browser defers cross-run comparison; sealed runs are rendered
  individually only.
- No external plugin lifecycle is managed by this repository cleanup.

## Machine State

This file does not claim current runtime availability. Check actual loopback
services and artifacts only during a separately authorized local run.
