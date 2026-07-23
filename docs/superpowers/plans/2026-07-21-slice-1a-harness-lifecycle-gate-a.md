# Slice 1a Shared Server Lifecycle Controller Gate A Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement Package 1 / Slice 1a only: a shared harness-owned lifecycle controller that can start and stop exactly one pinned OptiQ (`8080`), oMLX (`8100`), or Osaurus (`1337`) server at a time under a 20% RAM floor, with fail-closed ownership rules and fake-only tests — without OptiQ `0.4.2` pin bump (1b), Stage 2 unattended wiring (1c), live Gate B, run IDs, or disk upgrades.

**Architecture:** Extract a small shared API that reuses `matrix_lifecycle.spawn_pinned` / `ManagedProcess` / port helpers and the ownership patterns from `matrix_servers.SubprocessServerHandle`, without migrating matrix/preference runners in this slice. Stage 2 and Package 2 will consume this module later. No live subprocess spawns in Gate A tests — inject fakes for spawner, port probes, memory, Lab detection, and ready checks.

**Tech Stack:** Python 3 stdlib, `unittest` via `PYTHONPATH=src /opt/homebrew/bin/python3 -m unittest …`, existing `HostResourceProbe` / matrix lifecycle helpers. Plugin `0.3.0` unchanged.

## Global Constraints

- Spec: `docs/superpowers/specs/2026-07-21-stack-review-gate-a-queue-design.md` (Slice 1a section)
- Do **not** implement slices 1b/1c or Package 2 in this plan.
- Do **not** run Gate B, create run IDs/manifests, upgrade OptiQ/oMLX on disk, contact live servers for POSTs, or rebuild plugin `0.3.0`.
- Do **not** migrate `matrix_runner` / preference / overhead onto the new module yet (reuse patterns only).
- Prefer `/opt/homebrew/bin/python3` for tests.
- No commits of `config/matrix/omlx-roots/**`.
- Preserve green Stage 0/1/2 and matrix test suites.

## File map

| Area | Files |
|---|---|
| Types / pin | Create `src/local_model_runtime_evaluation/harness_lifecycle.py` |
| Tests | Create `tests/test_harness_lifecycle.py` |
| Docs | Short note in `docs/architecture.md` + pointer from stack-review spec “implementation status” only if needed; do **not** rewrite AGENTS Stage 2 “never start OptiQ” until slice 1c |

---

### Task 1: Server pin types + action counter

**Files:**
- Create: `src/local_model_runtime_evaluation/harness_lifecycle.py`
- Create: `tests/test_harness_lifecycle.py`

**Interfaces:**
- `ServerKind = Literal["optiq", "omlx", "osaurus"]`
- `@dataclass(frozen=True) class ServerPin: kind: ServerKind; port: int; start_command: tuple[str, ...]; stop_command: tuple[str, ...] = (); ready_model_id: str = ""`
- `DEFAULT_MEMORY_FLOOR_PERCENT = 20`
- `PORT_BY_KIND = {"optiq": 8080, "omlx": 8100, "osaurus": 1337}`
- `class HarnessLifecycleError(RuntimeError):` with `.code: str`
- `class LifecycleController:` (skeleton only this task) holding `lifecycle_actions: int` starting at `0`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_harness_lifecycle.py
class HarnessLifecyclePinTest(unittest.TestCase):
    def test_port_by_kind_matches_spec(self) -> None:
        self.assertEqual(PORT_BY_KIND["optiq"], 8080)
        self.assertEqual(PORT_BY_KIND["omlx"], 8100)
        self.assertEqual(PORT_BY_KIND["osaurus"], 1337)

    def test_server_pin_rejects_port_mismatch(self) -> None:
        with self.assertRaises(HarnessLifecycleError) as ctx:
            ServerPin(kind="optiq", port=9999, start_command=("optiq", "serve"))
        self.assertEqual(ctx.exception.code, "port_mismatch")
```

- [ ] **Step 2: Run — expect FAIL (module missing)**

```bash
PYTHONPATH=src /opt/homebrew/bin/python3 -m unittest tests.test_harness_lifecycle -v
```

- [ ] **Step 3: Implement pin validation + empty controller shell**

`ServerPin.__post_init__` (or factory `ServerPin.create`) requires `port == PORT_BY_KIND[kind]`.

- [ ] **Step 4: Re-run — expect PASS**

- [ ] **Step 5: Commit**

```bash
git add src/local_model_runtime_evaluation/harness_lifecycle.py tests/test_harness_lifecycle.py
git commit -m "$(cat <<'EOF'
Add harness lifecycle pin types for shared server control.

EOF
)"
```

---

### Task 2: Preflight gates (RAM, port, Lab, double-start)

**Files:**
- Modify: `src/local_model_runtime_evaluation/harness_lifecycle.py`
- Modify: `tests/test_harness_lifecycle.py`

**Interfaces:**
- `LifecycleController.__init__(self, *, memory_floor_percent: int = 20, free_memory: Callable[[], float], port_free: Callable[[int], bool], lab_closed: Callable[[], bool], spawner, stop_runner, wait_ready: Callable[[ServerPin, ManagedProcess | None], None] | None = None)`
- `start(self, pin: ServerPin) -> None` — increments `lifecycle_actions` by 1 on successful owned spawn (or 0 on observe-only Osaurus attach — document: observe-only does **not** count as a start action; stop of owned process counts +1)
- Exact error codes: `memory_floor`, `port_busy`, `lab_open`, `already_started`, `not_owned`

Suggested counting rule (lock in tests):
- Owned spawn success → `lifecycle_actions += 1`
- Owned stop success → `lifecycle_actions += 1`
- Observe-only Osaurus attach → no increment
- Failed preflight → no increment

- [ ] **Step 1: Write failing tests**

Minimum cases:
1. `free_memory < 20` → `HarnessLifecycleError(code="memory_floor")`, actions stay 0
2. Non-osaurus port busy → `port_busy`, actions 0
3. `lab_closed() is False` when starting optiq → `lab_open`, actions 0
4. Second `start` while already started → `already_started`
5. Happy path with fake spawner: port free, memory 50%, lab closed → owned process recorded, actions == 1

- [ ] **Step 2: Run — expect FAIL**

- [ ] **Step 3: Implement `start` preflight + spawn**

Reuse `spawn_pinned` as default spawner. Do not call real OptiQ/oMLX in tests.

OptiQ Lab check: inject `lab_closed` callable (Gate A fake). Real implementation helper may stub as “always True” behind a named function `default_lab_closed()` that documents “slice 1c / live wiring will probe Lab”; Gate A must not require a live Lab probe.

- [ ] **Step 4: Re-run — expect PASS**

- [ ] **Step 5: Commit**

```bash
git commit -m "$(cat <<'EOF'
Gate harness lifecycle start behind RAM, port, and Lab checks.

