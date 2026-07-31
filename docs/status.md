# Current Status

## Product Direction

LMRE now has a managed-run foundation: standing local policy, immutable plans,
exact runtime ownership, retained collector orchestration, checksummed
evidence, and overhead-only resume after an operator-owned provider reconnect.
The implementation is non-live validated only. It is not accepted as live
product evidence until a separately authorized local acceptance run passes.

## Accepted Current Evidence

| Area | Status | Evidence |
| --- | --- | --- |
| Native triple and routing overhead | Closed for the accepted window | `superpowers/verification/2026-07-23-native-triple-overhead-live-evidence.md` |
| Multi-family preference and RAG | Closed for the accepted window | `superpowers/verification/2026-07-24-multi-family-quality-live-evidence.md` |
| Personal selection policy | Operator decision | `superpowers/verification/2026-07-24-personal-selection-policy.md` |
| Discovery Gemma execution | Sealed PASS | `superpowers/verification/2026-07-24-discovery-20260725-004-pass.md` |
| Approach 3 Gemma collections | `EXECUTED_UNSEALED` | Historical run directories remain local; no product PASS claimed |

## Active Workflows

- managed `policy` / `plan` / `run` / `resume` / `status` / `report`
- Discovery proposal/show/execute
- Approach 3 explicit recipes
- native matrix
- pairwise preference
- oracle and keyword RAG
- direct-versus-Osaurus overhead

## Open Risks

- No reviewed live acceptance run has yet exercised the new managed path.
- Approach 3 evidence still needs a separate review/seal decision.
- Backend attach/reclaim behavior is powerful and requires an adopted policy
  authorizing the exact plan.
- Artifact paths are machine-local and may be missing even when config is valid.
- No external plugin lifecycle is managed by this repository cleanup.

## Machine State

This file does not claim current runtime availability. No runtime was contacted
to validate the managed implementation. Check actual loopback services and
artifacts only during a separately authorized local acceptance run.
