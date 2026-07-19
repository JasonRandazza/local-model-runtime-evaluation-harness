# Gemma 4 12B QAT 3×3 Native Matrix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Automate a safe, one-cell-at-a-time direct-to-native 3×3 performance screen (then finalist) for Gemma 4 12B IT QAT across JANG_4M, oQ4-fp16, and OptiQ-4bit on Osaurus, oMLX, and OptiQ.

**Architecture:** Evolve the personal-selection measurement pattern into a matrix campaign runner with pinned server adapters (start/stop/health), RAM gating, and `PASS`/`FAIL`/`N/A` cell outcomes. Reuse `LoopbackTransport`, `HostResourceProbe`, and response-contract validation. Do not modify Stage 2B engines, plugin `0.3.0`, or Gate B.

**Tech Stack:** Python 3.11 stdlib, `unittest`, existing `src/local_model_runtime_evaluation` package, JSON cell/campaign configs, Markdown reports under gitignored `results/matrix/`.

## Global Constraints

- Spec: `docs/superpowers/specs/2026-07-19-gemma-3x3-matrix-design.md`.
- Control artifacts only: `OsaurusAI/gemma-4-12B-it-qat-JANG_4M`, `avneetsb/gemma-4-12B-it-qat-oQ4-fp16`, `mlx-community/gemma-4-12B-it-qat-OptiQ-4bit`.
- Direct ports only: Osaurus `1337`, oMLX `8100`, OptiQ `8080` — all `http://127.0.0.1:<port>/v1`.
- Attempt all 9 cells; unloadable → `N/A` with reason; tear down anything this cell started.
- One cell at a time; preflight RAM floor; pinned argv only; verify process gone + port free before next cell.
- Screen = 1 warm-up + 3 measured; finalist = 1 + 5; three workloads from personal-selection class.
- TTFT/decode null unless streaming is incremental and token evidence is trustworthy.
- Unit tests use fakes only — no live Osaurus/oMLX/OptiQ contact in `unittest`.
- Do not delete or rewrite Stage 0–2B code; do not run Gate B; do not rebuild plugin `0.3.0`.
- Stage 2B-1 Gemma retarget, Osaurus routing overhead, and quality judges are **out of this plan**.
- Do not stage or commit unless Jason gives explicit current-session Git approval. This repo may still have no tracked baseline.

---

## File Structure

| Path | Responsibility |
|---|---|
| `config/matrix/cells/*.json` | Nine cell definitions (quant × server, ports, pinned start argv, model id) |
| `config/matrix/gemma-4-12b-qat-campaign.json` | Campaign: cell list, RAM floor, modes, suite path, results root |
| `suites/gemma-matrix-v1.json` | Three workloads (copy personal-selection prompts/contracts) |
| `src/.../matrix_config.py` | Load/validate Cell + Campaign |
| `src/.../matrix_lifecycle.py` | Generic spawn/stop/port-free helpers (stdlib subprocess) |
| `src/.../matrix_servers.py` | Osaurus / oMLX / OptiQ adapters behind one protocol |
| `src/.../matrix_measure.py` | Per-cell inventory + chat cohort + observation summary |
| `src/.../matrix_runner.py` | Campaign orchestration + 3×3 report |
| `bin/lmre-matrix` | CLI entry |
| `tests/test_matrix_*.py` | Deterministic unit tests with fakes |
| `docs/matrix.md` | Short operator pointer |
| `results/matrix/` | Gitignored outputs |

---

### Task 1: Cell, Campaign, And Suite Config

**Files:**
- Create: `suites/gemma-matrix-v1.json`
- Create: `config/matrix/cells/` (nine JSON files)
- Create: `config/matrix/gemma-4-12b-qat-campaign.json`
- Create: `src/local_model_runtime_evaluation/matrix_config.py`
- Create: `tests/test_matrix_config.py`

**Interfaces:**
- Produces: `Cell.load(path: Path) -> Cell`
- Produces: `Campaign.load(path: Path) -> Campaign`
- Produces: `MatrixSuite.load(path: Path) -> MatrixSuite` (or reuse personal-selection `Suite` if identical shape)

- [ ] **Step 1: Write the failing config tests**

