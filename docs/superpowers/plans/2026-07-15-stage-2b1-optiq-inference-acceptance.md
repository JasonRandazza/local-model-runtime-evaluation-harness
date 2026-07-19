# Stage 2B-1 OptiQ Inference Acceptance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Use superpowers:subagent-driven-development only when Jason explicitly authorizes Codex subagents for the implementation session. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a fail-closed eight-request OptiQ direct-versus-Osaurus inference acceptance path without changing the accepted Stage 2A observation path.

**Architecture:** Schema `3.2.0` routes only `operator_inference_probe` manifests to a new `StageTwoInferenceEngine`, dedicated fixed smoke-suite loader, and credential-free inference transport. The engine re-proves process, route, resource, memory, and active-lock identity before every POST, persists sanitized observations only, requires operator shutdown before cleanup, and reports infrastructure acceptance separately from response-contract acceptance.

**Tech Stack:** Python 3.11 standard library, `unittest`, JSON schemas and fixtures, existing OptiQ runtime profile revision `3`, existing Swift Osaurus plugin `0.3.0` unchanged, Markdown Deep Wiki documentation.

## Global Constraints

- Stage 2A run `stage2-20260715-003` is the immutable accepted baseline.
- Do not change `StageTwoEngine`, `StageTwoReadOnlyTransport`, runtime profile revision `3`, the foreground launcher, or plugin `0.3.0` behavior.
- Stage 2B-1 uses schema `3.2.0`, mode `operator_inference_probe`, and comparison class `optiq-operator-route-smoke` only.
- The fixed suite is `optiq-route-smoke-v1` revision `1`: two workloads, four excluded warm-ups, four measured requests, eight serial POST requests total.
- Direct model ID is `mlx-community/VibeThinker-3B-OptiQ-4bit`; routed model ID is `optiq/mlx-community/VibeThinker-3B-OptiQ-4bit`.
- Allowed network activity is loopback-only `GET /health`, `GET /v1/models`, and `POST /v1/chat/completions` on ports `8080` and `1337`.
- Stage 2B-1 sends no credential or authorization header on either route.
- Request timeout is exactly `120` seconds; maximum in-flight requests is `1`; memory must remain `normal` with at least 20 percent free.
- Raw prompt text and generated content must not enter run artifacts, logs, summaries, exceptions, or Coordinator reports.
- Behavioral contract failures finish the remaining safe cohort; transport, identity, memory, lock, lifecycle, or evidence failures stop before the next POST.
- The harness never starts, stops, signals, restarts, configures, loads, or unloads OptiQ or Osaurus.
- No live manifest, usable run ID, endpoint request, model load, provider mutation, plugin installation, or live Gate B action is permitted during Gate A implementation.
- Do not stage or commit repository changes unless Jason gives explicit current-session Git approval. The repository currently has no tracked baseline, so execution must not create an accidental spec-only initial commit.

---

### Task 1: Schema 3.2 Manifest and Fixed Smoke Suite

**Files:**
- Create: `tests/fixtures/valid-stage-2-inference.json`
- Create: `suites/optiq-route-smoke-v1.json`
- Create: `src/local_model_runtime_evaluation/stage_two_smoke_suite.py`
- Create: `tests/test_stage_two_smoke_suite.py`
- Modify: `src/local_model_runtime_evaluation/manifest.py`
- Modify: `src/local_model_runtime_evaluation/policy.py`
- Modify: `schemas/benchmark-manifest.schema.json`
- Modify: `schemas/benchmark-suite.schema.json`
- Modify: `tests/test_stage_two_manifest.py`
- Modify: `tests/test_policy.py`

**Interfaces:**
- Produces: `StageTwoSmokeSuite.load(path: Path) -> StageTwoSmokeSuite`.
- Produces: `StageTwoSmokeSuite.schedule() -> tuple[SmokeRequest, ...]`.
- Produces: `StageTwoSmokeSuite.validate_response(contract: str, content: str) -> tuple[bool, str]`.
- Produces: an active `BenchmarkManifest` carrying `suite_id`, `suite_revision`, `repetitions`, and `route_order` for schema `3.2.0`.

- [ ] **Step 1: Add the failing manifest tests**

Add tests that load `valid-stage-2-inference.json` and assert the exact active contract:

```python
def test_valid_stage_two_inference_manifest_loads(self) -> None:
    data = json.loads(
        (Path(__file__).parent / "fixtures" / "valid-stage-2-inference.json").read_text()
    )
    manifest = validate_manifest(data, now=self.now)
    self.assertEqual(manifest.schema_version, "3.2.0")
    self.assertEqual(manifest.mode, "operator_inference_probe")
    self.assertEqual(manifest.comparison_class, "optiq-operator-route-smoke")
    self.assertEqual(manifest.runtime_profile_revision, "3")
    self.assertEqual(manifest.suite_id, "optiq-route-smoke-v1")
    self.assertEqual(manifest.suite_revision, "1")
    self.assertEqual(manifest.repetitions, 1)
    self.assertEqual(manifest.route_order, "counterbalanced")
    self.assertEqual(manifest.limits, {
        "request_timeout_seconds": 120,
        "memory_stop_level": "warning",
        "maximum_in_flight_requests": 1,
        "total_request_limit": 8,
    })
```

