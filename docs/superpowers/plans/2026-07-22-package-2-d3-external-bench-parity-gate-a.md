# Package 2 D3 External-Bench Parity Gate A Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Land fake-only D3 Gate A: admin login + external-mode throughput bench client, cross-check note builder vs sealed `004`, parity runner with injectable lifecycle/client, and docs — without live POSTs or run IDs.

**Architecture:** Stdlib loopback HTTP client for `/admin/api/login` and `/admin/api/bench/*` with cookie jar; build the locked external bench request body from pin + matrix-local key; parse stream/results into metric records; pure function builds the required cross-check markdown fields; thin runner orchestrates start → login → bench → note → cleanup with honest `service_lifecycle_actions`.

**Tech Stack:** Python 3 stdlib (`http.client`, `unittest`) + existing `LifecycleController` / `OmlxThinkingPin`. Prefer `/opt/homebrew/bin/python3`. No `httpx` dependency.

## Global Constraints

- Design: `docs/superpowers/specs/2026-07-22-package-2-d3-external-bench-parity-design.md`
- No live oMLX contact; no new run IDs; no accuracy-bench; no omlx.ai upload
- Do not edit sealed measure evidence (`001`–`004`)
- Do not rewrite pin r2; `--api-key` pin bump is Gate B–gated only
- Plugin `0.3.0` unchanged
- Comparison class: `omlx-thinking-external-bench-parity-v1`
- Bench body locks: `prompt_lengths=[1024]`, `generation_length=4096`, `batch_sizes=[]`, `extra_body.chat_template_kwargs.enable_thinking=true`

## File map

| Area | Files |
|---|---|
| Client | Create `src/local_model_runtime_evaluation/omlx_admin_bench_client.py` |
| Cross-check | Create `src/local_model_runtime_evaluation/omlx_thinking_bench_parity.py` |
| Runner | Create `src/local_model_runtime_evaluation/omlx_thinking_bench_runner.py` |
| Tests | `tests/test_omlx_admin_bench_client.py`, `tests/test_omlx_thinking_bench_parity.py`, `tests/test_omlx_thinking_bench_runner.py` |
| Docs | `docs/package-2-omlx-thinking-d3.md`, update Gate D / D4 / D2 follow-on rows |

---

### Task 1: Admin bench client (login + start body + results parse)

**Files:**
- Create: `src/local_model_runtime_evaluation/omlx_admin_bench_client.py`
- Test: `tests/test_omlx_admin_bench_client.py`

**Interfaces:**
```python
@dataclass(frozen=True)
class BenchMetricRow:
    ttft_ms: float | None
    tpot_ms: float | None
    gen_tps: float | None
    e2e_latency_s: float | None
    prompt_tokens: int | None
    completion_tokens: int | None
    status: str
    error: str | None = None

class OmlxAdminBenchError(RuntimeError):
    def __init__(self, message: str, *, reason: str) -> None: ...

def build_external_bench_request(
    *,
    model_id: str,
    base_url: str,
    api_key: str,
    enable_thinking: bool = True,
) -> dict[str, object]:
    """Locked Gate A request body for POST /admin/api/bench/start."""

class OmlxAdminBenchClient:
    def __init__(self, admin_origin: str = "http://127.0.0.1:8100", timeout_seconds: float = 120.0) -> None: ...
    def login(self, api_key: str) -> None: ...
    def start_external_bench(self, body: dict[str, object]) -> str: ...  # returns bench_id
    def fetch_results(self, bench_id: str) -> tuple[str, tuple[BenchMetricRow, ...]]:
        """Return (run_status, metric rows). Fail-closed on HTTP errors."""
```

- [ ] **Step 1: Write failing tests**

```python
# tests/test_omlx_admin_bench_client.py
from local_model_runtime_evaluation.omlx_admin_bench_client import (
    OmlxAdminBenchClient,
    OmlxAdminBenchError,
    build_external_bench_request,
    parse_bench_results_payload,
)

class BuildExternalBenchRequestTest(unittest.TestCase):
    def test_locked_body_shape(self) -> None:
        body = build_external_bench_request(
            model_id="Qwen3.6-35B-A3B-OptiQ-4bit",
            base_url="http://127.0.0.1:8100/v1",
            api_key="lmre-matrix-local",
        )
        self.assertEqual(body["prompt_lengths"], [1024])
        self.assertEqual(body["generation_length"], 4096)
        self.assertEqual(body["batch_sizes"], [])
        self.assertEqual(body["model_id"], "Qwen3.6-35B-A3B-OptiQ-4bit")
        external = body["external"]
        self.assertEqual(external["base_url"], "http://127.0.0.1:8100/v1")
        self.assertEqual(external["api_key"], "lmre-matrix-local")
        self.assertEqual(external["model"], "Qwen3.6-35B-A3B-OptiQ-4bit")
        self.assertEqual(
            external["extra_body"],
            {"chat_template_kwargs": {"enable_thinking": True}},
        )

class ParseBenchResultsTest(unittest.TestCase):
    def test_parses_metric_rows(self) -> None:
        status, rows = parse_bench_results_payload({
            "status": "completed",
            "results": [{
                "ttft_ms": 12.5,
                "tpot_ms": 1.2,
                "gen_tps": 40.0,
                "e2e_latency_s": 1.5,
                "prompt_tokens": 1024,
                "completion_tokens": 200,
            }],
        })
        self.assertEqual(status, "completed")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].ttft_ms, 12.5)
        self.assertEqual(rows[0].completion_tokens, 200)
        self.assertEqual(rows[0].status, "ok")

class AdminBenchClientHttpTest(unittest.TestCase):
    # Use ThreadingHTTPServer handler that:
    # - POST /admin/api/login with {"api_key":"..."} sets Set-Cookie
    # - rejects missing/wrong key with 401
    # - POST /admin/api/bench/start requires Cookie; returns {"bench_id":"bench-1"}
    # - GET /admin/api/bench/bench-1/results returns completed payload
    def test_login_start_results_happy_path(self) -> None: ...
    def test_login_401_is_fail_closed(self) -> None: ...
    def test_bench_start_without_cookie_fails(self) -> None: ...
```

