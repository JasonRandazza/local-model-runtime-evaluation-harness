# Offline Doctor Design

**Status:** Current design for the offline `lmre doctor` slice (2026-08-05).
**Baseline:** `main` at `f3269e5` (portable artifact roots merged, PR #17;
results browser merged, PR #16).

## Goal

Give a competent operator a deterministic, offline answer to "is this machine
statically prepared for a later live evaluation?" without contacting,
executing, inspecting, or configuring any model runtime. The doctor reads
static local state and reports; it never mutates anything and writes nothing.

## Architecture Decision

Three shapes were compared:

| Shape | Verdict |
| --- | --- |
| Pure diagnostic engine + typed result + thin renderers wired into the managed CLI | **Chosen** (approved default; no repository conflict found). |
| Separate `lmre-doctor` executable | Rejected: duplicates managed CLI conventions with no compensating benefit. |
| Interactive setup wizard / HTML app | Out of scope by prompt. |

Import-boundary evidence drives the shape: `managed_run_cli.py` imports
live-capable modules (`runtime_manager`, `runtime_adapters`, `transport`,
`process_inspection`) at module import time, so the engine cannot live there
or import it. The verified transitively-clean import set for the engine is:
`artifact_profile`, `matrix_config`, `operator_policy`, `overhead_config`,
`preference_config`, `rag_config`, `managed_run_types`, `run_identity`, plus
stdlib (`shutil.which` performs PATH lookup only and executes nothing). The
CLI imports the engine for dispatch; the engine never imports the CLI.

## Module Boundaries

| Piece | Responsibility |
| --- | --- |
| `doctor.py` — `run_diagnostics(...)` | Read static inputs through existing validators; return one plain-dict diagnostic result. No printing, no writing, no live-capable imports. |
| `doctor.py` — `render_text(result)` | Pure projection of the same result to a concise operator checklist. No state access, no recomputation. |
| `managed_run_cli.py` | `doctor` subparser (`--format {json,text}`, `--state-dir`), dispatch, existing `_emit`/sanitized error path. |

Dependency injection (test seams, mirroring existing conventions):
`machine_profile_path` flows through the existing `main(argv, *,
machine_profile_path=DEFAULT_MACHINE_PROFILE_PATH)` keyword — no CLI option
exposes it. `run_diagnostics` accepts `which: Callable[[str], str | None] =
shutil.which`, `now: datetime | None = None`, `state_root`, and
`repository_root` keywords with production defaults.

## Readiness Vocabulary

Applied once, during aggregation:

- `OFFLINE_READY` — the prerequisite this offline command may check passed.
- `ACTION_REQUIRED` — a required local prerequisite is missing or invalid.
- `WARNING` — non-blocking condition worth attention.
- `NOT_CHECKED_LIVE` — the fact needs runtime, provider, credential,
  listener, process, memory, or inference contact and was deliberately not
  checked.

`overall_readiness` is `ACTION_REQUIRED` if any finding is
`ACTION_REQUIRED`, else `OFFLINE_READY`. Warnings never block;
`NOT_CHECKED_LIVE` never blocks and is always present. The words `READY`,
`PASS`, or any claim of live readiness never appear alone; the text renderer
carries a fixed disclaimer that live facts were not checked.

## Result Contract

```json
{
  "doctor_schema_version": "1.0.0",
  "overall_readiness": "OFFLINE_READY" | "ACTION_REQUIRED",
  "sections": [
    {"section": "harness" | "commands" | "machine_profile" | "configuration"
                | "artifacts" | "policy" | "families",
     "findings": [
       {"check": "<stable id>",
        "status": "<vocabulary value>",
        "summary": "<one line>",
        "detail": "<sanitized detail or null>",
        "remediation": "<manual action or null>",
        "doc": "<repo doc path or null>"}
     ]}
  ],
  "actions": ["<deterministic deduplicated remediation strings>"]
}
```

The CLI wraps it as `{"ok": true, "diagnostic": <result>}`. `ok` means the
diagnostic completed, not that prerequisites passed. Exit `0` whenever a
complete diagnostic is emitted (including `ACTION_REQUIRED`); nonzero only
for malformed invocation (argparse's conventional exit) or an unexpected
internal failure through the existing sanitized error path (exit `1`).

## Checks

1. **harness** — `sys.version_info >= (3, 11)` (the `pyproject.toml` floor);
   the seven `bin/` wrappers exist and are executable; core operator docs
   exist (`README.md`, `docs/managed-runs.md`, `docs/status.md`,
   `docs/architecture.md`).
2. **commands** — injected `which` lookup for the fixed names `osaurus`,
   `omlx`, `optiq`. Found → `OFFLINE_READY` (path shown locally); missing →
   `ACTION_REQUIRED`. Versions, health, and behavior are `NOT_CHECKED_LIVE`.
   Nothing is executed.
3. **machine_profile** — `load_artifact_roots(machine_profile_path)`.
   Valid → `OFFLINE_READY` with the two root paths; `ArtifactProfileError` →
   `ACTION_REQUIRED` with the sanitized message and the copy-example
   remediation. No repair, no override, no `~`/env expansion.
4. **configuration** — per managed recipe (`config/managed-runs/*.json` via
   `run_identity` recipe validation) and per active family:
   `Campaign.load`, `load_family`, cell loading/validation, `MatrixSuite`,
   `PreferenceSuite`, `RagSuite`, `RagCorpus` loaders, the
   preference/RAG/overhead mapping loaders, and the existing
   `run_identity` native-triple cross-check. A failure fails that
   family/recipe closed and continues; business rules are not duplicated.
5. **artifacts** — only when the profile is valid: resolve the active
   families/cells through the existing `.resolve(roots)` APIs and check each
   exact resolved path: present / missing / broken symlink / wrong-kind /
   unreadable. Model artifacts must be directories. No cache scan, no size
   calculation, no mutation. If the profile is invalid, the section reports
   one `ACTION_REQUIRED` "skipped: profile invalid" finding.
6. **policy** — `load_adopted_policy(state_root, now=now)`. Valid →
   `OFFLINE_READY` with `policy_id`, hash, `adopted_at`, expiry state;
   `PolicyError` codes (`missing`, `invalid`, `hash_mismatch`, `expired`) →
   `ACTION_REQUIRED` with the adopt-command remediation described as a
   manual review step. Never adopts, repairs, or prints anything beyond
   policy metadata (the policy schema holds no secrets).
7. **families** — per family + recipe combination: aggregate the statuses
   above into one offline readiness verdict with explicit reasons, plus the
   fixed `NOT_CHECKED_LIVE` qualifications: endpoint reachability, provider
   inventory, process identity, credentials, memory headroom, and actual
   model behavior.
8. **actions** — deduplicated, deterministically ordered remediation list
   derived from `ACTION_REQUIRED` findings, each linked to a current doc
   (`docs/managed-runs.md`, `docs/matrix.md`, `docs/doctor.md`). Suggested
   commands are existing safe LMRE commands, never executed.

## Error and Privacy Behavior

- One failed check never hides other sections; expected failures are
  structured findings, not stack traces.
- Detail strings come from the existing validators' sanitized messages and
  pass through the CLI's `_sanitize_error` redaction on the error path.
- No environment variables, credential values, provider bodies, raw model
  responses, or command output are ever read or printed. Local artifact and
  root paths may appear in local output for remediation; committed fixtures
  and docs use synthetic paths only.
- Nothing is persisted; the command writes no file.

## Explicit Non-Goals

Executing external CLIs (even `--version`); port/process/listener/provider/
inventory/memory/inference checks; credential or Keychain access; policy
adoption or repair; plan/proposal/run/evidence creation; model search,
download, or storage analysis; arbitrary path or executable selection; setup
wizard, server, or frontend; new dependencies; snapshot persistence/export
(deferred, separate design).

## Testing Contract

TDD. Injected `which`, `machine_profile_path`, `state_root`,
`repository_root`, and `now`; fixtures built with existing test helpers
(`write_machine_profile`, policy adoption via `adopt_policy` into temp
state roots) plus synthetic config trees under temp dirs. Coverage per the
handoff: fully-satisfied offline state (with `NOT_CHECKED_LIVE` present),
missing commands, missing/unreadable/broken-symlink artifacts, all policy
states (valid/absent/expired/hash-mismatch/malformed), all machine-profile
failure modes, template resolution failures surfaced through
`ArtifactProfileError` (no duplicate parsing), one malformed family that
does not hide other checks, mixed-family determinism and deduplicated
actions, JSON/text projection parity, hostile fixture strings not leaked,
exit-code behavior. Tripwire tests: monkeypatched `socket.socket`,
`subprocess.Popen/run/call`, and `os.kill` raise if touched during a full
diagnostic; a static import scan of `doctor.py` proves no forbidden module
(`transport`, `runtime_manager`, `runtime_adapters`, `process_inspection`,
`credentials`, `resources`, `matrix_lifecycle`, `matrix_servers`,
`managed_run`, `managed_run_cli`, `subprocess`, `socket`, `http`) is
imported directly or via the engine's import graph.
