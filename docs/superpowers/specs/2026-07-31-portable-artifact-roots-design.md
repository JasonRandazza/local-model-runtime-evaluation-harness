# Portable Artifact Roots Design

**Date:** 2026-07-31

**Status:** Approved for implementation

## Purpose

Remove developer-specific `/Users/jrazz/...` model locations from active
configuration without weakening LMRE's fixed-command, immutable-plan, or
exact-process safety boundaries.

The repository continues to define which model artifact each family/quant
uses. A local, ignored machine profile defines only where two approved root
categories live on one computer.

## Boundaries

This slice is non-live. It must not contact or control Osaurus, oMLX, OptiQ,
Keychain, provider configuration, listeners, processes, or models.

It does not:

- add arbitrary executable, endpoint, model, or output path arguments;
- scan caches or search for models;
- download, move, copy, link, rename, or delete model artifacts;
- change provider configuration;
- change the managed plan schema or invalidate existing sealed evidence;
- implement `lmre doctor`, a setup wizard, or a frontend.

## Configuration Contract

### Committed artifact templates

Family and cell JSON retain their existing strict schemas. Machine-specific
absolute paths are replaced by exactly one leading root token:

```text
{LMRE_ROOT:local_models}/gemma-4-12B-it-qat-JANG_4M
{LMRE_ROOT:huggingface_hub}/mlx-community/gemma-4-12B-it-qat-OptiQ-4bit
```

Only these root keys are accepted:

- `local_models`
- `huggingface_hub`

The suffix is committed product configuration. It must be a normalized,
non-empty POSIX-style relative path with no `.` or `..` segments. A root
token may appear only at the beginning of an artifact template.

Cell model IDs and fixed start-command arguments may use the exact
`{artifact_path}` token. Resolution substitutes the already validated
artifact path. Routed overhead model IDs use the same token and the already
resolved backend artifact. No other token syntax is accepted.

### Local machine profile

The fixed production location is:

```text
.lmre/machine-profile.json
```

The directory is already ignored by Git. The strict schema is:

```json
{
  "schema_version": "1.0.0",
  "artifact_roots": {
    "huggingface_hub": "/absolute/path/to/huggingface/hub",
    "local_models": "/absolute/path/to/local/models"
  }
}
```

Both keys are required and no other fields or root keys are accepted. Root
values must be absolute, normalized directories. Relative paths, `~`,
environment-variable interpolation, missing paths, files, and broken links
fail closed.

The repository includes a sanitized example at
`config/machine-profile.example.json`. The developer's actual profile remains
untracked.

## Resolution Model

`artifact_profile.py` owns profile parsing and token resolution. It returns an
immutable `ArtifactRoots` value.

Unresolved committed configuration remains safe to inspect without reading a
machine profile. `Cell.load` and `ModelFamily.load` first enforce the existing
cross-file identity rules on committed templates. Callers that require local
paths then resolve through an explicit `ArtifactRoots` dependency.

Resolution performs these checks in order:

1. validate the exact profile schema and fixed root-key set;
2. validate and normalize each absolute root directory;
3. parse the committed leading root token;
4. reject unsafe or unknown relative suffixes;
5. join and normalize the root and suffix;
6. prove the result remains beneath the configured root;
7. substitute `{artifact_path}` in allowlisted model-ID and command fields;
8. reject any unresolved or unknown token.

The resolved `Cell` retains the current runtime-facing shape: absolute
`artifact_path`, exact `model_id`, and exact `start_command`. Runtime adapters
therefore keep their current absolute-path and fixed-command validation.

## Managed Plan Binding

The managed plan schema remains `1.0.0`.

During plan creation, the fixed local profile is loaded and its SHA-256 is
added to the existing `input_hashes` map under the fixed repository-relative
key `.lmre/machine-profile.json`. The plan already incorporates
`input_hashes` into `plan_hash`, so the artifact-root mapping becomes part of
the authorized immutable plan without adding a new plan field.

Plan verification special-cases only that exact logical input key so tests can
inject a temporary profile. Production run and resume always verify the fixed
`.lmre/machine-profile.json`. A changed, missing, or malformed profile fails
before any collector or runtime action.

All managed collectors resolve cells using the verified profile. Low-level
live and dry-config surfaces use the same loader. Tests inject temporary
profiles and roots; they never depend on the developer's machine profile.

## Compatibility

- Existing sealed plans contain no machine-profile input entry and retain
  their original canonical serialization and hash behavior.
- Newly created plans use the unchanged schema with one additional ordinary
  `input_hashes` entry.
- Results-browser parsing remains unchanged.
- Fixed endpoints, executable names, ports, process identity, lifecycle,
  policy, and evidence semantics remain unchanged.

## Error Behavior

Expected configuration failures use sanitized, deterministic errors naming
the profile field, root key, cell, or artifact template—not arbitrary file
contents.

No profile or artifact path is a credential. Local paths may appear in local
dry-config remediation, but committed tests and documentation use synthetic
paths.

## Fable Doctor Integration

`lmre doctor` must consume `ArtifactRoots` and the existing matrix loaders.
It should report profile errors first, then exact resolved artifact readiness.
It must not implement a second token parser, accept path overrides, or scan
for candidate models.

## Acceptance Criteria

- No active family, cell, overhead-pair, source, README, or current operator
  documentation contains `/Users/jrazz` model paths.
- A valid temporary profile resolves every active family/cell deterministically.
- Invalid profiles and unsafe tokens fail closed.
- OptiQ model IDs and start commands use the resolved absolute artifact path.
- oMLX temporary catalogs receive the resolved absolute artifact path.
- New managed plans hash the fixed machine-profile input and run/resume detect
  profile changes.
- Existing managed plan schema and sealed-evidence reading remain compatible.
- Unit tests and every retained dry-config command pass without live contact.
