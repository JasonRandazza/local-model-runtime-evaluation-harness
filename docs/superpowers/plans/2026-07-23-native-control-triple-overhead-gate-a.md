# Native Control Triple + Four-Leg Overhead Gate A Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Retire cross-product matrix campaigns so each family schedules exactly three native cells (JANG/MXFP→Osaurus, oQ→oMLX, OptiQ→OptiQ), with fail-closed `native_server` enforcement, native-triple reports, and docs aligned to four-leg overhead — fake-only Gate A.

**Architecture:** Require `native_server` on every family quant. `Cell.validate_for_family` rejects any cell whose `server` ≠ that quant’s native server. `Campaign.load` loads cells and requires exactly one cell per family quant on the native server. Trim the three campaign JSONs to the native diagonal; keep historical cross-server cell JSON on disk unused. Rewrite `render_report` from a sparse 3×3 grid to a native-triple table. Overhead pair recipes already match; update operator docs only.

**Tech Stack:** Python 3 stdlib, `unittest`, existing matrix/overhead config under `config/matrix` and `config/overhead`. Prefer `/opt/homebrew/bin/python3` with `PYTHONPATH=src`.

## Global Constraints

- Spec: `docs/superpowers/specs/2026-07-23-native-control-triple-overhead-design.md`
- Fake-only Gate A: no live matrix/overhead runs, no Stage 2 POSTs/manifests, no provider edits, no plugin rebuild
- Do not delete historical cross-server cell JSON under `config/matrix/cells/`
- Do not rename `bin/lmre-matrix` (YAGNI)
- Do not commit `.harness-lifecycle/**`, `config/matrix/omlx-roots/**`, or secrets
- Prefer `/opt/homebrew/bin/python3` with `PYTHONPATH=src`

## Locked names

| Field | Value |
|---|---|
| Gemma cells | `jang_4m__osaurus`, `oq4_fp16__omlx`, `optiq_4bit__optiq` |
| Ornith cells | `ornith_jang_4m__osaurus`, `ornith_oq4__omlx`, `ornith_optiq_4bit__optiq` |
| Qwen cells | `qwen_mxfp4__osaurus`, `qwen_oq4__omlx`, `qwen_optiq_4bit__optiq` |
| Campaign ids | `gemma-4-12b-qat-native`, `ornith-35b-native`, `qwen36-35b-a3b-native` |
| Required family field | `native_server` ∈ `{osaurus, omlx, optiq}` |
| Optional family field | `role: "osaurus_native"` (only if `native_server == "osaurus"`) |
| Campaign cell count | exactly `3` |
| Overhead pairs (unchanged) | Gemma `oq4_fp16`+`optiq_4bit`; Ornith `ornith_oq4`+`ornith_optiq_4bit`; Qwen `qwen_oq4`+`qwen_optiq_4bit` |

## File map

| Area | Files |
|---|---|
| Loader | Modify `src/local_model_runtime_evaluation/matrix_config.py` |
| Families | Modify `config/matrix/families/gemma-4-12b-qat.json`, `ornith-35b.json`, `qwen36-35b-a3b.json` |
| Campaigns | Modify `config/matrix/gemma-4-12b-qat-campaign.json`, `ornith-35b-campaign.json`, `qwen36-35b-a3b-campaign.json` |
| Report/CLI | Modify `src/local_model_runtime_evaluation/matrix_runner.py` |
| Docs | Modify `docs/matrix.md`, `docs/overhead.md` (light alignment) |
| Tests | Modify `tests/test_matrix_config.py`, `tests/test_matrix_metrics.py`; touch other matrix tests only if campaign_id assertions break |

---

### Task 1: Require `native_server` and reject wrong-server cells

**Files:**
- Modify: `src/local_model_runtime_evaluation/matrix_config.py`
- Modify: `config/matrix/families/gemma-4-12b-qat.json`
- Modify: `config/matrix/families/ornith-35b.json`
- Modify: `config/matrix/families/qwen36-35b-a3b.json`
- Test: `tests/test_matrix_config.py`