Add table-driven rejections for schema, mode, comparison class, profile revision, suite ID, suite revision, repetitions, route order, route URL, timeout, memory stop level, in-flight count, request limit, unknown properties, and missing properties. Keep the existing schema `3.0.0` and `3.1.0` tests unchanged and passing.

- [ ] **Step 2: Run the manifest and policy tests and confirm red**

Run:

```zsh
python3 -m unittest tests.test_stage_two_manifest tests.test_policy -v
```

Expected: the new schema `3.2.0` case fails with `unsupported_schema`; existing Stage 0, Stage 1, and Stage 2A cases remain green.

- [ ] **Step 3: Add the exact Stage 2B-1 fixture and JSON-schema branch**

Create `tests/fixtures/valid-stage-2-inference.json` with this non-live test identity:

```json
{
  "schema_version": "3.2.0",
  "run_id": "stage2-20260715-901",
  "stage": 2,
  "mode": "operator_inference_probe",
  "operations": ["inventory", "preflight", "run-scenario", "status", "cancel", "cleanup"],
  "output_root": "/Users/jrazz/.osaurus/container/output/benchmark-runs",
  "approved_by": "unit-test",
  "approved_at": "2026-07-15T00:00:00Z",
  "expires_at": "2026-07-16T00:00:00Z",
  "comparison_class": "optiq-operator-route-smoke",
  "runtime_profile_id": "vibethinker-3b-optiq-4bit",
  "runtime_profile_revision": "3",
  "suite_id": "optiq-route-smoke-v1",
  "suite_revision": "1",
  "repetitions": 1,
  "route_order": "counterbalanced",
  "routes": {
    "direct": "http://127.0.0.1:8080/v1",
    "routed": "http://127.0.0.1:1337/v1"
  },
  "limits": {
    "request_timeout_seconds": 120,
    "memory_stop_level": "warning",
    "maximum_in_flight_requests": 1,
    "total_request_limit": 8
  }
}
```

Add a fifth `oneOf` branch to `schemas/benchmark-manifest.schema.json` with those exact constants. Do not relax any prior branch.

- [ ] **Step 4: Implement exact manifest parsing and policy authorization**

In `manifest.py`, add `STAGE_TWO_INFERENCE_KEYS` and select it only when `stage == 2` and `schema_version == "3.2.0"`:

```python
STAGE_TWO_INFERENCE_KEYS = STAGE_TWO_KEYS | {
    "suite_id", "suite_revision", "repetitions", "route_order",
}

schema_version = data.get("schema_version")
if stage == 2 and schema_version == "3.2.0":
    required_keys = STAGE_TWO_INFERENCE_KEYS
else:
    required_keys = (
        STAGE_ZERO_KEYS if stage == 0
        else STAGE_ONE_KEYS if stage == 1
        else STAGE_TWO_KEYS
    )
```

Add `3.2.0` to Stage 2 allowed schemas and map it only to `operator_inference_probe`. In the Stage 2 branch, validate the exact comparison, profile, suite, cohort, routes, and limits above, then populate the existing `BenchmarkManifest` fields.

In `policy.py`, authorize exactly two active Stage 2 tuples while leaving schema `3.0.0` historical-only:

```python
active_contracts = {
    (
        "3.1.0", "operator_route_probe",
        "optiq-operator-route-discovery", "3",
    ),
    (
        "3.2.0", "operator_inference_probe",
        "optiq-operator-route-smoke", "3",
    ),
}
contract = (
    manifest.schema_version, manifest.mode,
    manifest.comparison_class, manifest.runtime_profile_revision,
)
if contract not in active_contracts:
    raise PolicyError("stage_forbidden", "Stage 2 contract is not active")
```

- [ ] **Step 5: Add the dedicated smoke-suite tests**

Test the exact schedule and fixed content:

```python
def test_fixed_schedule_is_eight_serial_counterbalanced_requests(self) -> None:
    suite = StageTwoSmokeSuite.load(self.path)
    self.assertEqual(
        [(item.workload_id, item.route, item.measured) for item in suite.schedule()],
        [
            ("short-chat", "direct", False),
            ("short-chat", "routed", False),
            ("short-chat", "direct", True),
            ("short-chat", "routed", True),
            ("structured-tool-json", "routed", False),
            ("structured-tool-json", "direct", False),
            ("structured-tool-json", "routed", True),
            ("structured-tool-json", "direct", True),
        ],
    )
    self.assertEqual(sum(item.measured for item in suite.schedule()), 4)
```

Add rejection tests for a third workload, changed prompt, changed token limit, duplicate workload ID, nonzero temperature, non-streaming mode, changed response contract, and any schedule other than the fixed eight entries.

- [ ] **Step 6: Implement the fixed suite and response validator**

Create `suites/optiq-route-smoke-v1.json` with the two approved workload objects from the design. In `stage_two_smoke_suite.py`, define immutable `SmokeWorkload`, `SmokeRequest`, and `StageTwoSmokeSuite` types. Compare loaded JSON against exact constants rather than accepting user-selected fields.

The validator must implement only these contracts:

```python
@staticmethod
def validate_response(contract: str, content: str) -> tuple[bool, str]:
    if contract == "text":
        return (True, "PASS") if content.strip() else (False, "EMPTY_TEXT")
    if contract != "stage2b-status-tool-json":
        return False, "UNSUPPORTED_CONTRACT"
    try:
        payload = json.loads(content)
    except (json.JSONDecodeError, TypeError):
        return False, "INVALID_JSON"
    expected = {
        "name": "status",
        "arguments": {"run_id": "stage2b-test", "include_details": False},
    }
    return (
        (True, "PASS")
        if payload == expected
        else (False, "JSON_CONTRACT_MISMATCH")
    )
```

