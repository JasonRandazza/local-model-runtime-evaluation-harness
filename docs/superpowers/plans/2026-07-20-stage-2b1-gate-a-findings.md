# Stage 2B-1 Gate A Five-Finding Remediation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the five `GATE_A_STOPPED` architecture-review findings on the existing Stage 2B-1 engine with fail-closed regressions, without authorizing Gate B, Gemma `3.3.0`, or any live endpoint contact.

**Architecture:** Keep `StageTwoInferenceEngine` and `LoopbackTransport` as the ownership boundary. Harden wall-clock/SSE behavior inside transport; tighten cleanup lock + shutdown rechecks in the inference engine and `RunLock`; add a durable POST-attempt journal consulted by partial/complete summaries; require exact lifecycle history before reseal legitimizes a new checksum. Slice 2 (Gemma schema `3.3.0`) is intentionally **out of this plan**.

**Tech Stack:** Python 3 standard library, `unittest` (`PYTHONPATH=src python3 -m unittest …`), existing Stage 2B-1 fakes in `tests/test_stage_two_inference_engine.py`, Swift plugin `0.3.0` unchanged.

## Global Constraints

- Spec: `docs/superpowers/specs/2026-07-20-stage-2b1-gemma-retarget-design.md` — **Slice 1 only**.
- Findings source: `docs/handoffs/2026-07-15-stage-2b1-cursor-continuation-prompt.md`.
- Do not run Gate B, create a usable run ID, install a Coordinator prompt, contact OptiQ/Osaurus/Keychain, load a model, or mutate providers.
- Do not implement schema `3.3.0`, Gemma profile/suite, or measurement-lane Stage wrappers.
- Preserve Stage 0, Stage 1, and accepted Stage 2A GET-only behavior (`StageTwoEngine`, `StageTwoReadOnlyTransport`).
- Preserve eight serial POSTs, one in-flight, 120s contract, RAM gates, route/model identity, credential-free Stage 2B POSTs, redaction, manual OptiQ lifecycle, plugin `0.3.0`.
- Tests must be deterministic fakes only (no network to real services).
- Do not stage or commit unless Jason gives explicit current-session Git approval.
- Passing tests do not lift `GATE_A_STOPPED`; only an independent architecture review may.

## File map

| Area | Primary files |
|---|---|
| Wall-clock + SSE | `src/local_model_runtime_evaluation/transport.py` |
| Stage 2B transport façade | `src/local_model_runtime_evaluation/stage_two_inference_transport.py` (only if error mapping needs updates) |
| Lock API | `src/local_model_runtime_evaluation/locking.py` |
| Inference engine cleanup / POST evidence | `src/local_model_runtime_evaluation/stage_two_inference.py` |
| POST journal (new) | `src/local_model_runtime_evaluation/post_attempt_journal.py` |
| Reseal / checksums | `src/local_model_runtime_evaluation/artifacts.py` |
| Lifecycle history | `src/local_model_runtime_evaluation/lifecycle.py` (read/history; change only if a helper is required) |
| Runner lock release after cleanup | `src/local_model_runtime_evaluation/runner.py` (only if release semantics must fail-closed on missing lock) |
| Docs after green suite | `docs/stage-2b1-gate-a.md` (status note that findings are implemented pending independent review — do **not** self-declare Gate B ready) |

---

### Task 1: Hard wall-clock deadline and cancellation-aware reads

**Files:**
- Modify: `src/local_model_runtime_evaluation/transport.py`
- Modify: `tests/test_transport.py`
- Modify: `tests/test_stage_two_inference_transport.py` (keep 120s init contract)

**Interfaces:**
- Consumes: existing `LoopbackTransport.chat(..., cancel: threading.Event | None)`
- Produces: `LoopbackTransport.chat` enforces `deadline = time.monotonic() + self.timeout_seconds` for the whole request; stream reads use a short socket timeout (≤1s) so cancel and deadline are polled; raises `TransportError` with sanitized messages (`"request timed out"` / `"request cancelled"`) without prompt text

- [ ] **Step 1: Write the failing wall-clock trickle test**

In `tests/test_transport.py`, add a handler that sends one SSE content event then sleeps longer than a short transport timeout while keeping the connection open (no `[DONE]` yet). Construct `LoopbackTransport` with `timeout_seconds=2` for this unit test only (Stage 2B façade still pins 120 in its own tests).