**Interfaces:**
- Consumes: existing `FamilyQuant`, `_parse_family_quant`, `Cell.validate_for_family`, `ALLOWED_SERVERS`
- Produces: `FamilyQuant.native_server: str` (required); `validate_for_family` raises `MatrixError` when `cell.server != quant.native_server`

- [ ] **Step 1: Write failing native_server tests**

In `tests/test_matrix_config.py`, replace/extend role assertions and add:

```python
def test_gemma_family_native_servers(self) -> None:
    family = load_family("gemma-4-12b-qat")
    self.assertEqual(family.quants["jang_4m"].native_server, "osaurus")
    self.assertEqual(family.quants["oq4_fp16"].native_server, "omlx")
    self.assertEqual(family.quants["optiq_4bit"].native_server, "optiq")
    self.assertEqual(family.quants["jang_4m"].role, "osaurus_native")

def test_oq_quant_rejects_non_native_server(self) -> None:
    with self.assertRaises(MatrixError) as context:
        Cell.load(
            ROOT / "config/matrix/cells/oq4_fp16__optiq.json",
            family=GEMMA_FAMILY,
        )
    self.assertIn("native_server", str(context.exception))

def test_optiq_quant_rejects_non_native_server(self) -> None:
    with self.assertRaises(MatrixError) as context:
        Cell.load(
            ROOT / "config/matrix/cells/optiq_4bit__omlx.json",
            family=GEMMA_FAMILY,
        )
    self.assertIn("native_server", str(context.exception))

def test_osaurus_native_quant_rejects_non_osaurus_server(self) -> None:
    with self.assertRaises(MatrixError) as context:
        Cell.load(
            ROOT / "config/matrix/cells/jang_4m__optiq.json",
            family=GEMMA_FAMILY,
        )
    self.assertIn("native_server", str(context.exception))

def test_family_quant_rejects_missing_native_server(self) -> None:
    payload = {
        "family_id": "missing-native",
        "quants": {
            "jang_4m": {
                "artifact_path": "/tmp/x",
                "model_ids": ["x"],
            }
        },
    }
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "missing-native.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        with self.assertRaises(MatrixError):
            ModelFamily.load(path)

def test_family_quant_rejects_osaurus_native_role_on_non_osaurus(self) -> None:
    payload = {
        "family_id": "bad-role-native",
        "quants": {
            "oq4_fp16": {
                "role": "osaurus_native",
                "native_server": "omlx",
                "artifact_path": "/tmp/x",
                "model_ids": ["x"],
            }
        },
    }
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "bad-role-native.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        with self.assertRaises(MatrixError):
            ModelFamily.load(path)
```

Also update existing family artifact tests that assume `oq4`/`optiq` have `role is None` to still pass, and assert Ornith/Qwen `native_server` values in `test_load_ornith_family_by_id` / `test_load_qwen_family_by_id`:

```python
# ornith
self.assertEqual(family.quants["ornith_jang_4m"].native_server, "osaurus")
self.assertEqual(family.quants["ornith_oq4"].native_server, "omlx")
self.assertEqual(family.quants["ornith_optiq_4bit"].native_server, "optiq")

# qwen
self.assertEqual(family.quants["qwen_mxfp4"].native_server, "osaurus")
self.assertEqual(family.quants["qwen_oq4"].native_server, "omlx")
self.assertEqual(family.quants["qwen_optiq_4bit"].native_server, "optiq")
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/jrazz/Dev/active/local-model-runtime-evaluation-harness
PYTHONPATH=src /opt/homebrew/bin/python3 -m unittest \
  tests.FAKESECRET_s3t4u5v6w7x8y9z0a1b2 \
  tests.FAKESECRET_e1f2g3h4i5j6k7l8m9n0 \
  tests.FAKESECRET_s3t4u5v6w7x8y9z0a1b2 \
  tests.FAKESECRET_y3z4a5b6c7d8e9f0g1h2 \
  -v
```