- [ ] **Step 7: Verify Task 1**

Run:

```zsh
python3 -m unittest tests.test_stage_two_manifest tests.test_stage_two_smoke_suite tests.test_policy -v
```

Expected: all focused tests pass; no live manifest exists under `manifests/`.

---

### Task 2: Credential-Free Stage 2B Inference Transport

**Files:**
- Create: `src/local_model_runtime_evaluation/stage_two_inference_transport.py`
- Create: `tests/test_stage_two_inference_transport.py`
- Do not modify: `src/local_model_runtime_evaluation/stage_two_host.py`
- Do not modify: `src/local_model_runtime_evaluation/transport.py`

**Interfaces:**
- Produces: `StageTwoInferenceTransport.health(base_url: str) -> dict[str, object]`.
- Produces: `StageTwoInferenceTransport.list_models(base_url: str) -> tuple[ModelDescriptor, ...]`.
- Produces: `StageTwoInferenceTransport.chat(base_url: str, model_id: str, prompt: str, max_tokens: int, cancel: threading.Event) -> TransportResult`.
- Guarantees: no public credential argument and no `Authorization` header construction.

- [ ] **Step 1: Write transport allowlist and no-credential tests**

Use a local `ThreadingHTTPServer` fixture and capture method, path, request JSON, and headers. Assert:

```python
self.assertEqual(request["path"], "/v1/chat/completions")
self.assertEqual(request["body"], {
    "model": "mlx-community/VibeThinker-3B-OptiQ-4bit",
    "messages": [{"role": "user", "content": "fixed prompt"}],
    "temperature": 0,
    "max_tokens": 128,
    "stream": True,
    "stream_options": {"include_usage": True},
})
self.assertNotIn("Authorization", request["headers"])
```

Add failures for remote host, hostname `localhost`, HTTPS, wrong base path, wrong GET path, non-SSE POST response, HTTP error, empty stream, malformed SSE, cancellation, and a response exceeding the 120-second transport timeout through a fake connection.

- [ ] **Step 2: Run the focused transport tests and confirm red**

Run:

```zsh
python3 -m unittest tests.test_stage_two_inference_transport -v
```

Expected: import failure for `stage_two_inference_transport`.

- [ ] **Step 3: Implement composition without widening either accepted transport**

Create a class that composes the existing GET-only Stage 2A transport and existing loopback SSE parser, while exposing no credential parameter:

```python
class StageTwoInferenceTransport:
    def __init__(self, allowed_base_urls: set[str], timeout_seconds: int) -> None:
        if timeout_seconds != 120:
            raise StageTwoError("transport_policy_failed", "Stage 2B timeout must be 120 seconds")
        self._read = StageTwoReadOnlyTransport(allowed_base_urls, timeout_seconds)
        self._chat = LoopbackTransport(allowed_base_urls, timeout_seconds)

    def health(self, base_url: str) -> dict[str, object]:
        return self._read.health(base_url)

    def list_models(self, base_url: str) -> tuple[ModelDescriptor, ...]:
        return self._read.list_models(base_url)

    def chat(
        self, base_url: str, model_id: str, prompt: str, max_tokens: int,
        cancel: threading.Event,
    ) -> TransportResult:
        return self._chat.chat(
            base_url, model_id, prompt, max_tokens, None, cancel,
        )
```

Translate `TransportError` into `StageTwoError("transport_failed", ...)` without embedding response bodies, prompt text, generated content, headers, or model output in the exception message.

- [ ] **Step 4: Verify Task 2 and the unchanged transports**

Run:

```zsh
python3 -m unittest tests.test_stage_two_inference_transport tests.test_transport tests.test_stage_two_host -v
```

Expected: all tests pass and Stage 2A remains GET-only.

---

### Task 3: Sanitized Smoke Observations and Acceptance Summary

**Files:**
- Create: `src/local_model_runtime_evaluation/stage_two_smoke_measurement.py`
- Create: `tests/test_stage_two_smoke_measurement.py`

**Interfaces:**
- Produces: `SmokeObservation.from_result(request, workload, result, contract_result) -> SmokeObservation`.
- Produces: `SmokeObservation.as_json() -> dict[str, object]` with no content or prompt fields.
- Produces: `summarize_smoke(observations: tuple[SmokeObservation, ...]) -> dict[str, object]`.

- [ ] **Step 1: Write observation-redaction and acceptance tests**

Build one complete eight-observation cohort and assert:

```python
serialized = observation.as_json()
self.assertNotIn("content", serialized)
self.assertNotIn("prompt", serialized)
self.assertEqual(serialized["output_sha256"], "a" * 64)

summary = summarize_smoke(observations)
self.assertEqual(summary["total_requests"], 8)
self.assertEqual(summary["excluded_warmups"], 4)
self.assertEqual(summary["measured_requests"], 4)
self.assertEqual(summary["inference_path_acceptance"], "PASS")
self.assertEqual(summary["behavioral_contract_acceptance"], "PASS")
self.assertNotIn("median", json.dumps(summary).lower())
self.assertNotIn("p95", json.dumps(summary).lower())
```