```python
def test_chat_enforces_monotonic_wall_clock_deadline_on_trickle_stream(self) -> None:
    # Handler: emit one data event, then sleep 5s before [DONE]
    transport = LoopbackTransport(
        {f"http://127.0.0.1:{self.port}/v1"}, timeout_seconds=2,
    )
    started = time.monotonic()
    with self.assertRaises(TransportError) as ctx:
        transport.chat(
            f"http://127.0.0.1:{self.port}/v1", "model", "secret-prompt", 16, None,
        )
    elapsed = time.monotonic() - started
    self.assertLess(elapsed, 4.0)
    self.assertIn("timed out", str(ctx.exception).lower())
    self.assertNotIn("secret-prompt", str(ctx.exception))
```

Add a second test that sets `cancel` after the first event and asserts cancellation completes in <2s even if the server would trickle for 10s:

```python
def test_chat_observes_cancellation_during_blocked_stream_read(self) -> None:
    cancel = threading.Event()
    # Handler sleeps 10s between events; a background thread sets cancel after 0.2s
    transport = LoopbackTransport(
        {f"http://127.0.0.1:{self.port}/v1"}, timeout_seconds=120,
    )
    started = time.monotonic()
    with self.assertRaises(TransportError) as ctx:
        transport.chat(
            f"http://127.0.0.1:{self.port}/v1", "model", "secret-prompt", 16, None,
            cancel=cancel,
        )
    self.assertLess(time.monotonic() - started, 3.0)
    self.assertIn("cancelled", str(ctx.exception).lower())
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
PYTHONPATH=src python3 -m unittest \
  tests.test_transport.TransportTests.test_chat_enforces_monotonic_wall_clock_deadline_on_trickle_stream \
  tests.test_transport.TransportTests.test_chat_observes_cancellation_during_blocked_stream_read \
  -v
```

Expected: FAIL (trickle survives past 2s and/or cancel waits on blocking readline).

- [ ] **Step 3: Implement minimal wall-clock + polled reads**

In `LoopbackTransport.chat` (`transport.py`):

1. Record `deadline = time.monotonic() + self.timeout_seconds` immediately after `started`.
2. After opening the connection, set `connection.sock.settimeout(1.0)` (or ≤1s) so `readline` returns periodically.
3. In the read loop, before each read:
   - if `time.monotonic() >= deadline`: raise `TransportError("request timed out")`
   - if `cancel is not None and cancel.is_set()`: raise `TransportError("request cancelled")`
4. On socket timeout from readline, continue the loop (re-check deadline/cancel) instead of treating it as EOF.
5. Preserve allowlisting, credential header behavior, and existing JSON/usage validation.

Keep Stage 2A `health` / `list_models` on the existing connection timeout unless a shared helper cleanly applies; do not break GET-only Stage 2A tests.

- [ ] **Step 4: Re-run focused transport tests**

```bash
PYTHONPATH=src python3 -m unittest tests.test_transport tests.test_stage_two_inference_transport -v
```

Expected: PASS (including existing 120s façade init tests).

- [ ] **Step 5: Commit only if Jason explicitly approves**

```bash
git add src/local_model_runtime_evaluation/transport.py \
  tests/test_transport.py tests/test_stage_two_inference_transport.py
git commit -m "$(cat <<'EOF'
Enforce Stage 2B chat wall-clock deadline and cancel polls.

Replace inactivity-only SSE blocking reads with a monotonic request
deadline and short socket timeouts so trickle streams cannot outlive
the contract.
EOF
)"
```

---

### Task 2: Strict SSE framing

**Files:**
- Modify: `src/local_model_runtime_evaluation/transport.py`
- Modify: `tests/test_transport.py`
- Modify: `tests/test_stage_two_inference_transport.py`

**Interfaces:**
- Consumes: Task 1 read loop
- Produces: `chat` requires a `data: [DONE]` terminator before success; rejects unexpected non-empty non-`data:` lines (allow blank lines and optional SSE comment lines that start with `:` only if you document that allowance in the test); never sets `stream_valid=True` after ambiguous EOF

- [ ] **Step 1: Write failing framing tests**