Expected: FAIL (`native_server` missing / AttributeError / wrong message).

- [ ] **Step 3: Implement FamilyQuant.native_server + validation**

In `matrix_config.py`:

1. Change module docstring to mention native-control triple (drop “3×3” as the product claim).
2. Update constants:

```python
FAMILY_QUANT_REQUIRED_FIELDS = frozenset({"artifact_path", "model_ids", "native_server"})
FAMILY_QUANT_OPTIONAL_FIELDS = frozenset({"role"})
ALLOWED_QUANT_ROLES = frozenset({"osaurus_native"})
```

3. Extend dataclass:

```python
@dataclass(frozen=True)
class FamilyQuant:
    quant: str
    artifact_path: str
    model_ids: tuple[str, ...]
    native_server: str
    role: str | None = None
```

4. In `_parse_family_quant`, require `native_server` ∈ `ALLOWED_SERVERS`. If `role == "osaurus_native"`, require `native_server == "osaurus"`. Return `native_server=str(entry["native_server"])`.

5. Replace the `osaurus_native`-only branch in `Cell.validate_for_family` with:

```python
if self.server != quant.native_server:
    raise MatrixError(
        "cell server must match quant native_server "
        f"(got {self.quant!r} on {self.server!r}, "
        f"native_server={quant.native_server!r})"
    )
```

6. Patch family JSON files — add `"native_server"` to every quant:

| Family quant | `native_server` | keep `role`? |
|---|---|---|
| `jang_4m`, `ornith_jang_4m`, `qwen_mxfp4` | `osaurus` | yes `"osaurus_native"` |
| `oq4_fp16`, `ornith_oq4`, `qwen_oq4` | `omlx` | no |
| `optiq_4bit`, `ornith_optiq_4bit`, `qwen_optiq_4bit` | `optiq` | no |

- [ ] **Step 4: Run tests to verify they pass**

```bash
PYTHONPATH=src /opt/homebrew/bin/python3 -m unittest \
  tests.test_matrix_config.MatrixConfigTests.test_gemma_family_native_servers \
  tests.test_matrix_config.MatrixConfigTests.test_oq_quant_rejects_non_native_server \
  tests.test_matrix_config.MatrixConfigTests.test_optiq_quant_rejects_non_native_server \
  tests.test_matrix_config.MatrixConfigTests.test_osaurus_native_quant_rejects_non_osaurus_server \
  tests.test_matrix_config.MatrixConfigTests.test_family_quant_rejects_missing_native_server \
  tests.test_matrix_config.MatrixConfigTests.test_family_quant_rejects_osaurus_native_role_on_non_osaurus \
  tests.test_matrix_config.MatrixConfigTests.test_load_ornith_family_by_id \
  tests.test_matrix_config.MatrixConfigTests.test_load_qwen_family_by_id \
  -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add \
  src/local_model_runtime_evaluation/matrix_config.py \
  config/matrix/families/gemma-4-12b-qat.json \
  config/matrix/families/ornith-35b.json \
  config/matrix/families/qwen36-35b-a3b.json \
  tests/test_matrix_config.py
git commit -m "$(cat <<'EOF'
feat(matrix): require native_server on every family quant

Fail closed when a cell's server does not match the quant's only
capable native runtime (Osaurus / oMLX / OptiQ).
EOF
)"
```

---

### Task 2: Trim campaigns to the native diagonal + Campaign.load coverage

**Files:**
- Modify: `src/local_model_runtime_evaluation/matrix_config.py` (`Campaign.load`)
- Modify: `config/matrix/gemma-4-12b-qat-campaign.json`
- Modify: `config/matrix/ornith-35b-campaign.json`
- Modify: `config/matrix/qwen36-35b-a3b-campaign.json`
- Test: `tests/test_matrix_config.py`

