# Managed Free-Bind Declarations (2026-08-05)

**Status:** Implemented offline declaration and validation contract.
**Live authority:** None. Proposal, validation, inspection, and adoption do not
create a managed plan, contact a runtime, authorize inference, or permit process
lifecycle actions. Binding execution is a separate deferred slice.

## Purpose

Controlled comparison classes preserve the three-cell native baseline and may
append reviewed cells. Managed free binding is the next bounded step: an
operator may choose and order existing same-family native cells without editing
checked-in comparison-class configuration. The result is a local, immutable,
reviewable declaration rather than an executable plan.

## Offline workflow

```bash
./bin/lmre binding propose \
  --id gemma-curated-native-v1 \
  --family gemma-4-12b-qat \
  --cell jang_4m__osaurus \
  --cell oq4_fp16__omlx \
  --cell optiq_4bit__optiq \
  --notes "Reviewed ordered Gemma cells"

./bin/lmre binding show gemma-curated-native-v1
./bin/lmre binding validate gemma-curated-native-v1
./bin/lmre binding adopt gemma-curated-native-v1
```

`show` returns the immutable proposal, its current revalidation, and the
adoption record when one exists. Proposals are written beneath the ignored path
`.lmre/bindings/proposals/<binding-id>.json`. Explicit adoption writes a
separate immutable record beneath `.lmre/bindings/adopted/<binding-id>.json`.
Existing proposal or adoption records are never overwritten.

## Frozen contract

1. The CLI accepts a safe binding ID, safe family ID, and an ordered repeated
   `--cell` list. It does not accept a binding-specific configuration or output
   path, artifact root, endpoint, server, model ID, executable, or shell command.
2. A binding contains between two and nine unique cells. Every cell must be an
   exact regular JSON file under `config/matrix/cells/`; symlinks and
   path-shaped IDs fail closed.
3. Every cell must belong to the selected checked-in family and run on the
   native server declared for its quant. Cross-family, cross-size, arbitrary
   runtime, and non-native remapping remain outside this slice.
4. Proposal creation hashes the family file, every selected cell file, and the
   exact fixed `.lmre/machine-profile.json`. It resolves artifacts only through
   the two approved profile roots.
5. A proposal is `READY_FOR_ADOPTION` only when all selected artifact paths are
   readable directories. Missing, wrong-kind, unreadable, or invalid-template
   artifacts produce `ACTION_REQUIRED`; the proposal remains inspectable, but
   adoption fails closed.
6. Revalidation recomputes configuration and machine-profile hashes. Any
   change produces `STALE_INPUTS` and requires a new versioned proposal.
7. Proposal and adoption records use canonical SHA-256 hashes, mode `0600`,
   the managed state root, create-only writes, exact JSON fields, and
   `live_authority: false`.
8. Explicit adoption records review intent only. It does not adopt an operator
   policy, create an evidence bundle, modify repository configuration, or
   authorize later execution.
9. All commands report `NOT_CHECKED_LIVE`. The implementation does not import
   or invoke transports, runtime adapters, process inspection, credentials,
   resource checks, provider configuration, or inference code.

## Explicitly deferred

- binding an adopted declaration into a new immutable managed-plan schema;
- policy request calculation for the selected cells;
- managed collector routing, lifecycle, resume, evidence, and sealing;
- non-native-server cell remapping;
- cross-family, cross-size, or heterogeneous/open-mix comparison;
- arbitrary endpoints, commands, model paths, provider edits, or downloads.
