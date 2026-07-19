# Stage 1 Developer Runbook

Stage 1 implements one governed route-overhead comparison for the approved `vibethinker-3b-mlx-oq4` profile. It compares direct oMLX requests with the same oMLX-owned model routed through Osaurus.

## Non-Live Verification

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
swift test --package-path plugins/osaurus-evaluation-harness
swift build -c release --package-path plugins/osaurus-evaluation-harness
```

The transport tests use only an ephemeral fake server on `127.0.0.1`. They do not contact ports `1337` or `8100`.

## Approved Runtime Boundary

- oMLX owns the only resident model.
- The direct route uses the dedicated harness Keychain credential.
- The Osaurus route never receives that direct oMLX credential; Osaurus uses its own provider credential.
- The runner probes Osaurus `/health` and rejects any loaded, current, or resident native model.
- Requests are serial and counterbalanced.
- One fixed background worker performs the long cohort; the six typed tools retain status and cancellation control.
- The worker may terminate only its own process. It never starts, stops, configures, loads, or unloads Osaurus or oMLX.

## Completed Gate

Run `stage1-20260714-001`, profile revision `3`, and suite revision `2` completed and reached `cleaned`. Its exact authorization is consumed and must not be reused. Plugin `0.2.0` remains unchanged.

## Token Accounting

- `completion_tokens` is retained as the API total.
- `completion_tokens_details.reasoning_tokens` is retained when present and valid.
- visible output tokens are derived only as total minus reasoning tokens when both values are present and internally consistent.
- missing details produce `INCOMPARABLE_TOKEN_ACCOUNTING`; they never fall back to total completion tokens for decode throughput.
- malformed, negative, or greater-than-total reasoning counts fail closed.
- decode throughput uses visible output tokens divided by the observed first-to-last visible-content span.

TTFT, decode throughput, and token accounting have separate status fields. `streaming_metric_status` remains as a compatibility alias for TTFT qualification.

## Paired Analysis

Each direct and routed request is paired by workload and repetition. Summaries include median, range, population deviation, percentage median, and direction counts for routed-minus-direct total time. Difference-of-medians remains available for continuity, but paired deltas are preferred when timing drifts across a cohort.

Do not create the real Keychain item, install the plugin, contact live endpoints, load a model, or run inference during non-live verification.