- [ ] **Step 2: Run tests — expect fail (import / missing symbols)**

```bash
PYTHONPATH=src /opt/homebrew/bin/python3 -m unittest tests.test_omlx_admin_bench_client -q
```

Expected: FAIL (module or symbols missing)

- [ ] **Step 3: Implement `omlx_admin_bench_client.py`**

- `build_external_bench_request` returns the locked dict exactly.
- `parse_bench_results_payload` maps each results entry into `BenchMetricRow`; missing metrics → `None` fields; unknown/error run status preserved.
- `OmlxAdminBenchClient` uses `http.client` against `admin_origin` host/port only (`127.0.0.1`); stores `Cookie` from login `Set-Cookie`; sends cookie on subsequent admin calls.
- Raise `OmlxAdminBenchError(reason="login_failed"|"bench_start_failed"|"results_failed"|"endpoint_forbidden")` on non-success.

- [ ] **Step 4: Re-run tests — expect PASS**

```bash
PYTHONPATH=src /opt/homebrew/bin/python3 -m unittest tests.test_omlx_admin_bench_client -q
```

- [ ] **Step 5: Commit**

```bash
git add src/local_model_runtime_evaluation/omlx_admin_bench_client.py \
  tests/test_omlx_admin_bench_client.py
git commit -m "$(cat <<'EOF'
Add oMLX admin external-bench client for D3 parity.

EOF
)"
```

---

### Task 2: Cross-check note + decision helper

**Files:**
- Create: `src/local_model_runtime_evaluation/omlx_thinking_bench_parity.py`
- Test: `tests/test_omlx_thinking_bench_parity.py`

**Interfaces:**
```python
REFERENCE_MEASURE_RUN_ID = "omlx-thinking-measure-20260722-004"
COMPARISON_CLASS = "omlx-thinking-external-bench-parity-v1"

def decide_parity_outcome(
    *,
    bench_completed: bool,
    cleanup_ok: bool,
    cross_check_written: bool,
) -> str:
    """Return PASS | FAIL | FAIL_CLEANUP per design."""

def build_cross_check_markdown(
    *,
    run_id: str,
    decision: str,
    bench_status: str,
    rows: tuple[BenchMetricRow, ...],
    reference_run_id: str = REFERENCE_MEASURE_RUN_ID,
) -> str:
    """Must include TTFT semantic divergence, viability, informational throughput."""
```

- [ ] **Step 1: Write failing tests**

```python
class DecideParityOutcomeTest(unittest.TestCase):
    def test_pass_requires_all_three(self) -> None:
        self.assertEqual(
            decide_parity_outcome(
                bench_completed=True, cleanup_ok=True, cross_check_written=True
            ),
            "PASS",
        )
    def test_fail_cleanup_when_bench_ok_cleanup_bad(self) -> None:
        self.assertEqual(
            decide_parity_outcome(
                bench_completed=True, cleanup_ok=False, cross_check_written=True
            ),
            "FAIL_CLEANUP",
        )
    def test_fail_when_bench_incomplete(self) -> None:
        self.assertEqual(
            decide_parity_outcome(
                bench_completed=False, cleanup_ok=True, cross_check_written=True
            ),
            "FAIL",
        )
    def test_fail_when_cross_check_missing(self) -> None:
        self.assertEqual(
            decide_parity_outcome(
                bench_completed=True, cleanup_ok=True, cross_check_written=False
            ),
            "FAIL",
        )

class BuildCrossCheckMarkdownTest(unittest.TestCase):
    def test_mentions_ttft_divergence_and_reference(self) -> None:
        md = build_cross_check_markdown(
            run_id="omlx-thinking-bench-20260722-001",
            decision="PASS",
            bench_status="completed",
            rows=(BenchMetricRow(12.5, 1.2, 40.0, 1.5, 1024, 200, "ok"),),
        )
        self.assertIn("omlx-thinking-measure-20260722-004", md)
        self.assertIn("reasoning_content", md)
        self.assertIn("content-only", md)
        self.assertIn("1024", md)
        self.assertIn("ttft_ms", md.lower() or md)  # table or field present
```