```python
# tests/test_matrix_config.py
from __future__ import annotations

import unittest
from pathlib import Path

from local_model_runtime_evaluation.matrix_config import Campaign, Cell, MatrixError

ROOT = Path(__file__).resolve().parents[1]
CELLS = ROOT / "config" / "matrix" / "cells"


class MatrixConfigTests(unittest.TestCase):
    def test_all_nine_cells_load(self) -> None:
        paths = sorted(CELLS.glob("*.json"))
        self.assertEqual(len(paths), 9)
        cells = [Cell.load(path) for path in paths]
        servers = {(c.quant, c.server) for c in cells}
        self.assertEqual(len(servers), 9)
        for cell in cells:
            self.assertTrue(cell.base_url.startswith("http://127.0.0.1:"))
            self.assertTrue(cell.base_url.endswith("/v1"))
            self.assertIn(cell.server, {"osaurus", "omlx", "optiq"})
            self.assertIn(cell.quant, {"jang_4m", "oq4_fp16", "optiq_4bit"})
            self.assertIsInstance(cell.start_command, tuple)
            self.assertTrue(all(isinstance(part, str) for part in cell.start_command))

    def test_campaign_lists_exactly_nine_cells(self) -> None:
        campaign = Campaign.load(ROOT / "config" / "matrix" / "gemma-4-12b-qat-campaign.json")
        self.assertEqual(campaign.campaign_id, "gemma-4-12b-qat-3x3")
        self.assertEqual(campaign.memory_floor_percent, 20)
        self.assertEqual(len(campaign.cell_paths), 9)
        self.assertEqual(campaign.ports, {"osaurus": 1337, "omlx": 8100, "optiq": 8080})

    def test_rejects_non_loopback_base_url(self) -> None:
        with self.assertRaises(MatrixError):
            Cell(
                cell_id="bad", quant="jang_4m", server="osaurus",
                base_url="http://10.0.0.1:1337/v1", model_id="x",
                artifact_path="/tmp/x", start_command=("true",), stop_command=(),
                health_path="/health", notes="",
            )


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

```zsh
cd /Users/jrazz/Dev/active/local-model-runtime-evaluation-harness
PYTHONPATH=src python3 -m unittest tests.test_matrix_config -v
```

Expected: FAIL with `ModuleNotFoundError: matrix_config` or missing config files.

- [ ] **Step 3: Add suite JSON, nine cells, campaign, and loader**

Create `suites/gemma-matrix-v1.json` by copying workloads from `suites/personal-selection-v1.json` with `"suite_id": "gemma-matrix-v1"`.

Create nine cells named `{quant}__{server}.json`. Example diagonal cells:

```json
{
  "cell_id": "jang_4m__osaurus",
  "quant": "jang_4m",
  "server": "osaurus",
  "base_url": "http://127.0.0.1:1337/v1",
  "model_id": "gemma-4-12b-it-qat-jang_4m",
  "artifact_path": "/Users/jrazz/MLXModels/OsaurusAI/gemma-4-12B-it-qat-JANG_4M",
  "start_command": ["osaurus", "serve", "--port", "1337", "--yes"],
  "stop_command": ["osaurus", "stop"],
  "health_path": "/health",
  "notes": "Native Osaurus JANG path. First chat may load the model."
}
```

```json
{
  "cell_id": "oq4_fp16__omlx",
  "quant": "oq4_fp16",
  "server": "omlx",
  "base_url": "http://127.0.0.1:8100/v1",
  "model_id": "gemma-4-12B-it-qat-oQ4-fp16",
  "artifact_path": "/Users/jrazz/.cache/huggingface/hub/models--avneetsb--gemma-4-12B-it-qat-oQ4-fp16",
  "start_command": ["omlX", "serve", "avneetsb/gemma-4-12B-it-qat-oQ4-fp16", "--host", "127.0.0.1", "--port", "8100"],
  "stop_command": [],
  "health_path": "/health",
  "notes": "Direct oMLX. Empty stop_command means lifecycle helper kills the spawned process group."
}
```

```json
{
  "cell_id": "optiq_4bit__optiq",
  "quant": "optiq_4bit",
  "server": "optiq",
  "base_url": "http://127.0.0.1:8080/v1",
  "model_id": "mlx-community/gemma-4-12B-it-qat-OptiQ-4bit",
  "artifact_path": "/Users/jrazz/.cache/huggingface/hub/models--mlx-community--gemma-4-12B-it-qat-OptiQ-4bit",
  "start_command": ["optiq", "serve", "--model", "mlx-community/gemma-4-12B-it-qat-OptiQ-4bit", "--host", "127.0.0.1", "--port", "8080", "--no-anthropic", "--no-responses"],
  "stop_command": [],
  "health_path": "/health",
  "notes": "Requires optiq on PATH. Empty stop_command → kill spawned process group."
}
```

For the six off-diagonal cells, still emit full JSON with the **target server's** start style and the **quant's** artifact/model_id. Example `jang_4m__omlx` uses oMLX start args but JANG artifact path — expect runtime `N/A` if unloadable. Do not omit cells.

Campaign:

```json
{
  "campaign_id": "gemma-4-12b-qat-3x3",
  "suite_path": "suites/gemma-matrix-v1.json",
  "results_root": "results/matrix",
  "memory_floor_percent": 20,
  "ready_timeout_seconds": 180,
  "request_timeout_seconds": 120,
  "on_cell_failure": "continue",
  "ports": {"osaurus": 1337, "omlx": 8100, "optiq": 8080},
  "cells": [
    "config/matrix/cells/jang_4m__osaurus.json",
    "config/matrix/cells/jang_4m__omlx.json",
    "config/matrix/cells/jang_4m__optiq.json",
    "config/matrix/cells/oq4_fp16__osaurus.json",
    "config/matrix/cells/oq4_fp16__omlx.json",
    "config/matrix/cells/oq4_fp16__optiq.json",
    "config/matrix/cells/optiq_4bit__osaurus.json",
    "config/matrix/cells/optiq_4bit__omlx.json",
    "config/matrix/cells/optiq_4bit__optiq.json"
  ]
}
```

Implement `matrix_config.py` with frozen dataclasses, exact field validation, loopback-only URL check, and path resolution relative to repo root.

- [ ] **Step 4: Run tests to verify they pass**

```zsh
PYTHONPATH=src python3 -m unittest tests.test_matrix_config -v
```

Expected: PASS.

- [ ] **Step 5: Commit (only if Jason approved Git in this session)**

```bash
git add suites/gemma-matrix-v1.json config/matrix src/local_model_runtime_evaluation/matrix_config.py tests/test_matrix_config.py
git commit -m "$(cat <<'EOF'
Add Gemma 3×3 matrix cell and campaign config loaders.

