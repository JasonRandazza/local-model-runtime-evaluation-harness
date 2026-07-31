# Managed Local Run Foundation Implementation Plan

> **Documentation role:** Completed implementation record, not active agent
> instructions or live authority. Current operation follows `AGENTS.md` and
> `docs/managed-runs.md`. The task-by-task constraints below describe the
> implementation session only.

**Goal:** Add an explicitly adopted standing-policy workflow that can plan, execute, pause, resume, and seal bounded local evaluations while safely managing Osaurus, oMLX, and OptiQ.

**Architecture:** Build one managed-run layer above the retained matrix, preference, RAG, and overhead collectors. The new layer owns immutable planning, policy evaluation, exact process lifecycle, temporary oMLX catalogs, orchestration, resumable evidence, and the `lmre` CLI; collector measurement and scoring remain unchanged.

**Tech Stack:** Python 3.11 standard library, `unittest`, JSON/JSONL, SHA-256, macOS `lsof` and `ps`, existing LMRE collector interfaces.

## Global Constraints

- The active repository is the executable source of truth; the sibling archive remains the immutable home of retired Stage 0–2 and legacy code.
- Python remains `>=3.11` with no new runtime dependency.
- Non-live tests use fakes and temporary directories. They must not contact Osaurus, oMLX, OptiQ, Keychain, or a real model.
- A cloned repository grants no live authority. Managed execution requires an explicitly adopted, valid local policy beneath gitignored `.lmre/`.
- Managed network contact is limited to `127.0.0.1` ports `1337`, `8100`, and `8080`.
- The policy defaults are one in-flight model, `20` percent free-memory floor, `90` maximum minutes, and `250` maximum requests.
- Incompatible process handling is notify, wait `60` seconds, re-inspect the exact identity, send `SIGINT`, and optionally send `SIGTERM`. Never send `SIGKILL`.
- Exact reclaim requires matching PID, parent PID, executable path, argument array, start time, listener address, and listener port at revalidation.
- Provider creation, provider editing, provider reconnect, credential creation, model download, model-weight deletion, plugin changes, remote endpoints, schedules, and arbitrary executable paths remain out of scope.
- A missing Osaurus routed model blocks only overhead as `BLOCKED_PROVIDER_RECONNECT`; completed native evidence remains valid and resumable.
- Persistent `config/matrix/omlx-roots` catalogs are replaced by per-run symbolic-link catalogs. Cleanup unlinks only catalog links and never deletes model targets.
- Raw results and `.lmre/` remain untracked and must never contain secrets.
- During the implementation session, staging, committing, pushing, real policy
  adoption, runtime lifecycle, and live evaluation were excluded. Current
  managed execution authority is defined by `AGENTS.md` and
  `docs/managed-runs.md`.

---

## File and Responsibility Map

### New product files

| File | Single responsibility |
| --- | --- |
| `schemas/operator-policy.schema.json` | Machine-readable policy `1.0.0` field contract |
| `config/operator-policies/local-managed-v1.example.json` | Adoptable example whose presence alone grants no authority |
| `config/managed-runs/complete-native-quality-v1.json` | Ordered, bounded managed recipe |
| `src/local_model_runtime_evaluation/operator_policy.py` | Parse, adopt, load, hash, expire, and evaluate standing authority |
| `src/local_model_runtime_evaluation/managed_run_types.py` | Shared immutable plan, step, state, attempt, and summary types |
| `src/local_model_runtime_evaluation/run_identity.py` | Safe names, collision-safe IDs, comparison lineage, and plan hashes |
| `src/local_model_runtime_evaluation/evidence_bundle.py` | Atomic evidence writes, append-only journals, checksums, and resume validation |
| `src/local_model_runtime_evaluation/process_inspection.py` | Resolve a loopback listener to one exact macOS process identity |
| `src/local_model_runtime_evaluation/runtime_adapters/base.py` | Typed runtime requirement, observation, lease, and adapter contracts |
| `src/local_model_runtime_evaluation/runtime_adapters/osaurus.py` | Fixed Osaurus command and inventory compatibility |
| `src/local_model_runtime_evaluation/runtime_adapters/omlx.py` | Fixed oMLX command, credential injection, and catalog use |
| `src/local_model_runtime_evaluation/runtime_adapters/optiq.py` | Fixed OptiQ command and inventory compatibility |
| `src/local_model_runtime_evaluation/omlx_catalog.py` | Create and safely remove per-run model-directory symlink views |
| `src/local_model_runtime_evaluation/runtime_manager.py` | Attach/start/notify/revalidate/reclaim/verify/release state machine |
| `src/local_model_runtime_evaluation/managed_run.py` | Invoke retained collectors in the immutable planned order |
| `src/local_model_runtime_evaluation/managed_run_cli.py` | `policy`, `plan`, `run`, `resume`, `status`, and `report` commands |
| `bin/lmre` | Repository-local wrapper for the managed CLI |
| `docs/managed-runs.md` | Operator workflow, shutdown notice, blocked resume, and evidence guide |

### Existing files changed

| File | Change |
| --- | --- |
| `.gitignore` | Ignore `.lmre/` and preserve the existing generated-results rules |
| `pyproject.toml` | Register `lmre = "local_model_runtime_evaluation.managed_run_cli:main"` |
| `src/local_model_runtime_evaluation/matrix_lifecycle.py` | Add bounded no-`SIGKILL` owned-process shutdown primitives |
| `src/local_model_runtime_evaluation/matrix_servers.py` | Remove broad `pkill -f`; accept the managed runtime server factory |
| `config/matrix/cells/*__omlx.json` | Replace repository-local model-directory paths with the catalog token |
| `README.md` | Make managed runs the normal live entry point and retain low-level dry-config surfaces |
| `docs/architecture.md` | Document the managed layer and authority boundary |
| `docs/status.md` | Record implementation status without claiming live acceptance |
| `AGENTS.md` | Replace per-run live permission wording with adopted-policy rules while preserving the non-live and Git boundaries |

### New test files

`tests/test_operator_policy.py`, `tests/test_run_identity.py`,
`tests/test_evidence_bundle.py`, `tests/test_process_inspection.py`,
`tests/test_runtime_manager.py`, `tests/test_runtime_adapters.py`,
`tests/test_omlx_catalog.py`, `tests/test_managed_run.py`, and
`tests/test_managed_run_cli.py`.

---

### Task 1: Standing policy schema, validation, and explicit adoption

**Files:**
- Create: `schemas/operator-policy.schema.json`
- Create: `config/operator-policies/local-managed-v1.example.json`
- Create: `src/local_model_runtime_evaluation/operator_policy.py`
- Create: `tests/test_operator_policy.py`
- Modify: `.gitignore`

**Interfaces:**
- Consumes: `Path`, `datetime`, `timezone`, `hashlib`, and `json` from the standard library.
- Produces:
  - `OperatorPolicy`
  - `PolicyRequest`
  - `AdoptedPolicy`
  - `load_policy(path: Path, *, now: datetime | None = None) -> OperatorPolicy`
  - `adopt_policy(source: Path, state_root: Path, *, now: datetime | None = None) -> AdoptedPolicy`
  - `load_adopted_policy(state_root: Path, *, now: datetime | None = None) -> AdoptedPolicy`
  - `authorize(policy: OperatorPolicy, request: PolicyRequest) -> None`

- [x] **Step 1: Write policy validation and adoption tests**

Add tests that construct the complete example document, then prove exact-field
validation, loopback enforcement, expiry, hash verification, limit rejection,
and explicit adoption:

