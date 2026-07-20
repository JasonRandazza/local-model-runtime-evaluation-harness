# Osaurus Routing Overhead Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `bin/lmre-overhead` to measure Osaurus router tax for oQ4 and OptiQ-4bit: direct native vs routed via `:1337`, reporting Δ median total latency (primary) and Δ median TTFT (secondary).

**Architecture:** Pair configs pin direct/backend cells and routed model ids. Runner starts only the backend cell for both legs; measures direct against native `base_url`, then routed against `http://127.0.0.1:1337/v1` with a synthetic measure `Cell` (`server=osaurus`). Report computes paired deltas. Harness never starts or configures Osaurus.

**Tech Stack:** Python 3 stdlib, existing matrix `Cell` / `measure_cell` / `build_server` / credentials, `unittest`.

## Global Constraints

- Spec: `docs/superpowers/specs/2026-07-20-osaurus-routing-overhead-design.md`
- Pairs only: `oq4_fp16`, `optiq_4bit` (not JANG)
- Hybrid lifecycle: harness starts/stops backend only; Jason owns Osaurus + providers
- Suite: `suites/gemma-matrix-v1.json`; mode depth: matrix `screen` (`warmup=1`, `measured=3`)
- Primary metric: Δ median total (routed − direct); secondary: Δ median TTFT
- Unit tests: fakes only; no live endpoints
- Do not implement Approach 2 (`lmre-matrix --mode overhead`), metrics pack C, Stage 2B, plugin, Ornith/Qwen, RAG, preference
- Only create git commits when the user explicitly asks

---

## File Structure

| File | Responsibility |
|------|----------------|
| `config/overhead/pairs/oq4_fp16.json` | Pair config for oQ4 |
| `config/overhead/pairs/optiq_4bit.json` | Pair config for OptiQ |
| `overhead_config.py` | Load/validate `OverheadPair`; build routed measure `Cell` |
| `overhead_runner.py` | Direct → routed orchestration; write `raw.json` |
| `overhead_report.py` | Δ total / Δ TTFT table → `report.md` |
| `overhead_cli.py` / `bin/lmre-overhead` | dry-config / run / report |
| `docs/overhead.md` | Operator guide + live checklist |
| `docs/matrix.md` / `docs/preference.md` | One-line pointers |
| `tests/test_overhead_*.py` | Fakes only |

---

### Task 1: Pair config + routed measure cell

**Files:**
- Create: `config/overhead/pairs/oq4_fp16.json`
- Create: `config/overhead/pairs/optiq_4bit.json`
- Create: `src/local_model_runtime_evaluation/overhead_config.py`
- Create: `tests/test_overhead_config.py`

**Interfaces:**
- Produces:
  - `class OverheadError(RuntimeError)`
  - `@dataclass(frozen=True) class OverheadPair` with fields:
    - `pair_id: str`
    - `direct_cell_id: str`
    - `backend_cell_id: str`
    - `routed_base_url: str`  # must be exactly `http://127.0.0.1:1337/v1`
    - `routed_model_id: str`
  - `OverheadPair.load(path: Path) -> OverheadPair`
  - `DEFAULT_PAIR_IDS: tuple[str, ...] = ("oq4_fp16", "optiq_4bit")`
  - `DEFAULT_PAIRS_ROOT = REPOSITORY_ROOT / "config" / "overhead" / "pairs"`
  - `make_routed_measure_cell(backend: Cell, pair: OverheadPair) -> Cell`
    - Returns a valid `Cell` with `server="osaurus"`, `base_url=pair.routed_base_url`,
      `model_id=pair.routed_model_id`, `quant=backend.quant`,
      `cell_id=f"{backend.quant}__osaurus"`, `artifact_path=backend.artifact_path`,
      `start_command=backend.start_command` (unused for spawn — lifecycle uses backend),
      `stop_command=()`, `health_path=backend.health_path`,
      `notes="overhead routed measure cell; do not spawn via this cell"`
  - Raise `OverheadError` on invalid pair JSON / wrong routed_base_url / empty routed_model_id

**Checked-in pair JSON (exact):**

`config/overhead/pairs/oq4_fp16.json`:
```json
{
  "pair_id": "oq4_fp16",
  "direct_cell_id": "oq4_fp16__omlx",
  "backend_cell_id": "oq4_fp16__omlx",
  "routed_base_url": "http://127.0.0.1:1337/v1",
  "routed_model_id": "omlx/gemma-4-12B-it-qat-oQ4-fp16"
}
```