EOF
)"
```

---

### Task 2: Generic Process Lifecycle

**Files:**
- Create: `src/local_model_runtime_evaluation/matrix_lifecycle.py`
- Create: `tests/test_matrix_lifecycle.py`

**Interfaces:**
- Consumes: none from Task 1 beyond ports as ints
- Produces: `port_is_free(port: int) -> bool`
- Produces: `wait_port_free(port: int, timeout_seconds: float) -> None`
- Produces: `spawn_pinned(command: tuple[str, ...], log_path: Path) -> ManagedProcess`
- Produces: `ManagedProcess.stop(timeout_seconds: float = 15) -> None` (SIGTERM then SIGKILL process group)
- Produces: `run_stop_command(command: tuple[str, ...], timeout_seconds: float = 30) -> None`

- [ ] **Step 1: Write the failing lifecycle tests**

```python
# tests/test_matrix_lifecycle.py
from __future__ import annotations

import socket
import tempfile
import time
import unittest
from pathlib import Path

from local_model_runtime_evaluation.matrix_lifecycle import (
    LifecycleError,
    port_is_free,
    spawn_pinned,
    wait_port_free,
)


class MatrixLifecycleTests(unittest.TestCase):
    def test_spawn_and_stop_frees_port(self) -> None:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            probe.bind(("127.0.0.1", 0))
            port = probe.getsockname()[1]
        self.assertTrue(port_is_free(port))
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "server.log"
            code = (
                "import http.server, socketserver\n"
                f"httpd = socketserver.TCPServer(('127.0.0.1', {port}), http.server.BaseHTTPRequestHandler)\n"
                "httpd.handle_request()\n"
            )
            proc = spawn_pinned(("python3", "-c", code), log)
            deadline = time.time() + 5
            while time.time() < deadline and port_is_free(port):
                time.sleep(0.05)
            self.assertFalse(port_is_free(port))
            proc.stop()
            wait_port_free(port, timeout_seconds=5)
            self.assertTrue(port_is_free(port))

    def test_rejects_empty_command(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(LifecycleError):
                spawn_pinned((), Path(tmp) / "x.log")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

```zsh
PYTHONPATH=src python3 -m unittest tests.test_matrix_lifecycle -v
```

Expected: FAIL with `ModuleNotFoundError: matrix_lifecycle`.

- [ ] **Step 3: Implement minimal lifecycle helper**

```python
# src/local_model_runtime_evaluation/matrix_lifecycle.py
"""Pinned subprocess helpers for matrix server start/stop.

ponytail: thin wrapper over Popen + killpg; not Stage 2 OptiQLifecycleController.
"""

from __future__ import annotations

import os
import signal
import socket
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path


class LifecycleError(RuntimeError):
    code = "matrix_lifecycle_failed"


def port_is_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.settimeout(0.25)
        return probe.connect_ex(("127.0.0.1", port)) != 0


def wait_port_free(port: int, timeout_seconds: float) -> None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if port_is_free(port):
            return
        time.sleep(0.1)
    raise LifecycleError(f"port {port} did not free in time")


@dataclass
class ManagedProcess:
    pid: int
    process_group_id: int
    command: tuple[str, ...]
    _child: subprocess.Popen[bytes]

    def stop(self, timeout_seconds: float = 15) -> None:
        try:
            os.killpg(self.process_group_id, signal.SIGTERM)
        except ProcessLookupError:
            return
        try:
            self._child.wait(timeout=timeout_seconds)
            return
        except subprocess.TimeoutExpired:
            pass
        try:
            os.killpg(self.process_group_id, signal.SIGKILL)
        except ProcessLookupError:
            return
        self._child.wait(timeout=5)


def spawn_pinned(command: tuple[str, ...], log_path: Path) -> ManagedProcess:
    if not command:
        raise LifecycleError("start_command is empty")
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("ab") as log:
        child = subprocess.Popen(
            list(command),
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=log,
            start_new_session=True,
            close_fds=True,
        )
    return ManagedProcess(child.pid, child.pid, command, child)


def run_stop_command(command: tuple[str, ...], timeout_seconds: float = 30) -> None:
    if not command:
        return
    result = subprocess.run(
        list(command), capture_output=True, text=True, check=False, timeout=timeout_seconds,
    )
    if result.returncode != 0:
        raise LifecycleError(f"stop_command failed with code {result.returncode}")
```

- [ ] **Step 4: Run tests to verify they pass**

```zsh
PYTHONPATH=src python3 -m unittest tests.test_matrix_lifecycle -v
```

Expected: PASS.

- [ ] **Step 5: Commit (only if Jason approved Git)**

```bash
git add src/local_model_runtime_evaluation/matrix_lifecycle.py tests/test_matrix_lifecycle.py
git commit -m "$(cat <<'EOF'
Add pinned process lifecycle helpers for matrix servers.

EOF
)"
```

---

### Task 3: Server Adapters

**Files:**
- Create: `src/local_model_runtime_evaluation/matrix_servers.py`
- Create: `tests/test_matrix_servers.py`

**Interfaces:**
- Consumes: `Cell` from Task 1; `spawn_pinned` / `ManagedProcess` / `port_is_free` / `run_stop_command` / `wait_port_free` from Task 2
- Produces: `ServerHandle` with `start() -> None`, `wait_ready(model_id: str, timeout_seconds: float) -> None`, `stop() -> None`
- Produces: `build_server(cell, transport, log_dir, *, spawner=None, port_free=None) -> ServerHandle`
- Produces: `ServerError` (`code = "matrix_server_failed"`) for load/ready failures (caller maps to `N/A`)

Behavior:

- **oMLX / OptiQ:** `spawn_pinned(cell.start_command)`, poll `transport.list_models(cell.base_url, None)` until `model_id` present or timeout → `ServerError`.
- **Osaurus:** if port free, run `start_command`; if already up, skip spawn. Ready = model id in inventory (or accept first-request load after inventory lists the id). Stop uses `stop_command` when non-empty, else kill managed process.
- Campaign runner always stops the previous handle before the next cell so Osaurus cannot remain resident beside oMLX/OptiQ.

- [ ] **Step 1: Write the failing adapter tests with fakes**

```python
# tests/test_matrix_servers.py
from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock

from local_model_runtime_evaluation.matrix_config import Cell
from local_model_runtime_evaluation.matrix_servers import ServerError, build_server


def _cell(**overrides: object) -> Cell:
    data = dict(
        cell_id="oq4_fp16__omlx",
        quant="oq4_fp16",
        server="omlx",
        base_url="http://127.0.0.1:8100/v1",
        model_id="gemma-4-12B-it-qat-oQ4-fp16",
        artifact_path="/tmp/model",
        start_command=("true",),
        stop_command=(),
        health_path="/health",
        notes="",
    )
    data.update(overrides)
    return Cell(**data)  # type: ignore[arg-type]


class MatrixServerTests(unittest.TestCase):
    def test_ready_when_model_appears(self) -> None:
        transport = MagicMock()
        transport.list_models.side_effect = [
            (),
            ("gemma-4-12B-it-qat-oQ4-fp16",),
        ]
        with TemporaryDirectory() as tmp:
            handle = build_server(
                _cell(), transport, Path(tmp),
                spawner=lambda cmd, log: MagicMock(stop=MagicMock()),
                port_free=lambda port: True,
            )
            handle.start()
            handle.wait_ready("gemma-4-12B-it-qat-oQ4-fp16", timeout_seconds=2)
            handle.stop()

    def test_timeout_becomes_server_error(self) -> None:
        transport = MagicMock()
        transport.list_models.return_value = ()
        with TemporaryDirectory() as tmp:
            handle = build_server(
                _cell(), transport, Path(tmp),
                spawner=lambda cmd, log: MagicMock(stop=MagicMock()),
                port_free=lambda port: True,
            )
            handle.start()
            with self.assertRaises(ServerError):
                handle.wait_ready("missing", timeout_seconds=0.2)
            handle.stop()


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

```zsh
PYTHONPATH=src python3 -m unittest tests.test_matrix_servers -v
```

Expected: FAIL with `ModuleNotFoundError: matrix_servers`.

- [ ] **Step 3: Implement adapters**

One `SubprocessServerHandle` for all three servers. Optional injectable `spawner` / `port_free` for tests; defaults call `matrix_lifecycle`.

- [ ] **Step 4: Run tests to verify they pass**

```zsh
PYTHONPATH=src python3 -m unittest tests.test_matrix_servers -v
```

Expected: PASS.

- [ ] **Step 5: Commit (only if Jason approved Git)**

```bash
git add src/local_model_runtime_evaluation/matrix_servers.py tests/test_matrix_servers.py
git commit -m "$(cat <<'EOF'
Add matrix server start/ready/stop adapters with injectable fakes.

EOF
)"
```

---

### Task 4: Per-Cell Measurement

**Files:**
- Create: `src/local_model_runtime_evaluation/matrix_measure.py`
- Create: `tests/test_matrix_measure.py`

**Interfaces:**
- Consumes: `Cell`, suite loader, `LoopbackTransport`, `HostResourceProbe`
- Produces: `MODES = {"screen": {"warmup": 1, "measured": 3}, "finalist": {"warmup": 1, "measured": 5}}`
- Produces: `measure_cell(cell, suite, mode, transport, probe, cancel) -> CellResult`
- Produces: `CellResult` with `status: Literal["PASS","FAIL","N/A"]`, `na_reason: str | None`, observations, summary, memory before/after

Reuse `validate_response_contract` and mirror personal-selection `_run_one` / `summarize` (ponytail: prefer small duplication over a premature shared abstraction). Do **not** start/stop servers here.

Status rules:

- Missing model after ready → `N/A`
- Any measured transport or contract failure → cell `FAIL` (finish remaining requests in the cell unless cancel set)
- All measured succeed and contracts pass → `PASS`
- Warm-ups recorded but excluded from PASS/FAIL aggregates

- [ ] **Step 1: Write the failing measure tests**

Copy the `Handler` / `FakeProbe` pattern from `tests/test_personal_selection.py` (same SSE bodies and contract prompts). Key assertions:

```python
def test_screen_run_counts_twelve_posts(self) -> None:
    cell = Cell(
        cell_id="jang_4m__osaurus", quant="jang_4m", server="osaurus",
        base_url=self.base_url, model_id=Handler.model_id, artifact_path="/tmp",
        start_command=("true",), stop_command=(), health_path="/health", notes="",
    )
    result = measure_cell(
        cell,
        Suite.load(ROOT / "suites/gemma-matrix-v1.json"),
        "screen",
        LoopbackTransport({self.base_url}),
        FakeProbe([80, 79]),
        threading.Event(),
    )
    self.assertEqual(Handler.posts, 12)
    self.assertEqual(result.status, "PASS")
    self.assertEqual(result.summary["measured_count"], 9)
    self.assertEqual(result.summary["contract_pass_count"], 9)
    self.assertEqual(result.memory_free_percent_before, 80)
    self.assertEqual(result.memory_free_percent_after, 79)