**Interfaces:**
- Consumes: `Cell.load`, `ModelFamily.quants`, Task 1 `native_server`
- Produces: `Campaign.load` accepts only campaigns with exactly three unique cells covering every family quant on that quant’s native server; campaign ids renamed to `*-native`

- [ ] **Step 1: Write failing campaign-shape tests**

Replace the “nine/seven cells” tests with native-triple expectations:

```python
def test_gemma_native_campaign_loads_three_cells(self) -> None:
    campaign = Campaign.load(GEMMA_CAMPAIGN)
    self.assertEqual(campaign.campaign_id, "gemma-4-12b-qat-native")
    self.assertEqual(campaign.family_id, "gemma-4-12b-qat")
    self.assertEqual(len(campaign.cell_paths), 3)
    cells = [Cell.load(path, family=GEMMA_FAMILY) for path in campaign.cell_paths]
    self.assertEqual(
        {(c.quant, c.server) for c in cells},
        {
            ("jang_4m", "osaurus"),
            ("oq4_fp16", "omlx"),
            ("optiq_4bit", "optiq"),
        },
    )

def test_ornith_native_campaign_loads_three_cells(self) -> None:
    campaign = Campaign.load(ORNITH_CAMPAIGN)
    self.assertEqual(campaign.campaign_id, "ornith-35b-native")
    self.assertEqual(len(campaign.cell_paths), 3)
    cells = [Cell.load(path, family=ORNITH_FAMILY) for path in campaign.cell_paths]
    self.assertEqual(
        {(c.quant, c.server) for c in cells},
        {
            ("ornith_jang_4m", "osaurus"),
            ("ornith_oq4", "omlx"),
            ("ornith_optiq_4bit", "optiq"),
        },
    )

def test_qwen_native_campaign_loads_three_cells(self) -> None:
    campaign = Campaign.load(QWEN_CAMPAIGN)
    self.assertEqual(campaign.campaign_id, "qwen36-35b-a3b-native")
    self.assertEqual(len(campaign.cell_paths), 3)
    cells = [Cell.load(path, family=QWEN_FAMILY) for path in campaign.cell_paths]
    self.assertEqual(
        {(c.quant, c.server) for c in cells},
        {
            ("qwen_mxfp4", "osaurus"),
            ("qwen_oq4", "omlx"),
            ("qwen_optiq_4bit", "optiq"),
        },
    )

def test_campaign_rejects_wrong_cell_count(self) -> None:
    bad = {
        "campaign_id": "gemma-4-12b-qat-native",
        "family_id": "gemma-4-12b-qat",
        "suite_path": "suites/gemma-matrix-v1.json",
        "results_root": "results/matrix",
        "memory_floor_percent": 20,
        "ready_timeout_seconds": 180,
        "request_timeout_seconds": 120,
        "on_cell_failure": "continue",
        "ports": {"osaurus": 1337, "omlx": 8100, "optiq": 8080},
        "cells": [
            "config/matrix/cells/jang_4m__osaurus.json",
            "config/matrix/cells/oq4_fp16__omlx.json",
        ],
    }
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as handle:
        json.dump(bad, handle)
        path = Path(handle.name)
    try:
        with self.assertRaises(MatrixError) as context:
            Campaign.load(path)
        self.assertIn("exactly three", str(context.exception))
    finally:
        path.unlink(missing_ok=True)

def test_campaign_rejects_cross_server_cell(self) -> None:
    bad = {
        "campaign_id": "gemma-4-12b-qat-native",
        "family_id": "gemma-4-12b-qat",
        "suite_path": "suites/gemma-matrix-v1.json",
        "results_root": "results/matrix",
        "memory_floor_percent": 20,
        "ready_timeout_seconds": 180,
        "request_timeout_seconds": 120,
        "on_cell_failure": "continue",
        "ports": {"osaurus": 1337, "omlx": 8100, "optiq": 8080},
        "cells": [
            "config/matrix/cells/jang_4m__osaurus.json",
            "config/matrix/cells/oq4_fp16__osaurus.json",
            "config/matrix/cells/optiq_4bit__optiq.json",
        ],
    }
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as handle:
        json.dump(bad, handle)
        path = Path(handle.name)
    try:
        with self.assertRaises(MatrixError):
            Campaign.load(path)
    finally:
        path.unlink(missing_ok=True)
```

