# Release-Readiness Hardening

**Status:** Proposed bounded slice (2026-08-07). Not yet approved for
implementation.
**Predecessor:** the North Star feature chain is functionally complete through
PR #32 (recorded metric visibility and the functional run console).

## Goal

Make the first public release credible and repeatable. The feature work is
done; what is missing is a truthful, verifiable story for how a new operator
obtains this tool, confirms it is ready, and inspects results — plus the
release mechanics to publish and roll back.

This slice adds no evaluation capability. It changes packaging, documentation,
and coverage only.

## Findings from the clean-environment audit (2026-08-07)

These were measured, not assumed. A throwaway virtualenv installed the project
with `pip install .` from a neutral working directory.

| # | Finding | Evidence |
|---|---|---|
| 1 | **The installed CLI is entirely non-functional.** `lmre --help` crashes before argument parsing. | `FileNotFoundError` for `<venv>/lib/python3.14/config/preference/defaults.json` |
| 2 | Root cause: `config/` is never packaged, and configuration is read at **import time**. | `preference_config.py` executes `default_preference_cells()` at module scope; `managed_run_cli` imports it transitively via `doctor`. |
| 3 | Path resolution assumes a repository checkout. | 21 modules derive paths from `Path(__file__).resolve().parents[2]` (`REPOSITORY_ROOT`), which lands inside `site-packages` once installed. |
| 4 | Five of seven CLI entry points are undeclared. | `[project.scripts]` declares `lmre` and `lmre-discover` only; `bin/` provides seven. |
| 5 | No `[build-system]` table. | Install works only via setuptools' legacy fallback; the build backend is unpinned. |
| 6 | No `LICENSE`, no `CHANGELOG`, no release notes. | Absent from the repository root. |
| 7 | No CI. | No `.github/`; `gh pr checks` reports nothing, so local verification is the only gate. |
| 8 | Run-console HTTP boundary is untested at handler level. | `Host`/`Origin`/CSRF tests call the pure validators directly; nothing proves `do_POST` invokes them in order. |

Findings 1–3 are one defect with one decision behind it, addressed first.

## Decision required: what is the supported distribution shape?

The tool is currently a **repository-checkout tool** that also happens to
declare console scripts. Those two facts contradict each other, and the
contradiction is what finding 1 exposes.

**Option A — declare checkout-based operation as the only supported path
(recommended).** Remove `[project.scripts]`, document `git clone` plus the
`bin/` wrappers as the supported invocation, and add a `[build-system]` table
only if the package must remain importable for tests. Smallest honest change;
matches how the harness is actually used and how `config/`, `suites/`,
`corpora/`, and `results/` already resolve relative to the checkout.

**Option B — make the package genuinely installable.** Move `config/` inside
the package as package data, convert 21 modules from `REPOSITORY_ROOT` to
`importlib.resources`, make configuration loading lazy instead of
import-time, and declare all seven entry points. Substantially larger, touches
path resolution used by sealed-evidence code, and risks changing plan input
hashes — which would invalidate comparability against existing sealed runs.

Option B's hash risk is the deciding factor: plan hashes bind executable input
paths, and existing sealed evidence must stay verifiable. Recommend Option A
for this release and revisit B only if external distribution is ever wanted.

**This decision belongs to Jason and is not assumed by this spec.**

## Scope

1. **Resolve the packaging contradiction.** Implement the chosen option above.
   Whichever is chosen, `pip install .` must either work end to end or must
   not be advertised at all. A published install path that crashes on `--help`
   is not acceptable.
2. **Define the supported first-run path.** One documented sequence from
   obtaining the tool through the offline `lmre doctor` readiness check to
   read-only `lmre browse` inspection, with no live run and no policy adoption.
   Each step must state what it does *not* authorize.
3. **Close the run-console handler gap (finding 8).** Add coverage that drives
   the real HTTP handler over a loopback socket and proves: a wrong `Host` is
   refused, a missing/foreign `Origin` is refused, a missing or mismatched CSRF
   token is refused, `GET` cannot mutate, and a valid POST reaches the
   controller exactly once. Fake child processes only; no live run.
