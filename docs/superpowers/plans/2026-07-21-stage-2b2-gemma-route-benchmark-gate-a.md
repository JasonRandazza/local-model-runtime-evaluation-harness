# Stage 2B-2 Gemma OptiQ Route Benchmark Gate A Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement Stage 2B-2 Gate A only: schema `3.4.0` / mode `operator_route_benchmark` / 72-POST Gemma OptiQ route benchmark on profile revision `2`, with tests and docs, without authorizing Gate B, a live manifest, usable run ID, or inference.

**Architecture:** Keep `StageTwoInferenceEngine` (`3.3.0` smoke) untouched as rollback. Add `StageTwoBenchmarkEngine` dispatched from `build_stage_two_engine` for `(3.4.0, operator_route_benchmark)`. Reuse `StageTwoInferenceTransport`, post-attempt journal, operator controller, resource gates, and lifecycle/artifact patterns. New suite module owns the immutable 72-request schedule; new measurement module owns medians and route-overhead summary.

**Tech Stack:** Python 3 stdlib, `unittest` via `PYTHONPATH=src /opt/homebrew/bin/python3 -m unittest …`, existing Stage 2 fakes, Swift plugin `0.3.0` unchanged.

## Global Constraints

- Spec: `docs/superpowers/specs/2026-07-21-stage-2b2-gemma-route-benchmark-design.md`
- Do **not** run Gate B, create a usable live run ID, install a Coordinator prompt into Osaurus, contact OptiQ/Osaurus/Keychain for live POSTs, load a model, or mutate providers.
- Do **not** rebuild/reinstall plugin `0.3.0`.
- Preserve Stage 0/1/2A and Stage 2B-1 (`3.3.0`) behavior and green suites.
- Template manifests only: placeholder approval fields are never live authority.
- Prefer `/opt/homebrew/bin/python3` for tests.
- No commits of `config/matrix/omlx-roots/**`.

## File map

| Area | Files |
|---|---|
| Suite + schedule | Create `src/local_model_runtime_evaluation/stage_two_benchmark_suite.py`; Create `suites/gemma-optiq-route-benchmark-v1.json`; Test `tests/test_stage_two_benchmark_suite.py` |
| Measurement / medians | Create `src/local_model_runtime_evaluation/stage_two_benchmark_measurement.py`; Test `tests/test_stage_two_benchmark_measurement.py` |
| Manifest / policy | Modify `src/local_model_runtime_evaluation/manifest.py`; Modify `src/local_model_runtime_evaluation/policy.py`; Create `manifests/stage-2-optiq-route-benchmark.json.template`; Tests `tests/test_manifest.py`, `tests/test_policy.py` |
| Engine | Create `src/local_model_runtime_evaluation/stage_two_benchmark.py`; Test `tests/test_stage_two_benchmark_engine.py` (fakes patterned on `tests/test_stage_two_inference_engine.py`) |
| Factory / runner | Modify `src/local_model_runtime_evaluation/stage_two_factory.py`; touch `runner.py` only if dispatch needs it |
| Docs / AGENTS | Create `docs/stage-2b2-gate-a.md`; Modify `AGENTS.md`, `docs/architecture.md`, `README.md` as needed; Create vault/repo operator-prep stub for 2B-2 (non-live) |
| Prompt | Create non-live Coordinator prompt draft under `docs/` (do not install) |

---

### Task 1: Immutable 72-request benchmark suite

**Files:**
- Create: `suites/gemma-optiq-route-benchmark-v1.json`
- Create: `src/local_model_runtime_evaluation/stage_two_benchmark_suite.py`
- Create: `tests/test_stage_two_benchmark_suite.py`

**Interfaces:**
- Produces: `StageTwoBenchmarkSuite.load(path) -> StageTwoBenchmarkSuite` with `.workloads`, `.schedule() -> tuple[BenchmarkRequest, ...]`, `.validate_response(contract, content) -> tuple[bool, str]`
- `BenchmarkRequest(workload_id: str, route: str, measured: bool, sequence: int, repetition: int)` frozen dataclass
- Schedule length exactly 72; sequences `1..72`; 12 warmups + 60 measured; per cell 3 warm + 15 measured for each of `{short-chat, structured-tool-json} × {direct, routed}`