```python
class OperatorPolicyTests(unittest.TestCase):
    def test_example_is_not_authority_until_adopted(self) -> None:
        with TemporaryDirectory() as tmp:
            state_root = Path(tmp) / ".lmre"
            with self.assertRaises(PolicyError) as ctx:
                load_adopted_policy(state_root)
            self.assertEqual(ctx.exception.code, "operator_policy_missing")

    def test_adopt_round_trip_preserves_hash_and_timestamp(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "policy.json"
            source.write_text(json.dumps(_policy_document()), encoding="utf-8")
            adopted = adopt_policy(
                source,
                root / ".lmre",
                now=datetime(2026, 7, 30, 18, 0, tzinfo=timezone.utc),
            )
            loaded = load_adopted_policy(root / ".lmre")
            self.assertEqual(loaded.policy_hash, adopted.policy_hash)
            self.assertEqual(loaded.adopted_at, "2026-07-30T18:00:00+00:00")

    def test_authorize_rejects_remote_endpoint_and_request_overage(self) -> None:
        policy = OperatorPolicy.from_dict(_policy_document())
        with self.assertRaises(PolicyError):
            authorize(
                policy,
                PolicyRequest(
                    runtimes=frozenset({"osaurus"}),
                    endpoints=("https://example.com/v1",),
                    inference=True,
                    start=True,
                    exact_reclaim=False,
                    parallel_models=1,
                    memory_floor_percent=20,
                    estimated_minutes=20,
                    request_count=251,
                ),
            )
```

- [x] **Step 2: Run the new test and verify the missing-module failure**

Run:

```bash
PYTHONPATH=src python3 -m unittest tests.test_operator_policy -v
```

Expected: `ERROR` with
`ModuleNotFoundError: No module named 'local_model_runtime_evaluation.operator_policy'`.

- [x] **Step 3: Add the policy contract and implementation**

The JSON schema and Python loader must require exactly the fields in the
approved design. Use frozen dataclasses and stable canonical JSON:

```python
POLICY_SCHEMA_VERSION = "1.0.0"
ADOPTED_POLICY_FILENAME = "operator-policy.json"

class PolicyError(RuntimeError):
    code = "operator_policy_invalid"

@dataclass(frozen=True)
class PolicyRequest:
    runtimes: frozenset[str]
    endpoints: tuple[str, ...]
    inference: bool
    start: bool
    exact_reclaim: bool
    parallel_models: int
    memory_floor_percent: int
    estimated_minutes: int
    request_count: int

@dataclass(frozen=True)
class AdoptedPolicy:
    policy: OperatorPolicy
    policy_hash: str
    adopted_at: str

def canonical_hash(body: dict[str, object]) -> str:
    encoded = json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()
```

`OperatorPolicy.from_dict` must reject unknown or missing fields, runtimes
outside `{"osaurus", "omlx", "optiq"}`, any non-`standing_local` mode,
non-`60` grace, force-kill or provider-edit authority, non-positive limits,
and malformed/non-UTC expiry. `authorize` must check every requested
capability and require each endpoint to equal one of:

```python
APPROVED_ENDPOINTS = frozenset({
    "http://127.0.0.1:1337/v1",
    "http://127.0.0.1:8100/v1",
    "http://127.0.0.1:8080/v1",
})
```

`adopt_policy` writes one atomic local record with this shape:

```json
{
  "adopted_at": "2026-07-30T18:00:00+00:00",
  "policy": {},
  "policy_hash": "sha256-of-canonical-policy"
}
```

Write through `operator-policy.json.tmp`, call `Path.replace`, and set the
missing-record exception code to `operator_policy_missing`, expired to
`operator_policy_expired`, and exceeded authority to
`operator_policy_denied`.

- [x] **Step 4: Add the example and ignore local adoption**

Copy the exact representative policy from the approved spec into
`config/operator-policies/local-managed-v1.example.json`. Add:

```gitignore
.lmre/
```

The example contains authority flags but has no effect until copied into the
validated adopted-policy record by `adopt_policy`.

- [x] **Step 5: Run focused and retained policy-independent tests**

Run:

```bash
PYTHONPATH=src python3 -m unittest \
  tests.test_operator_policy \
  tests.test_discovery_types \
  tests.test_matrix_config -v
```

Expected: all tests pass; no `.lmre/` directory appears in the repository.

- [x] **Step 6: Verification checkpoint**

Run:

```bash
git diff --check
git status --short
```

Confirm only the intended unstaged files changed. Do not stage or commit.

---

### Task 2: Immutable run identity, recipes, and request budgets

**Files:**
- Create: `config/managed-runs/complete-native-quality-v1.json`
- Create: `src/local_model_runtime_evaluation/managed_run_types.py`
- Create: `src/local_model_runtime_evaluation/run_identity.py`
- Create: `tests/test_run_identity.py`

**Interfaces:**
- Consumes: `OperatorPolicy`, existing family/cell/pair configs, and retained
  `MatrixSuite`, `PreferenceSuite`, and `RagSuite` loaders.
- Produces:
  - `ManagedStep`, `StepState`, `RunSummaryState`, and `Ownership` string enums
  - `RunIdentity`, `ManagedRunPlan`, `StepRecord`, and `ManagedRunState`
  - `sanitize_run_name(value: str) -> str`
  - `allocate_run_identity(results_root: Path, *, run_name: str, comparison_id: str | None, parent_run_id: str | None, now: datetime | None = None, entropy: str | None = None) -> RunIdentity`
  - `build_plan(recipe_path: Path, *, family_id: str, run_name: str | None, comparison_id: str | None, parent_run_id: str | None, results_root: Path, now: datetime | None = None, entropy: str | None = None) -> ManagedRunPlan`
  - `verify_plan_hash(plan: ManagedRunPlan) -> None`

- [x] **Step 1: Write identity, ordering, and budget tests**

```python
class RunIdentityTests(unittest.TestCase):
    def test_name_and_id_are_separate_and_collision_safe(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = allocate_run_identity(
                root,
                run_name=" Qwen Native / Baseline ",
                comparison_id=None,
                parent_run_id=None,
                now=_fixed_time(),
                entropy="a1b2c3",
            )
            second = allocate_run_identity(
                root,
                run_name=" Qwen Native / Baseline ",
                comparison_id=None,
                parent_run_id=None,
                now=_fixed_time(),
                entropy="d4e5f6",
            )
            self.assertEqual(first.run_name, "qwen-native-baseline")
            self.assertNotEqual(first.run_id, second.run_id)

    def test_complete_recipe_has_fixed_order_and_bounded_requests(self) -> None:
        plan = build_plan(
            RECIPE,
            family_id="gemma-4-12b-qat",
            run_name="gemma managed baseline",
            comparison_id=None,
            parent_run_id=None,
            results_root=Path("/tmp/results"),
            now=_fixed_time(),
            entropy="a1b2c3",
        )
        self.assertEqual(
            plan.steps,
            (
                ManagedStep.PREFLIGHT,
                ManagedStep.MATRIX,
                ManagedStep.PREFERENCE,
                ManagedStep.RAG_ORACLE,
                ManagedStep.RAG_KEYWORD,
                ManagedStep.OVERHEAD,
                ManagedStep.SEAL,
            ),
        )
        self.assertLessEqual(plan.request_count, 250)
        verify_plan_hash(plan)
```

Also test invalid names, unknown family, recipe steps out of order, mismatched
preference/RAG native triples, unknown overhead pairs, changed plan content,
and a collision when the same run ID directory already exists.

- [x] **Step 2: Run the focused test and verify it fails**

Run:

```bash
PYTHONPATH=src python3 -m unittest tests.test_run_identity -v
```

Expected: missing-module error for `managed_run_types`.

- [x] **Step 3: Define shared run types**

Use `StrEnum` so serialized values stay stable:

```python
class ManagedStep(StrEnum):
    PREFLIGHT = "preflight"
    MATRIX = "matrix"
    PREFERENCE = "preference"
    RAG_ORACLE = "rag-oracle"
    RAG_KEYWORD = "rag-keyword"
    OVERHEAD = "overhead"
    SEAL = "seal"

class StepState(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    PASS = "PASS"
    FAIL = "FAIL"
    BLOCKED_PROVIDER_RECONNECT = "BLOCKED_PROVIDER_RECONNECT"
    STOPPED = "STOPPED"
    INCOMPARABLE = "INCOMPARABLE"

class RunSummaryState(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    PASS = "PASS"
    FAIL = "FAIL"
    STOPPED = "STOPPED"
    PARTIAL_BLOCKED = "PARTIAL_BLOCKED"

class Ownership(StrEnum):
    ATTACHED = "attached"
    OWNED = "owned"
    RECLAIMED = "reclaimed"
```

`ManagedRunPlan.to_dict()` must include identity, family, recipe, exact ordered
steps, cell IDs, pair IDs, suite paths, endpoints, runtimes, request count,
estimated minutes, memory floor, creation time, and `plan_hash`.

- [x] **Step 4: Implement deterministic planning**

Permit run names matching `[a-z0-9]+(?:-[a-z0-9]+)*`, capped at 80 characters.
Allocate IDs as:

```python
run_id = f"run-{now:%Y%m%d-%H%M%S}-{entropy}"
```

The recipe JSON must contain:

```json
{
  "schema_version": "1.0.0",
  "recipe_id": "complete-native-quality-v1",
  "steps": [
    "preflight",
    "matrix",
    "preference",
    "rag-oracle",
    "rag-keyword",
    "overhead",
    "seal"
  ],
  "matrix_mode": "screen",
  "estimated_minutes": 90,
  "memory_floor_percent": 20
}
```

Compute the request ceiling from loaded suite sizes:

```python
matrix_requests = len(cell_ids) * len(matrix_suite.workloads)
preference_collect_requests = len(cell_ids) * len(preference_suite.prompts)
preference_judge_requests = (
    len(cell_ids) * (len(cell_ids) - 1) // 2
) * len(preference_suite.prompts)
rag_requests = 2 * len(cell_ids) * len(rag_suite.questions)
overhead_requests = 2 * len(pair_ids) * len(overhead_suite.workloads)
request_count = (
    matrix_requests
    + preference_collect_requests
    + preference_judge_requests
    + rag_requests
    + overhead_requests
)
```

Resolve all config paths to repository-relative POSIX strings before hashing.
Hash canonical JSON with `plan_hash` omitted.

- [x] **Step 5: Run focused tests**

Run:

```bash
PYTHONPATH=src python3 -m unittest \
  tests.test_run_identity \
  tests.test_matrix_config \
  tests.test_preference_config \
  tests.test_rag_config \
  tests.test_overhead_config -v
```

Expected: all tests pass and no results directory is created outside the test
temporary directories.

- [x] **Step 6: Verification checkpoint**

Run `git diff --check` and inspect `git status --short`. Do not stage or commit.

---

### Task 3: Atomic evidence bundles and resumable state

**Files:**
- Create: `src/local_model_runtime_evaluation/evidence_bundle.py`
- Create: `tests/test_evidence_bundle.py`

**Interfaces:**
- Consumes: `ManagedRunPlan`, `ManagedRunState`, `StepState`, and
  `AdoptedPolicy`.
- Produces:
  - `EvidenceError`
  - `EvidenceBundle.create(results_root: Path, plan: ManagedRunPlan, adopted_policy: AdoptedPolicy, environment: dict[str, object]) -> EvidenceBundle`
  - `EvidenceBundle.load(run_dir: Path) -> EvidenceBundle`
  - `append_event(event_type: str, payload: dict[str, object]) -> None`
  - `append_lifecycle(runtime: str, action: str, payload: dict[str, object]) -> None`
  - `transition_step(step: ManagedStep, state: StepState, *, detail: dict[str, object] | None = None) -> None`
  - `begin_attempt() -> int`
  - `step_attempt_dir(step: ManagedStep, attempt: int) -> Path`
  - `write_summary(summary: dict[str, object]) -> None`
  - `seal() -> Path`
  - `verify() -> None`

- [x] **Step 1: Write atomicity, checksum, and resume tests**

```python
class EvidenceBundleTests(unittest.TestCase):
    def test_create_writes_immutable_inputs_and_pending_state(self) -> None:
        bundle = _make_bundle()
        self.assertTrue((bundle.run_dir / "plan.json").is_file())
        self.assertTrue((bundle.run_dir / "policy-snapshot.json").is_file())
        state = json.loads((bundle.run_dir / "state.json").read_text())
        self.assertEqual(state["attempt"], 1)
        self.assertEqual(state["summary_state"], "PENDING")

    def test_seal_then_verify_detects_tampering(self) -> None:
        bundle = _make_bundle()
        bundle.write_summary({"status": "PASS"})
        bundle.seal()
        bundle.verify()
        (bundle.run_dir / "summary.json").write_text('{"status":"FAIL"}\n')
        with self.assertRaises(EvidenceError) as ctx:
            bundle.verify()
        self.assertEqual(ctx.exception.code, "evidence_checksum_mismatch")

    def test_resume_attempt_uses_new_directory_without_overwrite(self) -> None:
        bundle = _make_bundle()
        first = bundle.step_attempt_dir(ManagedStep.OVERHEAD, 1)
        first.mkdir(parents=True)
        (first / "raw.json").write_text("{}\n")
        self.assertEqual(bundle.begin_attempt(), 2)
        second = bundle.step_attempt_dir(ManagedStep.OVERHEAD, 2)
        self.assertNotEqual(first, second)
        self.assertTrue((first / "raw.json").is_file())
```

Also test append-only JSONL, illegal state transitions, secret-key rejection,
cleanup-before-seal enforcement, and checksum manifest path traversal.

- [x] **Step 2: Run the focused test and verify it fails**

Run:

```bash
PYTHONPATH=src python3 -m unittest tests.test_evidence_bundle -v
```

Expected: missing-module error for `evidence_bundle`.

- [x] **Step 3: Implement atomic JSON and append-only journals**

Use a single private writer:

```python
def _atomic_json(path: Path, body: dict[str, object]) -> None:
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(
        json.dumps(body, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)
```

Before writing any payload, recursively reject keys whose lowercase spelling
contains `api_key`, `authorization`, `credential`, `password`, `secret`, or
`token`. Event and lifecycle lines include UTC timestamp, attempt, event/action,
and payload.

Use this explicit transition table:

```python
ALLOWED_STEP_TRANSITIONS = {
    StepState.PENDING: {StepState.RUNNING, StepState.STOPPED},
    StepState.RUNNING: {
        StepState.PASS,
        StepState.FAIL,
        StepState.BLOCKED_PROVIDER_RECONNECT,
        StepState.STOPPED,
        StepState.INCOMPARABLE,
    },
    StepState.BLOCKED_PROVIDER_RECONNECT: {StepState.RUNNING},
    StepState.PASS: set(),
    StepState.FAIL: set(),
    StepState.STOPPED: set(),
    StepState.INCOMPARABLE: set(),
}
```

`begin_attempt` is legal only when overhead is
`BLOCKED_PROVIDER_RECONNECT`. It increments `attempt`, changes only overhead
back to `PENDING`, and records `attempt_started`.

- [x] **Step 4: Implement sealing and verification**

Require a lifecycle cleanup record for every owned or reclaimed lease and an
explicit `untouched` record for every attached lease before sealing. Hash every
regular file beneath the run directory except temporary files and
`checksums.sha256`, sort by relative POSIX path, and write:

```text
<sha256><two spaces><relative/path>
```

`verify` rejects missing files, extra files, duplicate paths, absolute paths,
`..` components, checksum mismatch, plan-hash mismatch, or an unsealed state.

- [x] **Step 5: Run evidence and identity tests**

Run:

```bash
PYTHONPATH=src python3 -m unittest \
  tests.test_evidence_bundle \
  tests.test_run_identity \
  tests.test_discovery_types -v
```

Expected: all pass.

- [x] **Step 6: Verification checkpoint**