```

- [ ] **Step 2: Run test to verify it fails**

```zsh
PYTHONPATH=src python3 -m unittest tests.test_matrix_measure -v
```

Expected: FAIL with `ModuleNotFoundError: matrix_measure`.

- [ ] **Step 3: Implement `measure_cell`**

Allow `probe=None` to skip memory sampling in unit tests (record `null`).

- [ ] **Step 4: Run tests to verify they pass**

```zsh
PYTHONPATH=src python3 -m unittest tests.test_matrix_measure -v
```

Expected: PASS.

- [ ] **Step 5: Commit (only if Jason approved Git)**

```bash
git add src/local_model_runtime_evaluation/matrix_measure.py tests/test_matrix_measure.py
git commit -m "$(cat <<'EOF'
Add per-cell matrix measurement on LoopbackTransport.

EOF
)"
```

---

### Task 5: Campaign Runner And 3×3 Report

**Files:**
- Create: `src/local_model_runtime_evaluation/matrix_runner.py`
- Create: `tests/test_matrix_runner.py`
- Modify: `.gitignore` (ensure `results/` is ignored if not already)

**Interfaces:**
- Consumes: `Campaign`, `build_server`, `measure_cell`, `HostResourceProbe`
- Produces: `run_campaign(campaign, mode, results_dir, *, cell_filter: tuple[str, ...] | None = None) -> Path`
- Produces: campaign bundle JSON + `report.md` with a Markdown 3×3 table

Campaign loop:

1. Load suite + cells.
2. For each cell (or filtered finalist ids):
   - Probe free memory; if `< memory_floor_percent`, stop the campaign.
   - Always stop the previous `ServerHandle` first.
   - `handle.start()` → `wait_ready` → on `ServerError`: record `N/A`, `handle.stop()`, continue when `on_cell_failure=continue`.
   - `measure_cell(...)` → record PASS/FAIL.
   - `handle.stop()`; verify subprocess-owned ports are free.
3. Write `results/matrix/<campaign_id>-<mode>-<stamp>/` with `raw.json` and `report.md`.

- [ ] **Step 1: Write the failing campaign tests**

```python
def test_na_then_pass_continues(self) -> None:
    campaign = MagicMock(
        campaign_id="test",
        memory_floor_percent=20,
        ready_timeout_seconds=1,
        request_timeout_seconds=5,
        on_cell_failure="continue",
        suite_path=ROOT / "suites/gemma-matrix-v1.json",
        cell_paths=[],
        ports={"osaurus": 1337, "omlx": 8100, "optiq": 8080},
    )
    cells = (
        Cell("a__osaurus", "jang_4m", "osaurus", "http://127.0.0.1:1337/v1",
             "m", "/tmp", ("true",), (), "/health", ""),
        Cell("b__omlx", "oq4_fp16", "omlx", "http://127.0.0.1:8100/v1",
             "m2", "/tmp", ("true",), (), "/health", ""),
    )
    na_handle = MagicMock()
    na_handle.wait_ready.side_effect = ServerError("unloadable")
    ok_handle = MagicMock()
    pass_result = MagicMock(
        status="PASS", na_reason=None, summary={"median_total_seconds": 1.5},
        cell_id="b__omlx", quant="oq4_fp16", server="omlx",
    )
    with TemporaryDirectory() as tmp:
        out = run_campaign(
            campaign, "screen", Path(tmp),
            cells=cells,
            build_server=MagicMock(side_effect=[na_handle, ok_handle]),
            measure_cell=MagicMock(return_value=pass_result),
            probe=FakeProbe([80, 80, 80]),
        )
        raw = json.loads((out / "raw.json").read_text())
        self.assertEqual(raw["cells"][0]["status"], "N/A")
        self.assertEqual(raw["cells"][1]["status"], "PASS")
        self.assertIn("N/A", (out / "report.md").read_text())