Remove or rewrite obsolete helpers named `test_all_nine_*` / `test_*_lists_exactly_nine_cells` / `test_gemma_campaign_loads_with_family_id` so they use the new campaign ids and counts. Update port-rejection fixtures that still list nine duplicate cell paths — two or three paths is enough for those tests (they fail on ports before cell coverage).

Also update `test_gemma_campaign_loads_with_family_id` campaign_id assertion to `gemma-4-12b-qat-native`.

- [ ] **Step 2: Run tests to verify they fail**

```bash
PYTHONPATH=src /opt/homebrew/bin/python3 -m unittest \
  tests.FAKESECRET_u3v4w5x6y7z8a9b0c1d2 \
  tests.FAKESECRET_i4j5k6l7m8n9o0p1q2r3 \
  tests.FAKESECRET_y1z2a3b4c5d6e7f8g9h0 \
  tests.FAKESECRET_e3f4g5h6i7j8k9l0m1n2 \
  tests.FAKESECRET_u2v3w4x5y6z7a8b9c0d1 \
  -v
```

Expected: FAIL (campaign still seven cells / old ids / count rule still `at most nine`).

- [ ] **Step 3: Trim campaign JSON + enforce coverage in Campaign.load**

1. Rewrite the three campaign files to:

**Gemma** (`config/matrix/gemma-4-12b-qat-campaign.json`):

```json
{
  "campaign_id": "gemma-4-12b-qat-native",
  "family_id": "gemma-4-12b-qat",
  "suite_path": "suites/gemma-matrix-v1.json",
  "results_root": "results/matrix",
  "memory_floor_percent": 20,
  "ready_timeout_seconds": 180,
  "request_timeout_seconds": 120,
  "on_cell_failure": "continue",
  "ports": {"osaurus": 1337, "omlx": 8100, "optiq": 8080},
  "cells": [
    "config/matrix/cells/jang_4m__osaurus.json",
    "config/matrix/cells/oq4_fp16__omlx.json",
    "config/matrix/cells/optiq_4bit__optiq.json"
  ]
}
```

**Ornith** — `campaign_id: "ornith-35b-native"`; cells:
`ornith_jang_4m__osaurus`, `ornith_oq4__omlx`, `ornith_optiq_4bit__optiq` (keep existing timeouts 300/180).

**Qwen** — `campaign_id: "qwen36-35b-a3b-native"`; cells:
`qwen_mxfp4__osaurus`, `qwen_oq4__omlx`, `qwen_optiq_4bit__optiq` (keep existing timeouts 300/180).

2. In `Campaign.load`, replace the `len(cells) > 9` check with:

```python
if len(cells) != 3:
    raise MatrixError("campaign must list exactly three native cells")
if len(set(cells)) != len(cells):
    raise MatrixError("campaign cell paths must be unique")
cell_paths = tuple(_resolve_repo_path(str(item)) for item in cells)
loaded = tuple(Cell.load(path, family=family) for path in cell_paths)
seen_quants = {cell.quant for cell in loaded}
if seen_quants != set(family.quants):
    raise MatrixError("campaign must include exactly one cell per family quant")
if len(family.quants) != 3:
    raise MatrixError("family must declare exactly three quants")
```

Keep storing `cell_paths` only (do not add a new Campaign field unless a later task needs it).

- [ ] **Step 4: Run tests to verify they pass**