Run `git diff --check` and inspect `git status --short`. Do not stage or commit.

---

### Task 4: Exact macOS listener identity and no-force shutdown

**Files:**
- Create: `src/local_model_runtime_evaluation/process_inspection.py`
- Create: `tests/test_process_inspection.py`
- Modify: `src/local_model_runtime_evaluation/matrix_lifecycle.py`
- Modify: `tests/test_matrix_lifecycle.py`

**Interfaces:**
- Consumes: fixed `/usr/sbin/lsof`, `/bin/ps`, `os.killpg`, and standard
  `signal`.
- Produces:
  - `ProcessIdentity`
  - `ProcessInspector.inspect_listener(host: str, port: int) -> ProcessIdentity | None`
  - `ProcessInspector.still_matches(expected: ProcessIdentity) -> bool`
  - `interrupt_process_group(process_group_id: int) -> None`
  - `terminate_process_group(process_group_id: int) -> None`
  - `wait_process_exit(process: ManagedProcess, timeout_seconds: float) -> bool`

- [x] **Step 1: Write parser, identity-change, and signal tests**

Inject a command runner so unit tests never inspect or signal real processes:

```python
class ProcessInspectionTests(unittest.TestCase):
    def test_inspect_listener_builds_exact_identity(self) -> None:
        runner = FakeRunner({
            ("/usr/sbin/lsof", "-nP", "-iTCP:8100", "-sTCP:LISTEN", "-Fpn"):
                "p321\nn127.0.0.1:8100\n",
            ("/usr/sbin/lsof", "-a", "-p", "321", "-d", "txt", "-Fn"):
                "n/Users/test/.venv/bin/python3.11\n",
            ("/bin/ps", "-p", "321", "-o", "ppid="): "100\n",
            ("/bin/ps", "-p", "321", "-o", "lstart="):
                "Thu Jul 30 18:00:00 2026\n",
            ("/bin/ps", "-p", "321", "-o", "command="):
                "omlx-server --host 127.0.0.1 --port 8100\n",
        })
        identity = ProcessInspector(runner=runner).inspect_listener(
            "127.0.0.1", 8100,
        )
        self.assertEqual(identity.pid, 321)
        self.assertEqual(identity.executable, "/Users/test/.venv/bin/python3.11")
        self.assertEqual(identity.argv[-2:], ("--port", "8100"))

    def test_wildcard_or_multiple_listener_fails_closed(self) -> None:
        with self.assertRaises(ProcessInspectionError):
            _inspector_with_listener("p1\np2\nn*:8100\n").inspect_listener(
                "127.0.0.1", 8100,
            )
```

Patch `os.killpg` in lifecycle tests and prove interrupt uses `SIGINT`,
termination uses `SIGTERM`, and no call uses `SIGKILL`.

- [x] **Step 2: Run focused tests and verify failure**

Run:

```bash
PYTHONPATH=src python3 -m unittest \
  tests.test_process_inspection \
  tests.test_matrix_lifecycle -v
```

Expected: missing-module error for `process_inspection`.

- [x] **Step 3: Implement exact listener inspection**

```python
@dataclass(frozen=True)
class ProcessIdentity:
    pid: int
    ppid: int
    executable: str
    argv: tuple[str, ...]
    started_at: str
    listener_host: str
    listener_port: int

    def fingerprint(self) -> tuple[object, ...]:
        return (
            self.pid,
            self.ppid,
            self.executable,
            self.argv,
            self.started_at,
            self.listener_host,
            self.listener_port,
        )
```

The inspector must require one PID, one `127.0.0.1:<port>` listener, one
absolute executable path from the `txt` descriptor, one parent PID, one start
time, and a `shlex.split`-parsable command. A listener on `*`, `0.0.0.0`,
`::`, or any non-loopback address fails with code
`runtime_listener_not_loopback`.

- [x] **Step 4: Remove force-kill behavior from owned-process primitives**

Replace `ManagedProcess.stop` with explicit bounded methods:

```python
def interrupt(self) -> None:
    os.killpg(self.process_group_id, signal.SIGINT)

def terminate(self) -> None:
    os.killpg(self.process_group_id, signal.SIGTERM)

def wait(self, timeout_seconds: float) -> bool:
    try:
        self._child.wait(timeout=timeout_seconds)
        return True
    except subprocess.TimeoutExpired:
        return False
```

Keep a compatibility `stop` that performs interrupt, waits, then terminates and
raises `LifecycleError` if the process still lives. It must never escalate to
`SIGKILL`.

- [x] **Step 5: Run focused lifecycle tests**

Run:

```bash
PYTHONPATH=src python3 -m unittest \
  tests.test_process_inspection \
  tests.test_matrix_lifecycle -v
```

Expected: all pass and the source scan below returns no matches:

```bash
rg -n "SIGKILL|pkill" src/local_model_runtime_evaluation/matrix_lifecycle.py
```

- [x] **Step 6: Verification checkpoint**

Run `git diff --check` and inspect `git status --short`. Do not stage or commit.

---

### Task 5: Typed runtime adapters and the 60-second reclaim state machine

**Files:**
- Create: `src/local_model_runtime_evaluation/runtime_adapters/__init__.py`
- Create: `src/local_model_runtime_evaluation/runtime_adapters/base.py`
- Create: `src/local_model_runtime_evaluation/runtime_adapters/osaurus.py`
- Create: `src/local_model_runtime_evaluation/runtime_adapters/omlx.py`
- Create: `src/local_model_runtime_evaluation/runtime_adapters/optiq.py`
- Create: `src/local_model_runtime_evaluation/runtime_manager.py`
- Create: `tests/test_runtime_adapters.py`
- Create: `tests/test_runtime_manager.py`
- Modify: `src/local_model_runtime_evaluation/matrix_servers.py`
- Modify: `tests/test_matrix_servers.py`

**Interfaces:**
- Consumes: `OperatorPolicy`, `ProcessInspector`, `Cell`, `Credential`,
  `ManagedProcess`, `TransportProtocol`, and an evidence lifecycle sink.
- Produces:
  - `RuntimeRequirement`, `RuntimeObservation`, `RuntimeLease`, `RuntimeAdapter`
  - `OsaurusAdapter`, `OmlxAdapter`, `OptiqAdapter`
  - `RuntimeManager.prepare(requirement: RuntimeRequirement, context: RuntimeContext) -> RuntimeLease`
  - `RuntimeManager.release(lease: RuntimeLease) -> None`
  - `RuntimeManager.build_server(cell: Cell, transport: TransportProtocol, log_dir: Path, credential: Credential | None) -> ServerHandle`

- [x] **Step 1: Write adapter compatibility and fixed-command tests**

```python
class RuntimeAdapterTests(unittest.TestCase):
    def test_each_adapter_accepts_only_its_fixed_port_and_server(self) -> None:
        cases = (
            (OsaurusAdapter, _cell(server="osaurus", port=1337)),
            (OmlxAdapter, _cell(server="omlx", port=8100)),
            (OptiqAdapter, _cell(server="optiq", port=8080)),
        )
        for adapter_type, cell in cases:
            adapter = adapter_type(_fake_dependencies())
            requirement = adapter.requirement_from_cell(cell)
            self.assertEqual(requirement.runtime, cell.server)

    def test_optiq_command_is_derived_from_pinned_cell_not_user_input(self) -> None:
        requirement = OptiqAdapter(_fake_dependencies()).requirement_from_cell(
            _optiq_cell(),
        )
        self.assertEqual(
            requirement.start_command[:4],
            ("optiq", "serve", "--model", _optiq_cell().artifact_path),
        )
        self.assertIn("127.0.0.1", requirement.start_command)
```

Also prove model compatibility is an exact inventory membership check and that
Osaurus/oMLX/OptiQ reject the wrong server, port, executable, or model.

- [x] **Step 2: Write state-machine tests with an injected clock**