Add cases proving:
- invalid measured response contract yields behavioral `FAIL` but keeps infrastructure `PASS`
- direct/routed output hash mismatch is recorded in `behavioral_findings`
- `length`, buffered delivery, and ambiguous token accounting are recorded without fabricated TTFT or decode claims
- an incomplete or duplicate cohort raises `StageTwoError("evidence_incomplete", ...)`
- route pair deltas contain one direct and one routed measured observation only

- [ ] **Step 2: Run focused tests and confirm red**

Run:

```zsh
python3 -m unittest tests.test_stage_two_smoke_measurement -v
```

Expected: import failure for `stage_two_smoke_measurement`.

- [ ] **Step 3: Implement the immutable sanitized observation**

The dataclass contains only:

```python
@dataclass(frozen=True)
class SmokeObservation:
    sequence: int
    workload_id: str
    route: str
    measured: bool
    repetition: int
    http_status: int
    stream_valid: bool
    total_seconds: float
    ttft_seconds: float | None
    completion_tokens: int | None
    reasoning_tokens: int | None
    visible_output_tokens: int | None
    token_accounting_status: str
    content_event_count: int
    content_span_seconds: float
    streaming_semantics: str
    finish_reason: str | None
    response_contract_valid: bool
    response_contract_status: str
    output_sha256: str
```

Set `ttft_seconds` to `None` unless delivery is incremental. Do not calculate decode rate unless delivery is incremental, token accounting is `EXACT_VISIBLE`, visible tokens are positive, and content span is positive.

Construct the observation from the in-memory transport result without retaining content:

```python
@classmethod
def from_result(
    cls, request: SmokeRequest, workload: SmokeWorkload,
    result: TransportResult, contract_result: tuple[bool, str],
) -> "SmokeObservation":
    content_span = max(0.0, result.last_content_seconds - result.ttft_seconds)
    incremental = result.content_event_count >= 2 and content_span >= 0.01
    contract_valid, contract_status = contract_result
    return cls(
        sequence=request.sequence,
        workload_id=workload.workload_id,
        route=request.route,
        measured=request.measured,
        repetition=request.repetition,
        http_status=result.http_status,
        stream_valid=result.stream_valid,
        total_seconds=result.total_seconds,
        ttft_seconds=result.ttft_seconds if incremental else None,
        completion_tokens=result.completion_tokens,
        reasoning_tokens=result.reasoning_tokens,
        visible_output_tokens=result.visible_output_tokens,
        token_accounting_status=result.token_accounting_status,
        content_event_count=result.content_event_count,
        content_span_seconds=content_span,
        streaming_semantics="incremental" if incremental else "buffered",
        finish_reason=result.finish_reason,
        response_contract_valid=contract_valid,
        response_contract_status=contract_status,
        output_sha256=result.content_sha256,
    )
```

- [ ] **Step 4: Implement the non-benchmark summary**

Return direct and routed observations, two measured pair deltas, metric qualification labels, response-contract counts, finish-reason counts, output-hash pair status, and behavioral findings. Never call `statistics.median`, never emit p95, and never call Stage 1 `aggregate()`.

`behavioral_contract_acceptance` depends only on all four measured response contracts. Hash mismatch, token capping, buffered delivery, and ambiguous accounting remain explicit findings and metric suppressors rather than infrastructure failures.

- [ ] **Step 5: Verify Task 3**

Run:

```zsh
python3 -m unittest tests.test_stage_two_smoke_measurement tests.test_measurement -v
```

Expected: focused tests pass and the Stage 1 stable-median implementation remains unchanged.

---

### Task 4: Dedicated StageTwoInferenceEngine and Per-Request Safety Gates

**Files:**
- Create: `src/local_model_runtime_evaluation/stage_two_inference.py`
- Create: `tests/test_stage_two_inference_engine.py`
- Modify: `src/local_model_runtime_evaluation/locking.py`
- Modify: `tests/test_locking.py`
- Do not modify: `src/local_model_runtime_evaluation/stage_two.py`

**Interfaces:**
- Produces: `RunLock.owner() -> str | None`.
- Produces: `StageTwoInferenceEngine.preflight() -> dict[str, object]`.
- Produces: `StageTwoInferenceEngine.run(cancel: threading.Event) -> dict[str, object]`.
- Consumes: `resource_probe(routed_health: Mapping[str, object]) -> ResourceSnapshot` and `lock_owner() -> str | None`.

- [ ] **Step 1: Add lock ownership tests**

Assert `owner()` returns `None` without a lock, the exact run ID after acquire, and a different run ID when a competing lock fixture is present. `owner()` must never create, modify, or release a lock.

- [ ] **Step 2: Write engine preflight tests**

Use fakes for controller, host validation, transport, resource probe, and lock owner. Prove preflight:
- accepts only schema `3.2.0` and mode `operator_inference_probe`
- validates runtime profile and smoke-suite references
- validates exact operator process and immutable host identity
- requires lock owner equal to the current run ID
- rejects warning and critical memory
- rejects any native residency other than no model or exact Gemma Coordinator
- proves direct and routed inventories before POST authority
- writes runtime, artifact, operator, endpoint, suite, preflight, memory, request, service, and lifecycle evidence
- attempts zero inference and zero POST requests

- [ ] **Step 3: Write the exact eight-request schedule test**

The fake transport records every method and request. Assert:

```python
self.assertEqual(len(transport.chat_calls), 8)
self.assertEqual([call.route for call in transport.chat_calls], [
    "direct", "routed", "direct", "routed",
    "routed", "direct", "routed", "direct",
])
self.assertEqual(max(transport.in_flight), 1)
self.assertEqual(result["inference_request_attempts"], 8)
self.assertEqual(result["http_post_attempts"], 8)
self.assertEqual(result["state"], "awaiting_review")
```

Assert every POST is preceded by cancellation, lock, controller, direct health, routed health, direct inventory, routed inventory, residency, and memory checks; every POST is followed by process and memory checks.

- [ ] **Step 4: Write fail-closed and behavioral-continuation tests**

Create one test for each failure boundary:
- cancellation before request 1 sends zero POSTs
- cancellation while consuming SSE sends no subsequent POST
- process identity drift before request N prevents request N
- route inventory drift before request N prevents request N
- lock ownership drift before request N prevents request N
- warning memory before request N prevents request N
- warning memory after request N preserves request N and prevents request N+1
- transport timeout, malformed SSE, and HTTP failure prevent the next request
- artifact append failure prevents the next request
- invalid JSON or empty text records behavioral failure and continues through request 8
- no ninth request is possible

- [ ] **Step 5: Run engine tests and confirm red**

Run:

```zsh
python3 -m unittest tests.test_locking tests.test_stage_two_inference_engine -v
```

Expected: import failure for `StageTwoInferenceEngine` and missing `RunLock.owner`.

- [ ] **Step 6: Implement read-only lock ownership**

Add:

```python
def owner(self) -> str | None:
    if not self.path.exists():
        return None
    value = self.path.read_text(encoding="utf-8").strip()
    return value or None
```

- [ ] **Step 7: Implement isolated preflight**

`StageTwoInferenceEngine.__init__` must reject every manifest other than the exact `3.2.0` contract. It may import immutable types and predicates from `stage_two.py`, but it must not subclass or modify `StageTwoEngine`.

Preflight sequence:

```text
queued -> preflight -> resource_gate -> endpoint_identity -> ready
```

It records the operator identity, immutable host identities, exact route proof, fixed suite, normal memory, current lock ownership, and zero POST counters. Any failure transitions to `failed` through the runner recovery path and grants no inference authority.

- [ ] **Step 8: Implement the per-request gate and cohort loop**

Use one private method for the complete pre-POST gate:

```python
def _gate_before_post(self, cancel: threading.Event, sequence: int) -> None:
    if cancel.is_set():
        raise StageTwoError("cancelled", "Stage 2B-1 cancelled before next request")
    if self.lock_owner() != self.manifest.run_id:
        raise StageTwoError("lock_identity_failed", "current run does not own the active lock")
    identity = self._load_operator_identity()
    if not self.controller.matches(identity):
        raise StageTwoError("operator_identity_changed", "operator service identity changed")
    direct_health = self._health(self.profile.direct_base_url, "direct_health", sequence)
    routed_health = self._health(self.profile.routed_base_url, "routed_health", sequence)
    if not self._direct_health_is_safe(direct_health):
        raise StageTwoError("operator_health_failed", "direct health is unavailable or conflicting")
    if not routed_health_is_ready(routed_health):
        raise StageTwoError("route_health_failed", "routed health is unavailable")
    direct_models = self._models(self.profile.direct_base_url, "direct_models", sequence)
    routed_models = self._models(self.profile.routed_base_url, "routed_models", sequence)
    discover_route_identity(self.profile, direct_models, routed_models)
    self._assert_normal_resources(self.resource_probe(routed_health), f"before_request_{sequence}")
```

After `chat`, validate the response in memory, create a sanitized `SmokeObservation`, append it, discard the `TransportResult` content reference, then recheck process identity and normal memory before the next request.

Increment `inference_request_attempts` and `http_post_attempts` immediately before each transport `chat` call. This preserves an honest attempt count when the POST times out, returns a non-200 status, yields malformed SSE, or fails before an observation can be appended. Append POST request evidence containing only sequence, workload ID, route label, method, endpoint label, status when known, and a fixed-request digest; never store the request body or prompt.

Lifecycle sequence:

```text
ready -> running -> warmup -> measured -> artifact_validation -> awaiting_review
```

The lifecycle phase names describe cohort progress; `raw-runs.jsonl` sequence metadata remains the authoritative record of interleaved warm-up and measured requests.

- [ ] **Step 9: Verify Task 4 and Stage 2A regression**

Run:

```zsh
python3 -m unittest tests.test_locking tests.test_stage_two_inference_engine tests.test_stage_two_engine tests.test_stage_two_contract -v
```

Expected: all tests pass; Stage 2A still performs five GET observations and zero POST requests.

---

### Task 5: Stage 2B Evidence, Manual-Shutdown Cleanup, and Recovery

**Files:**
- Modify: `src/local_model_runtime_evaluation/stage_two_inference.py`
- Modify: `src/local_model_runtime_evaluation/artifacts.py`
- Modify: `tests/test_stage_two_inference_engine.py`
- Modify: `tests/test_artifacts.py`
- Modify: `tests/test_stage_two_contract.py`

**Interfaces:**
- Produces: `STAGE_TWO_INFERENCE_REQUIRED_FILES`.
- Produces: `StageTwoInferenceEngine.cleanup() -> dict[str, object]`.
- Produces: full `summary.json` with independent `inference_path_acceptance` and `behavioral_contract_acceptance`.

