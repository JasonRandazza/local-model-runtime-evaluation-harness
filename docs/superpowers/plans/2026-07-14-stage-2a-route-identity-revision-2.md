# Stage 2A Route Identity Revision 2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the invalid `optiq/` prefix hypothesis with exact upstream model identity proof while preserving sanitized failure evidence and preventing consumed run reuse.

**Architecture:** Runtime profile revision `2` pins the routed ID `mlx-community/VibeThinker-3B-OptiQ-4bit` and rejects the local ID `vibethinker-3b-optiq-4bit`. The read-only transport returns sanitized model descriptors, the engine persists endpoint inventory before deciding identity, and the Gate B checker refuses any run whose canonical output directory already exists.

**Tech Stack:** Python 3 standard library, `unittest`, JSON Schema, Swift plugin contract tests, Osaurus loopback HTTP APIs, Markdown operational documentation.

## Global Constraints

- Make no inference, warm-up, benchmark, model-load, conversion, quantization, or HTTP POST request.
- Do not start OptiQ Lab or manually start `optiq serve` during implementation.
- Do not modify the Osaurus provider configuration.
- Keep plugin `0.3.0`; its native tool contract is unchanged.
- Treat `owned_by` and `root` as diagnostic evidence, not acceptance gates.
- Preserve `stage2-20260714-001` and its artifacts as consumed historical evidence.
- Create no active revision-2 manifest or run ID without separate current-session authorization.
- Do not stage or commit files unless Jason separately requests Git operations.

---

### Task 1: Pin Runtime Profile Revision 2

**Files:**
- Modify: `config/runtime-profiles/vibethinker-3b-optiq-4bit.json`
- Modify: `schemas/runtime-profile.schema.json`
- Modify: `src/local_model_runtime_evaluation/stage_two_profiles.py`
- Modify: `tests/test_stage_two_profile.py`
- Modify: `tests/fixtures/valid-stage-2.json`

**Interfaces:**
- Produces: `RuntimeProfile.routed_model_id: str`
- Produces: `RuntimeProfile.rejected_local_model_ids: tuple[str, ...]`
- Removes: `RuntimeProfile.routed_prefix_hypothesis`

- [x] **Step 1: Write failing revision-2 profile tests**

Update the profile test to request revision `2` and assert exact identities:

```python
profile = RuntimeProfileRegistry(self.root / "config" / "runtime-profiles").get(
    "vibethinker-3b-optiq-4bit", "2"
)
self.assertEqual(
    profile.routed_model_id,
    "mlx-community/VibeThinker-3B-OptiQ-4bit",
)
self.assertEqual(
    profile.rejected_local_model_ids,
    ("vibethinker-3b-optiq-4bit",),
)
self.assertFalse(hasattr(profile, "routed_prefix_hypothesis"))
```

Add mutations proving alternate routed IDs, an empty rejection list, revision `1`, and the removed prefix field are rejected.

- [x] **Step 2: Run the focused profile tests and verify RED**

Run:

```zsh
/usr/bin/env PYTHONPATH=src python3 -m unittest tests.test_stage_two_profile -v
```

Expected: failure because revision `2` and the new fields do not exist.

- [x] **Step 3: Implement the strict profile migration**

Change the dataclass fields to:

```python
routed_model_id: str
rejected_local_model_ids: tuple[str, ...]
```

Require exactly:

```python
data["revision"] == "2"
data["routed_model_id"] == "mlx-community/VibeThinker-3B-OptiQ-4bit"
data["rejected_local_model_ids"] == ["vibethinker-3b-optiq-4bit"]
```

Update `_FIELDS`, JSON Schema required properties, profile JSON, and the Stage 2 fixture's `runtime_profile_revision` to `2`. Remove `routed_prefix_hypothesis` everywhere in the active profile contract.

- [x] **Step 4: Run focused profile and manifest tests and verify GREEN**

Run:

```zsh
/usr/bin/env PYTHONPATH=src python3 -m unittest \
  tests.test_stage_two_profile tests.test_stage_two_manifest -v
```

Expected: all tests pass.

- [x] **Step 5: Review checkpoint**

Inspect the diff and confirm only revision-2 profile contracts changed; do not create a live manifest.

---

### Task 2: Add Sanitized Model Descriptors And Exact Route Matching

**Files:**
- Modify: `src/local_model_runtime_evaluation/stage_two.py`
- Modify: `src/local_model_runtime_evaluation/stage_two_host.py`
- Modify: `tests/test_stage_two_engine.py`
- Modify: `tests/test_stage_two_host.py`

**Interfaces:**
- Produces: `ModelDescriptor(id: str, owned_by: str | None, root: str | None)`
- Changes: `StageTwoTransport.list_models(base_url: str) -> tuple[ModelDescriptor, ...]`
- Changes: `discover_route_identity(profile, direct_models, routed_models) -> str`

- [x] **Step 1: Write failing descriptor parsing tests**

Add transport tests whose `/v1/models` payload contains:

```json
{
  "data": [
    {
      "id": "mlx-community/VibeThinker-3B-OptiQ-4bit",
      "owned_by": "Optiq",
      "root": "mlx-community/VibeThinker-3B-OptiQ-4bit",
      "ignored": "discard-me"
    }
  ]
}
```

Assert the transport returns only `id`, `owned_by`, and `root`. Add malformed cases for missing/empty `id`, non-string metadata, and a non-list `data` value; each must raise `StageTwoError("transport_failed", ...)`.

- [x] **Step 2: Write failing exact route-identity tests**

Use `ModelDescriptor` fixtures to prove:

```python
exact = ModelDescriptor(
    "mlx-community/VibeThinker-3B-OptiQ-4bit", "Optiq", "upstream"
)
local = ModelDescriptor("vibethinker-3b-optiq-4bit", "osaurus", "local")
```

Required cases:

- exact routed descriptor passes
- local descriptor alone fails
- lowercased full repository ID fails
- `optiq/VibeThinker-3B-OptiQ-4bit` fails
- duplicate exact descriptors fail
- exact descriptor plus unrelated inventory passes
- direct inventory without an approved direct ID fails

- [x] **Step 3: Run focused tests and verify RED**

Run:

```zsh
/usr/bin/env PYTHONPATH=src python3 -m unittest \
  tests.test_stage_two_engine tests.test_stage_two_host -v
```

Expected: failures because descriptors and exact revision-2 matching are absent.

- [x] **Step 4: Implement descriptor sanitization and exact matching**

Add:

```python
@dataclass(frozen=True)
class ModelDescriptor:
    id: str
    owned_by: str | None = None
    root: str | None = None

    def evidence(self) -> dict[str, str]:
        result = {"id": self.id}
        if self.owned_by is not None:
            result["owned_by"] = self.owned_by
        if self.root is not None:
            result["root"] = self.root
        return result
```

Change `StageTwoReadOnlyTransport.list_models()` to validate and return descriptors. Change route discovery to compare `descriptor.id` with exact case-sensitive equality:

```python
approved_direct = {
    item.id for item in direct_models
    if item.id in profile.direct_model_identities
}
routed_candidates = [
    item for item in routed_models
    if item.id == profile.routed_model_id
]
if len(routed_candidates) != 1:
    raise StageTwoError(
        "route_identity_failed",
        "OptiQ routed model identity is missing or ambiguous",
    )
return routed_candidates[0].id
```

Explicitly fail profile parsing if `routed_model_id` appears in `rejected_local_model_ids`.

- [x] **Step 5: Run focused tests and verify GREEN**

Run the Task 2 test command again. Expected: all tests pass.

- [x] **Step 6: Review checkpoint**

Scan production Stage 2 code and confirm descriptors cannot retain arbitrary endpoint fields or response bodies.

---

### Task 3: Persist Endpoint Inventory Before Route Acceptance

**Files:**
- Modify: `src/local_model_runtime_evaluation/stage_two.py`
- Modify: `tests/test_stage_two_engine.py`
- Modify: `tests/test_stage_two_contract.py`

**Interfaces:**
- Produces artifact: `endpoint-inventory.json`
- Initial decision: `route_identity.status == "PENDING"`
- Successful decision: `route_identity.status == "PASS"`

- [x] **Step 1: Write a failing partial-evidence test**

Construct routed descriptors containing only the rejected local ID. Run the engine and assert it raises `route_identity_failed`, stops the controller, and leaves an endpoint inventory containing:

```python
{
    "expected_routed_model_id": "mlx-community/VibeThinker-3B-OptiQ-4bit",
    "rejected_local_model_ids": ["vibethinker-3b-optiq-4bit"],
    "route_identity": {"status": "PENDING"},
}
```

Assert both direct and routed arrays contain only descriptor evidence fields.

- [x] **Step 2: Strengthen the success-path test**

After a successful fake run, assert `endpoint-inventory.json` contains:

```python
"route_identity": {
    "status": "PASS",
    "discovered_routed_model_id": "mlx-community/VibeThinker-3B-OptiQ-4bit",
}
```

- [x] **Step 3: Run the engine tests and verify RED**

Run:

```zsh
/usr/bin/env PYTHONPATH=src python3 -m unittest tests.test_stage_two_engine -v
```

Expected: partial-evidence test fails because inventory is currently written after discovery.

- [x] **Step 4: Reorder evidence writes**

Build one sanitized inventory mapping immediately after both GETs. Write it with `PENDING`, call `discover_route_identity`, replace only the decision with `PASS`, and rewrite the JSON atomically. Do not catch or downgrade `StageTwoError`.

- [x] **Step 5: Run engine and artifact contract tests and verify GREEN**

Run:

```zsh
/usr/bin/env PYTHONPATH=src python3 -m unittest \
  tests.test_stage_two_engine tests.test_stage_two_contract -v
```

Expected: all tests pass, including partial evidence and successful checksum finalization.

- [x] **Step 6: Review checkpoint**