```python
class RuntimeManagerTests(unittest.TestCase):
    def test_incompatible_process_gets_notice_grace_revalidation_and_interrupt(self) -> None:
        old = _identity(pid=321, model="old")
        adapter = FakeAdapter([
            _observation(old, compatible=False),
            _observation(old, compatible=False),
            _absent_observation(),
            _compatible_owned_observation(),
        ])
        notices: list[str] = []
        sleeps: list[float] = []
        manager = _manager(
            adapter,
            notice=notices.append,
            sleep=sleeps.append,
        )
        lease = manager.prepare(_requirement(), _context())
        self.assertEqual(sleeps, [60])
        self.assertEqual(adapter.interrupted, [old])
        self.assertEqual(lease.ownership, Ownership.RECLAIMED)
        self.assertIn("PID 321", notices[0])
        self.assertIn("Ctrl+C", notices[0])

    def test_changed_identity_cancels_reclaim(self) -> None:
        adapter = FakeAdapter([
            _observation(_identity(pid=321), compatible=False),
            _observation(_identity(pid=654), compatible=False),
        ])
        with self.assertRaises(RuntimeManagerError) as ctx:
            _manager(adapter).prepare(_requirement(), _context())
        self.assertEqual(ctx.exception.code, "runtime_identity_changed")
        self.assertEqual(adapter.interrupted, [])
```

Cover absent/start/owned, compatible/attach/untouched, user shutdown during
grace, `SIGINT` success, policy-gated `SIGTERM`, no-force failure, start
verification failure, cleanup failure, and lifecycle evidence for every path.

- [x] **Step 3: Run the focused tests and verify failure**

Run:

```bash
PYTHONPATH=src python3 -m unittest \
  tests.test_runtime_adapters \
  tests.test_runtime_manager -v
```

Expected: missing runtime-adapter modules.

- [x] **Step 4: Define runtime contracts**

```python
@dataclass(frozen=True)
class RuntimeRequirement:
    runtime: str
    cell_id: str
    base_url: str
    model_id: str
    artifact_path: str
    start_command: tuple[str, ...]
    stop_command: tuple[str, ...]

@dataclass(frozen=True)
class RuntimeObservation:
    identity: ProcessIdentity | None
    inventory: tuple[str, ...]
    compatible: bool
    reason: str

@dataclass
class RuntimeLease:
    requirement: RuntimeRequirement
    ownership: Ownership
    identity: ProcessIdentity
    process: ManagedProcess | None

class RuntimeAdapter(Protocol):
    runtime: str
    def requirement_from_cell(self, cell: Cell) -> RuntimeRequirement:
        raise NotImplementedError
    def inspect(self, requirement: RuntimeRequirement, credential: Credential | None) -> RuntimeObservation:
        raise NotImplementedError
    def attach(self, requirement: RuntimeRequirement, observation: RuntimeObservation) -> RuntimeLease:
        raise NotImplementedError
    def start(self, requirement: RuntimeRequirement, context: RuntimeContext) -> RuntimeLease:
        raise NotImplementedError
    def interrupt(self, identity: ProcessIdentity) -> None:
        raise NotImplementedError
    def terminate(self, identity: ProcessIdentity) -> None:
        raise NotImplementedError
    def release(self, lease: RuntimeLease, context: RuntimeContext) -> None:
        raise NotImplementedError
```

`RuntimeContext` contains log directory, credential, policy, lifecycle sink,
catalog root, injected monotonic clock, injected sleep, and fixed timeouts. It
must not be serialized because it may hold a credential.

- [x] **Step 5: Implement the runtime manager**

Implement this exact decision order:

```python
observation = adapter.inspect(requirement, context.credential)
if observation.identity is None:
    lease = adapter.start(requirement, context)
elif observation.compatible:
    lease = adapter.attach(requirement, observation)
else:
    context.notice(render_notice(requirement, observation, policy))
    context.sleep(policy.reclaim_grace_seconds)
    rechecked = adapter.inspect(requirement, context.credential)
    if rechecked.identity is None:
        lease = adapter.start(requirement, context)
    else:
        require_same_identity(observation.identity, rechecked.identity)
        authorize(policy, context.reclaim_request)
        adapter.interrupt(rechecked.identity)
        if not wait_until_absent(adapter, requirement, context.interrupt_timeout):
            if not policy.allow_terminate_after_interrupt:
                raise RuntimeManagerError("runtime remained after interrupt")
            adapter.terminate(rechecked.identity)
            if not wait_until_absent(adapter, requirement, context.terminate_timeout):
                raise RuntimeManagerError("runtime remained after terminate")
        started = adapter.start(requirement, context)
        lease = replace(started, ownership=Ownership.RECLAIMED)
verified = adapter.inspect(requirement, context.credential)
require_compatible_identity(lease, verified)
return lease
```

The notice includes runtime, port, observed model inventory, required model,
PID, grace deadline, policy ID, and `Press Ctrl+C to cancel this run`.

- [x] **Step 6: Implement concrete adapters**

Each adapter derives fixed commands only from retained cell configuration:

```python
OSAURUS_PREFIX = ("osaurus", "serve", "--port", "1337", "--yes")
OMLX_PREFIX = ("omlx", "serve", "--model-dir")
OPTIQ_PREFIX = ("optiq", "serve", "--model")
```

Before releasing any lease, re-inspect and require its exact identity. Osaurus,
oMLX, and OptiQ stop only their exact harness-owned process group. Attached
leases record `untouched` and perform no signal or stop command.

- [x] **Step 7: Remove broad reclaim from the legacy server adapter**

Delete `OPTIQ_RECLAIM_COMMAND`, `OMLX_RECLAIM_COMMAND`, and all `pkill` paths.
When low-level `build_server` sees an incompatible busy listener without a
managed `RuntimeManager`, raise:

```python
raise ServerError(
    "incompatible runtime is active; use the managed lmre command "
    "with an adopted operator policy"
)
```

Update the old reclaim tests to assert failure, no stop command, and no spawn.
Managed reclaim behavior belongs only in `tests/test_runtime_manager.py`.

- [x] **Step 8: Run focused runtime tests**

Run:

```bash
PYTHONPATH=src python3 -m unittest \
  tests.test_runtime_adapters \
  tests.test_runtime_manager \
  tests.test_matrix_servers \
  tests.test_matrix_lifecycle -v
```

Expected: all pass. This scan must produce no active source match:

```bash
rg -n "pkill|SIGKILL" src/local_model_runtime_evaluation
```

- [x] **Step 9: Verification checkpoint**

Run `git diff --check` and inspect `git status --short`. Do not stage or commit.

---

### Task 6: Per-run oMLX catalogs and persistent-root retirement

**Files:**
- Create: `src/local_model_runtime_evaluation/omlx_catalog.py`
- Create: `tests/test_omlx_catalog.py`
- Modify: `src/local_model_runtime_evaluation/runtime_adapters/omlx.py`
- Modify: `config/matrix/cells/oq4_fp16__omlx.json`
- Modify: `config/matrix/cells/ornith_oq4__omlx.json`
- Modify: `config/matrix/cells/qwen_oq4__omlx.json`
- Delete: `config/matrix/omlx-roots/`
- Modify: `.gitignore`
- Modify: `tests/test_matrix_config.py`

**Interfaces:**
- Consumes: an authorized oMLX `RuntimeRequirement` and the run's private
  working directory.
- Produces:
  - `OMLX_CATALOG_TOKEN = "{LMRE_OMLX_CATALOG}"`
  - `CatalogEntry`
  - `TemporaryOmlxCatalog.create(root: Path, entries: tuple[CatalogEntry, ...]) -> TemporaryOmlxCatalog`
  - `TemporaryOmlxCatalog.command(command: tuple[str, ...]) -> tuple[str, ...]`
  - `TemporaryOmlxCatalog.cleanup() -> None`

- [x] **Step 1: Write safe-link and cleanup tests**

