# Discovery MVP (Gate A) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship Gate A Discovery MVP: observe loopback + pinned artifacts, write an auditable proposal, and execute one ready family’s preference + RAG pipelines in-process — with fake-only tests and no live contact.

**Architecture:** Approach 2 thin orchestration. Match/propose observe servers via injectable transport; execute calls existing `run_collect` / `run_review` / `run_judge` / `run_tally` / `score_run` (or test doubles). No subprocess CLIs. No silent model copy/relocate. No provider edit.

**Tech Stack:** Python ≥3.11 stdlib, existing matrix/preference/RAG modules, `unittest`, `/opt/homebrew/bin/python3` with `PYTHONPATH=src`.

## Global Constraints

- Spec: `docs/superpowers/specs/2026-07-24-discovery-mvp-design.md`
- Parent vision: `docs/superpowers/specs/2026-07-24-harness-north-star-vision.md`
- Schema: `schema_version` = `"1.0.0"`; `confirm_policy` = `"explicit_execute"`
- Results root: `results/discovery/<proposal_id>/proposal.json` (+ `execution.json` on execute)
- Ports: `osaurus` 1337, `omlx` 8100, `optiq` 8080 (`matrix_config.SERVER_PORTS`)
- Suites on execute: preference (`suites/multi-family-preference-v1.json`) + RAG oracle + RAG keyword; **not** matrix measure
- Judge cell: first cell in the family’s preference recipe (Osaurus-native), never hard-code `jang_4m__osaurus` for non-Gemma
- One family per `execute`; partial native triples never executable
- Gate A: fakes only — no real loopback, Keychain, OptiQ/oMLX/Osaurus, Stage 2 IDs/manifests, plugin rebuild
- Never copy/move/relocate model weights; do **not** implement `place` in this plan
- Preference/RAG CLIs and sealed scoring semantics stay unchanged
- Only create git commits when the user explicitly asks
- PATH for CLI: `PATH="/Users/jrazz/.local/bin:/opt/homebrew/bin:$PATH"` when invoking `./bin/lmre-*`

---

## File Structure

| File | Responsibility |
|------|----------------|
| `src/local_model_runtime_evaluation/discovery_types.py` | `DiscoveryError`, proposal/execution dataclasses, content hash, proposal id allocation, JSON load/save |
| `src/local_model_runtime_evaluation/discovery_match.py` | Recipe agreement, artifact check, server health + identity match, `build_proposal` |
| `src/local_model_runtime_evaluation/discovery_execute.py` | Load/verify proposal; run preference then RAG oracle/keyword; write `execution.json`; stop on first failure |
| `src/local_model_runtime_evaluation/discovery_cli.py` | `lmre-discover` argparse: propose / show / execute / dry-config |
| `bin/lmre-discover` | PYTHONPATH wrapper like `bin/lmre-preference` |
| `docs/discovery.md` | Operator-facing Gate A docs |
| `docs/stage-discovery-gate-a.md` | Gate A checklist |
| `tests/test_discovery_types.py` | Hash + IO |
| `tests/test_discovery_match.py` | Ready / partial / recipe mismatch (fakes) |
| `tests/test_discovery_execute.py` | Pipeline order + stop-on-failure (injected fakes) |
| `tests/test_discovery_cli.py` | dry-config + propose/show/execute wiring with fakes |

Do **not** create: `place` command, auto-run policy, all-families execute, custom mixes, provider automation.

---

### Task 1: Proposal types, content hash, and disk IO

**Files:**
- Create: `src/local_model_runtime_evaluation/discovery_types.py`
- Create: `tests/test_discovery_types.py`