`config/overhead/pairs/optiq_4bit.json`:
```json
{
  "pair_id": "optiq_4bit",
  "direct_cell_id": "optiq_4bit__optiq",
  "backend_cell_id": "optiq_4bit__optiq",
  "routed_base_url": "http://127.0.0.1:1337/v1",
  "routed_model_id": "mlx-community/gemma-4-12B-it-qat-OptiQ-4bit"
}
```

Note: `routed_model_id` must already be in `QUANT_CONTROL_ARTIFACTS[quant]["model_ids"]` so `Cell` validation passes. If Jason’s live inventory id differs, update the pair JSON (and allowlist if needed) before live run — do not invent ids at runtime.

- [ ] **Step 1: Write failing tests**

```python
def test_load_oq4_pair(self) -> None:
    pair = OverheadPair.load(ROOT / "config/overhead/pairs/oq4_fp16.json")
    self.assertEqual(pair.pair_id, "oq4_fp16")
    self.assertEqual(pair.routed_base_url, "http://127.0.0.1:1337/v1")
    self.assertEqual(pair.routed_model_id, "omlx/gemma-4-12B-it-qat-oQ4-fp16")

def test_reject_non_osaurus_routed_base_url(self) -> None:
    # temp JSON with routed_base_url http://127.0.0.1:8100/v1 → OverheadError

def test_make_routed_measure_cell_uses_osaurus_endpoint(self) -> None:
    backend = Cell.load(ROOT / "config/matrix/cells/oq4_fp16__omlx.json")
    pair = OverheadPair.load(ROOT / "config/overhead/pairs/oq4_fp16.json")
    routed = make_routed_measure_cell(backend, pair)
    self.assertEqual(routed.server, "osaurus")
    self.assertEqual(routed.base_url, "http://127.0.0.1:1337/v1")
    self.assertEqual(routed.model_id, pair.routed_model_id)
    self.assertEqual(routed.cell_id, "oq4_fp16__osaurus")
```

- [ ] **Step 2: Run — expect FAIL**

`PYTHONPATH=src python3 -m unittest tests.test_overhead_config -v`

- [ ] **Step 3: Implement config + pair JSON files**

Exact pair fields: `pair_id`, `direct_cell_id`, `backend_cell_id`, `routed_base_url`, `routed_model_id` (no extras). Require `pair_id` ∈ `DEFAULT_PAIR_IDS` when loading from default names (or at least that `direct_cell_id` / `backend_cell_id` are non-empty and `routed_base_url` is exactly `http://127.0.0.1:1337/v1`).

- [ ] **Step 4: Run — expect PASS**

- [ ] **Step 5: Commit only if user asked**

---

### Task 2: Runner + report deltas

**Files:**
- Create: `src/local_model_runtime_evaluation/overhead_runner.py`
- Create: `src/local_model_runtime_evaluation/overhead_report.py`
- Create: `tests/test_overhead_runner.py`
- Create: `tests/test_overhead_report.py`

**Interfaces:**
- Consumes: `OverheadPair`, `make_routed_measure_cell`, `Cell.load`, `MatrixSuite.load`, `build_server`, `measure_cell`, `resolve_credential` (from preference_collect), `port_is_free`, `HostResourceProbe`
- Produces:
  - `require_osaurus_listening(*, port_free) -> None` — raise `OverheadError` if port `1337` is free (Osaurus down)
  - `run_overhead(pair_ids, pairs_root, cells_root, suite_path, results_root, ...) -> Path`
  - `pair_deltas(direct_summary: dict, routed_summary: dict) -> dict` with keys:
    - `direct_median_total_seconds`, `routed_median_total_seconds`,
    - `delta_median_total_seconds` (routed − direct; `None` if either missing),
    - `direct_median_ttft_seconds`, `routed_median_ttft_seconds`,
    - `delta_median_ttft_seconds`
  - `render_overhead_report(raw: dict) -> str` / `write_report(run_dir) -> Path`

**Runner logic (per pair, serial):**

1. Load pair + `direct = Cell.load(.../direct_cell_id.json)` + `backend = Cell.load(.../backend_cell_id.json)`.
2. **Direct leg:** verify backend port free; `build_server(backend, ...)`; start; wait_ready; `measure_cell(direct, suite, "screen", ...)` with credential for `direct.server`; stop backend; verify backend port free. Record status/summary.
3. **Routed leg:** `require_osaurus_listening`; verify backend port free; start **backend** again; `routed = make_routed_measure_cell(backend, pair)`; `measure_cell(routed, suite, "screen", ...)` with credential for `"osaurus"`; stop **backend only**; verify backend port free. Never spawn Osaurus.
4. Append pair record to `raw.json` with both leg summaries + statuses.
5. After all pairs: write `report.md` via report helpers.