```python
def test_chat_rejects_eof_without_done(self) -> None:
    # Server sends one valid data event then closes without [DONE]
    with self.assertRaises(TransportError) as ctx:
        transport.chat(...)
    self.assertIn("incomplete", str(ctx.exception).lower())

def test_chat_rejects_unexpected_non_data_line(self) -> None:
    # Body includes a line "event: message" or "hello" between data events
    with self.assertRaises(TransportError) as ctx:
        transport.chat(...)
    self.assertIn("framing", str(ctx.exception).lower())

def test_chat_rejects_malformed_data_payload(self) -> None:
    # data: {not-json}
    with self.assertRaises(TransportError):
        transport.chat(...)
```

Extend `tests/test_stage_two_inference_transport.py` so the Stage 2B façade still surfaces these as sanitized `StageTwoError` / transport failures without prompt leakage (mirror existing `test_rejects_malformed_sse`).

- [ ] **Step 2: Run tests to verify they fail**

```bash
PYTHONPATH=src python3 -m unittest tests.test_transport -v
```

Expected: FAIL on EOF-without-DONE (currently accepted).

- [ ] **Step 3: Implement fail-closed framing**

In the SSE loop:

- Track `saw_done = False`.
- On `data: [DONE]`, set `saw_done = True` and break.
- On empty readline (EOF): if not `saw_done`, raise `TransportError("incomplete SSE stream")`.
- On non-empty line that is not `data: ...` and not an allowed SSE comment (`:` prefix): raise `TransportError("unsupported SSE framing")`.
- Keep blank-line handling as continue.
- Only construct a successful `TransportResult(..., stream_valid=True)` after `saw_done`.

- [ ] **Step 4: Re-run transport + Stage 2B transport tests**

```bash
PYTHONPATH=src python3 -m unittest tests.test_transport tests.test_stage_two_inference_transport -v
```

Expected: PASS. Update any fixtures that omit `[DONE]` (valid streams in tests must end with `data: [DONE]`).

- [ ] **Step 5: Commit only if Jason explicitly approves**

```bash
git commit -m "$(cat <<'EOF'
Fail closed on incomplete or unsupported SSE framing.

Require data [DONE] before accepting a chat stream and reject unexpected
non-data lines so ambiguous EOF cannot mark stream_valid.
EOF
)"
```

---

### Task 3: Cleanup lock ownership and shutdown TOCTOU

**Files:**
- Modify: `src/local_model_runtime_evaluation/locking.py`
- Modify: `src/local_model_runtime_evaluation/stage_two_inference.py`
- Modify: `tests/test_locking.py`
- Modify: `tests/test_stage_two_inference_engine.py`
- Modify: `tests/test_stage_two_inference_runner.py` (if runner release path must match new fail-closed semantics)

**Interfaces:**
- Consumes: `RunLock.owner`, `RunLock.release`, `StageTwoInferenceEngine._assert_current_lock`, `controller.assert_stopped`
- Produces:
  - `RunLock.release(run_id)` raises `LockError` if the lock file is missing (no silent success)
  - `RunLock.assert_owner(run_id) -> None` (or equivalent) fails if missing or mismatched
  - `cleanup` / `_finalize_and_validate` call lock assert before checksum write/reseal and immediately before returning success that allows runner lock release
  - `cleanup` calls `controller.assert_stopped` again immediately before successful final seal (after evidence reconcile, before `_finalize_and_validate` returns sealed success)

- [ ] **Step 1: Write failing lock + TOCTOU tests**

In `tests/test_locking.py`:

```python
def test_release_fails_when_lock_file_is_missing(self) -> None:
    lock = RunLock(self.root)
    lock.acquire("run-a")
    lock.path.unlink()
    with self.assertRaises(LockError):
        lock.release("run-a")
```

In `tests/test_stage_two_inference_engine.py` (use existing fake harness patterns):

```python
def test_cleanup_fails_if_lock_disappears_before_seal(self) -> None:
    # Drive engine to awaiting_review, unlink lock during cleanup before seal
    ...
    with self.assertRaises(StageTwoError) as ctx:
        engine.cleanup()
    self.assertEqual(ctx.exception.code, "lock_identity_failed")

def test_cleanup_fails_if_lock_owner_is_replaced_before_seal(self) -> None:
    # Replace lock contents with another run id mid-cleanup
    ...

def test_cleanup_rechecks_shutdown_immediately_before_final_seal(self) -> None:
    # FakeController.assert_stopped: first call ok, second call raises (service restarted)
    ...
    with self.assertRaises(StageTwoError) as ctx:
        engine.cleanup()
    self.assertEqual(ctx.exception.code, "cleanup_failed")
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
PYTHONPATH=src python3 -m unittest tests.test_locking tests.test_stage_two_inference_engine -v
```

