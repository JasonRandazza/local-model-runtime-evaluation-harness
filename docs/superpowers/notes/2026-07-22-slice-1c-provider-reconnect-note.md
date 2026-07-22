# Slice 1c Provider Verify-Only + Reconnect Tap Policy

Policy note for the Stage 2 **harness-unattended** lane (schema `3.5.0`, profile
revision `4`). Non-live Gate A documentation only — does **not** authorize Gate
B, a live manifest, a usable run ID, POST smoke, provider file writes, or
OptiQ upgrade on disk.

## Locked policy

| Rule | Detail |
|---|---|
| Provider **edit** | **Forbidden.** The harness must never create, update, delete, or rewrite Osaurus provider configuration (`~/.osaurus/providers/remote.json` or equivalent). |
| Provider **activation** | Profile revision `4` sets `provider_activation: verify_routed_id_only`. The harness reads provider identity (endpoint, enabled, header counts) and verifies the exact routed inventory ID after harness-owned OptiQ is up. |
| Routed ID verification | After `HarnessOptiQController.capture()` starts OptiQ, preflight calls `GET /v1/models` on direct and routed loopback endpoints and accepts only the profile-pinned `routed_model_id` (exact inventory string). |
| Reconnect tap | If Osaurus has not attached the `Optiq` provider to the new listener and no safe **non-editing** reconnect API exists, Gate A documents **at most one** remaining operator reconnect tap before preflight inventory — not full lifecycle ownership. |
| Prefer eliminate tap | Future work should prove a safe reconnect path (read-only API or automatic attach after harness start) so the operator tap can be removed entirely. |

## Operator-owned lanes (unchanged)

Schemas `3.3.0` / `3.4.0` and Stage 2A revision `3` retain
`provider_activation: operator_reconnect_required`. Jason owns foreground OptiQ
start/stop and explicit provider reconnect without editing provider settings.
Those lanes still record `service_lifecycle_actions: 0` and require operator
`Ctrl+C` after `awaiting_review`.

## Gate A code boundary

- `HostValidator._provider()` is read-only (parse JSON, never write).
- No harness helper calls provider edit, create, or reconnect APIs.
- `StageTwoInferenceEngine._validate_provider_activation()` rejects unknown
  activation modes and refuses edit-style activation on the harness contract.

## Live follow-up (separately gated)

Before any live `3.5.0` cohort:

1. Confirm disk `mlx-optiq 0.4.2` pin (Slice 1b pin-confirm checklist).
2. Ensure Osaurus is running with the existing `Optiq` provider configured for
   `127.0.0.1:8080` (no edits).
3. If routed inventory is absent after harness OptiQ start, perform **one**
   operator reconnect tap only — then re-run read-only inventory checks.
4. Gate B, Jason's exact-ID authorization, and a short-lived manifest remain
   required separately.

Design authority: `docs/superpowers/specs/2026-07-21-stack-review-gate-a-queue-design.md`
(Slice 1c). Implementation plan:
`docs/superpowers/plans/2026-07-22-slice-1c-harness-unattended-gate-a.md`.
