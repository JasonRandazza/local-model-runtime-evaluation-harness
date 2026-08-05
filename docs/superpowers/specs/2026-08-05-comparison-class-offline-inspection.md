# Comparison-Class Offline Inspection (2026-08-05)

**Status:** Implementation contract.
**Authority:** Read-only and non-live. This command grants no planning,
execution, lifecycle, provider, credential, or inference authority.

## Purpose

The controlled-expansion contract must not require an operator to guess
whether a class is still baseline-only, whether the repository contains a
reviewed extra native cell, or whether selected artifacts exist under the
approved machine roots. `lmre comparison-class inspect <id>` answers those
questions without creating a plan or contacting a service.

## Frozen contract

1. The command accepts a safe comparison-class ID, never a path, endpoint,
   cell list, model ID, command, or artifact root.
2. It loads the existing checked-in class, family, baseline campaign, and
   native cell declarations through their production validators.
3. Reviewed candidates are derived only from additional quant definitions in
   the class family and the exact corresponding native cell file under
   `config/matrix/cells/`. Arbitrary on-disk directories are not inferred to
   be family members.
4. Artifact templates resolve only through the fixed ignored machine profile.
   Inspection reports `PRESENT`, `MISSING`, `WRONG_KIND`, `UNREADABLE`, or
   `INVALID_TEMPLATE` for selected and reviewed-candidate artifacts.
5. The stable expansion states are:
   - `BASELINE_ONLY`: the class has no extra cells and the repository has no
     reviewed candidate cells;
   - `REVIEWED_CANDIDATES_AVAILABLE`: at least one reviewed candidate exists,
     but the class has not selected an extra cell;
   - `DECLARED_EXPANSION_READY`: the class selects extra cells and every
     selected artifact is statically usable;
   - `ACTION_REQUIRED`: the selected class cannot be used from the current
     machine profile because a selected artifact is missing, unreadable, or
     the wrong kind.
6. `live_status` is always `NOT_CHECKED_LIVE`. The command must not import or
   invoke transports, runtime adapters, process inspection, Keychain access,
   service commands, provider configuration, or inference code.
7. The command writes nothing. It does not create proposals, plans, evidence
   bundles, policies, or generated configuration.
8. A successful inspection returns `ok: true` even when the honest status is
   `ACTION_REQUIRED`; malformed or unknown configuration uses the existing
   sanitized CLI error envelope and a non-zero exit code.

## Output boundary

The JSON result includes class identity, ordered baseline/extra/selected cell
IDs, declared duration, expansion status, selected artifact findings, reviewed
candidate findings, a stable next action, and `live_status`. Local resolved
paths may be shown because the output remains on the operator's machine and is
not promoted into committed evidence.

## Explicitly deferred

- scanning arbitrary model directories and guessing model-family identity;
- downloading, moving, deleting, or converting model artifacts;
- generating or modifying family, cell, class, or policy files;
- runtime reachability, loaded-model, provider, credential, or memory checks;
- policy adoption, immutable planning, or live execution;
- cross-family, cross-size, or open-mix comparison contracts.