**Interfaces:**
- Produces:
  - `DISCOVERY_SCHEMA_VERSION = "1.0.0"`
  - `CONFIRM_POLICY_EXPLICIT = "explicit_execute"`
  - `class DiscoveryError(Exception)`
  - `DEFAULT_DISCOVERY_RESULTS_ROOT = REPOSITORY_ROOT / "results" / "discovery"`
  - `def proposal_content_hash(body: dict[str, object]) -> str` — SHA-256 hex of `json.dumps({k: v for k, v in sorted(body.items()) if k != "content_hash"}, sort_keys=True, separators=(",", ":"))`
  - `def allocate_proposal_id(results_root: Path, *, now: datetime | None = None) -> str` — `discovery-YYYYMMDD-NNN` where NNN is next unused 3-digit sequence for that date under `results_root`
  - `def write_proposal(results_root: Path, proposal: dict[str, object]) -> Path` — writes `results_root / proposal_id / proposal.json` with `content_hash` set; returns path
  - `def load_proposal(results_root: Path, proposal_id: str) -> dict[str, object]`
  - `def verify_proposal_hash(proposal: dict[str, object]) -> None` — raises `DiscoveryError` if missing/mismatch
  - `def write_execution(proposal_dir: Path, execution: dict[str, object]) -> Path`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_discovery_types.py
from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from local_model_runtime_evaluation.discovery_types import (
    DiscoveryError,
    allocate_proposal_id,
    load_proposal,
    proposal_content_hash,
    verify_proposal_hash,
    write_execution,
    write_proposal,
)