```

Wire `run_campaign` to accept these test doubles as optional kwargs; production callers omit them.

- [ ] **Step 2: Run test to verify it fails**

```zsh
PYTHONPATH=src python3 -m unittest tests.test_matrix_runner -v
```

Expected: FAIL with `ModuleNotFoundError: matrix_runner`.

- [ ] **Step 3: Implement runner + report**

Report table shape:

```markdown
| quant \\ server | osaurus | omlx | optiq |
|---|---|---|---|
| jang_4m | PASS 2.1s | N/A unloadable | FAIL |
```

Include median latency for timed cells; `N/A` shows a short reason.

- [ ] **Step 4: Run tests to verify they pass**

```zsh
PYTHONPATH=src python3 -m unittest tests.test_matrix_runner -v
```

Expected: PASS.

- [ ] **Step 5: Commit (only if Jason approved Git)**

```bash
git add src/local_model_runtime_evaluation/matrix_runner.py tests/test_matrix_runner.py .gitignore
git commit -m "$(cat <<'EOF'
Add matrix campaign runner with PASS/FAIL/N/A 3×3 report.

EOF
)"
```

---

### Task 6: CLI, Docs, And Full Non-Live Verification

**Files:**
- Create: `bin/lmre-matrix` (same PYTHONPATH pattern as `bin/lmre-personal-select`)
- Create: `docs/matrix.md`
- Modify: `README.md` (short “Gemma 3×3 matrix” pointer; do not rewrite Stage 2B narrative)
- Create: `tests/test_matrix_cli.py`

**Interfaces:**
- Produces: `matrix_runner.main(argv) -> int`
- Flags: `--mode screen|finalist`, `--campaign PATH`, `--cells id,id`, `--results-dir PATH`, `--dry-config`

- [ ] **Step 1: Write failing CLI test for `--dry-config`**

```python
def test_dry_config_prints_ok(self) -> None:
    code = main(["--dry-config", "--campaign", "config/matrix/gemma-4-12b-qat-campaign.json"])
    self.assertEqual(code, 0)