4. **Reconcile release metadata.** Version, changelog or release notes, a
   `LICENSE` decision, an explicit support boundary, and a known-limitations
   list that matches `docs/status.md` rather than restating it loosely.
5. **Write the release checklist.** Non-live verification gates, the optional
   separately authorized live acceptance step, artifact expectations, and
   rollback.

## Release checklist (draft deliverable for item 5)

### Packaging and clean-environment install
- [ ] Create a throwaway virtualenv on a supported Python and obtain the tool
      by the documented supported path only.
- [ ] Confirm every advertised entry point runs `--help` successfully from a
      working directory outside the source tree.
- [ ] Confirm no configuration file is read at import time.
- [ ] Confirm every declared entry point exists and every existing entry point
      is either declared or documented as unsupported.
- [ ] Confirm the build backend is explicitly declared and pinned.
- [ ] Confirm no network access is required by install or by any readiness
      command.

### Supported first-run path
- [ ] Follow the documented first-run sequence verbatim on a clean checkout and
      confirm each step succeeds without editing an undocumented file.
- [ ] Confirm the readiness check reports honestly on a machine with no local
      model artifacts present, and labels every live fact as not checked.
- [ ] Confirm read-only inspection works against an empty results root and
      against a results root containing one degraded bundle.
- [ ] Confirm no step in the documented path adopts policy or starts inference.

### Version, changelog, and support boundary
- [ ] Confirm the package version, any documented version, and the release tag
      agree.
- [ ] Confirm release notes list user-visible changes since the previous tag
      and name the specific evidence states that changed meaning, if any.
- [ ] Confirm the support boundary states the supported OS, Python version,
      runtimes, and explicitly names what is out of scope.
- [ ] Confirm known limitations match the current status document with no
      claim that local verification did not establish.
- [ ] Confirm a licensing decision is recorded.

### Pre-release verification gates
- [ ] Full retained test suite passes; every skip is explained and attributed
      to the environment, not to the diff.
- [ ] All retained dry-config commands pass.
- [ ] Linter and formatter pass on all changed modules.
- [ ] Whitespace and byte-compilation checks pass.
- [ ] No credential, token, absolute local path, run identity, or raw evidence
      appears in any file added or changed for the release.
- [ ] Generated results remain untracked.
- [ ] Confirm no live run, policy adoption, or provider edit occurred during
      release preparation.

### Optional live acceptance (separately authorized)
- [ ] Obtain explicit current-session live authorization before any live step.
- [ ] Run exactly one configured lane against one immutable plan already
      authorized by the adopted policy.
- [ ] Confirm the run seals, its checksum manifest verifies, and runtime
      ownership is recorded truthfully including any attached operator process.
- [ ] Record the outcome honestly even if it fails; do not retroactively seal
      or reinterpret prior evidence.

### Rollback
- [ ] Confirm the previous release tag remains checked out and functional.
- [ ] Confirm rolling back requires no change to existing sealed evidence and
      no re-run of a completed evaluation.
- [ ] Confirm any packaging change is reversible without rewriting plan hashes
      or invalidating sealed comparability.
- [ ] Record the rollback trigger conditions and who decides.

## Explicit Non-Goals

- new evaluation capability, collectors, suites, or metrics;
- cloud services, hosted endpoints, telemetry, or auto-update;
- automatic provider editing or installer-driven model downloads;
- a generalized plugin system;
- retroactive sealing or reinterpretation of existing evidence;
- publishing to a public package index as part of this slice.

## Verification Contract

Non-live throughout. Tests use temporary directories, fake processes, and
configuration reads only, and must not contact Osaurus, oMLX, OptiQ, Keychain,
or a real model. The clean-environment install audit runs in a throwaway
virtualenv outside the source tree and must not require network access.

The retained suite and all retained dry-config commands must pass before
publication. Any live acceptance is a separate, explicitly authorized step
governed by `AGENTS.md` and the exact adopted policy.