Expected: FAIL (`release` currently returns when missing; cleanup lacks second shutdown + seal-time lock asserts).

- [ ] **Step 3: Implement fail-closed lock + recheck**

1. Change `RunLock.release` so a missing file raises `LockError("active run lock is missing")`.
2. Add `RunLock.assert_owner(self, run_id: str) -> None` that raises if missing or mismatched.
3. In `StageTwoInferenceEngine.cleanup` / `_finalize_and_validate`:
   - `_assert_current_lock()` at cleanup start (after status check)
   - after evidence reconcile and **immediately before** `reseal_after_state_transition` / checksum finalization: `_assert_current_lock()` again
   - call `controller.assert_stopped(identity)` a second time immediately before that final seal path
4. Ensure sealing failure still retains the lock for retry (existing runner tests must keep passing).
5. Update any unit test that relied on missing-lock release being a no-op.

- [ ] **Step 4: Re-run lock, engine, and runner tests**

```bash
PYTHONPATH=src python3 -m unittest \
  tests.test_locking \
  tests.test_stage_two_inference_engine \
  tests.test_stage_two_inference_runner \
  -v
```

Expected: PASS.

- [ ] **Step 5: Commit only if Jason explicitly approves**

```bash
git commit -m "$(cat <<'EOF'
Fail closed on cleanup lock drift and shutdown TOCTOU.

Require lock ownership through seal and re-verify operator shutdown
immediately before final evidence sealing.
EOF
)"
```

---

### Task 4: Durable POST-attempt journal

**Files:**
- Create: `src/local_model_runtime_evaluation/post_attempt_journal.py`
- Create: `tests/test_post_attempt_journal.py`
- Modify: `src/local_model_runtime_evaluation/stage_two_inference.py`
- Modify: `tests/test_stage_two_inference_engine.py`
- Modify: `src/local_model_runtime_evaluation/artifacts.py` only if the journal file must be listed in required checksum sets

**Interfaces:**
- Produces:

```python
class PostAttemptPhase(str, Enum):
    PREPARED = "prepared"
    DISPATCHED = "dispatched"
    COMPLETED = "completed"
    FAILED = "failed"

class PostAttemptJournal:
    def __init__(self, bundle: ArtifactBundle) -> None: ...
    def record(
        self,
        *,
        sequence: int,
        phase: PostAttemptPhase,
        workload_id: str,
        route: str,
        detail: str | None = None,
    ) -> None: ...
    def conservative_post_count(self) -> int:
        """Count sequences that reached DISPATCHED or later; never underreport a possible POST."""
        ...
```

- Engine `run` must: `PREPARED` (durable) → `DISPATCHED` (durable, immediately before transport call) → `COMPLETED` or `FAILED` after transport returns/raises
- `_partial_summary` / cleanup reconciliation must derive `http_post_attempts` conservatively from the journal (and must not claim fewer POSTs than durable dispatched evidence)
- Fault injection: if append fails after `DISPATCHED` but before transport returns, subsequent POSTs must stop; summaries must not underreport

- [ ] **Step 1: Write failing journal unit tests**

```python
def test_conservative_count_includes_dispatched_without_completion(self) -> None:
    journal.record(sequence=1, phase=PostAttemptPhase.PREPARED, ...)
    journal.record(sequence=1, phase=PostAttemptPhase.DISPATCHED, ...)
    self.assertEqual(journal.conservative_post_count(), 1)

def test_prepared_only_does_not_count_as_sent_post(self) -> None:
    journal.record(sequence=1, phase=PostAttemptPhase.PREPARED, ...)
    self.assertEqual(journal.conservative_post_count(), 0)
```

In `tests/test_stage_two_inference_engine.py`:

```python
def test_dispatch_journal_survives_when_post_evidence_append_fails(self) -> None:
    # After DISPATCHED, make request-evidence append fail; ensure cleanup/partial
    # summary still reports at least one possible POST from the journal
    ...
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
PYTHONPATH=src python3 -m unittest tests.test_post_attempt_journal -v
```