```

- [ ] **Step 2: Implement `main` + `bin/lmre-matrix`, make executable**

```zsh
PYTHONPATH=src python3 -m unittest tests.test_matrix_cli -v
chmod +x bin/lmre-matrix
```

- [ ] **Step 3: Write `docs/matrix.md`**

Cover: restore `optiq` on PATH; artifact paths; screen then finalist commands; safety rules; no live contact in unit tests; Stage 2B untouched.

- [ ] **Step 4: Run the full non-live suite**

```zsh
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

Expected: existing tests still PASS; new matrix tests PASS.

- [ ] **Step 5: Commit (only if Jason approved Git)**

```bash
git add bin/lmre-matrix docs/matrix.md README.md tests/test_matrix_cli.py
git commit -m "$(cat <<'EOF'
Expose lmre-matrix CLI and operator docs for the Gemma 3×3 campaign.

EOF
)"
```

---

## Out Of Scope (Next Plans)

1. **Live campaign execution** — needs Jason’s explicit live authorization after this plan is unit-green.
2. **Stage 2B-1 Gemma OptiQ retarget** — separate plan; surgical wall-clock/SSE only.
3. **Osaurus routing overhead add-on**
4. **Quality / judge / long RAG add-on**

## Spec Coverage Self-Check

| Spec requirement | Task |
|---|---|
| 9 cells, three artifacts, three direct servers | Task 1 |
| Attempt all 9, `N/A` unloadable | Tasks 3–5 |
| Automated start/stop with RAM floor + port verify | Tasks 2–3, 5 |
| Screen then finalist depths | Tasks 4–6 |
| Metrics + null TTFT when untrusted | Task 4 |
| 3×3 report under `results/matrix/` | Task 5 |
| Stage 2B frozen / no Gate B / no plugin change | Global constraints |
| Later Stage 2B-1 / overhead / quality | Out of scope section |

## Placeholder Scan

No TBD/TODO implementation steps. Commit steps remain gated on Jason’s Git approval.

## Type Consistency

- Stable names: `Cell`, `Campaign`, `ManagedProcess`, `ServerHandle`, `CellResult`, `run_campaign`, `main`.
- Ports fixed at `1337` / `8100` / `8080`.