```python
class OmlxCatalogTests(unittest.TestCase):
    def test_catalog_links_only_authorized_artifact(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "weights"
            target.mkdir()
            catalog = TemporaryOmlxCatalog.create(
                root / "run" / "runtime" / "omlx-catalog",
                (CatalogEntry("model-a", target),),
            )
            link = catalog.path / "model-a"
            self.assertTrue(link.is_symlink())
            self.assertEqual(link.resolve(), target.resolve())
            command = catalog.command(
                ("omlx", "serve", "--model-dir", OMLX_CATALOG_TOKEN),
            )
            self.assertEqual(command[-1], str(catalog.path))

    def test_cleanup_unlinks_catalog_without_deleting_target(self) -> None:
        catalog, target = _catalog_fixture()
        catalog.cleanup()
        self.assertTrue(target.is_dir())
        self.assertFalse(catalog.path.exists())
```

Also reject missing/non-directory targets, duplicate or unsafe link names,
pre-existing catalog directories, commands without exactly one token, and
cleanup of any non-symlink entry.

- [x] **Step 2: Run the focused test and verify failure**

Run:

```bash
PYTHONPATH=src python3 -m unittest tests.test_omlx_catalog -v
```

Expected: missing-module error for `omlx_catalog`.

- [x] **Step 3: Implement the catalog**

```python
OMLX_CATALOG_TOKEN = "{LMRE_OMLX_CATALOG}"
SAFE_CATALOG_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}")

@dataclass(frozen=True)
class CatalogEntry:
    model_id: str
    artifact_path: Path

    @property
    def link_name(self) -> str:
        if not SAFE_CATALOG_NAME.fullmatch(self.model_id):
            raise OmlxCatalogError("oMLX model id is not a safe catalog name")
        return self.model_id
```

Create the root with `mkdir(parents=True, exist_ok=False)` and each entry with
`link.symlink_to(target.resolve(), target_is_directory=True)`. Cleanup first
verifies every child is one of the recorded symlinks and still resolves to its
recorded target, then unlinks children and removes the now-empty root.

- [x] **Step 4: Route oMLX startup through the catalog**

The oMLX adapter creates exactly one catalog entry from the requirement's
`model_id` and `artifact_path`, substitutes the token, then appends the
in-memory API key:

```python
command = catalog.command(requirement.start_command)
command = command + ("--api-key", context.credential.api_key())
```

The credential-bearing command must never be passed to lifecycle evidence.
Record a redacted command with the value after `--api-key` replaced by
`"<redacted>"`.

- [x] **Step 5: Migrate configs and remove repository catalogs**

Change all three retained oMLX cell commands to:

```json
[
  "omlx",
  "serve",
  "--model-dir",
  "{LMRE_OMLX_CATALOG}",
  "--host",
  "127.0.0.1",
  "--port",
  "8100"
]
```

Delete only the repository-local `config/matrix/omlx-roots` links, READMEs, and
`.DS_Store`. Do not touch any symlink target or external model cache. Remove
the now-obsolete oMLX-root exceptions from `.gitignore`.

- [x] **Step 6: Add a fail-closed unmanaged-start guard**

In `matrix_servers.SubprocessServerHandle._start_command`, reject an unresolved
catalog token:

```python
if OMLX_CATALOG_TOKEN in command:
    raise ServerError(
        "oMLX requires a temporary managed catalog; run through lmre"
    )
```

This preserves low-level dry-config and fake tests while preventing a broken
live command from using a nonexistent repository path.

- [x] **Step 7: Run focused config and catalog tests**

Run:

```bash
PYTHONPATH=src python3 -m unittest \
  tests.test_omlx_catalog \
  tests.test_runtime_adapters \
  tests.test_matrix_config \
  tests.test_matrix_servers \
  tests.test_discovery_cli -v
```

Expected: all pass. These scans must return no match:

```bash
rg -n "config/matrix/omlx-roots" config src tests README.md docs/*.md
find config/matrix -path '*omlx-roots*' -print
```

- [x] **Step 8: Verification checkpoint**

Inspect `git status --short` and confirm the deleted paths are only repository
catalog links/metadata. Do not stage or commit; do not delete external weights.

---

### Task 7: Managed collector hooks and normal execution

**Files:**
- Create: `src/local_model_runtime_evaluation/managed_run.py`
- Create: `tests/test_managed_run.py`
- Modify: `src/local_model_runtime_evaluation/runtime_manager.py`

**Interfaces:**
- Consumes: `ManagedRunPlan`, `AdoptedPolicy`, `EvidenceBundle`,
  `RuntimeManager`, and retained collector entry points.
- Produces:
  - `ManagedCollectorHooks`
  - `default_collector_hooks(plan: ManagedRunPlan, runtime_manager: RuntimeManager, bundle: EvidenceBundle) -> ManagedCollectorHooks`
  - `execute_managed_run(plan: ManagedRunPlan, adopted_policy: AdoptedPolicy, bundle: EvidenceBundle, runtime_manager: RuntimeManager, hooks: ManagedCollectorHooks) -> dict[str, object]`

- [x] **Step 1: Write orchestration order and failure tests**

```python
class ManagedRunTests(unittest.TestCase):
    def test_normal_run_calls_collectors_in_immutable_order(self) -> None:
        calls: list[str] = []
        hooks = FakeHooks(calls=calls, routed_models=_required_routes())
        summary = execute_managed_run(
            _plan(),
            _adopted_policy(),
            _bundle(),
            _runtime_manager(),
            hooks,
        )
        self.assertEqual(
            calls,
            ["preflight", "matrix", "preference", "rag-oracle",
             "rag-keyword", "route-check", "overhead"],
        )
        self.assertEqual(summary["status"], "PASS")

    def test_collector_failure_stops_dependent_steps_and_cleans_owned_leases(self) -> None:
        hooks = FakeHooks(fail_at="preference")
        runtime_manager = _runtime_manager()
        summary = execute_managed_run(
            _plan(), _adopted_policy(), _bundle(), runtime_manager, hooks,
        )
        self.assertEqual(summary["status"], "FAIL")
        self.assertEqual(_state("preference"), "FAIL")
        self.assertEqual(_state("rag-oracle"), "STOPPED")
        self.assertTrue(runtime_manager.all_owned_released)
```

Cover policy denial before preflight, memory-floor denial, `KeyboardInterrupt`
to `STOPPED`, exact step directories, collector result-path capture, attached
lease untouched, cleanup failure preventing `PASS`, and seal ordering.

- [x] **Step 2: Run the focused test and verify failure**

Run:

```bash
PYTHONPATH=src python3 -m unittest tests.test_managed_run -v
```

Expected: missing-module error for `managed_run`.

- [x] **Step 3: Define injectable collector hooks**

```python
@dataclass(frozen=True)
class ManagedCollectorHooks:
    preflight: Callable[[ManagedRunPlan], dict[str, object]]
    matrix: Callable[[ManagedRunPlan, Path, BuildServer], Path]
    preference: Callable[[ManagedRunPlan, Path, BuildServer], Path]
    rag_oracle: Callable[[ManagedRunPlan, Path, BuildServer], Path]
    rag_keyword: Callable[[ManagedRunPlan, Path, BuildServer], Path]
    routed_models: Callable[[ManagedRunPlan], tuple[str, ...]]
    overhead: Callable[[ManagedRunPlan, Path, BuildServer], Path]
```

Default hooks call the current public functions:

```python
matrix_runner.run_campaign
preference_collect.run_collect
preference_review.run_review
preference_judge.run_judge
preference_tally.run_tally
rag_collect.run_collect
rag_score.score_run
overhead_runner.run_overhead
```

Pass `runtime_manager.build_server` into every collector and judge call. Give
each collector its `steps/<step>/attempt-<NNN>/` root so its own timestamped
run directory remains intact beneath the managed bundle.

- [x] **Step 4: Implement the coordinator**