```bash
PYTHONPATH=src /opt/homebrew/bin/python3 -m unittest tests.test_matrix_config -v
```

Expected: PASS for the whole module.

- [ ] **Step 5: Commit**

```bash
git add \
  src/local_model_runtime_evaluation/matrix_config.py \
  config/matrix/gemma-4-12b-qat-campaign.json \
  config/matrix/ornith-35b-campaign.json \
  config/matrix/qwen36-35b-a3b-campaign.json \
  tests/test_matrix_config.py
git commit -m "$(cat <<'EOF'
feat(matrix): schedule only the three native control cells

Campaigns become native diagonals with fail-closed coverage checks;
historical cross-server cell JSON stays on disk unused.
EOF
)"
```

---

### Task 3: Native-triple report + CLI copy

**Files:**
- Modify: `src/local_model_runtime_evaluation/matrix_runner.py`
- Test: `tests/test_matrix_metrics.py`

**Interfaces:**
- Consumes: `raw["cells"]` list with `quant`/`server`/`status`/`summary`
- Produces: `render_report` emits `## Native triple results` and metric tables with columns `| quant | native server | <value> |` (no sparse 3×3 server grid)

- [ ] **Step 1: Write failing report tests**

Update `tests/test_matrix_metrics.py`:

```python
def test_report_includes_metric_tables(self) -> None:
    raw = {
        "campaign_id": "gemma-4-12b-qat-native",
        "mode": "screen",
        "suite_id": "gemma-matrix-v1",
        "suite_revision": "1",
        "cells": [
            {
                "cell_id": "jang_4m__osaurus",
                "quant": "jang_4m",
                "server": "osaurus",
                "status": "PASS",
                "na_reason": None,
                "summary": {
                    "median_total_seconds": 2.16,
                    "median_ttft_seconds": 1.2,
                    "median_decode_tokens_per_second": None,
                    "median_estimated_decode_tokens_per_second": 18.5,
                    "measured_count": 9,
                    "success_count": 9,
                    "contract_pass_count": 9,
                },
            },
            {
                "cell_id": "optiq_4bit__optiq",
                "quant": "optiq_4bit",
                "server": "optiq",
                "status": "PASS",
                "na_reason": None,
                "summary": {
                    "median_total_seconds": 2.7,
                    "median_ttft_seconds": 0.5,
                    "median_decode_tokens_per_second": 40.0,
                    "median_estimated_decode_tokens_per_second": 42.0,
                    "measured_count": 9,
                    "success_count": 9,
                    "contract_pass_count": 9,
                },
            },
        ],
    }
    report = render_report(raw)
    self.assertIn("## Native triple results", report)
    self.assertNotIn("## 3×3 results", report)
    self.assertNotIn("| quant \\\\ server | osaurus | omlx | optiq |", report)
    self.assertIn("| quant | native server | result |", report)
    self.assertIn("| jang_4m | osaurus |", report)
    self.assertIn("## Metrics", report)
    self.assertIn("### Median TTFT", report)
    self.assertIn("| quant | native server |", report)
    self.assertIn("1.20s", report)
    self.assertIn("40.0", report)
    self.assertIn("18.5 est.", report)
    self.assertIn("9/9", report)

def test_report_quant_order_follows_campaign_cells(self) -> None:
    # keep the three-cell Qwen fixture; change campaign_id to *-native
    # assert row order and:
    self.assertIn("## Native triple results", report)
```

(Use the existing three-cell Qwen fixture body; only change `campaign_id` to `qwen36-35b-a3b-native` and add the native-triple header assertion.)

- [ ] **Step 2: Run tests to verify they fail**

```bash
PYTHONPATH=src /opt/homebrew/bin/python3 -m unittest \
  tests.test_matrix_metrics.MatrixMetricsTest.test_report_includes_metric_tables \
  tests.test_matrix_metrics.MatrixMetricsTest.test_report_quant_order_follows_campaign_cells \
  -v
```

