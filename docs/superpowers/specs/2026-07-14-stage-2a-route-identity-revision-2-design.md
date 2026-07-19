# Stage 2A Route Identity Revision 2 Design

> Historical disposition: experimentally disproven by `stage2-20260715-001`. Preserve this design as the rationale for revision `2`, but do not use it to authorize another run. The live evidence showed that Osaurus did not reconnect the `Optiq` provider after the harness started the service and that connected remote-provider API IDs are provider-prefixed.

## Decision

Replace the failed `optiq/` routed-prefix hypothesis with one exact upstream model identity:

```text
mlx-community/VibeThinker-3B-OptiQ-4bit
```

Osaurus's separate local model ID, `vibethinker-3b-optiq-4bit`, must never satisfy routed-provider proof.

## Evidence Basis

Run `stage2-20260714-001` proved the owned OptiQ service lifecycle but stopped because runtime profile revision `1` required a routed ID beginning with `optiq/`. Current Osaurus custom-provider behavior presents remote models under their provider in the UI while preserving the upstream model name at the API boundary. The OptiQ provider UI displays the full upstream repository ID when its service is connected.

The failed run safely stopped its owned service, released port `8080`, and made zero model-load, inference, or POST requests. Its partial evidence did not persist endpoint inventory because identity validation occurred before the inventory artifact was written.

## Scope

Revision 2 changes only Stage 2A route discovery and its evidence ordering.

In scope:

- runtime profile revision `2`
- exact routed upstream model ID
- sanitized model descriptors for endpoint inventory
- inventory persistence before route acceptance
- explicit rejection of the local lowercase model as provider proof
- failed-run and consumed-run readiness protections
- tests and operator documentation

Out of scope:

- inference, warm-up, benchmarking, or Stage 2B
- provider-file mutation by the harness
- unsupported manual aliases
- model loading
- changing the six native tool schemas
- plugin version changes

## Route Identity Contract

Direct discovery must contain at least one already-approved identity for the pinned artifact:

- `mlx-community/VibeThinker-3B-OptiQ-4bit`
- the canonical immutable snapshot path

Routed discovery must contain exactly one descriptor whose `id` equals:

```text
mlx-community/VibeThinker-3B-OptiQ-4bit
```

The following ID is inventory only and cannot prove the provider route:

```text
vibethinker-3b-optiq-4bit
```

No case-folded, suffix-only, prefix-only, fuzzy, or substring match is accepted. Exact case-sensitive equality prevents a local Osaurus model from satisfying the route contract.

## Catalog Descriptor

The read-only transport will return a bounded descriptor for each `/v1/models` item:

- `id`: required non-empty string
- `owned_by`: optional string
- `root`: optional string

Unknown fields are discarded. Raw endpoint payloads are not persisted.

`owned_by` and `root` are diagnostic evidence in revision 2. They are not acceptance gates because their remote-provider values have not yet been observed and are not documented as stable routing contracts. Manager review may promote them into a later profile only after measured evidence.

## Evidence Ordering

After both GET requests return valid descriptors, the worker writes `endpoint-inventory.json` before evaluating route identity. The artifact contains:

- sanitized direct descriptors
- sanitized routed descriptors
- expected routed ID
- explicitly rejected local ID
- route decision initially marked `PENDING`

After validation, the worker updates the decision to `PASS` and records the discovered routed ID. If validation fails, the already-written inventory remains available in the partial bundle and cleanup preserves it.

No endpoint inventory is written when either response is malformed or a GET fails before a valid descriptor set exists.

## Lifecycle And Safety

All existing Stage 2A safeguards remain unchanged:

- exact pinned `mlx-optiq 0.3.3` environment and artifact hashes
- OptiQ Lab closed and port `8080` initially free
- one harness-owned process group
- GET-only health and model inventory
- zero model-load attempts
- zero inference requests
- zero HTTP POST requests
- exact idle Gemma Coordinator as the only permitted resident native model
- verified owned shutdown and port release
- cooperative cancellation

The harness does not alter the Osaurus provider or select a model in the UI.

## Consumed Run Protection

The non-live Gate B checker must reject a run ID when its canonical output directory already exists. A cleaned, failed, cancelled, or completed run is consumed even if its manifest has not expired.

Run `stage2-20260714-001` remains preserved and cannot be reused.

## Configuration Changes

Runtime profile revision `2` will replace `routed_prefix_hypothesis` with:

- `routed_model_id`: `mlx-community/VibeThinker-3B-OptiQ-4bit`
- `rejected_local_model_ids`: [`vibethinker-3b-optiq-4bit`]

The profile parser and schema will reject unknown fields, revision drift, alternate IDs, and mutable aliases.

No active revision-2 manifest is created during implementation. A new run ID requires separate current-session authorization after Gate B validation.

## Test Design

Unit tests will prove:

- the exact full upstream ID passes
- the local lowercase ID alone fails
- suffix, prefix, case-folded, and duplicate matches fail
- optional `owned_by` and `root` are sanitized and retained
- malformed descriptors fail closed
- endpoint inventory is written before identity validation
- failed identity discovery preserves sanitized inventory
- no inference, POST, or model-load path is introduced
- consumed output directories stop non-live readiness
- runtime profile revision `1` cannot satisfy revision `2`

Regression verification includes the complete Python suite, native plugin tests when plugin source is unchanged only as a contract confirmation, JSON parsing, source scans, and the non-live exact-host checker.

## Operator Flow

1. Implement and review revision `2` without starting OptiQ.
2. Run full deterministic and non-live checks.
3. Confirm the existing `Optiq` provider remains enabled, header-free, and unmodified.
4. Authorize one new Stage 2 run ID.
5. Create one short-lived revision-2 manifest.
6. Run Stage 2A with OptiQ Lab closed.
7. Review endpoint inventory, route identity, lifecycle ownership, zero-activity counters, and checksums before any Stage 2B proposal.

## Rollback

Revision `1` code and the failed run artifacts remain historical evidence but are not eligible for another live run. Source rollback removes only the revision-2 profile, descriptor transport, inventory-ordering, consumed-run guard, tests, and associated documentation. Plugin `0.3.0` remains installed because its native tool contract is unchanged.