Expected: FAIL (module missing).

- [ ] **Step 3: Implement journal + wire into engine**

1. Create `post_attempt_journal.py` writing append-only `post-attempts.jsonl` via `bundle.append_jsonl`.
2. Each record: `sequence`, `phase`, `workload_id`, `route`, optional sanitized `detail` (no prompts/content).
3. In `StageTwoInferenceEngine.run`, before `_chat`:
   - `record(PREPARED)` then `record(DISPATCHED)` then call transport
   - on success `record(COMPLETED)`; on transport/identity failure `record(FAILED)`
4. Keep existing `request-evidence.jsonl` POST rows; journal is the crash-consistent authority for attempt counts when they disagree.
5. Update `_partial_summary` / complete summary builders to set `http_post_attempts` / `inference_request_attempts` from `max(existing_reconcile, journal.conservative_post_count())` with explicit fail-closed behavior if evidence is contradictory in an unsafe direction (prefer over-count possible POSTs over under-count).
6. Add `post-attempts.jsonl` to required artifact sets used by finalize/partial validate as appropriate so cleanup fails closed if the journal is missing after any DISPATCHED phase.

- [ ] **Step 4: Re-run journal + inference engine tests**

```bash
PYTHONPATH=src python3 -m unittest \
  tests.test_post_attempt_journal \
  tests.test_stage_two_inference_engine \
  -v
```

Expected: PASS. Existing timeout/cancel/HTTP failure tests still prevent the next POST and remain sanitized.

- [ ] **Step 5: Commit only if Jason explicitly approves**

```bash
git commit -m "$(cat <<'EOF'
Add durable Stage 2B POST-attempt journal phases.

Record prepared/dispatched/completed/failed attempts so cleanup counts
cannot underreport a possible POST after persistence faults.
EOF
)"
```

---

### Task 5: Exact lifecycle reconciliation during reseal

**Files:**
- Modify: `src/local_model_runtime_evaluation/artifacts.py`
- Modify: `src/local_model_runtime_evaluation/stage_two_inference.py`
- Modify: `tests/test_artifacts.py`
- Modify: `tests/test_stage_two_inference_engine.py`
- Optionally modify: `src/local_model_runtime_evaluation/lifecycle.py` if a pure helper `expected_history_fingerprint` fits better there

**Interfaces:**
- Consumes: `LifecycleStore.history(run_id) -> list[transition records]`
- Produces: `ArtifactBundle.reseal_after_state_transition(expected_lifecycle_lines: tuple[str, ...] | None = None)` — when expected lines are provided (Stage 2B path), verify `lifecycle.jsonl` byte-for-byte or record-equal to the expected history **before** rewriting checksums; reject append/remove/reorder/duplicate/modify
- Stage 2A callers that today call `reseal_after_state_transition()` with no args must keep working **only if** Stage 2A tests still pass; prefer requiring Stage 2B to pass expected history while Stage 2A either passes its own expected history or uses a separate internal path that still verifies history equals the store’s authoritative read at seal time

Recommended fail-closed approach for both Stage 2A and 2B:

```python
def reseal_after_state_transition(
    self, *, expected_lifecycle_sha256: str,
) -> None:
    ...
```

Engine computes `expected_lifecycle_sha256` from `lifecycle.history` **immediately before** the transition that is about to be sealed, then after writing the new lifecycle row re-reads the file and requires the digest to match the concatenation of prior expected + new row (or re-hash full file against a just-built expected digest). Tampering between transition write and reseal must fail.

- [ ] **Step 1: Write failing tamper tests**

```python
def test_reseal_rejects_appended_lifecycle_row(self) -> None: ...
def test_reseal_rejects_removed_lifecycle_row(self) -> None: ...
def test_reseal_rejects_reordered_lifecycle_rows(self) -> None: ...
def test_reseal_rejects_duplicated_lifecycle_row(self) -> None: ...
def test_reseal_rejects_modified_lifecycle_row(self) -> None: ...
```

In engine recovery tests, ensure `_recover_cleaned` / cleanup reseal cannot checksum-legitimize a tampered `lifecycle.jsonl`.

- [ ] **Step 2: Run tests to verify they fail**

```bash
PYTHONPATH=src python3 -m unittest tests.test_artifacts tests.test_stage_two_inference_engine -v
```