- [ ] **Step 2: Run — expect FAIL**

```bash
PYTHONPATH=src /opt/homebrew/bin/python3 -m unittest tests.test_omlx_thinking_bench_parity -q
```

- [ ] **Step 3: Implement helpers** — markdown must explicitly state harness D4 TTFT is content-only while oMLX external times first content or reasoning_content; must not claim metric equality as PASS criterion.

- [ ] **Step 4: Re-run — expect PASS**

- [ ] **Step 5: Commit**

```bash
git commit -m "$(cat <<'EOF'
Add D3 external-bench cross-check note and decision helpers.

EOF
)"
```

---

### Task 3: Parity runner + docs

**Files:**
- Create: `src/local_model_runtime_evaluation/omlx_thinking_bench_runner.py`
- Test: `tests/test_omlx_thinking_bench_runner.py`
- Create: `docs/package-2-omlx-thinking-d3.md`
- Modify: `docs/package-2-omlx-thinking-gate-d.md`, `docs/package-2-omlx-thinking-d4.md`, `docs/package-2-omlx-thinking-d2.md`

**Interfaces:**
```python
class ThinkingBenchParityRunner:
    def __init__(
        self,
        pin: OmlxThinkingPin,
        *,
        controller: LifecycleController,
        admin_client: OmlxAdminBenchClient,
        api_key: str,
        port_free: Callable[[int], bool],
    ) -> None: ...

    @property
    def lifecycle_actions(self) -> int: ...

    def run_parity(self) -> dict[str, object]:
        """start → login → start bench → fetch results → build note fields.
        Does not write files or authorize run IDs. Raises on fail-closed errors.
        Caller owns evidence persistence and cleanup invocation.
        """

    def cleanup(self) -> None: ...
```

- [ ] **Step 1: Write failing runner tests with fakes**

```python
# Fake controller increments lifecycle_actions on start/stop;
# Fake admin client records login/start/results calls and returns completed rows.
# Assert:
# - run_parity calls login then start with build_external_bench_request(...) body
# - returns dict with comparison_class, rows, cross_check_markdown, bench_status
# - lifecycle_actions > 0 after start
# - login failure raises and does not start bench
```

- [ ] **Step 2: Run — expect FAIL**

```bash
PYTHONPATH=src /opt/homebrew/bin/python3 -m unittest tests.test_omlx_thinking_bench_runner -q
```

- [ ] **Step 3: Implement runner** — reuse `omlx_server_pin_from_pin` from `omlx_thinking_runner.py` (import, do not duplicate). Start via controller; login with `api_key`; start external bench; fetch results; attach `build_cross_check_markdown` using a placeholder run_id argument `"(unauthorized-gate-a)"` for Gate A tests only (live CLI later supplies real ID).

- [ ] **Step 4: Docs**

`docs/package-2-omlx-thinking-d3.md`:
```markdown
# Package 2 D3: External-Bench Parity

## Current Decision

`D3_GATE_A_READY` — fake-only implementation landed.

Does **not** authorize live admin login, bench POSTs, or a new run ID.

## Next

1. Gate B: pin r2 + port free + **live admin login proof**
2. Jason authorizes unused ID (e.g. `omlx-thinking-bench-20260722-001`)
3. Live cohort + sealed cross-check vs `004`
```

Update Gate D D3 row → **Gate A ready**; D4/D2 follow-on text: D3 Gate A ready, live separately gated.

- [ ] **Step 5: Full verification**

```bash
PYTHONPATH=src /opt/homebrew/bin/python3 -m unittest \
  tests.test_omlx_admin_bench_client \
  tests.test_omlx_thinking_bench_parity \
  tests.test_omlx_thinking_bench_runner \
  tests.test_omlx_thinking_runner -q
```

Expected: OK

- [ ] **Step 6: Commit**

```bash
git commit -m "$(cat <<'EOF'
Add D3 external-bench parity runner and Gate A docs.

EOF
)"
```

## Verification

```bash
PYTHONPATH=src /opt/homebrew/bin/python3 -m unittest \
  tests.test_omlx_admin_bench_client \
  tests.test_omlx_thinking_bench_parity \
  tests.test_omlx_thinking_bench_runner -q
```

## Out of scope

- Gate B live admin login  
- Live run ID / evidence seal  
- Pin revision with `--api-key`  
- Accuracy-bench / omlx.ai upload  

## Spec coverage checklist

| Spec item | Task |
|---|---|
| External-mode locked body | Task 1 |
| Admin login + cookie + fail-closed | Task 1 |
| Metric row fields | Task 1–2 |
| Cross-check TTFT divergence + viability | Task 2 |
| PASS/FAIL/FAIL_CLEANUP | Task 2 |
| Harness-owned lifecycle orchestration | Task 3 |
| Docs Gate A ready | Task 3 |
| No live authority | Global + all tasks |

## Execution

Inline in this session unless Jason chooses subagent-driven.