- [ ] **Step 1: Write failing suite tests**

```python
# tests/test_stage_two_benchmark_suite.py
class StageTwoBenchmarkSuiteTest(unittest.TestCase):
    def test_schedule_has_seventy_two_counterbalanced_requests(self) -> None:
        suite = StageTwoBenchmarkSuite.load(REPO / "suites/gemma-optiq-route-benchmark-v1.json")
        schedule = suite.schedule()
        self.assertEqual(len(schedule), 72)
        self.assertEqual([r.sequence for r in schedule], list(range(1, 73)))
        self.assertEqual(sum(1 for r in schedule if not r.measured), 12)
        self.assertEqual(sum(1 for r in schedule if r.measured), 60)
        for workload in ("short-chat", "structured-tool-json"):
            for route in ("direct", "routed"):
                warm = [r for r in schedule if r.workload_id == workload and r.route == route and not r.measured]
                measured = [r for r in schedule if r.workload_id == workload and r.route == route and r.measured]
                self.assertEqual(len(warm), 3)
                self.assertEqual(len(measured), 15)

    def test_rejects_tampered_suite_file(self) -> None:
        # copy suite JSON, change a prompt, assert StageTwoBenchmarkSuite.load raises
        ...
```

- [ ] **Step 2: Run tests — expect FAIL (module missing)**

```bash
cd /Users/jrazz/Dev/active/local-model-runtime-evaluation-harness
PYTHONPATH=src /opt/homebrew/bin/python3 -m unittest tests.test_stage_two_benchmark_suite -v
```

- [ ] **Step 3: Implement suite JSON + loader**

Copy workload prompts/contracts from `suites/gemma-optiq-route-smoke-v1.json`. Build `_SCHEDULE` in code as an immutable tuple (like `stage_two_smoke_suite.py`), not generated at load time from loops that could drift — generate once in the module as a constant built from an explicit nested structure checked by tests.

Suggested construction (verify counts in tests):

```python
def _build_schedule() -> tuple[BenchmarkRequest, ...]:
    requests: list[BenchmarkRequest] = []
    sequence = 1
    for workload_id in ("short-chat", "structured-tool-json"):
        # warmups: alternate starting route by workload for counterbalance
        start_routed_first = workload_id == "structured-tool-json"
        for rep in range(3):
            routes = ("routed", "direct") if start_routed_first else ("direct", "routed")
            for route in routes:
                requests.append(BenchmarkRequest(workload_id, route, False, sequence, rep))
                sequence += 1
        for rep in range(15):
            routes = ("routed", "direct") if start_routed_first else ("direct", "routed")
            for route in routes:
                requests.append(BenchmarkRequest(workload_id, route, True, sequence, rep))
                sequence += 1
    assert len(requests) == 72 and sequence == 73
    return tuple(requests)
```

Reuse the same `validate_response` contract logic as smoke (import or duplicate the small helper — do not weaken smoke).

- [ ] **Step 4: Re-run tests — expect PASS**

- [ ] **Step 5: Commit**

```bash
git add suites/gemma-optiq-route-benchmark-v1.json \
  src/local_model_runtime_evaluation/stage_two_benchmark_suite.py \
  tests/test_stage_two_benchmark_suite.py
git commit -m "$(cat <<'EOF'
Add Stage 2B-2 immutable 72-request benchmark suite.

EOF
)"
```

---

### Task 2: Benchmark measurement medians and route-overhead summary

**Files:**
- Create: `src/local_model_runtime_evaluation/stage_two_benchmark_measurement.py`
- Create: `tests/test_stage_two_benchmark_measurement.py`

