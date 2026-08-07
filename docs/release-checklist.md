# Release Checklist

Run this before publishing a release. Every item is verifiable as done or not
done; none is a judgement call. Nothing here authorizes a live run.

Record the results somewhere durable. If an item fails, fix it or state the
limitation in the release notes — do not silently pass it.

## 1. Packaging and clean-environment install

- [ ] Build a wheel and install it into a throwaway virtualenv on a supported
      Python, from a working directory **outside** the source tree.
- [ ] Run `--help` for every declared console script. All seven must succeed.
- [ ] Confirm the shipped workspace template is present in the installed
      package and contains `config/`, `suites/`, and `corpora/`.
- [ ] `lmre init` into an empty directory succeeds and reports the files copied.
- [ ] `lmre init` into a populated workspace is refused without `--force`.
- [ ] From the scaffolded workspace, `lmre doctor` reports the harness and
      configuration sections `OFFLINE_READY`.
- [ ] Confirm no configuration is read at import time
      (`tests/test_import_purity.py` passes).
- [ ] Confirm install requires no network access beyond fetching the build
      backend and the package itself. No model, corpus, or runtime is downloaded.

## 2. Supported first-run path

- [ ] Follow the README install sequence verbatim on a clean machine or fresh
      virtualenv, with no undocumented edits.
- [ ] Confirm `lmre doctor` reports honestly with no model artifacts present and
      labels every live fact `NOT_CHECKED_LIVE`.
- [ ] Confirm `lmre browse` works against an empty results root and against a
      results root holding one degraded bundle.
- [ ] Confirm no documented first-run step adopts a policy or starts inference.
- [ ] Confirm the source-checkout path still works via the `./bin/` wrappers.

## 3. Version, changelog, and support boundary

- [ ] `__init__.py`, the built wheel metadata, and the release tag all agree.
- [ ] CHANGELOG lists operator-visible changes and names anything whose meaning
      changed.
- [ ] The support boundary states the supported OS, Python floor, and runtimes,
      and names what is out of scope.
- [ ] Known limitations in `docs/status.md` match reality, with no claim local
      verification did not establish.
- [ ] A licensing decision is recorded. Resolved: MIT, in `LICENSE`, declared in
      package metadata as `License-Expression: MIT`.

## 4. Pre-release verification gates

- [ ] Full retained suite passes. Every skip is explained and attributed to the
      environment, not to the diff.
- [ ] All six retained dry-config commands pass.
- [ ] Linter passes on every changed module.
- [ ] `git diff --check` and byte-compilation pass.
- [ ] **Plan-hash oracle is byte-identical** for the managed and open-mix
      planning paths. This is the evidence-comparability gate; see below.
- [ ] No credential, token, absolute local path, run identity, or raw evidence
      appears in any added or changed file.
- [ ] Generated results remain untracked.
- [ ] Confirm no live run, policy adoption, or provider edit occurred during
      release preparation.

### The plan-hash gate

`input_hashes` is a cross-run comparison dimension and its keys are
workspace-relative path strings. Anything that changes where a plan input
resolves — moving `config/`, changing workspace resolution, renaming a
suite file — changes those keys, and runs planned before and after would read
`INCOMPARABLE` despite byte-identical content.

Sealed bundles are not at risk: `EvidenceBundle.verify()` recomputes the plan
hash from the stored plan and never touches the filesystem. The risk is
strictly to *future* comparability against existing evidence.

Before releasing a change that touches path resolution or configuration layout,
build the plan for every checked-in recipe and open mix using the real machine
profile, record the plan hash and `input_hashes` keys, and confirm they are
unchanged afterwards.

## 5. Optional live acceptance (separately authorized)

- [ ] Obtain explicit current-session live authorization first.
- [ ] Run exactly one configured lane against one immutable plan the adopted
      policy already authorizes.
- [ ] Confirm the run seals, its checksum manifest verifies, and runtime
      ownership is recorded truthfully, including any attached operator-owned
      process.
- [ ] Record the outcome honestly even if it fails. Do not retroactively seal or
      reinterpret prior evidence.

## 6. Rollback

- [ ] The previous release remains installable and functional.
- [ ] Rolling back requires no change to existing sealed evidence and no re-run
      of a completed evaluation.
- [ ] Any packaging change is reversible without rewriting plan hashes or
      invalidating sealed comparability.
- [ ] Rollback trigger conditions and the deciding owner are recorded.

## Known gaps

- No pinned linter configuration, so the default rule set reports pre-existing
  findings across the tree. Prior slices required only new modules to be clean,
  and CI therefore does not run a linter. Adopting a pinned configuration would
  let CI enforce it.
- CI does not run a whitespace check. The obvious whole-tree form fails on
  intentional Markdown hard line breaks, which are trailing spaces by design;
  scoping it to a pull-request diff is possible but was not worth the
  complexity. `git diff --check` remains a local pre-publication step.
- No live acceptance runs in CI, deliberately. Live work stays operator-driven
  and separately authorized.

Resolved since first draft: MIT licensing, and CI now runs the suite on two
Python versions, the six dry-config commands, and a clean-environment install
smoke test of the documented first-run path.