Confirm a failed route never produces `summary.json` or `checksums.txt`, while a successful run still finalizes the complete required bundle.

---

### Task 4: Reject Consumed Run IDs In Non-Live Readiness

**Files:**
- Modify: `src/local_model_runtime_evaluation/stage_two_gate_b_check.py`
- Modify: `tests/test_stage_two_gate_b_check.py`

**Interfaces:**
- Changes: `load_authorized_manifest(repository_root, run_id, output_root=None)`
- Raises: a bounded consumed-run error before reporting lifecycle readiness

- [x] **Step 1: Write the failing consumed-run test**

Create a temporary output root containing `stage2-20260714-001/state.json`, then call:

```python
load_authorized_manifest(
    repository_root,
    "stage2-20260714-001",
    output_root=temporary_output_root,
)
```

Assert it raises an error whose stable code is `run_id_consumed`. Add a control asserting an absent output directory returns the validated manifest.

- [x] **Step 2: Run focused checker tests and verify RED**

Run:

```zsh
/usr/bin/env PYTHONPATH=src python3 -m unittest tests.test_stage_two_gate_b_check -v
```

Expected: failure because consumed output is not inspected.

- [x] **Step 3: Implement the consumed-run guard**

After exact manifest resolution, select `output_root` from the injected test argument or the validated canonical manifest path. If `output_root / run_id` exists, raise a typed readiness error with code `run_id_consumed`. Do not inspect or mutate the historical directory.

Update the checker's profile registry lookup from revision `1` to revision `2`. Include `runtime_profile_id` and `runtime_profile_revision` in the bounded readiness report so operator output proves which contract was checked.

- [x] **Step 4: Run focused checker tests and verify GREEN**

Run the Task 4 command again. Expected: all tests pass.

- [x] **Step 5: Review checkpoint**

Run the checker against `stage2-20260714-001` and confirm it returns `STOPPED` with `error_kind: run_id_consumed`, zero activity counters, and no filesystem changes.

---

### Task 5: Reconcile Documentation And Run Full Verification

**Files:**
- Modify: `AGENTS.md`
- Modify: `docs/architecture.md`
- Modify: `docs/stage-2-gate-a.md`
- Modify: `docs/plugin-0.3.0-review.md` only if contract wording references revision `1`
- Modify: `10 Wiki/Projects/Local Model Benchmark Overhaul/Stage 2A Benchmark Coordinator Setup and Gate B Guide.md`
- Modify: `20 Records/Projects/Local Model Stack/Tier 5/Local Model Runtime Evaluation Harness Stage 2 Gate C Review - 2026-07-14.md`
- Modify: `00 System/Audit/Agent Activity/2026-07-14.md`

**Interfaces:**
- Documents revision `2` as implemented but not live-authorized
- Preserves failed revision-1 evidence and plugin `0.3.0` rollback history

- [x] **Step 1: Update canonical project documentation**

Replace the active `optiq/` hypothesis with the exact upstream ID contract. Document sanitized descriptor evidence, inventory-before-validation ordering, consumed-run protection, and diagnostic-only ownership metadata. Keep revision `1` only in historical failure sections.

- [x] **Step 2: Run stale-assumption scans**

Run:

```zsh
rg -n "routed_prefix_hypothesis|optiq/VibeThinker|revision 1" \
  AGENTS.md config schemas src tests docs
```

Expected: matches only in historical documents or explicit rejection tests.

Run:

```zsh
rg -n "chat/completions|/responses|/messages|POST|warm.?up|benchmark|quantiz|convert" \
  src/local_model_runtime_evaluation/stage_two.py \
  src/local_model_runtime_evaluation/stage_two_host.py
```

Expected: no executable Stage 2 request path for forbidden operations.

- [x] **Step 3: Run the complete Python suite**

Run with loopback permission:

```zsh
/usr/bin/env PYTHONPATH=src python3 -m unittest discover -s tests -v
```

Expected: all tests pass.

- [x] **Step 4: Confirm the unchanged native plugin contract**

Run:

```zsh
swift test --package-path plugins/osaurus-evaluation-harness
```

Expected: all native tests pass; no plugin source or version change is required.

- [x] **Step 5: Validate JSON and vault documentation**

Parse the runtime profile and schemas with `jq`, then run:

```zsh
python3 '00 System/Automation/validate_vault.py' '/Users/jrazz/Documents/ObsidianNotes'
```

Expected: JSON parsing and vault validation pass.

- [x] **Step 6: Run non-live host readiness without a new manifest**

Run:

```zsh
/Users/jrazz/Dev/active/local-model-runtime-evaluation-harness/bin/lmre-stage2-gate-b-check
```

Expected: `READY_FOR_MANIFEST_AUTHORIZATION`, with profile revision `2`, plugin `0.3.0`, free port `8080`, no OptiQ process, and zero activity counters.

- [x] **Step 7: Final review checkpoint**

Report changed files, test counts, non-live readiness, rollback posture, and the exact manual actions remaining. Do not create a new run ID or manifest until Jason explicitly authorizes one.
