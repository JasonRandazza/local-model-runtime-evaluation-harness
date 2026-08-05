# Controlled Expansion Comparison Class (2026-08-05)

**Status:** Implemented non-live contract and managed-plan binding.
**Live authority:** Unchanged. Creating a plan is non-live; `lmre run` still
requires an explicit user request and an adopted policy authorizing the exact
immutable plan.

## Purpose

Controlled expansion is the bounded step between the retained native diagonal
and Approach 3 free binding. It lets a reviewed managed comparison append
optional same-family cells without weakening the three-cell native baseline,
accepting arbitrary paths, or opening heterogeneous model mixes.

## Frozen contract

1. Definitions live only at
   `config/comparison-classes/<comparison-class-id>.json`. The CLI accepts the
   safe ID, not a path or comma-separated cell list.
2. A definition contains exactly `schema_version`, `comparison_class_id`,
   `revision`, `family_id`, `baseline_campaign_path`, `extra_cell_ids`,
   `estimated_minutes`, and `notes`. Unknown or missing fields fail closed.
3. `baseline_campaign_path` must be the family's fixed
   `config/matrix/<family-id>-campaign.json`. Its three native cells remain
   first and in their existing order.
4. Extra cells must already exist under `config/matrix/cells/`, belong to the
   same family, match their quant's declared `native_server`, use the fixed
   loopback endpoint for that server, and be unique. Symlinks and path-shaped
   cell IDs are rejected.
5. A family may declare additional reviewed quants, but its retained native
   campaign still contains exactly three distinct baseline quants and exactly
   one native cell for each of Osaurus, oMLX, and OptiQ.
6. Managed preference and RAG operate over the complete ordered class. Matrix
   measurement uses the baseline campaign settings with the reviewed extra
   cells appended. Overhead remains limited to the family's existing baseline
   pair definitions; this slice does not invent routes for extra cells.
7. Each class declares `estimated_minutes`. Planning rejects an estimate below
   the conservative request-count-scaled baseline, then passes the declared
   duration through the existing adopted-policy ceiling.
8. Execution remains sequential (`max_parallel_models = 1`) and subject to
   the existing memory floor, request ceiling, runtime identity, reclaim
   notice, loopback, credential, provider, and cleanup rules.
9. Plan schema `1.1.0` records `comparison_class_id`, the repository-relative
   class path, and `baseline_cell_ids`. Its input hashes bind the class, family,
   campaign, every selected cell, suites, pairs, corpus, recipe, and machine
   profile before inference.
10. Legacy plan schema `1.0.0` remains readable and hash-verifiable. It is
   interpreted as an undeclared native-baseline plan; its serialized shape and
   original hash are not rewritten.
11. The sealed-results browser exposes the class ID and treats it as a
    comparability dimension. Different classes or selected-cell inputs never
    become silently comparable because they share a human-supplied comparison
    ID.

## Current checked-in class

`gemma-native-baseline-v1` declares the existing Gemma native triple with no
extra cells. It proves the contract without fabricating an unverified model
artifact. A real expansion requires a new reviewed family quant, cell file,
and versioned class definition; adding those artifacts is a separate,
evidence-backed configuration change.

## Managed planning shape

```bash
./bin/lmre plan \
  --family gemma-4-12b-qat \
  --recipe config/managed-runs/complete-native-quality-v1.json \
  --comparison-class gemma-native-baseline-v1 \
  --name gemma-declared-native-baseline
```

This command reads configuration and creates an immutable local evidence
bundle. It does not contact a runtime, provider, credential store, or model.

## Explicitly deferred

- arbitrary CLI-provided cells, paths, endpoints, servers, suites, or pairs;
- cross-family or cross-size mixes;
- automatic discovery-to-class promotion;
- extra-cell overhead route generation;
- parallel model residency;
- provider edits and Osaurus reconnection;
- richer comparison metrics, rankings, or run-orchestration UI.