class DiscoveryTypesTests(unittest.TestCase):
    def test_content_hash_ignores_existing_hash_field(self) -> None:
        body = {
            "schema_version": "1.0.0",
            "proposal_id": "discovery-20260724-001",
            "content_hash": "should-be-ignored",
            "confirm_policy": "explicit_execute",
        }
        digest = proposal_content_hash(body)
        self.assertEqual(digest, proposal_content_hash({**body, "content_hash": "other"}))
        self.assertEqual(len(digest), 64)

    def test_write_load_and_verify_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            proposal = {
                "schema_version": "1.0.0",
                "proposal_id": "discovery-20260724-001",
                "created_at": "2026-07-24T00:00:00+00:00",
                "confirm_policy": "explicit_execute",
                "servers": {},
                "families": {},
                "executable_families": [],
            }
            path = write_proposal(root, proposal)
            self.assertEqual(path, root / "discovery-20260724-001" / "proposal.json")
            loaded = load_proposal(root, "discovery-20260724-001")
            self.assertIn("content_hash", loaded)
            verify_proposal_hash(loaded)
            loaded["executable_families"] = ["tampered"]
            with self.assertRaises(DiscoveryError):
                verify_proposal_hash(loaded)

    def test_allocate_proposal_id_increments(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            now = datetime(2026, 7, 24, tzinfo=timezone.utc)
            first = allocate_proposal_id(root, now=now)
            self.assertEqual(first, "discovery-20260724-001")
            (root / first).mkdir()
            second = allocate_proposal_id(root, now=now)
            self.assertEqual(second, "discovery-20260724-002")

    def test_write_execution(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            proposal_dir = Path(tmp) / "discovery-20260724-001"
            proposal_dir.mkdir()
            path = write_execution(proposal_dir, {"ok": False, "steps": []})
            self.assertEqual(path, proposal_dir / "execution.json")
            data = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(data["ok"], False)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `/opt/homebrew/bin/python3 -m unittest tests.test_discovery_types -v`  
Expected: FAIL (import / module not found)

- [ ] **Step 3: Implement `discovery_types.py`**

Implement the interfaces above. Use `REPOSITORY_ROOT = Path(__file__).resolve().parents[2]`. `write_proposal` must:

1. Require `proposal_id` key.
2. Set `content_hash` via `proposal_content_hash`.
3. `mkdir(parents=True, exist_ok=False)` for the proposal dir.
4. Write pretty JSON (`indent=2`, `sort_keys=True`) + trailing newline.

`load_proposal` raises `DiscoveryError` if file missing. `verify_proposal_hash` compares stored hash to recomputed hash.

- [ ] **Step 4: Run tests to verify they pass**

Run: `/opt/homebrew/bin/python3 -m unittest tests.test_discovery_types -v`  
Expected: PASS

- [ ] **Step 5: Commit only if Jason asks**

---

### Task 2: Match engine (artifact, reachability, identity)

**Files:**
- Create: `src/local_model_runtime_evaluation/discovery_match.py`
- Create: `tests/test_discovery_match.py`

**Interfaces:**
- Consumes: `discovery_types.DiscoveryError`, `DISCOVERY_SCHEMA_VERSION`, `CONFIRM_POLICY_EXPLICIT`; `matrix_config.SERVER_PORTS`, `Cell`, `load_family`; `preference_config.load_family_cell_recipes`; `rag_config.load_rag_family_cell_recipes`
- Produces:
  - `def native_base_url(server: str) -> str` → `f"http://127.0.0.1:{SERVER_PORTS[server]}/v1"`
  - `def require_agreeing_recipes(*, preference_recipes: dict[str, tuple[str, ...]], rag_recipes: dict[str, tuple[str, ...]]) -> dict[str, tuple[str, ...]]` — intersection of family ids; each shared family must have **identical** cell tuples; else `DiscoveryError`
  - `@dataclass(frozen=True) class ProbeTransport` protocol-ish: methods `health(self, base_url: str) -> dict[str, object]` and `list_models(self, base_url: str, credential: object | None) -> tuple[str, ...]` — use a `Protocol` named `DiscoveryTransport`
  - `def probe_servers(transport: DiscoveryTransport, servers: tuple[str, ...] = ("osaurus", "omlx", "optiq")) -> dict[str, dict[str, object]]`
  - `def match_family(*, family_id: str, cell_ids: tuple[str, ...], cells_root: Path, transport: DiscoveryTransport, server_probe: dict[str, dict[str, object]], credential_for: Callable[[str], object | None] | None = None, path_exists: Callable[[str], bool] | None = None) -> dict[str, object]` — returns family block `{ready, cells, suites}` where `suites` is always `["preference", "rag_oracle", "rag_keyword"]`
  - `def build_proposal(*, proposal_id: str, created_at: str, preference_recipes: dict[str, tuple[str, ...]], rag_recipes: dict[str, tuple[str, ...]], cells_root: Path, transport: DiscoveryTransport, credential_for: Callable[[str], object | None] | None = None, path_exists: Callable[[str], bool] | None = None) -> dict[str, object]` — no `content_hash` yet (writer adds it)

**Match rules (exact):**
1. For each cell: load `Cell` with `load_family(family_id)`.
2. `artifact_ok = path_exists(cell.artifact_path)` (default `Path(path).exists`).
3. Server entry from `server_probe[cell.server]`; `reachable = bool(entry.get("reachable"))`.
4. If not reachable → `identity_ok = False`, reason from probe.
5. If reachable → `list_models(native_base_url(cell.server), credential_for(cell.server) if credential_for else None)`; `identity_ok` if `cell.model_id in ids` **or** any `family.quants[cell.quant].model_ids` id is in `ids`. On transport error → `identity_ok = False`.
6. Cell ready iff `artifact_ok and reachable and identity_ok`.
7. Family `ready` iff all cells ready; `executable_families` = sorted ready family ids.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_discovery_match.py
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from local_model_runtime_evaluation.discovery_match import (
    build_proposal,
    match_family,
    probe_servers,
    require_agreeing_recipes,
)
from local_model_runtime_evaluation.discovery_types import DiscoveryError
from local_model_runtime_evaluation.matrix_config import REPOSITORY_ROOT, load_family


class FakeTransport:
    def __init__(
        self,
        *,
        health_ok: set[str] | None = None,
        models: dict[str, tuple[str, ...]] | None = None,
    ) -> None:
        self.health_ok = health_ok or set()
        self.models = models or {}

    def health(self, base_url: str) -> dict[str, object]:
        if base_url not in self.health_ok:
            raise RuntimeError("down")
        return {"status": "ok"}

    def list_models(self, base_url: str, credential: object | None) -> tuple[str, ...]:
        return self.models.get(base_url, ())


class DiscoveryMatchTests(unittest.TestCase):
    def test_recipe_disagreement_raises(self) -> None:
        with self.assertRaises(DiscoveryError):
            require_agreeing_recipes(
                preference_recipes={"gemma-4-12b-qat": ("a", "b", "c")},
                rag_recipes={"gemma-4-12b-qat": ("a", "b", "d")},
            )

    def test_partial_triple_not_ready(self) -> None:
        cells_root = REPOSITORY_ROOT / "config" / "matrix" / "cells"
        family_id = "gemma-4-12b-qat"
        cell_ids = (
            "jang_4m__osaurus",
            "oq4_fp16__omlx",
            "optiq_4bit__optiq",
        )
        family = load_family(family_id)
        # Only osaurus reachable; pretend all artifacts exist
        osaurus = f"http://127.0.0.1:1337/v1"
        transport = FakeTransport(
            health_ok={osaurus},
            models={osaurus: tuple(family.quants["jang_4m"].model_ids)},
        )
        probe = probe_servers(transport)
        result = match_family(
            family_id=family_id,
            cell_ids=cell_ids,
            cells_root=cells_root,
            transport=transport,
            server_probe=probe,
            path_exists=lambda _p: True,
        )
        self.assertFalse(result["ready"])
        self.assertFalse(result["cells"]["oq4_fp16__omlx"]["identity_ok"])
        self.assertFalse(result["cells"]["optiq_4bit__optiq"]["identity_ok"])

    def test_full_triple_ready_when_artifacts_and_ids_match(self) -> None:
        cells_root = REPOSITORY_ROOT / "config" / "matrix" / "cells"
        family_id = "gemma-4-12b-qat"
        cell_ids = (
            "jang_4m__osaurus",
            "oq4_fp16__omlx",
            "optiq_4bit__optiq",
        )
        family = load_family(family_id)
        urls = {
            "osaurus": "http://127.0.0.1:1337/v1",
            "omlx": "http://127.0.0.1:8100/v1",
            "optiq": "http://127.0.0.1:8080/v1",
        }
        models = {
            urls["osaurus"]: tuple(family.quants["jang_4m"].model_ids),
            urls["omlx"]: tuple(family.quants["oq4_fp16"].model_ids),
            urls["optiq"]: tuple(family.quants["optiq_4bit"].model_ids),
        }
        transport = FakeTransport(health_ok=set(urls.values()), models=models)
        probe = probe_servers(transport)
        result = match_family(
            family_id=family_id,
            cell_ids=cell_ids,
            cells_root=cells_root,
            transport=transport,
            server_probe=probe,
            path_exists=lambda _p: True,
        )
        self.assertTrue(result["ready"])

        preference = {family_id: cell_ids}
        proposal = build_proposal(
            proposal_id="discovery-20260724-001",
            created_at="2026-07-24T00:00:00+00:00",
            preference_recipes=preference,
            rag_recipes=preference,
            cells_root=cells_root,
            transport=transport,
            path_exists=lambda _p: True,
        )
        self.assertEqual(proposal["executable_families"], [family_id])
        self.assertEqual(proposal["confirm_policy"], "explicit_execute")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `/opt/homebrew/bin/python3 -m unittest tests.test_discovery_match -v`  
Expected: FAIL

- [ ] **Step 3: Implement `discovery_match.py`**

`probe_servers`: for each server, call `health(native_base_url(server))`; on any exception set `reachable: False` and `reason: str(error)`; on success set `reachable: True`, `port: SERVER_PORTS[server]`. Do not call `list_models` inside `probe_servers` (identity is per-cell in `match_family`).

Wrap `health`/`list_models` exceptions; never leak credentials into proposal JSON.

- [ ] **Step 4: Run tests to verify they pass**

Run: `/opt/homebrew/bin/python3 -m unittest tests.test_discovery_match -v`  
Expected: PASS

- [ ] **Step 5: Commit only if Jason asks**

---

### Task 3: Execute orchestration (injected suite runners)

**Files:**
- Create: `src/local_model_runtime_evaluation/discovery_execute.py`
- Create: `tests/test_discovery_execute.py`

**Interfaces:**
- Consumes: `load_proposal`, `verify_proposal_hash`, `write_execution`, `DiscoveryError`; preference/RAG configs for cell recipes
- Produces:
  - `@dataclass(frozen=True) class DiscoverySuiteHooks` with callables:
    - `run_preference(family_id: str, cell_ids: tuple[str, ...], judge_cell_id: str) -> Path`
    - `run_rag_oracle(family_id: str, cell_ids: tuple[str, ...]) -> Path`
    - `run_rag_keyword(family_id: str, cell_ids: tuple[str, ...]) -> Path`
  - `def default_suite_hooks(...) -> DiscoverySuiteHooks` — wires real library APIs (used by CLI live path later; Gate A tests inject fakes)
  - `def execute_proposal(*, results_root: Path, proposal_id: str, family_id: str, hooks: DiscoverySuiteHooks, preference_recipes: dict[str, tuple[str, ...]] | None = None) -> dict[str, object]`

**Execute rules (exact):**
1. `load_proposal` + `verify_proposal_hash`.
2. If `family_id` not in `proposal["executable_families"]` → `DiscoveryError`.
3. Resolve `cell_ids` from preference recipes for `family_id`; `judge_cell_id = cell_ids[0]`.
4. Steps in order: `preference`, `rag_oracle`, `rag_keyword`.
5. On success append `{step, status: "PASS", run_dir: str(path)}`.
6. On exception append `{step, status: "FAIL", error: str(exc)}`, set `ok: False`, **stop** (do not run later steps), write `execution.json`, re-raise or return failed payload (return failed payload; CLI maps to exit 1).
7. All PASS → `ok: True`, write `execution.json`.

`default_suite_hooks` implementation sketch (real wiring):

```python
def default_suite_hooks(
    *,
    preference_suite: Path,
    rag_suite: Path,
    rag_corpus: Path,
    cells_root: Path,
    preference_results: Path,
    rag_results: Path,
) -> DiscoverySuiteHooks:
    def run_preference(family_id: str, cell_ids: tuple[str, ...], judge_cell_id: str) -> Path:
        from local_model_runtime_evaluation.preference_collect import run_collect
        from local_model_runtime_evaluation.preference_config import PreferenceSuite
        from local_model_runtime_evaluation.preference_judge import run_judge
        from local_model_runtime_evaluation.preference_review import run_review
        from local_model_runtime_evaluation.preference_tally import run_tally

        run_dir = run_collect(
            cell_ids, preference_suite, cells_root, preference_results,
            family_id=family_id,
        )
        suite = PreferenceSuite.load(preference_suite)
        run_review(run_dir, seed=0, cell_ids=cell_ids, suite=suite)
        run_judge(
            run_dir,
            judge_cell_id=judge_cell_id,
            cells_root=cells_root,
            suite=suite,
            family_id=family_id,
        )
        run_tally(run_dir)
        return run_dir

    def run_rag(mode: str):
        def _inner(family_id: str, cell_ids: tuple[str, ...]) -> Path:
            from local_model_runtime_evaluation.rag_collect import run_collect
            from local_model_runtime_evaluation.rag_config import RagSuite
            from local_model_runtime_evaluation.rag_score import score_run

            run_dir = run_collect(
                cell_ids, rag_suite, rag_corpus, cells_root, rag_results,
                family_id=family_id, mode=mode,
            )
            score_run(run_dir, RagSuite.load(rag_suite))
            return run_dir
        return _inner

    return DiscoverySuiteHooks(
        run_preference=run_preference,
        run_rag_oracle=run_rag("oracle"),
        run_rag_keyword=run_rag("keyword"),
    )
```

(Adjust imports if `PreferenceSuite` / `RagSuite` live in different modules — use the same imports as `preference_cli` / `rag_cli`.)

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_discovery_execute.py
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from local_model_runtime_evaluation.discovery_execute import (
    DiscoverySuiteHooks,
    execute_proposal,
)
from local_model_runtime_evaluation.discovery_types import (
    DiscoveryError,
    write_proposal,
)


class DiscoveryExecuteTests(unittest.TestCase):
    def _proposal(self, root: Path, family_id: str = "gemma-4-12b-qat") -> str:
        proposal_id = "discovery-20260724-001"
        write_proposal(root, {
            "schema_version": "1.0.0",
            "proposal_id": proposal_id,
            "created_at": "2026-07-24T00:00:00+00:00",
            "confirm_policy": "explicit_execute",
            "servers": {},
            "families": {family_id: {"ready": True, "cells": {}, "suites": []}},
            "executable_families": [family_id],
        })
        return proposal_id

    def test_rejects_family_not_executable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            proposal_id = self._proposal(root)
            hooks = DiscoverySuiteHooks(
                run_preference=lambda *a, **k: Path("/nope"),
                run_rag_oracle=lambda *a, **k: Path("/nope"),
                run_rag_keyword=lambda *a, **k: Path("/nope"),
            )
            with self.assertRaises(DiscoveryError):
                execute_proposal(
                    results_root=root,
                    proposal_id=proposal_id,
                    family_id="ornith-35b",
                    hooks=hooks,
                    preference_recipes={"gemma-4-12b-qat": ("a", "b", "c")},
                )

    def test_stops_after_preference_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            proposal_id = self._proposal(root)
            calls: list[str] = []

            def fail_pref(family_id: str, cell_ids: tuple[str, ...], judge_cell_id: str) -> Path:
                calls.append("preference")
                raise RuntimeError("collect failed")

            def rag_ok(name: str):
                def _inner(family_id: str, cell_ids: tuple[str, ...]) -> Path:
                    calls.append(name)
                    return root / name
                return _inner

            hooks = DiscoverySuiteHooks(
                run_preference=fail_pref,
                run_rag_oracle=rag_ok("rag_oracle"),
                run_rag_keyword=rag_ok("rag_keyword"),
            )
            result = execute_proposal(
                results_root=root,
                proposal_id=proposal_id,
                family_id="gemma-4-12b-qat",
                hooks=hooks,
                preference_recipes={
                    "gemma-4-12b-qat": ("jang_4m__osaurus", "oq4_fp16__omlx", "optiq_4bit__optiq"),
                },
            )
            self.assertFalse(result["ok"])
            self.assertEqual(calls, ["preference"])
            self.assertEqual(result["steps"][0]["status"], "FAIL")
            execution = json.loads(
                (root / proposal_id / "execution.json").read_text(encoding="utf-8")
            )
            self.assertFalse(execution["ok"])

    def test_full_pipeline_order(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            proposal_id = self._proposal(root)
            calls: list[str] = []

            def pref(family_id: str, cell_ids: tuple[str, ...], judge_cell_id: str) -> Path:
                self.assertEqual(judge_cell_id, "jang_4m__osaurus")
                calls.append("preference")
                return root / "pref"

            def rag_ok(name: str):
                def _inner(family_id: str, cell_ids: tuple[str, ...]) -> Path:
                    calls.append(name)
                    return root / name
                return _inner

            hooks = DiscoverySuiteHooks(
                run_preference=pref,
                run_rag_oracle=rag_ok("rag_oracle"),
                run_rag_keyword=rag_ok("rag_keyword"),
            )
            result = execute_proposal(
                results_root=root,
                proposal_id=proposal_id,
                family_id="gemma-4-12b-qat",
                hooks=hooks,
                preference_recipes={
                    "gemma-4-12b-qat": ("jang_4m__osaurus", "oq4_fp16__omlx", "optiq_4bit__optiq"),
                },
            )
            self.assertTrue(result["ok"])
            self.assertEqual(calls, ["preference", "rag_oracle", "rag_keyword"])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `/opt/homebrew/bin/python3 -m unittest tests.test_discovery_execute -v`  
Expected: FAIL

- [ ] **Step 3: Implement `discovery_execute.py`**

Include `default_suite_hooks` wired to real APIs. Gate A unit tests must **not** call `default_suite_hooks` against live servers.

- [ ] **Step 4: Run tests to verify they pass**

Run: `/opt/homebrew/bin/python3 -m unittest tests.test_discovery_execute -v`  
Expected: PASS

- [ ] **Step 5: Commit only if Jason asks**

---

### Task 4: CLI + `bin/lmre-discover` + dry-config

**Files:**
- Create: `src/local_model_runtime_evaluation/discovery_cli.py`
- Create: `bin/lmre-discover`
- Create: `tests/test_discovery_cli.py`
- Modify: `pyproject.toml` — add `lmre-discover = "local_model_runtime_evaluation.discovery_cli:main"` under `[project.scripts]`

**Interfaces:**
- Produces: `def main(argv: Sequence[str] | None = None) -> int`
- Commands:
  - `propose` (default if no subcommand): build proposal via `build_proposal` + `allocate_proposal_id` + `write_proposal`; print JSON summary `{ok, proposal_id, executable_families, path}`
  - `show <proposal_id>`: load + verify hash; print proposal JSON
  - `execute <proposal_id> --family <family_id>`: `execute_proposal` with `default_suite_hooks` unless tests inject hooks via optional internal kwargs / env not required — **tests call library functions directly**; CLI execute uses defaults
  - `dry-config`: load agreeing recipes; for each family load cells with `load_family`; print `{ok, families, cells}` **without** transport/network

For Gate A CLI tests of `propose`, pass a fake transport by extracting `cmd_propose(..., transport=...)` helpers, or test `build_proposal`/`write_proposal` in match tests and only assert `dry-config` + argparse dispatch in CLI tests.

Recommended split:
- `discovery_cli.py` exposes `_cmd_dry_config`, `_cmd_propose`, `_cmd_show`, `_cmd_execute` taking explicit deps where needed.
- CLI propose constructs `LoopbackTransport` over the three base URLs only when not injected — unit tests always inject `FakeTransport`.

- [ ] **Step 1: Write the failing CLI tests**

Do **not** add a `--transport fake` CLI flag. Export helpers `_cmd_dry_config`, `_cmd_propose`, `_cmd_show`, `_cmd_execute` for injection.

```python
# tests/test_discovery_cli.py
from __future__ import annotations

import json
import tempfile
import unittest
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from local_model_runtime_evaluation.discovery_cli import (
    _cmd_execute,
    _cmd_propose,
    _cmd_show,
    main,
)
from local_model_runtime_evaluation.discovery_execute import DiscoverySuiteHooks
from local_model_runtime_evaluation.discovery_types import DiscoveryError, load_proposal
from local_model_runtime_evaluation.matrix_config import load_family


class FakeTransport:
    def __init__(self) -> None:
        family = load_family("gemma-4-12b-qat")
        self.urls = {
            "osaurus": "http://127.0.0.1:1337/v1",
            "omlx": "http://127.0.0.1:8100/v1",
            "optiq": "http://127.0.0.1:8080/v1",
        }
        self.models = {
            self.urls["osaurus"]: tuple(family.quants["jang_4m"].model_ids),
            self.urls["omlx"]: tuple(family.quants["oq4_fp16"].model_ids),
            self.urls["optiq"]: tuple(family.quants["optiq_4bit"].model_ids),
        }

    def health(self, base_url: str) -> dict[str, object]:
        return {"status": "ok"}

    def list_models(self, base_url: str, credential: object | None) -> tuple[str, ...]:
        return self.models[base_url]


class DiscoveryCliTests(unittest.TestCase):
    def test_dry_config_ok_no_network(self) -> None:
        buf = StringIO()
        with patch("sys.stdout", buf):
            code = main(["dry-config"])
        self.assertEqual(code, 0)
        payload = json.loads(buf.getvalue())
        self.assertTrue(payload["ok"])
        self.assertIn("gemma-4-12b-qat", payload["families"])

    def test_propose_show_execute_with_fakes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cells = (
                "jang_4m__osaurus",
                "oq4_fp16__omlx",
                "optiq_4bit__optiq",
            )
            summary = _cmd_propose(
                results_root=root,
                transport=FakeTransport(),
                path_exists=lambda _p: True,
                preference_recipes={"gemma-4-12b-qat": cells},
                rag_recipes={"gemma-4-12b-qat": cells},
            )
            self.assertTrue(summary["ok"])
            self.assertIn("gemma-4-12b-qat", summary["executable_families"])
            proposal_id = summary["proposal_id"]
            shown = _cmd_show(results_root=root, proposal_id=proposal_id)
            self.assertEqual(shown["proposal_id"], proposal_id)

            hooks = DiscoverySuiteHooks(
                run_preference=lambda family_id, cell_ids, judge_cell_id: root / "pref",
                run_rag_oracle=lambda family_id, cell_ids: root / "oracle",
                run_rag_keyword=lambda family_id, cell_ids: root / "keyword",
            )
            execution = _cmd_execute(
                results_root=root,
                proposal_id=proposal_id,
                family_id="gemma-4-12b-qat",
                hooks=hooks,
                preference_recipes={"gemma-4-12b-qat": cells},
            )
            self.assertTrue(execution["ok"])
            with self.assertRaises(DiscoveryError):
                _cmd_execute(
                    results_root=root,
                    proposal_id=proposal_id,
                    family_id="ornith-35b",
                    hooks=hooks,
                    preference_recipes={"gemma-4-12b-qat": cells},
                )
            loaded = load_proposal(root, proposal_id)
            self.assertEqual(loaded["schema_version"], "1.0.0")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `/opt/homebrew/bin/python3 -m unittest tests.test_discovery_cli -v`  
Expected: FAIL

- [ ] **Step 3: Implement CLI + bin wrapper**

`bin/lmre-discover` — copy pattern from `bin/lmre-preference`:

```python
#!/usr/bin/env python3
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
source = str(ROOT / "src")
existing = os.environ.get("PYTHONPATH")
os.environ["PYTHONPATH"] = source if not existing else f"{source}{os.pathsep}{existing}"
sys.path.insert(0, source)

from local_model_runtime_evaluation.discovery_cli import main

if __name__ == "__main__":
    raise SystemExit(main())
```

`chmod +x bin/lmre-discover`.

Defaults for paths:
- preference suite: `suites/multi-family-preference-v1.json`
- rag suite / corpus: same defaults as `rag_cli.py`
- cells root: `config/matrix/cells`
- results: `results/discovery`

- [ ] **Step 4: Run discovery + related unit tests**

Run:

```bash
cd /Users/jrazz/Dev/active/local-model-runtime-evaluation-harness
PYTHONPATH=src /opt/homebrew/bin/python3 -m unittest \
  tests.test_discovery_types \
  tests.test_discovery_match \
  tests.test_discovery_execute \
  tests.test_discovery_cli -v
```

Expected: PASS

Also run a quick smoke:

```bash
./bin/lmre-discover dry-config
```

Expected: JSON with `"ok": true` (no network beyond what dry-config forbids — dry-config must not open sockets).

- [ ] **Step 5: Commit only if Jason asks**

---

### Task 5: Docs + Gate A checklist + design status

**Files:**
- Create: `docs/discovery.md`
- Create: `docs/stage-discovery-gate-a.md`
- Modify: `docs/superpowers/specs/2026-07-24-discovery-mvp-design.md` — set **Status:** `APPROVED (Jason, 2026-07-24)` 
- Modify: `docs/superpowers/specs/2026-07-24-harness-north-star-vision.md` — point Next slice to this plan + design
- Modify: `README.md` — one short bullet under tools/CLIs for `lmre-discover` (Gate A / non-live)

**`docs/stage-discovery-gate-a.md` must include:**
- Decision line placeholder: `GATE_A_PENDING` until Jason accepts after tests
- Fake-only verification commands (the unittest block above)
- Explicit non-goals: no live propose, no `place`, no Stage 2, no provider edit, no silent model copy
- Exit criteria: all discovery unit tests PASS; `dry-config` works; design APPROVED

**`docs/discovery.md` must include:**
- Propose → show → execute flow
- Fail-closed partial triples
- Judge cell = first recipe cell
- Model placement: discovery never copies; gaps are reported only
- Live execute requires separate authorization after Gate A

- [ ] **Step 1: Write the docs listed above**
- [ ] **Step 2: Re-run discovery unit tests once** (sanity after doc-only changes — should still PASS)
- [ ] **Step 3: Commit only if Jason asks**

---

## Spec coverage self-check

| Spec section | Task |
|---|---|
| §1 Goals (propose/execute, one family, Gate A) | 2–5 |
| §2 Approach 2 in-process | 3 (`default_suite_hooks`) |
| §3 Match rules | 2 |
| §4 Proposal schema + hash | 1 |
| §5 CLI commands | 4 |
| §6 Execute pipeline + judge cell | 3 |
| §7 No silent place; place deferred | Global Constraints + Task 5 docs (not implemented) |
| §8 Gate A fake boundaries | All test tasks |
| §9 Deferred tracks | Task 5 docs only |
| §10 Touch list | File Structure |

## Out of scope reminder (do not implement)

- `lmre-discover place`
- `confirm_policy: auto_when_ready`
- All-ready-families execute toggle
- Custom any-3 mixes
- Osaurus provider CLI automation
- Live authorize / live propose-execute
- Matrix measure in default execute
- Plugin changes

---

## Execution handoff

Plan complete and saved to `docs/superpowers/plans/2026-07-24-discovery-mvp-gate-a.md`.

**Two execution options:**

1. **Subagent-Driven (recommended)** — fresh subagent per task, review between tasks  
2. **Inline Execution** — execute tasks in this session with checkpoints  

Which approach?