Expected: FAIL (reseal currently allows any `lifecycle.jsonl` change).

- [ ] **Step 3: Implement exact reconciliation**

1. Before `_write_checksums` in reseal, verify lifecycle content against the caller-supplied expected digest/history.
2. Update all `reseal_after_state_transition` call sites in Stage 2A/2B engines to supply the expected value from the lifecycle store.
3. Keep atomic checksum replacement behavior from existing tests.

- [ ] **Step 4: Re-run artifact, Stage 2A, and Stage 2B engine tests**

```bash
PYTHONPATH=src python3 -m unittest \
  tests.test_artifacts \
  tests.test_lifecycle \
  tests.test_stage_two_engine \
  tests.test_stage_two_inference_engine \
  -v
```

Expected: PASS.

- [ ] **Step 5: Commit only if Jason explicitly approves**

```bash
git commit -m "$(cat <<'EOF'
Require exact lifecycle history before artifact reseal.

Reject tampered lifecycle rows so a new checksum cannot legitimize
unauthorized transition evidence.
EOF
)"
```

---

### Task 6: Full Gate A verification and docs note

**Files:**
- Modify: `docs/stage-2b1-gate-a.md` (implementation status only)
- Verify: `tests/test_stage_two_gate_a_e2e.py`
- Do **not** modify Deep Wiki / Obsidian vault unless Jason explicitly asks after independent review

**Interfaces:** none new

- [ ] **Step 1: Run deterministic Stage 2B-1 e2e**

```bash
PYTHONPATH=src python3 -m unittest tests.test_stage_two_gate_a_e2e -v
```

Expected: PASS — exactly eight fake POSTs, four warm-ups, four measured, independent accept decisions, redaction, checksum validation, lock retention until successful cleanup.

- [ ] **Step 2: Run full Python suite**

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

Expected: PASS (record pass count in the verification note).

- [ ] **Step 3: Run Swift plugin suite (unchanged 0.3.0)**

From the plugin package directory used by this repo (see README / existing Stage 2B plan):

```bash
swift test
```

Expected: all four tests PASS; version remains `0.3.0`. Do not rebuild or reinstall the plugin.

- [ ] **Step 4: Static scans**

Confirm with ripgrep / file checks:

- no active Stage 2B manifest with a usable live run ID under `manifests/` beyond templates/fixtures
- no new provider mutation helpers
- no credential serialization into artifacts
- no Stage 2B-2 authority symbols introduced

- [ ] **Step 5: Update Gate A doc status carefully**

In `docs/stage-2b1-gate-a.md`, add a short note that the five findings have **code+test remediation in-tree pending independent architecture review**. Keep decision as `GATE_A_STOPPED` until that review. Do not write `READY_FOR_STAGE_2B1_GATE_B`.

- [ ] **Step 6: Write verification log**

Create `docs/superpowers/verification/2026-07-20-stage-2b1-gate-a-findings.md` listing exact commands, pass/fail, and residual live-only risks (SSE under real load, provider reconnect flakiness).

- [ ] **Step 7: Commit only if Jason explicitly approves**

```bash
git commit -m "$(cat <<'EOF'
Document Stage 2B-1 Gate A finding remediation verification.

Keep GATE_A_STOPPED until independent review; record suite commands
and residual live-only risks.
EOF
)"
```

---

## Out of plan (next plan after independent review)

- Schema `3.3.0` + `gemma-4-12b-optiq-4bit` rev `1` + `gemma-optiq-route-smoke-v1`
- Live pin capture, Gate B, unused run ID, eight-POST Gemma smoke
- Measurement-lane Stage wrappers (roadmap annex only in the design)

## Spec coverage self-check

| Spec Slice 1 requirement | Task |
|---|---|
| Finding 1 wall-clock + cancel | Task 1 |
| Finding 2 strict SSE | Task 2 |
| Finding 3 cleanup lock + shutdown TOCTOU | Task 3 |
| Finding 4 durable POST accounting | Task 4 |
| Finding 5 lifecycle reseal reconciliation | Task 5 |
| Full suite + e2e + plugin + scans + no self-lift of gate | Task 6 |
| No Gemma `3.3.0` / live auth | Explicitly out of plan |
| Roadmap annex | Not implemented (design-only) |