Expected: FAIL (still `## 3×3 results` / old grid header).

- [ ] **Step 3: Rewrite render_report helpers**

In `matrix_runner.py`:

1. Update module docstring / argparse description away from “3×3” / “all nine”.
2. Change `--only` help from `default: all nine` to `default: all campaign cells`.
3. Replace status + metric table builders:

```python
def _format_status_cell(entry: dict[str, Any] | None) -> str:
    if entry is None:
        return "—"
    status = entry.get("status")
    if status == "N/A" and entry.get("na_reason"):
        return f"N/A ({entry['na_reason']})"
    return str(status or "—")


def _metric_table(
    by_key: dict[tuple[str, str], dict[str, Any]],
    *,
    title: str,
    key: str,
    kind: str,
    cells: Sequence[dict[str, Any]],
) -> list[str]:
    lines = [
        f"### {title}",
        "",
        "| quant | native server | value |",
        "|---|---|---|",
    ]
    for item in cells:
        quant = item["quant"]
        server = item["server"]
        value = _format_metric_cell(by_key.get((quant, server)), key=key, kind=kind)
        lines.append(f"| {quant} | {server} | {value} |")
    lines.append("")
    return lines


def render_report(raw: dict[str, Any]) -> str:
    cells = list(raw["cells"])
    by_key = {(item["quant"], item["server"]): item for item in cells}
    lines = [
        f"# Matrix campaign {raw['campaign_id']}",
        "",
        f"Mode: `{raw['mode']}`",
        f"Suite: `{raw['suite_id']}` revision `{raw['suite_revision']}`",
        "",
        "## Native triple results",
        "",
        "| quant | native server | result |",
        "|---|---|---|",
    ]
    for item in cells:
        lines.append(
            f"| {item['quant']} | {item['server']} | {_format_status_cell(item)} |"
        )
    if raw.get("stopped_early"):
        lines.extend(["", f"Campaign stopped early: `{raw.get('stop_reason')}`"])
    lines.extend([
        "",
        "## Metrics",
        "",
        "Option A decode tok/s requires incremental streaming and `EXACT_VISIBLE` token accounting. "
        "Option B estimated decode tok/s uses `completion_tokens / (total − TTFT)` when incremental "
        "timing exists (labeled `est.`). Incomparable cells show `—`.",
        "",
    ])
    for title, key, kind in (
        ("Median total latency", "median_total_seconds", "seconds"),
        ("Median TTFT", "median_ttft_seconds", "seconds"),
        ("Median decode tok/s (exact)", "median_decode_tokens_per_second", "toks"),
        ("Median decode tok/s (estimated)", "median_estimated_decode_tokens_per_second", "toks_est"),
        ("Contract passes / successes", "", "ratio"),
    ):
        lines.extend(_metric_table(by_key, title=title, key=key, kind=kind, cells=cells))
    return "\n".join(lines)
```

Remove now-unused `_quant_order` / `SERVER_ORDER` usages from the report path if nothing else needs them (keep symbols only if still referenced by runner helpers).

- [ ] **Step 4: Run tests to verify they pass**

```bash
PYTHONPATH=src /opt/homebrew/bin/python3 -m unittest tests.test_matrix_metrics -v
PYTHONPATH=src /opt/homebrew/bin/python3 -m unittest discover -s tests -name 'test_matrix_*' -v
```

Expected: PASS. If other matrix tests assert old campaign ids or “3×3” strings, update those assertions in this same task before commit.

- [ ] **Step 5: Commit**

```bash
git add \
  src/local_model_runtime_evaluation/matrix_runner.py \
  tests/test_matrix_metrics.py \
  tests/test_matrix_*.py
git commit -m "$(cat <<'EOF'
feat(matrix): report native triples instead of 3x3 grids

Status and metric tables list each quant on its native server only.
EOF
)"
```

---

### Task 4: Operator docs (matrix + overhead alignment)