- [ ] **Step 1: Write complete-bundle and redaction tests**

Require exactly these Stage 2B additions on top of applicable revision-3 identity evidence:

```python
STAGE_TWO_INFERENCE_REQUIRED_FILES = {
    "manifest.json", "preflight.json", "runtime-identity.json",
    "artifact-identity.json", "operator-service-identity.json",
    "service-events.jsonl", "request-evidence.jsonl",
    "endpoint-inventory.json", "memory-samples.jsonl", "lifecycle.jsonl",
    "inference-suite.json", "raw-runs.jsonl", "smoke-summary.json",
    "direct-observations.json", "routed-observations.json", "summary.json",
}
```

Scan every artifact byte and exception string for the two fixed prompts, generated fixture content, `Authorization`, `Bearer`, and a fake secret. Assert `draft-report.md`, `route-comparison.json`, and stable-median fields are absent.

- [ ] **Step 2: Write cleanup and recovery tests**

Prove:
- cleanup refuses while the recorded OptiQ process still runs
- successful infrastructure cohort plus manual shutdown yields disposition `PASS`
- behavioral contract failure yields infrastructure disposition `PASS` and behavioral `FAIL`
- failed or cancelled cohort yields disposition `STOPPED` after manual shutdown
- exact shutdown is checked before checksums and lock release
- tampered route, observation count, sequence, method, output hash, or summary fails sealing
- one post-transition reseal failure is recoverable through a new cleanup call
- already-cleaned PASS and STOPPED bundles revalidate idempotently

- [ ] **Step 3: Run evidence tests and confirm red**

Run:

```zsh
python3 -m unittest tests.test_artifacts tests.test_stage_two_contract tests.test_stage_two_inference_engine -v
```

Expected: Stage 2B bundle selection and cleanup assertions fail.

- [ ] **Step 4: Add schema-aware artifact requirements**

In `ArtifactBundle._required_files()`, select `STAGE_TWO_INFERENCE_REQUIRED_FILES` only when:

```python
manifest.get("schema_version") == "3.2.0"
and manifest.get("mode") == "operator_inference_probe"
and manifest.get("runtime_profile_revision") == "3"
```

Keep the schema `3.1.0` Stage 2A branch byte-for-byte equivalent in behavior.

- [ ] **Step 5: Implement successful cleanup reconciliation**

Before finalization, reload and reconcile:
- exact endpoint identity
- exactly eight sequential sanitized observations
- four warm-ups and four measurements
- exact route order and workload IDs
- eight POST request-evidence records with no unauthorized method or endpoint
- normal pre/post memory samples for every request
- `smoke-summary.json` decisions matching recomputation
- operator shutdown proof

The bounded final summary contains:

```python
summary = {
    "run_id": run_id,
    "stage": 2,
    "mode": "operator_inference_probe",
    "comparison_class": "optiq-operator-route-smoke",
    "runtime_profile_id": self.profile.profile_id,
    "runtime_profile_revision": self.profile.revision,
    "suite_id": self.suite.suite_id,
    "suite_revision": self.suite.revision,
    "state": "cleaned",
    "disposition": "PASS",
    "inference_path_acceptance": "PASS",
    "behavioral_contract_acceptance": smoke["behavioral_contract_acceptance"],
    "measured_requests": 4,
    "excluded_warmups": 4,
    "inference_request_attempts": 8,
    "http_post_attempts": 8,
    "model_load_attempts": 0,
    "service_lifecycle_actions": 0,
    "operator_shutdown_verified": "PASS",
    "manager_review_required": True,
}
```

- [ ] **Step 6: Implement partial cleanup**

For `failed` and `cancelled`, require operator shutdown, preserve all present observations, report exact attempted/completed request counts, set `inference_path_acceptance` to `FAIL` or `STOPPED` according to the terminal state, finalize a partial bundle, transition to `cleaned`, reseal lifecycle, and validate partial checksums. Never rewrite a prior observation or reuse the run ID.

- [ ] **Step 7: Verify Task 5**

Run:

```zsh
python3 -m unittest tests.test_artifacts tests.test_stage_two_contract tests.test_stage_two_inference_engine -v
```

Expected: all focused tests pass, including Stage 2A required-file regression.

---

### Task 6: Factory and Runner Mode Routing

**Files:**
- Modify: `src/local_model_runtime_evaluation/stage_two_factory.py`
- Modify: `src/local_model_runtime_evaluation/runner.py`
- Modify: `tests/test_stage_two_runner.py`
- Create: `tests/test_stage_two_inference_runner.py`
- Modify: `tests/test_wait_for_review.py`

**Interfaces:**
- Produces: exact mode dispatch from `build_stage_two_engine(...)`.
- Produces: unchanged six Coordinator operations for both active Stage 2 modes.
- Preserves: `_stage2-worker` and `lmre-stage2-wait` command surfaces.

- [ ] **Step 1: Write exact factory-selection tests**

Assert schema `3.1.0` plus `operator_route_probe` returns `StageTwoEngine`; schema `3.2.0` plus `operator_inference_probe` returns `StageTwoInferenceEngine`; every mixed schema/mode pair fails before constructing a transport.

- [ ] **Step 2: Write runner tests for Stage 2B**