**Interfaces:**
- Consumes: observation objects compatible with smoke fields (`sequence`, `workload_id`, `route`, `measured`, `total_seconds`, `ttft_seconds`, `streaming_semantics`, `token_accounting_status`, `visible_output_tokens`, `content_span_seconds`, `response_contract_valid`, `finish_reason`, `output_sha256`)
- Produces: `summarize_benchmark(observations: tuple[...]) -> dict[str, object]` including:
  - `inference_path_acceptance` / `behavioral_contract_acceptance`
  - `excluded_warmups: 12`, `measured_requests: 60`
  - `route_overhead_summary`: per `(workload_id, route)` median `total_seconds` (and qualified TTFT/decode when all measured in that cell qualify)
  - `route_overhead_deltas`: per workload `routed_median_total - direct_median_total`
  - Reuse smoke qualification labels where applicable (`QUALIFIED_*` / `SUPPRESSED_*`)

- [ ] **Step 1: Write failing median / cohort validation tests**

```python
def test_summarize_benchmark_requires_sixty_measured_and_twelve_warmups(self) -> None:
    # build 71 fake observations -> evidence error
    ...

def test_route_overhead_medians_and_deltas(self) -> None:
    # 72 observations with known totals; assert median math and delta signs
    ...
```

Use a tiny local `_median(values: list[float]) -> float` (sort; average middle two if even — 15 measured per cell is odd so single middle element).

- [ ] **Step 2: Run — expect FAIL**

- [ ] **Step 3: Implement `summarize_benchmark`**

Prefer importing/adapting helpers from `stage_two_smoke_measurement.py` rather than rewriting qualification from scratch. Cohort validation must require exactly 72 observations with the cell counts from Task 1.

- [ ] **Step 4: Run — expect PASS**

- [ ] **Step 5: Commit**

```bash
git add src/local_model_runtime_evaluation/stage_two_benchmark_measurement.py \
  tests/test_stage_two_benchmark_measurement.py
git commit -m "$(cat <<'EOF'
Add Stage 2B-2 benchmark median and route-overhead summary.

EOF
)"
```

---

### Task 3: Manifest schema `3.4.0` and StageTwoPolicy

**Files:**
- Modify: `src/local_model_runtime_evaluation/manifest.py`
- Modify: `src/local_model_runtime_evaluation/policy.py`
- Create: `manifests/stage-2-optiq-route-benchmark.json.template`
- Modify: `tests/test_manifest.py`, `tests/test_policy.py` (and package/schema tests if they enumerate schemas)

**Interfaces:**
- Manifest accepts `schema_version == "3.4.0"`, `mode == "operator_route_benchmark"`, comparison `gemma-optiq-operator-route-benchmark`, profile `gemma-4-12b-optiq-4bit` / `2`, suite `gemma-optiq-route-benchmark-v1` / `1`, `repetitions == 1`, `route_order == counterbalanced`, routes loopback pair, limits exactly:

```python
{
    "request_timeout_seconds": 120,
    "memory_stop_level": "warning",
    "maximum_in_flight_requests": 1,
    "total_request_limit": 72,
}
```

- `StageTwoPolicy.active_contracts` adds `("3.4.0", "operator_route_benchmark", "gemma-optiq-operator-route-benchmark", "2")`
- Keep `3.3.0` smoke contract active

- [ ] **Step 1: Write failing manifest/policy tests for 3.4.0 accept + reject wrong limit 8 / wrong suite**

- [ ] **Step 2: Run — expect FAIL**

- [ ] **Step 3: Implement manifest branch + policy + template**

Template must use obvious placeholders for `run_id` / `approved_at` / `expires_at` (never a live ID). Mirror structure of `manifests/stage-2-optiq-inference-smoke.json.template` with 2B-2 fields.

- [ ] **Step 4: Run focused + `tests.test_package` if schema enums listed — expect PASS**

- [ ] **Step 5: Commit**

```bash
git add src/local_model_runtime_evaluation/manifest.py \
  src/local_model_runtime_evaluation/policy.py \
  manifests/stage-2-optiq-route-benchmark.json.template \
  tests/test_manifest.py tests/test_policy.py
git commit -m "$(cat <<'EOF'
Authorize Stage 2B-2 schema 3.4.0 manifest and policy contract.

EOF
)"
```

---