**Files:**
- Modify: `docs/matrix.md`
- Modify: `docs/overhead.md`

**Interfaces:**
- Consumes: Task 2 campaign ids/cell lists; Task 3 report section name
- Produces: Docs describe native triple (3 cells) + four-leg overhead; no “must run nine/seven cells” / full 3×3 science claims

- [ ] **Step 1: Rewrite `docs/matrix.md` lead + campaign table**

Replace the title/lead with native-control framing. Required content (keep Keychain/oMLX/OptiQ prep sections intact aside from deleting cross-product N/A claims):

- Title: `# Multi-Family Native Control Triple`
- Lead: exactly three cells per family — each quant on its only capable native server; historical cross-server cell JSON may remain on disk but is not scheduled.
- Document required family field `native_server` and optional `role: "osaurus_native"` (must agree with `native_server: "osaurus"`).
- Campaign table rows: Gemma/Ornith/Qwen **native** (not 3×3); same campaign JSON paths.
- Live screen note: “three cells”, not seven/nine.
- Results: `report.md` has native-triple PASS/FAIL/N/A table (not 3×3).
- Delete the bullet that says full 3×3 still records MXFP-on-OptiQ evidence.

- [ ] **Step 2: Align `docs/overhead.md` wording**

Keep pair recipes unchanged. Edit only framing:

- Replace “Separate from `lmre-matrix` 3×3 science” with “Separate from `lmre-matrix` native control triple”.
- State explicitly: overhead is **four legs** (two pairs × direct/routed); no JANG/MXFP overhead pair.
- Confirm checked-in `config/overhead/family-pairs.json` still lists only oQ + OptiQ pairs for all three families (read-only verify; change only if a stale pair appears).

- [ ] **Step 3: Dry-config all three campaigns (non-live)**

```bash
./bin/lmre-matrix --dry-config --campaign config/matrix/gemma-4-12b-qat-campaign.json
./bin/lmre-matrix --dry-config --campaign config/matrix/ornith-35b-campaign.json
./bin/lmre-matrix --dry-config --campaign config/matrix/qwen36-35b-a3b-campaign.json
```

Expected: JSON with `cell_count: 3` and the locked native cell ids for each family. No process start.

- [ ] **Step 4: Full matrix unit suite**

```bash
PYTHONPATH=src /opt/homebrew/bin/python3 -m unittest discover -s tests -name 'test_matrix_*' -v
PYTHONPATH=src /opt/homebrew/bin/python3 -m unittest discover -s tests -name 'test_overhead*' -v
```

Expected: PASS; overhead suite unchanged aside from any incidental string expectations (update only if a test asserts “3×3”).

- [ ] **Step 5: Commit**

```bash
git add docs/matrix.md docs/overhead.md
git commit -m "$(cat <<'EOF'
docs: describe native control triple and four-leg overhead

Retire full cross-product matrix language; keep overhead pair recipes.
EOF
)"
```

---

## Spec coverage (self-review)

| Spec requirement | Task |
|---|---|
| Locked native map (3 families) | Task 1 family JSON + Task 2 campaigns |
| Required `native_server` + fail-closed Cell load | Task 1 |
| Campaign exactly three / one per quant | Task 2 |
| Historical cross-server JSON unused but retained | Task 2 (no deletes) |
| Report native triple not 3×3 | Task 3 |
| Docs stop claiming full 3×3; overhead four legs | Task 4 |
| Overhead recipes verify (docs-only unless stale) | Task 4 |
| Fake-only Gate A / dry-config OK | Task 4 Steps 3–4 |
| Out of scope: live runs, plugin, Stage 2, CLI rename | Global Constraints |

## Placeholder / consistency scan

- No TBD/TODO steps.
- Campaign ids consistently `*-native` across Tasks 2–4.
- Error substring `native_server` / `exactly three` match test assertions.
- Report header exactly `## Native triple results`.
