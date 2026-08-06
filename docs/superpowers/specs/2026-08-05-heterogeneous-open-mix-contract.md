# Heterogeneous Open-Mix Comparison Contract (2026-08-05)

**Status:** Implemented and verified for non-live inspection, planning, and
browser identity; not approved or implemented for live execution.
**Live authority:** None. A mix definition, inspection result, or immutable plan
must never be treated as authorization to contact a runtime, load a model, edit
a provider, or manage a process.

## Purpose

The North Star calls for comparisons such as Qwen-27B versus a 35B-A3B model
versus a Nemotron-class model. The current managed binding path cannot represent
that honestly: one `family_id` selects the campaign, cells, suites, overhead
pairs, plan identity, and browser comparison dimensions. Open mix therefore
needs an explicit heterogeneous comparison-set identity rather than a relaxed
same-family binding.

This contract is for capability and workload evidence across reviewed native
cells. It does not claim that raw latency, token rate, quantization, or routing
overhead are directly comparable across different model families or sizes.

## Proposed operator surface

The first implementation remains checked-in and review-first:

```bash
./bin/lmre open-mix inspect qwen-ornith-capability-v1

./bin/lmre plan \
  --open-mix qwen-ornith-capability-v1 \
  --recipe config/managed-runs/complete-native-quality-v1.json \
  --name qwen-ornith-capability-review
```

`--open-mix` is mutually exclusive with `--family`, `--comparison-class`, and
`--binding`. The CLI accepts a safe ID only, never a path, cell list, endpoint,
model ID, executable, artifact root, or shell command.

## Definition shape

Definitions live only beneath `config/open-mixes/<open-mix-id>.json` and use a
strict schema:

```json
{
  "schema_version": "1.0.0",
  "open_mix_id": "qwen-ornith-capability-v1",
  "revision": "1",
  "members": [
    {"family_id": "qwen36-35b-a3b", "cell_id": "qwen_mxfp4__osaurus"},
    {"family_id": "ornith-35b", "cell_id": "ornith_oq4__omlx"}
  ],
  "suite_contract_id": "shared-capability-v1",
  "estimated_minutes": 90,
  "notes": "Reviewed heterogeneous capability comparison"
}
```

Unknown and missing fields fail closed. A definition contains two to six
ordered, unique members. Every family and cell must be an exact checked-in
regular JSON file; symlinks and path-shaped IDs are rejected. Each cell must
belong to its declared family, use that quant's reviewed native server, and
resolve only through the fixed machine profile.

The initial contract does not accept local proposal/adoption records. A future
user-authored mix workflow may reuse the create-only review pattern after the
checked-in contract and evidence identity have been accepted.

## Suite and result semantics

1. `suite_contract_id` identifies a checked-in contract that fixes the exact
   preference prompts, RAG corpus/questions, generation settings, response
   contract, and scoring qualifications shared by every member.
2. A mix is rejected unless every member supports the complete suite contract.
   Silent per-family prompt substitution is forbidden.
3. Matrix observations remain per-member diagnostics. Latency, TTFT, and token
   rate are reported verbatim with model, family, quant, server, token-source,
   and response-contract qualifications; the harness derives no cross-family
   performance winner.
4. Preference collection may blind member labels and preserve pairwise human or
   reviewed-judge evidence, but the managed run derives no automatic overall
   winner or composite score.
5. RAG fact-hit and retrieval evidence remains question-level and member-level.
   Missing or incomparable token accounting stays explicit rather than being
   normalized into a fabricated score.
6. Overhead is evaluated only for a member with an existing reviewed
   direct-versus-Osaurus pair. Each pair is an independent routing result, not
   a cross-model ranking dimension. Unsupported members record `N/A`.

## Planning and immutable identity

Open-mix planning requires a new backward-compatible managed plan schema. The
plan records:

- `comparison_scope: "open_mix"`;
- open-mix ID, revision, repository-relative path, and canonical definition
  hash;
- the ordered `(family_id, cell_id)` member identities;
- every family, cell, suite-contract, suite, corpus, pair, recipe, and fixed
  machine-profile input hash;
- selected runtimes, approved loopback endpoints, request count, conservative
  duration, memory floor, and policy-relevant lifecycle bounds.

Existing plan schemas `1.0.0` through `1.2.0` remain readable and
hash-verifiable without rewriting. They retain `comparison_scope: "family"`
as an in-memory interpretation only; their serialized bytes and hashes do not
change.

The results browser groups open-mix runs only when the open-mix ID, revision,
definition hash, ordered members, suite contract, executable input hashes, and
human comparison ID all agree. A shared display name or overlapping member is
never enough. Only `SEALED_VERIFIED` evidence participates.

## Scheduling and lifecycle

- Execution remains sequential with `max_parallel_models = 1`.
- Planning binds the configured memory floor into policy evaluation without
  probing a live service. Live resource checks occur before and between every
  member lane using the existing conservative runtime boundary.
- Runtime contact remains limited to profile-approved loopback endpoints and
  fixed checked-in commands.
- Exact attach/reclaim identity, the 60-second notice, `Ctrl+C`, bounded
  `SIGINT` then `SIGTERM`, ownership-aware cleanup, and the ban on force kill
  remain unchanged.
- Osaurus provider creation and reconnection remain operator-owned UI actions.
- A routed-overhead lane may use the existing reviewed direct/routed pair, but
  no unrelated model lanes may be resident in parallel under harness control.

## Fail-closed outcomes

Planning fails before inference when a member, artifact, suite contract, input
hash, policy limit, endpoint, or runtime mapping is invalid. Execution and
resume preserve the current `PASS`, `FAIL`, `STOPPED`, `PARTIAL_BLOCKED`, `N/A`,
and sealed/unsealed distinctions. A missing member or incomplete shared suite
cannot seal as a successful open-mix comparison.

## Explicit exclusions

- arbitrary CLI-provided families, cells, paths, endpoints, commands, or model
  IDs;
- model discovery automatically promoting a mix;
- downloads, conversions, moves, or deletion of weights;
- provider edits or automatic Osaurus reconnection;
- parallel model residency;
- cross-family performance ranking, synthetic normalization, composite scores,
  or automatic winner selection;
- run-orchestration UI.

## Initial acceptance boundary

The first implementation slice is non-live: strict definition loading,
inspection, suite-contract validation, plan construction, backward-compatible
identity and browser behavior, and offline tests. A checked-in example must use
only repository fixtures or artifacts already proven available; otherwise the
example remains synthetic in tests. Live acceptance requires a separate
current-session authorization after this contract and its implementation are
reviewed.