### Task 4: `StageTwoBenchmarkEngine` with fakes (no network)

**Files:**
- Create: `src/local_model_runtime_evaluation/stage_two_benchmark.py`
- Create: `tests/test_stage_two_benchmark_engine.py`

**Interfaces:**
- Constructor mirrors inference engine dependencies: `manifest`, `profile`, `suite`, `output_root`, `resources`, `host_validate`, `controller`, `transport`, `lock_owner`
- Methods: `preflight() -> dict`, `run(cancel: threading.Event) -> dict`, `cleanup() -> dict`
- Constants: `_STAGE_2B_2_LIMITS` with `total_request_limit: 72`, operations tuple same six ops as 2B-1
- Reuse `StageTwoInferenceTransport.chat` / health / list_models; post-attempt journal; operator shutdown checks from inference patterns
- `run` iterates `suite.schedule()`, gates before each POST, increments attempt counters, writes `raw-runs.jsonl`, stops on transport failure, summarizes via `summarize_benchmark`, transitions lifecycle to `awaiting_review`
- Hard-fail if `http_post_attempts` would exceed 72

- [ ] **Step 1: Write failing engine tests** (copy fake scaffolding from `tests/test_stage_two_inference_engine.py`)

Minimum cases:
1. Happy path: fake transport returns valid SSE-equivalent `TransportResult` for 72 calls → `inference_path_acceptance == PASS` when contracts pass
2. Stops before 73rd POST
3. First transport failure → `failed` lifecycle, journal `failed`, no further POSTs
4. Cleanup requires operator stopped (same as 2B-1)
5. Wrong schema/mode rejected at factory (covered more in Task 5)

Use a transport fake that counts `chat` calls.

- [ ] **Step 2: Run — expect FAIL**

- [ ] **Step 3: Implement engine**

Implementation strategy: start from `StageTwoInferenceEngine` structure in `stage_two_inference.py`, but:
- Do **not** modify the inference engine file except unavoidable shared helper extraction
- If a shared helper is extracted (e.g. journal wiring), keep 2B-1 tests green in the same commit
- Write artifacts named per spec: `benchmark-suite.json`, `benchmark-summary.json`, etc.

- [ ] **Step 4: Run engine + 2B-1 inference tests — expect PASS**

```bash
PYTHONPATH=src /opt/homebrew/bin/python3 -m unittest \
  tests.test_stage_two_benchmark_engine \
  tests.test_stage_two_inference_engine -q
```

- [ ] **Step 5: Commit**

```bash
git add src/local_model_runtime_evaluation/stage_two_benchmark.py \
  tests/test_stage_two_benchmark_engine.py
git commit -m "$(cat <<'EOF'
Add Stage 2B-2 benchmark engine with fake-only Gate A coverage.

EOF
)"
```

---

### Task 5: Factory dispatch for `(3.4.0, operator_route_benchmark)`

**Files:**
- Modify: `src/local_model_runtime_evaluation/stage_two_factory.py`
- Modify: `tests/test_stage_two_contract.py` and/or add factory assertions in `tests/test_stage_two_benchmark_engine.py`

**Interfaces:**
- `_validate_stage_two_benchmark_manifest(manifest)` exact contract check (suite id, limits 72, etc.)
- `build_stage_two_engine` returns `StageTwoBenchmarkEngine` for the 3.4.0 contract; still rejects unknown pairs

- [ ] **Step 1: Failing test — factory builds benchmark engine for valid 3.4.0 fixture; rejects 3.3.0 suite id on 3.4.0 mode**

- [ ] **Step 2: Run — expect FAIL**

- [ ] **Step 3: Wire factory** (load `suites/gemma-optiq-route-benchmark-v1.json`, same transport/controller/lock pattern as inference)

- [ ] **Step 4: Run factory + prior tests — expect PASS**

- [ ] **Step 5: Commit**

```bash
git add src/local_model_runtime_evaluation/stage_two_factory.py tests/
git commit -m "$(cat <<'EOF'
Dispatch Stage 2B-2 benchmark engine from schema 3.4.0 manifests.

EOF
)"
```