At entry:

```python
verify_plan_hash(plan)
authorize(adopted_policy.policy, plan.policy_request())
bundle.append_event("policy_authorized", {
    "policy_id": adopted_policy.policy.policy_id,
    "policy_hash": adopted_policy.policy_hash,
})
```

For each planned step, transition `PENDING -> RUNNING`, call the exact hook,
record the returned relative path, then transition to `PASS`. On exception,
record only exception type/code and sanitized message, mark the current step
`FAIL`, later unstarted steps `STOPPED`, release all owned/reclaimed leases,
write `FAIL`, and seal. On `KeyboardInterrupt`, use `STOPPED` instead.

Preflight checks artifact directories, fixed executables, all suite/config
loads, current free memory, request budget, and loopback endpoints without
starting a process or issuing inference.

- [x] **Step 5: Run managed and collector regression tests**

Run:

```bash
PYTHONPATH=src python3 -m unittest \
  tests.test_managed_run \
  tests.test_matrix_runner \
  tests.test_preference_collect \
  tests.test_preference_judge \
  tests.test_rag_collect \
  tests.test_overhead_runner -v
```

Expected: all pass using fakes only.

- [x] **Step 6: Verification checkpoint**

Run `git diff --check` and inspect `git status --short`. Do not stage or commit.

---

### Task 8: Provider-reconnect blocking and overhead-only resume

**Files:**
- Modify: `src/local_model_runtime_evaluation/managed_run.py`
- Modify: `src/local_model_runtime_evaluation/evidence_bundle.py`
- Modify: `tests/test_managed_run.py`
- Modify: `tests/test_evidence_bundle.py`

**Interfaces:**
- Consumes: sealed `PARTIAL_BLOCKED` evidence and exact routed IDs from each
  `OverheadPair`.
- Produces:
  - `resume_managed_run(run_dir: Path, adopted_policy: AdoptedPolicy, runtime_manager: RuntimeManager, hooks: ManagedCollectorHooks) -> dict[str, object]`

- [x] **Step 1: Write blocked-run and resume tests**

```python
def test_missing_route_preserves_native_steps_and_blocks_overhead(self) -> None:
    hooks = FakeHooks(routed_models=())
    summary = execute_managed_run(
        _plan(),
        _adopted_policy(),
        _bundle(),
        _runtime_manager(),
        hooks,
    )
    self.assertEqual(summary["status"], "PARTIAL_BLOCKED")
    self.assertEqual(_state("rag-keyword"), "PASS")
    self.assertEqual(_state("overhead"), "BLOCKED_PROVIDER_RECONNECT")
    self.assertFalse(hooks.overhead_called)
    _bundle().verify()

def test_resume_runs_only_overhead_and_preserves_attempt_one(self) -> None:
    bundle = _sealed_blocked_bundle()
    before = (bundle.run_dir / "steps" / "rag-keyword").read_bytes()
    calls: list[str] = []
    summary = resume_managed_run(
        bundle.run_dir,
        _adopted_policy(),
        _runtime_manager(),
        FakeHooks(calls=calls, routed_models=_required_routes()),
    )
    self.assertEqual(calls, ["route-check", "overhead"])
    self.assertEqual(summary["status"], "PASS")
    self.assertEqual(
        (bundle.run_dir / "steps" / "rag-keyword").read_bytes(), before,
    )
    self.assertTrue(
        (bundle.run_dir / "steps" / "overhead" / "attempt-002").is_dir()
    )
```

Also reject resume after PASS/FAIL, missing exact route, changed plan hash,
changed policy hash without reauthorization, checksum damage, and a second
active writer.

- [x] **Step 2: Run the focused tests and verify failure**

Run:

```bash
PYTHONPATH=src python3 -m unittest \
  tests.test_managed_run \
  tests.test_evidence_bundle -v
```

Expected: failure because resume behavior does not yet exist.

- [x] **Step 3: Implement route blocking**

Before overhead, load every planned pair and compare all exact
`routed_model_id` values with Osaurus inventory. When any are missing:

```python
bundle.transition_step(
    ManagedStep.OVERHEAD,
    StepState.BLOCKED_PROVIDER_RECONNECT,
    detail={
        "missing_routed_model_ids": list(missing),
        "operator_action": (
            "Reconnect the existing provider in the Osaurus UI, "
            "then run lmre resume <run-id>."
        ),
    },
)
bundle.write_summary({
    "status": RunSummaryState.PARTIAL_BLOCKED,
    "completed_native_steps_valid": True,
    "missing_routed_model_ids": list(missing),
})
```

Release owned processes, record cleanup, and seal normally. Do not edit or
reconnect an Osaurus provider.

- [x] **Step 4: Implement resume validation and attempt two**

`resume_managed_run` must:

1. Load and verify the sealed bundle.
2. Require summary `PARTIAL_BLOCKED` and overhead
   `BLOCKED_PROVIDER_RECONNECT`.
3. Verify plan hash and current adopted policy.
4. Reauthorize the unchanged plan.
5. Verify all exact routed IDs.
6. Call `begin_attempt`.
7. Execute only overhead beneath `attempt-002`.
8. Release owned processes, write PASS or FAIL, and replace the checksum
   manifest atomically.

Use an atomic lock:

```python
descriptor = os.open(
    bundle.run_dir / ".resume.lock",
    os.O_WRONLY | os.O_CREAT | os.O_EXCL,
    0o600,
)
os.close(descriptor)
```

Always remove it in `finally`. Treat `.resume.lock` as ephemeral: checksum
creation and verification ignore it, while every other unexpected regular file
still fails verification.

- [x] **Step 5: Run blocked/resume tests**

Run:

```bash
PYTHONPATH=src python3 -m unittest \
  tests.test_managed_run \
  tests.test_evidence_bundle -v
```

Expected: all pass and attempt-one evidence hashes remain unchanged.

- [x] **Step 6: Verification checkpoint**

Run `git diff --check` and inspect `git status --short`. Do not stage or commit.

---

### Task 9: Managed CLI and local operator workflow

**Files:**
- Create: `src/local_model_runtime_evaluation/managed_run_cli.py`
- Create: `tests/test_managed_run_cli.py`
- Create: `bin/lmre`
- Modify: `pyproject.toml`

**Interfaces:**
- Consumes: all policy, planning, runtime, orchestration, resume, and evidence
  interfaces from Tasks 1–8.
- Produces:
  - `main(argv: Sequence[str] | None = None) -> int`
  - commands `policy show`, `policy adopt`, `plan`, `run`, `resume`, `status`,
    and `report`.

- [x] **Step 1: Write non-live CLI tests**

```python
def _main_json(argv: list[str]) -> tuple[int, dict[str, object]]:
    output = StringIO()
    with redirect_stdout(output):
        code = main(argv)
    return code, json.loads(output.getvalue())

class ManagedRunCliTests(unittest.TestCase):
    def test_plan_fails_when_policy_is_not_adopted(self) -> None:
        code, payload = _main_json([
            "--state-dir", str(self.state_root),
            "--results-dir", str(self.results_root),
            "plan",
            "--family", "gemma-4-12b-qat",
            "--recipe", str(RECIPE),
            "--name", "gemma baseline",
        ])
        self.assertEqual(code, 1)
        self.assertEqual(payload["error"]["kind"], "operator_policy_missing")

    def test_policy_adopt_then_plan_writes_no_live_activity(self) -> None:
        with patch(
            "local_model_runtime_evaluation.managed_run_cli.execute_managed_run",
            side_effect=AssertionError("planning must not execute"),
        ), patch(
            "local_model_runtime_evaluation.matrix_lifecycle.spawn_pinned",
            side_effect=AssertionError("planning must not spawn"),
        ):
            code, adopted = _main_json([
                "--state-dir", str(self.state_root),
                "policy", "adopt", "--from", str(self.policy_path),
            ])
            self.assertEqual(code, 0)
            code, planned = _main_json([
                "--state-dir", str(self.state_root),
                "--results-dir", str(self.results_root),
                "plan",
                "--family", "gemma-4-12b-qat",
                "--recipe", str(RECIPE),
                "--name", "gemma baseline",
            ])
            self.assertEqual(code, 0)
            self.assertIn("run_id", planned)

    def test_resume_delegates_only_after_bundle_validation(self) -> None:
        with patch(
            "local_model_runtime_evaluation.managed_run_cli.resume_managed_run",
            return_value={"status": "PASS"},
        ) as resume:
            code, payload = _main_json([
                "--state-dir", str(self.state_root),
                "--results-dir", str(self.results_root),
                "resume", "run-20260730-180000-a1b2c3",
            ])
            self.assertEqual(code, 0)
            self.assertEqual(payload["status"], "PASS")
            resume.assert_called_once()
```

