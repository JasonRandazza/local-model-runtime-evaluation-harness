# Local Model Runtime Evaluation Harness

This repository contains the executable source of truth for controlled local-model runtime evaluation across Osaurus, oMLX, and mlx-optiq.

Stage 0 is deliberately non-inference. It validates manifests, typed operations, lifecycle cancellation, cleanup, and artifact integrity without loading a model, contacting an endpoint, or changing an Osaurus provider.

Stage 1 completed two separately gated route-overhead runs for one approved VibeThinker oMLX profile. Their live authority is consumed. Post-Gate C hardening now separates total completion tokens, hidden reasoning tokens, and visible output tokens; independently qualifies TTFT, decode throughput, and token accounting; and reports paired direct-versus-routed deltas. Decode throughput remains null unless exact visible-token evidence and incremental content delivery are both present.

Stage 2A revision `3` is a separately bounded, zero-generation OptiQ route-observation lane. It pins `mlx-optiq 0.3.3`, one VibeThinker OptiQ snapshot, its artifact hashes, and one API-only foreground launcher at `bin/lmre-stage2-operator-serve`. The operator starts that service, explicitly retries or reconnects the existing Osaurus `Optiq` provider, and later stops the foreground launcher with `Ctrl+C`. The harness observes the service and route only: it never starts, stops, signals, restarts, or configures OptiQ or Osaurus.

The installed MLX-LM server returns only `status: ok` from `/health`; that response does not prove model residency. Its generation worker calls `load_default()` during startup even though OptiQ's banner describes a first-request load. The harness therefore binds the pinned model through the exact process command, immutable snapshot, and artifact hashes. Health must be available, optional model diagnostics may not conflict with that pinned identity, and optional activity counters must remain zero. Route discovery uses only `GET /health` and `GET /v1/models` and accepts the exact routed ID `optiq/mlx-community/VibeThinker-3B-OptiQ-4bit`. The worker reaches `awaiting_review` while the operator service remains running. Cleanup requires manual shutdown, verifies the recorded process is absent, observes port `8080` free twice, and reports `service_lifecycle_actions: 0`, including failed and cancelled cleanup paths.

Run `stage2-20260715-002` exercised revision `3` and stopped safely because the worker accepted `status: ok` while Osaurus reports `status: healthy`. Gate B had not applied that same predicate. The worker now accepts both supported healthy forms, and Gate B uses the shared predicate so it cannot authorize a response the worker would reject. The run is cleaned and permanently consumed. A new Gate B pass and explicit authorization of a new unused run ID remain required. Plugin `0.3.0` is unchanged, and Stage 2B inference, POST, and benchmark authority does not exist.

Run `stage2-20260715-003` is the accepted Stage 2A revision-3 baseline. It proved the exact operator-owned OptiQ service, provider-prefixed Osaurus route, GET-only observation sequence, manual shutdown gate, final checksum seal, and zero harness model-load, inference, POST, or lifecycle actions. The run is cleaned, independently bundle-validated, and permanently consumed. Stage 2A is complete; Stage 2B remains a separate unauthorized phase.

Stage 2B-1 Gemma OptiQ inference-path acceptance is evidenced by cohort `stage2-20260721-005` (schema `3.3.0`, eight POSTs, sealed **PASS**). It is path smoke only and cannot establish stable medians or route-performance conclusions. Stage 2B-2 Gate A is `GATE_A_PASSED` (schema `3.4.0`, seventy-two POSTs, suite `gemma-optiq-route-benchmark-v1` revision `1`). Gates B–D, live manifest authorization, Coordinator prompt installation, and inference remain separately gated. Plugin `0.3.0` is unchanged. See `docs/stage-2b1-gate-a.md` and `docs/stage-2b2-gate-a.md`.

Gate B repeats direct safe-health validation after inventory. Preflight failures preserve bounded partial evidence for manager cleanup without touching operator OptiQ. Cleanup revalidates the exact routed ID, uses atomic checksum replacement, and retains the run lock until a cleaned bundle has been successfully resealed and validated; a post-transition sealing failure is retryable.

The native `cleanup` operation validates the host-owned artifact bundle and returns a bounded evidence summary. Sandbox filesystem access is not part of the Stage 0 acceptance contract.

Historical checksummed bundles are immutable. New aggregation behavior may be applied read-only for supplemental analysis, but it does not rewrite accepted artifacts.

## Gemma 4 12B QAT 3×3 matrix

Nine-cell direct screen (then finalist) across JANG_4M, oQ4-fp16, and OptiQ-4bit on Osaurus, oMLX, and OptiQ. Separate from Stage 2B; no Gate B or plugin involvement.

```bash
./bin/lmre-matrix --dry-config \
  --campaign config/matrix/gemma-4-12b-qat-campaign.json

./bin/lmre-matrix --mode screen \
  --campaign config/matrix/gemma-4-12b-qat-campaign.json
```

See `docs/matrix.md` for artifact paths, finalist flow, and safety rules.

## Personal Model Selection (Phase A) — paused 2026-07-16

A lean Osaurus-front-door screen compared Gemma 4 12B native JANG versus OptiQ-behind-Osaurus. Active work is paused; see `docs/personal-selection-temporary-closeout-2026-07-16.md` and the Deep Wiki temporary closeout record.

```bash
./bin/lmre-personal-select --mode screen \
  --lane config/personal-selection/lanes/gemma-4-12b-native-osaurus.json
```

## Verification

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

The native Osaurus plugin is built separately and is not installed by repository tests.

See `docs/stage-1.md`, `docs/stage-2-gate-a.md`, `docs/stage-2b1-gate-a.md`, and `docs/stage-2b2-gate-a.md` for the separate approval boundaries.