---

### Task 6: Docs, Gate A status, non-live prompt/prep

**Files:**
- Create: `docs/stage-2b2-gate-a.md` (decision `GATE_A_IN_PROGRESS` or `GATE_A_IMPLEMENTED_PENDING_REVIEW` — **not** live-ready)
- Create: `docs/stage-2b2-operator-prep.md` (checklist stub; state no active run ID)
- Create: Coordinator system prompt draft under `docs/` (explicitly non-installed)
- Modify: `AGENTS.md` Stage 2B-1 boundary → add Stage 2B-2 Gate A planning/impl note; keep live unauthorized
- Modify: `docs/architecture.md` / `README.md` brief pointers
- Optional vault mirror later; do not install Osaurus prompt

- [ ] **Step 1: Write docs stating Gate A is code/test only; Gate B/C/D blocked; plugin 0.3.0 unchanged; 005 remains PASS evidence**

- [ ] **Step 2: Static scan commands (document expected empty/PASS)**

```bash
rg -n 'stage2-2026' manifests/ | rg -v 'template|smoke|lifecycle|operator-route-00|optiq-inference-00' || true
rg -n 'operator_route_benchmark|3\.4\.0' src/local_model_runtime_evaluation --glob '*.py'
# Expect symbols present for Gate A; expect no live approved_at manifests for 2B-2
ls manifests/stage-2-optiq-route-benchmark*.json 2>/dev/null || echo 'no live 2B-2 manifest'
```

- [ ] **Step 3: Commit docs**

```bash
git add docs/stage-2b2-gate-a.md docs/stage-2b2-operator-prep.md docs/ AGENTS.md README.md
git commit -m "$(cat <<'EOF'
Document Stage 2B-2 Gate A status without live authorization.

EOF
)"
```

---

### Task 7: Full Gate A verification

**Files:** none new (verification only)

- [ ] **Step 1: Run Python suites**

```bash
cd /Users/jrazz/Dev/active/local-model-runtime-evaluation-harness
PYTHONPATH=src /opt/homebrew/bin/python3 -m unittest \
  tests.test_stage_two_benchmark_suite \
  tests.test_stage_two_benchmark_measurement \
  tests.test_stage_two_benchmark_engine \
  tests.test_manifest \
  tests.test_policy \
  tests.test_stage_two_inference_engine \
  tests.test_stage_two_gate_a_e2e \
  tests.test_transport \
  tests.test_package -q
```

Expected: OK

- [ ] **Step 2: Swift plugin contract (unchanged 0.3.0)**

```bash
cd plugins/osaurus-evaluation-harness && swift test
```

Expected: PASS; do not bump version

- [ ] **Step 3: Confirm no live 2B-2 manifest / usable ID committed**

- [ ] **Step 4: Final commit only if verification fixed anything; otherwise note green in handoff**

---

## Spec coverage check

| Spec requirement | Task |
|---|---|
| Schema `3.4.0` / mode / comparison / suite / limits 72 | 3, 5 |
| 72 schedule, 12 warm / 60 measured, counterbalance | 1 |
| Separate benchmark engine; 2B-1 untouched | 4, 5 |
| Medians + route deltas; dual acceptance axes | 2, 4 |
| Reuse transport/journal/operator lifecycle | 4, 5 |
| Plugin 0.3.0 unchanged | 6, 7 |
| Gate A only; no live ID/manifest | Global + 6 + 7 |
| Docs / prompt / prep non-live | 6 |

## Placeholder scan

No TBD/TODO steps. Engine Task 4 intentionally references inference-engine fake patterns by path rather than pasting the entire fake harness — implementers must open `tests/test_stage_two_inference_engine.py` and adapt.

---

## Execution handoff

Plan complete and saved to `docs/superpowers/plans/2026-07-21-stage-2b2-gemma-route-benchmark-gate-a.md`.

**Two execution options:**

1. **Subagent-Driven (recommended)** — fresh subagent per task, review between tasks  
2. **Inline Execution** — execute tasks in this session with checkpoints  

Which approach?