EOF
)"
```

---

### Task 3: Osaurus observe-only + oMLX busy handling

**Files:**
- Modify: `harness_lifecycle.py`
- Modify: `tests/test_harness_lifecycle.py`

**Interfaces:**
- Osaurus: if port free → spawn owned; if port busy → attach observe-only (`owned=False`), do not spawn, do not run stop later
- oMLX: if port busy → run `stop_command` or default `("omlX", "stop")` via injected `stop_runner`, wait until port free (inject `wait_port_free`), then spawn owned
- OptiQ: if port busy → always `port_busy` (never steal Lab/foreign serve)

- [ ] **Step 1: Write failing tests** for the three behaviors above

- [ ] **Step 2: Run — expect FAIL**

- [ ] **Step 3: Implement** mirroring `SubprocessServerHandle.start` branches

- [ ] **Step 4: Re-run — expect PASS**

- [ ] **Step 5: Commit**

```bash
git commit -m "$(cat <<'EOF'
Handle Osaurus observe-only and oMLX port reclaim in harness lifecycle.

EOF
)"
```

---

### Task 4: Stop ownership + port-free verification

**Files:**
- Modify: `harness_lifecycle.py`
- Modify: `tests/test_harness_lifecycle.py`

**Interfaces:**
- `stop(self) -> None`
- If nothing started → no-op or `not_started` (prefer no-op with actions unchanged — lock in test)
- If observe-only Osaurus → **must not** kill; clear handle; actions unchanged
- If owned → `ManagedProcess.stop`, wait port free, `lifecycle_actions += 1`
- Attempting to stop when `owned is False` after explicit foreign attach already covered; `stop` must never call killpg on foreign PIDs

- [ ] **Step 1: Write failing tests**

1. Owned start then stop → actions == 2, port_free checked
2. Observe-only Osaurus stop → actions == 0, stop_runner/spawner kill not called
3. Double stop after clear → safe no-op

- [ ] **Step 2–4: TDD implement + PASS**

- [ ] **Step 5: Commit**

```bash
git commit -m "$(cat <<'EOF'
Stop only harness-owned servers and verify ports free.

EOF
)"
```

---

### Task 5: Ready wait hook + docs pointer

**Files:**
- Modify: `harness_lifecycle.py`
- Modify: `tests/test_harness_lifecycle.py`
- Modify: `docs/architecture.md` (short subsection under Stage 2 / automation — planning status for shared lifecycle Gate A in progress / landed)
- Modify: `docs/superpowers/specs/2026-07-21-stack-review-gate-a-queue-design.md` — one line under Slice 1a: “Gate A implementation plan: `docs/superpowers/plans/2026-07-21-slice-1a-harness-lifecycle-gate-a.md`”

**Interfaces:**
- After owned spawn (and after observe-only attach), call optional `wait_ready(pin, process_or_none)`
- If `wait_ready` raises → surface as `HarnessLifecycleError(code="ready_failed")` and attempt owned stop cleanup if owned

- [ ] **Step 1: Test ready failure rolls back owned process**

- [ ] **Step 2–4: Implement + docs**

- [ ] **Step 5: Full verification**

```bash
PYTHONPATH=src /opt/homebrew/bin/python3 -m unittest \
  tests.test_harness_lifecycle \
  tests.test_matrix_lifecycle \
  tests.test_matrix_servers \
  tests.test_stage_two_inference_engine \
  tests.test_stage_two_benchmark_engine -q
```

Expected: OK

- [ ] **Step 6: Commit**

```bash
git commit -m "$(cat <<'EOF'
Add harness lifecycle ready hook and document Slice 1a Gate A.

EOF
)"
```

---

## Spec coverage check

| Spec requirement | Task |
|---|---|
| Shared controller OptiQ/oMLX/Osaurus | 1–4 |
| 20% RAM floor | 2 |
| Lab closed / no foreign OptiQ steal | 2–3 |
| `_owned` / never kill foreign Osaurus | 3–4 |
| Honest `lifecycle_actions` | 2–4 |
| Fake-only Gate A tests | 1–5 |
| No 1b/1c / no live auth | Global |
| Reuse matrix patterns | 2–4 |

## Placeholder scan

No TBD steps. Real Lab probe and Stage 2 wiring are explicitly deferred to later slices.

---

## Execution handoff

Plan complete and saved to `docs/superpowers/plans/2026-07-21-slice-1a-harness-lifecycle-gate-a.md`.

**Two execution options:**

1. **Subagent-Driven (recommended)** — fresh subagent per task, review between tasks  
2. **Inline Execution** — execute tasks in this session with checkpoints  

Which approach?