RAM floor: same pattern as preference/matrix — break before starting a leg if free memory ≤ floor (default `20`).

Fake tests: inject FakeHandle / FakeTransport / fake `port_free` / fake measure results — do not contact live servers.

- [ ] **Step 1: Write failing tests**

```python
def test_pair_deltas_primary_total(self) -> None:
    d = pair_deltas(
        {"median_total_seconds": 2.0, "median_ttft_seconds": 0.5},
        {"median_total_seconds": 2.5, "median_ttft_seconds": 0.8},
    )
    self.assertAlmostEqual(d["delta_median_total_seconds"], 0.5)
    self.assertAlmostEqual(d["delta_median_ttft_seconds"], 0.3)

def test_require_osaurus_listening_fails_when_port_free(self) -> None:
    with self.assertRaises(OverheadError):
        require_osaurus_listening(port_free=lambda port: True)

def test_run_overhead_writes_raw_and_report(self) -> None:
    # Fake build_server + measure returning PASS summaries; assert raw.json has
    # two pairs / four legs; report.md contains "Δ" or "delta" total column header
```

- [ ] **Step 2: Run — expect FAIL**

- [ ] **Step 3: Implement runner + report**

Report table columns (markdown):

`| Pair | Direct median total | Routed median total | Δ total | Δ TTFT | Direct status | Routed status |`

Include a short note: full equal-weight metric pack (incl. estimated decode tok/s) is a later expansion.

- [ ] **Step 4: Run — expect PASS** + Task 1 tests

- [ ] **Step 5: Commit only if user asked**

---

### Task 3: CLI + docs

**Files:**
- Create: `src/local_model_runtime_evaluation/overhead_cli.py`
- Create: `bin/lmre-overhead` (same PYTHONPATH bootstrap as `bin/lmre-rag`)
- Create: `docs/overhead.md`
- Create: `tests/test_overhead_cli.py`
- Modify: `docs/matrix.md` — one-line pointer to overhead
- Modify: `docs/preference.md` — replace stale “RAG not implemented” follow-on with pointer to rag.md + overhead.md; keep Osaurus overhead listed as implemented via overhead.md once this ships

**Interfaces:**
- Produces: `main(argv: Sequence[str] | None = None) -> int`
- Subcommands: `run`, `report`; global/`run` flag `--dry-config`
- Defaults:
  - pairs root: `config/overhead/pairs`
  - cells root: `config/matrix/cells`
  - suite: `suites/gemma-matrix-v1.json`
  - results: `results/overhead`
  - `--pairs` default `oq4_fp16,optiq_4bit`

Dry-config JSON must include: `ok`, `pairs`, `suite_id`, `mode` (`"screen"`), and per-pair `direct_cell_id` / `routed_model_id` / `routed_base_url`. No network.

Docs must include: hybrid lifecycle, prep checklist (Osaurus + providers + confirm routed ids), live authorize requirement, Approach 2 later option with pros/cons (copy from spec), metrics pack C later.

- [ ] **Step 1: Write failing tests**

```python
def test_dry_config_ok(self) -> None:
    # main(["run", "--dry-config"]) → ok true, pairs include oq4_fp16 and optiq_4bit

def test_report_missing_run_fails(self) -> None:
    # main(["report", "--run", "/nonexistent"]) → nonzero, ok false
```

- [ ] **Step 2: Run — expect FAIL**

- [ ] **Step 3: Implement CLI + docs + pointers**

- [ ] **Step 4: Full suite**

```bash
PYTHONPATH=src python3 -m unittest \
  tests.test_overhead_config tests.test_overhead_runner \
  tests.test_overhead_report tests.test_overhead_cli -v
```

- [ ] **Step 5: Commit only if user asked**

---

## Spec Coverage Check

| Spec item | Task |
|-----------|------|
| Two pairs oQ4 + OptiQ | 1 |
| Hybrid lifecycle; never start Osaurus | 2 |
| Screen suite + depth | 2 |
| Δ total primary, Δ TTFT secondary | 2 |
| `lmre-overhead` dry-config / run / report | 3 |
| Docs + live checklist | 3 |
| Approach 2 later + pros/cons | 3 (docs) |
| Metrics C later note | 2–3 |
| Fakes only; no Stage 2B | all |

---

## Execution Handoff

Plan complete. Proceeding awaits Jason’s execution choice (Subagent-Driven vs Inline).