Prove the existing six operations behave as follows:
- preflight acquires the exact run lock and invokes the inference engine
- run-scenario launches only `_stage2-worker`
- status remains a single bounded lifecycle read
- cancel signals only the harness-owned worker
- cleanup invokes inference-engine shutdown/evidence validation before releasing the lock
- preflight failure creates bounded recovery evidence with the actual manifest mode and zero POST count
- cleanup sealing failure retains the lock for retry

- [ ] **Step 3: Run focused integration tests and confirm red**

Run:

```zsh
python3 -m unittest tests.test_stage_two_runner tests.test_stage_two_inference_runner tests.test_wait_for_review -v
```

Expected: Stage 2B factory and runner cases fail while current Stage 2A cases pass.

- [ ] **Step 4: Route factory dependencies by exact mode**

Keep the existing `operator_route_probe` construction unchanged. For `operator_inference_probe`:
- load runtime profile revision `3`
- load `suites/optiq-route-smoke-v1.json`
- construct `StageTwoInferenceTransport` with exactly the manifest routes and timeout `120`
- construct the existing observation-only `OperatorOptiQController`
- create a resource probe using `HostResourceProbe.free_memory_percent()` and the already-observed routed health
- pass `RunLock(output_root).owner` into the inference engine

Reject any other active mode with `ValueError("unsupported Stage 2 mode")`.

- [ ] **Step 5: Generalize runner labels without weakening policy**

Use `manifest.mode` and `manifest.comparison_class` in Stage 2 recovery summaries instead of hardcoding `operator_route_probe`. Keep the same `_stage2-worker`, cooperative SIGTERM behavior, operator-shutdown requirement, cleanup lock ordering, and error envelope.

- [ ] **Step 6: Verify Task 6 and all runner regressions**

Run:

```zsh
python3 -m unittest tests.test_stage_two_runner tests.test_stage_two_inference_runner tests.test_runner_permissions tests.test_worker tests.test_wait_for_review -v
```

Expected: all runner and worker tests pass; plugin-visible tool names remain unchanged.

---

### Task 7: Non-Authorizing Template, Coordinator Prompt, and Operator Runbook

**Files:**
- Create: `manifests/stage-2-optiq-inference-smoke.json.template`
- Create: `docs/stage-2b1-gate-a.md`
- Modify: `README.md`
- Modify: `AGENTS.md`
- Modify: `docs/architecture.md`
- Create: `/Users/jrazz/Documents/ObsidianNotes/00 System/Templates/Prompts/Benchmark Coordinator/Benchmark Coordinator Stage 2B-1 Agent System Prompt.md`
- Create: `/Users/jrazz/Documents/ObsidianNotes/10 Wiki/Projects/Local Model Benchmark Overhaul/Stage 2B-1 Benchmark Coordinator Setup and Acceptance Guide.md`
- Modify: `/Users/jrazz/Documents/ObsidianNotes/10 Wiki/Projects/Local Model Benchmark Overhaul/Local Model Benchmark Overhaul.md`
- Modify: `/Users/jrazz/Documents/ObsidianNotes/10 Wiki/Projects/Local Model Benchmark Overhaul/Local Model Benchmark Overhaul Board.md`

**Interfaces:**
- Produces: a template with placeholder approval timestamps and no usable run ID.
- Produces: a separately installable Stage 2B-1 Coordinator prompt; Stage 2A prompt remains preserved as rollback.
- Produces: an operator sequence that distinguishes Gate A, Gate B, exact-ID authorization, live run, manual shutdown, cleanup, and manager review.

- [ ] **Step 1: Add package tests for the non-authorizing template and unchanged plugin**

Assert the template contains schema `3.2.0`, exact routes and limits, placeholder run ID `stage2-YYYYMMDD-NNN`, and no current approval window. Assert plugin version remains `0.3.0`, the six tool names are unchanged, and no seventh tool exists.

- [ ] **Step 2: Run package tests and confirm the template case is red**

Run:

```zsh
python3 -m unittest tests.test_package -v
```

Expected: the new template assertion fails because the file does not yet exist.

- [ ] **Step 3: Write repository documentation**

Document:
- Stage 2B-1 is inference-path acceptance, not a benchmark
- eight total requests and no stable medians
- exact routes, models, suite, memory threshold, timeout, and operator ownership
- Gate A contains no live authority
- plugin `0.3.0` requires no rebuild or reinstall
- the Stage 2A accepted baseline and rollback remain intact
- Stage 2B-2 remains separately gated

- [ ] **Step 4: Write the Stage 2B-1 Coordinator prompt**

The prompt must enforce:
- exact Gemma Coordinator identity
- exact schema `3.2.0` bounded preflight fields
- one native tool call at a time with one-time approval
- normal order `inventory -> preflight -> run_scenario -> host waiter -> manual shutdown -> status -> cleanup`
- no polling loop
- no ambient Agent Channel, filesystem, Sandbox, Search, MCP, memory, provider-edit, service-lifecycle, or subagent authority
- expected counters: eight inference requests, eight POSTs, zero model loads, zero service lifecycle actions
- final report includes both `inference_path_acceptance` and `behavioral_contract_acceptance`
- no raw prompts, outputs, payloads, headers, process details, or performance conclusions

- [ ] **Step 5: Write the operator guide**