Also test `status`, `report`, JSON error shape, duplicate plan ID, expired
policy, `run` refusing an unplanned ID, and help text that says provider
reconnect is UI-owned.

- [x] **Step 2: Run the focused test and verify failure**

Run:

```bash
PYTHONPATH=src python3 -m unittest tests.test_managed_run_cli -v
```

Expected: missing-module error for `managed_run_cli`.

- [x] **Step 3: Implement parser and JSON output**

Top-level syntax:

```text
lmre policy show
lmre policy adopt --from <example.json>
lmre plan --family <family-id> --recipe <recipe.json> [--name <name>]
lmre run <run-id>
lmre resume <run-id>
lmre status <run-id>
lmre report <run-id>
```

Global options include `--state-dir` defaulting to `.lmre` and
`--results-dir` defaulting to `results/runs`. Every command prints one JSON
object. Errors use:

```python
{
    "ok": False,
    "error": {
        "kind": getattr(error, "code", error.__class__.__name__),
        "message": sanitize_error(str(error)),
    },
}
```

`policy adopt` prints the policy ID, hash, adoption time, lifecycle authority,
inference authority, 60-second reclaim grace, and explicit exclusions before
writing. The invoked command itself is the explicit adoption action; do not add
a second interactive confirmation.

- [x] **Step 4: Wire executable entry points**

Add:

```toml
[project.scripts]
lmre = "local_model_runtime_evaluation.managed_run_cli:main"
lmre-discover = "local_model_runtime_evaluation.discovery_cli:main"
```

Create `bin/lmre` using the same `PYTHONPATH=src` wrapper pattern as retained
repository CLIs and make it executable:

```bash
chmod +x bin/lmre
```

- [x] **Step 5: Run CLI tests and help-only smoke checks**

Run:

```bash
PYTHONPATH=src python3 -m unittest \
  tests.test_managed_run_cli \
  tests.test_discovery_cli \
  tests.test_matrix_cli \
  tests.test_preference_cli \
  tests.test_rag_cli \
  tests.test_overhead_cli -v

./bin/lmre --help
./bin/lmre policy --help
./bin/lmre plan --help
./bin/lmre resume --help
```

Expected: tests pass and help exits zero. Do not run `policy adopt`, `run`, or
`resume` against real repository state.

- [x] **Step 6: Verification checkpoint**

Run `git diff --check` and inspect `git status --short`. Do not stage or commit.

---

### Task 10: Operator docs, repository rules, and complete non-live validation

**Files:**
- Create: `docs/managed-runs.md`
- Modify: `README.md`
- Modify: `docs/architecture.md`
- Modify: `docs/status.md`
- Modify: `AGENTS.md`
- Test: retained `tests/` suite and all dry-config commands

**Interfaces:**
- Consumes: final command syntax and behavior from Tasks 1–9.
- Produces: one self-contained operator runbook and current repository safety
  rules; no live evidence.

- [x] **Step 1: Write the managed-run operator guide**

Document this exact safe sequence:

```bash
# Recommended before a run:
osaurus stop
omlx stop
# Stop any foreground `optiq serve` with Ctrl+C.

# One-time deliberate local adoption:
./bin/lmre policy adopt \
  --from config/operator-policies/local-managed-v1.example.json

# Plan, inspect, then execute:
./bin/lmre plan \
  --family gemma-4-12b-qat \
  --recipe config/managed-runs/complete-native-quality-v1.json \
  --name gemma-managed-baseline
./bin/lmre status <run-id>
./bin/lmre run <run-id>

# If overhead is blocked, reconnect the existing provider in Osaurus UI:
./bin/lmre resume <run-id>
./bin/lmre report <run-id>
```

Explain attached/owned/reclaimed, the 60-second notice, `Ctrl+C`, no pre-run
process restoration, temporary catalogs, policy replacement, evidence states,
and why model-cache deletion is a separate explicit storage task.

- [x] **Step 2: Update README, architecture, status, and agent rules**

README makes `./bin/lmre` the normal managed live path and labels retained
collector CLIs as low-level diagnostic/dry-config surfaces. Architecture adds:

```text
adopted policy -> immutable plan -> runtime manager -> retained collectors
               -> evidence bundle -> blocked resume or sealed report
```

`docs/status.md` says implementation is non-live validated only until a
separately authorized local acceptance run passes. `AGENTS.md` permits a
managed run only when the adopted policy authorizes the exact plan; it must
still forbid live execution, policy adoption, Git actions, provider edits, and
plugin changes unless the user explicitly requested the corresponding action.

- [x] **Step 3: Run placeholder and stale-reference scans**

Run:

```bash
rg -n "TBD|TODO|implement later|fill in details|pkill|SIGKILL" \
  src tests config README.md AGENTS.md docs/*.md

rg -n "config/matrix/omlx-roots|lmre run resume" \
  src tests config README.md AGENTS.md docs/*.md
```

Expected: no product-source match for broad kill, old roots, or old resume
syntax. Existing unrelated source comments should be reviewed individually,
not mechanically deleted.

- [x] **Step 4: Run the complete retained Python suite**

Run:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

Expected: all retained tests pass. Any environment-only port skip must remain
an explicit skip, not be converted to PASS.

- [x] **Step 5: Run every non-live configuration command**

Run:

```bash
./bin/lmre-discover dry-config
./bin/lmre-approach3 dry-config \
  config/approach3/gemma-freeform-native-triple-v1.json
./bin/lmre-matrix --dry-config \
  --campaign config/matrix/gemma-4-12b-qat-campaign.json
./bin/lmre-preference collect --dry-config
./bin/lmre-rag collect --dry-config
./bin/lmre-overhead run --dry-config
```

Expected: each exits zero and reports configuration only. Do not execute
`lmre plan`, because even a plan requires a locally adopted policy and would
write a run bundle.

- [x] **Step 6: Verify the active Graphify corpus still builds**

Refresh the existing graph after the deletion-heavy implementation, then
regenerate the tree:

```bash
graphify update . --force
graphify tree \
  --graph graphify-out/graph.json \
  --output graphify-out/GRAPH_TREE.html \
  --root "$PWD" \
  --label local-model-runtime-evaluation-harness
```

Confirm the graph completes without ingesting `graphify-out/`, `results/`,
`.lmre/`, the sibling archive, or deleted historical files. Record counts from
`graphify-out/graph.json` in the task handoff; keep generated Graphify output
ignored.

- [x] **Step 7: Final verification checkpoint**

Run:

```bash
git diff --check
git status --short
```

Report:

- files created, modified, and deleted;
- focused and full test counts;
- dry-config results;
- Graphify node/edge/community counts;
- confirmation that no policy was adopted;
- confirmation that no runtime was contacted, started, stopped, or signaled;
- confirmation that external model weights were untouched;
- confirmation that changes remain unstaged and uncommitted.

Historical implementation stop point: no real policy was adopted and no live
acceptance run was performed as part of this plan. Current policy adoption and
managed execution follow `docs/managed-runs.md`.
