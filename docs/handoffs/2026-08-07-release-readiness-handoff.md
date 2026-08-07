# Continuation handoff — 2026-08-07

Successor to `2026-08-06-claude-code-continuation-handoff.md`. That brief's
immediate continuation sequence is complete except for the final merge.

## What landed

Branch `claude/metrics-visibility-and-run-console`, PR #32, four commits:

| Commit | Content |
|---|---|
| `e76aea7` | Recorded metric visibility in sealed cross-run comparison (slice A), plus the sealed Qwen JANGTQ4 / Ornith acceptance record |
| `9b8ef8e` | Functional fixed-loopback run console `lmre ui` (slice B) |
| `2479734` | Verified OmniRoute delegation boundary and repo-local offload skill |
| `5520c9a` | Review fix: run-console index survives an auto-selection race |

The two protected 2026-08-05 Fable prompt documents were never staged and
remain untracked, as required.

## Open item: merge PR #32

**PR #32 is reviewed, green, and ready to merge, but not merged.** The
`gh pr merge` call was refused by the local permission classifier, not by
GitHub and not for any repository reason. Either merge it manually or grant
the permission and re-run. Nothing else blocks it.

## Review findings from this pass

Two defects were found by review and fixed, both filesystem-race class:

1. `_comparison_scan` set `metrics` to `None` when the state read failed after
   `classify_bundle` had already verified the bundle, and `build_comparisons`
   then dereferenced it — raising `TypeError` and failing the whole comparisons
   build. Now reports `UNAVAILABLE` and keeps the member visible.
2. `GET /` auto-selects the newest plan and had no handler for `ConsoleError`,
   so a racing bundle escaped the request handler unsanitized and stranded
   every other plan behind the entry point. Auto-selection now degrades to the
   plan list; explicit `/runs/<id>` requests still fail closed.

Both have regression tests. The second test was confirmed to fail against the
pre-fix module.

One gap was found and deliberately **not** closed: the run console's
`Host`/`Origin`/CSRF tests exercise the pure validator functions, not the real
HTTP handler, so nothing proves `do_POST` invokes them in the right order. The
validators are correct by inspection. This is item 3 of the next slice.

## Verification state at handoff

- 566 retained tests pass; 5 skip because a local Osaurus holds port 1337
  (pre-existing, environment-dependent, unrelated to the diff).
- All six retained dry-config commands pass.
- `ruff check` clean on all new UI modules and tests. Note that pre-existing
  findings exist elsewhere in the tree under a default rule set; only the new
  modules were required to be clean, matching prior slices.
- `git diff --check` and byte-compilation clean.
- No live run was initiated. No policy was adopted or replaced. No runtime,
  provider, credential, or model was contacted.
- **This repository has no CI.** `gh pr checks` reports nothing. Local
  verification is the only gate; re-run it rather than quoting it.

## Next slice: release-readiness hardening

Spec: `docs/superpowers/specs/2026-08-07-release-readiness-hardening.md`.

It contains a measured clean-environment install audit. The headline finding:
**`pip install .` produces a CLI that crashes on `lmre --help`**, because
`config/` is never packaged and configuration is read at import time, while 21
modules resolve paths from a presumed repository checkout.

The spec opens with a **decision that belongs to Jason** and must not be
assumed: whether the supported distribution shape is the repository checkout
(recommended — smallest honest change) or a genuinely installable package
(larger, and risks changing plan input hashes, which would invalidate
comparability against existing sealed evidence). Get that answer before
implementing.

## OmniRoute

Guide: `docs/omniroute-claude-code.md`. Skill:
`.claude/skills/omniroute-offload/SKILL.md`.

Verified working: routing with an explicit model, zero cost on the free lanes.
Verified broken: no combos configured, so combo-selection tools fail; the
registered `chatgpt-lmre-context` skill is listed but returns
`Skill not found`. Newly measured: **long generations time out** at the MCP
call boundary — short exchanges only. Do not plan a slice around bulk
offload until that is retested.

The sanitization boundary is unchanged. Obtain current-session approval before
transmitting project context, and exclude credentials, source code, local
paths, run identities, raw evidence, model outputs, and machine-specific
configuration.