Use the same hand-held format as the accepted Stage 2A guide. The guide must tell Jason exactly when to:
1. keep OptiQ Lab closed
2. start the existing foreground launcher
3. reconnect the existing provider without editing it
4. ask Codex for read-only Gate B
5. authorize one exact unused ID only after Gate B
6. install the Stage 2B-1 prompt and use a fresh Coordinator chat
7. approve the first three tools one at a time
8. run `bin/lmre-stage2-wait <run-id>`
9. stop OptiQ with Control-C
10. return for one status and one cleanup call
11. return the Coordinator report to Codex for manager review

- [ ] **Step 6: Verify Task 7**

Run:

```zsh
python3 -m unittest tests.test_package -v
```

Then parse all changed JSON files with `jq empty` individually. Expected: tests and parsing pass; no plugin source or manifest with a usable run ID changed.

---

### Task 8: Full Gate A Verification, Review, and Deep Wiki Closeout

**Files:**
- Create: `/Users/jrazz/Documents/ObsidianNotes/20 Records/Projects/Local Model Stack/Tier 5/Local Model Runtime Evaluation Harness Stage 2B-1 Gate A Review - 2026-07-15.md`
- Modify: `/Users/jrazz/Documents/ObsidianNotes/00 System/Audit/Agent Activity/2026-07-15.md`
- Review only: all files changed by Tasks 1 through 7

**Interfaces:**
- Produces: a non-live Gate A acceptance record with remaining Gate B boundary.
- Produces: deterministic evidence that Stage 0, Stage 1, Stage 2A, Stage 2B-1, plugin, JSON, redaction, and vault contracts all pass.

- [ ] **Step 1: Run the full Python suite**

Run:

```zsh
python3 -m unittest discover -s tests -v
```

Expected: every test passes with no live network dependency outside test-owned loopback servers.

- [ ] **Step 2: Run the unchanged Swift plugin contract suite**

Run:

```zsh
swift test --package-path plugins/osaurus-evaluation-harness
```

Expected: all four existing plugin tests pass and plugin version remains `0.3.0`.

- [ ] **Step 3: Validate JSON and executable boundaries**

Run `jq empty` separately on:
- `schemas/benchmark-manifest.schema.json`
- `schemas/benchmark-suite.schema.json`
- `suites/optiq-route-smoke-v1.json`
- `tests/fixtures/valid-stage-2-inference.json`
- `manifests/stage-2-optiq-inference-smoke.json.template`

Scan source and artifacts fixtures for credentials, raw generated content, live run IDs, Stage 2A POST authority, plugin version drift, and a ninth-request path. Expected: no prohibited path exists.

- [ ] **Step 4: Run a deterministic fake end-to-end Stage 2B-1 flow**

Using only fake transports, fake resources, and a temporary output root, execute:

```text
preflight -> run worker -> awaiting_review -> fake operator shutdown -> cleanup -> validate bundle
```

Assert exact lifecycle, eight POSTs, four warm-ups, four measurements, independent acceptance decisions, checksums, no raw content, and active-lock release only after successful validation.

- [ ] **Step 5: Run the vault validator**

Run:

```zsh
python3 "/Users/jrazz/Documents/ObsidianNotes/00 System/Automation/validate_vault.py" "/Users/jrazz/Documents/ObsidianNotes"
```

Expected: vault validation passes.

- [ ] **Step 6: Perform the manager self-review**

Review the design specification requirement by requirement and record:
- exact requirement-to-test mapping
- Stage 2A files proven unchanged or regression-tested
- live boundaries still blocked
- rollback files and commands
- any residual risk around provider behavior, SSE fidelity, memory pressure, or operator timing

Do not authorize Gate B, create a live manifest, install a prompt, start OptiQ, reconnect a provider, or run inference during this review.

- [ ] **Step 7: Write the Gate A closeout**

The closeout must state one of:
- `READY_FOR_STAGE_2B1_GATE_B` when all deterministic checks pass
- `GATE_A_STOPPED` with exact failed checks and preserved rollback state

It must also state that Stage 2B-2 remains unauthorized regardless of Gate A result.

## Implementation Rollback

Before any live Stage 2B-1 authorization, rollback is file-scoped:

1. Remove the new Stage 2B-1 source modules, suite, fixture, template, and tests.
2. Remove only the schema `3.2.0`, policy tuple, factory branch, runner generalization, lock-owner reader, and Stage 2B artifact branch added by this plan.
3. Restore the pre-implementation versions of repository and Deep Wiki documentation changed by Tasks 7 and 8.
4. Rerun the complete Python suite, unchanged Swift plugin suite, JSON parsing checks, and vault validator.
5. Confirm schema `3.1.0` still selects the accepted GET-only `StageTwoEngine`, plugin `0.3.0` remains installed and unchanged, and `stage2-20260715-003` evidence remains untouched.

After any future live attempt, never delete or rewrite its full or partial evidence bundle and never reuse its run ID. Roll back only source and documentation under a new manager review.

## Execution Boundary

Completing this plan implements and verifies Gate A only. The next live steps remain separate approvals:

1. Gate B read-only host readiness while Jason owns the foreground OptiQ service.
2. One exact unused Stage 2B-1 run ID authorized by Jason after Gate B passes.
3. One short-lived live manifest created for only that ID.
4. Eight-request Coordinator run, manual OptiQ shutdown, cleanup, and manager review.
5. A separate Stage 2B-2 proposal only after Stage 2B-1 infrastructure acceptance.
