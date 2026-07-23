# Slice 1c Reconnect-Tap Elimination Gate A Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Land Design 1 Gate A only: profile revision `5` with `verify_routed_id_only_no_tap`, harness inventory wait-and-verify without “tap” language/events, and docs supersession — fake-only; no live contact.

**Architecture:** Clone Gemma harness profile r4 → r5 with hardened activation. Teach `StageTwoInferenceEngine` to accept the new activation on harness contracts and rename preflight inventory-wait events away from `provider_reconnect_tap_*`. Keep schema `3.5.0` / revision `4` smoke pairing fail-closed and sealed `003` untouched. Do not implement schema `3.6.0` here.

**Tech Stack:** Python 3 stdlib, `unittest`, existing Stage 2 profiles/inference engine. Prefer `/opt/homebrew/bin/python3`. Plugin `0.3.0` unchanged.

## Global Constraints

- Spec: `docs/superpowers/specs/2026-07-23-slice-1c-reconnect-tap-elimination-design.md`
- Depends on sealed harness smoke `stage2-20260723-003` and pin-confirm `0.4.2`
- No live manifests, run IDs, POSTs, provider edits, OptiQ upgrade, plugin rebuild, or `3.6.0` benchmark work
- Do not mutate sealed r2/r3/r4 parser constants used by sealed cohorts beyond additive r5
- No commits of `config/matrix/omlx-roots/**` or `.harness-lifecycle/**`
- Prefer `/opt/homebrew/bin/python3` with `PYTHONPATH=src`

## Locked names

| Field | Value |
|---|---|
| Profile id | `gemma-4-12b-optiq-4bit` |
| Profile revision | `5` |
| `service_ownership` | `harness` |
| `provider_activation` | `verify_routed_id_only_no_tap` (exact) |
| Inventory wait events | `routed_inventory_waiting`, `routed_inventory_ready` (replace tap-named events) |
| Wait window | 300 seconds (unchanged) |
| Historical smoke | `3.5.0` / r4 / `verify_routed_id_only` — still loadable; factory pairing unchanged |

## File map

| Area | Files |
|---|---|
| Profile | Create `config/runtime-profiles/gemma-4-12b-optiq-4bit-r5.json`; modify `src/local_model_runtime_evaluation/stage_two_profiles.py` |
| Engine | Modify `src/local_model_runtime_evaluation/stage_two_inference.py` (`_validate_provider_activation`, `_observe_routes_for_preflight`) |
| Docs | Modify `docs/superpowers/notes/2026-07-22-slice-1c-provider-reconnect-note.md`; `docs/stage-2-harness-unattended-gate-a.md`; `AGENTS.md` (brief); Design 1 spec status line optional |
| Tests | Modify `tests/test_stage_two_profile.py`; `tests/test_stage_two_inference_engine.py` (or small focused harness wait tests) |

---

### Task 1: Profile revision 5 loader

**Files:**
- Create: `config/runtime-profiles/gemma-4-12b-optiq-4bit-r5.json`
- Modify: `src/local_model_runtime_evaluation/stage_two_profiles.py`
- Test: `tests/test_stage_two_profile.py`

**Interfaces:**
- Consumes: existing `_parse_gemma_revision_four`, `_GEMMA_R4_PACKAGE_VERSIONS`, `_REVISION_THREE_FIELDS`, Gemma pin constants
- Produces: `_parse_gemma_revision_five(data: dict) -> RuntimeProfile`; registry loads revision `"5"` with `provider_activation == "verify_routed_id_only_no_tap"`

- [ ] **Step 1: Write failing profile tests**

Add to `tests/test_stage_two_profile.py` (mirror r4 helpers):

```python
def _gemma_revision_five_fixture(self) -> dict:
    data = self._gemma_revision_four_fixture()
    data["revision"] = "5"
    data["provider_activation"] = "verify_routed_id_only_no_tap"
    return data

def _write_gemma_revision_five_fixture(self, temp: str, data: dict | None = None) -> None:
    payload = self._gemma_revision_five_fixture() if data is None else data
    Path(temp, "gemma-4-12b-optiq-4bit-r5.json").write_text(json.dumps(payload))

def test_gemma_revision_five_profile_loads_with_no_tap_activation(self) -> None:
    with tempfile.TemporaryDirectory() as temp:
        self._write_gemma_revision_five_fixture(temp)
        profile = RuntimeProfileRegistry(Path(temp)).get("gemma-4-12b-optiq-4bit", "5")
        self.assertEqual(profile.revision, "5")
        self.assertEqual(profile.service_ownership, "harness")
        self.assertEqual(profile.provider_activation, "verify_routed_id_only_no_tap")
        self.assertEqual(profile.runtime_version, "0.4.2")

def test_gemma_revision_five_rejects_legacy_verify_routed_id_only(self) -> None:
    with tempfile.TemporaryDirectory() as temp:
        data = self._gemma_revision_five_fixture()
        data["provider_activation"] = "verify_routed_id_only"
        self._write_gemma_revision_five_fixture(temp, data)
        with self.assertRaises(RuntimeProfileError):
            RuntimeProfileRegistry(Path(temp)).get("gemma-4-12b-optiq-4bit", "5")

def test_gemma_revision_four_still_rejects_no_tap_activation(self) -> None:
    with tempfile.TemporaryDirectory() as temp:
        data = self._gemma_revision_four_fixture()
        data["provider_activation"] = "verify_routed_id_only_no_tap"
        self._write_gemma_revision_four_fixture(temp, data)
        with self.assertRaises(RuntimeProfileError):
            RuntimeProfileRegistry(Path(temp)).get("gemma-4-12b-optiq-4bit", "4")
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/jrazz/Dev/active/local-model-runtime-evaluation-harness
PYTHONPATH=src /opt/homebrew/bin/python3 -m unittest \
  tests.FAKESECRET_a3b4c5d6e7f8g9h0i1j2 \
  tests.FAKESECRET_m1n2o3p4q5r6s7t8u9v0 \
  tests.FAKESECRET_i2j3k4l5m6n7o8p9q0r1 \
  -v
```

Expected: FAIL (revision 5 not approved / not loadable).

- [ ] **Step 3: Implement r5 JSON + parser**

1. Copy `config/runtime-profiles/gemma-4-12b-optiq-4bit-r4.json` → `…-r5.json`.
2. Set `"revision": "5"` and `"provider_activation": "verify_routed_id_only_no_tap"`. Keep all pin/hash/argv fields identical to r4.
3. In `stage_two_profiles.py` `_parse`:
   - Add `if profile_id == "gemma-4-12b-optiq-4bit" and revision == "5": return _parse_gemma_revision_five(data)`.
4. Add `_parse_gemma_revision_five` by cloning `_parse_gemma_revision_four` with:
   - error string `"revision 5 profile fields are invalid"`
   - require `data["provider_activation"] == "verify_routed_id_only_no_tap"`
   - require `data["service_ownership"] == "harness"`
   - reuse `_GEMMA_R4_PACKAGE_VERSIONS` (same `0.4.2` pin)

- [ ] **Step 4: Run tests to verify they pass**

```bash
PYTHONPATH=src /opt/homebrew/bin/python3 -m unittest tests.test_stage_two_profile -q
```

Expected: OK. Also:

```bash
PYTHONPATH=src /opt/homebrew/bin/python3 -c \
  "from pathlib import Path; from local_model_runtime_evaluation.stage_two_profiles import RuntimeProfileRegistry; \
p=RuntimeProfileRegistry(Path('config/runtime-profiles')).get('gemma-4-12b-optiq-4bit','5'); \
assert p.provider_activation=='verify_routed_id_only_no_tap'"
```

- [ ] **Step 5: Commit**

```bash
git add config/runtime-profiles/gemma-4-12b-optiq-4bit-r5.json \
  src/local_model_runtime_evaluation/stage_two_profiles.py \
  tests/test_stage_two_profile.py
git commit -m "$(cat <<'EOF'
Add Gemma OptiQ profile revision 5 with no-tap provider activation.

EOF
)"
```

---

### Task 2: Activation validation + inventory-wait event rename

**Files:**
- Modify: `src/local_model_runtime_evaluation/stage_two_inference.py`
- Test: `tests/test_stage_two_inference_engine.py`

**Interfaces:**
- Consumes: `RuntimeProfile.provider_activation`, harness `_harness` flag, `_observe_routes`
- Produces: `_validate_provider_activation` accepts `verify_routed_id_only` **or** `verify_routed_id_only_no_tap` when `_harness`; `_observe_routes_for_preflight` emits `routed_inventory_waiting` / `routed_inventory_ready` (never `provider_reconnect_tap_*`)

- [ ] **Step 1: Write failing engine tests**

Add tests that use the existing harness fixture/engine construction pattern from `test_harness_preflight_and_cleanup_record_controller_lifecycle_actions`:

```python
def test_harness_accepts_no_tap_provider_activation_on_profile_replace(self) -> None:
    # Build harness engine as in existing harness preflight test, but
    # profile = replace(harness_profile, provider_activation="verify_routed_id_only_no_tap")
    # (revision stays "4" so contract validation still passes).
    # preflight() must succeed; service-events must NOT contain "provider_reconnect_tap_".

def test_harness_inventory_wait_emits_routed_inventory_events_not_tap(self) -> None:
    # FakeTransport: first N list_models on routed URL omit required id
    # (raise route_identity_failed path), then succeed.
    # After preflight, service-events.jsonl contains routed_inventory_waiting
    # and routed_inventory_ready; assert "provider_reconnect_tap" not in file.

def test_harness_rejects_unknown_provider_activation(self) -> None:
    # replace(..., provider_activation="automatic") on harness profile
    # preflight → StageTwoError provider_activation_failed
```

Implement the wait test by making routed `list_models` fail identity once then succeed (inspect `FakeTransport` / `discover_route_identity` failure mode used elsewhere). If the existing fake cannot delay identity, add the smallest fake hook needed in the test file only.

- [ ] **Step 2: Run tests to verify they fail**

```bash
PYTHONPATH=src /opt/homebrew/bin/python3 -m unittest \
  tests.FAKESECRET_c4d5e6f7g8h9i0j1k2l3 \
  tests.FAKESECRET_u2v3w4x5y6z7a8b9c0d1 \
  tests.FAKESECRET_q2r3s4t5u6v7w8x9y0z1 \
  -v
```

Expected: FAIL (activation rejected and/or old tap event names).

- [ ] **Step 3: Implement minimal engine changes**

In `_validate_provider_activation`:

```python
def _validate_provider_activation(self) -> None:
    activation = self.profile.provider_activation
    if activation in {"verify_routed_id_only", "verify_routed_id_only_no_tap"}:
        if not self._harness:
            raise StageTwoError(
                "provider_activation_failed",
                f"{activation} requires the harness-unattended contract",
            )
        return
    if activation != "operator_reconnect_required":
        raise StageTwoError(
            "provider_activation_failed",
            "unsupported provider activation policy",
        )
```

In `_observe_routes_for_preflight`:

- Update docstring to wait-and-verify / no operator tap API.
- Replace event names:
  - `provider_reconnect_tap_waiting` → `routed_inventory_waiting`
  - `provider_reconnect_tap_observed` → `routed_inventory_ready`
- Keep 300s deadline and 2.0s sleep; still re-raise last `route_identity_failed` on timeout.

Do **not** change `3.5.0`/r4 factory or manifest pairing.

- [ ] **Step 4: Run focused + harness regression tests**

```bash
PYTHONPATH=src /opt/homebrew/bin/python3 -m unittest \
  tests.test_stage_two_inference_engine \
  tests.test_stage_two_harness_lifecycle \
  -q
```

Expected: OK. Grep guarantee:

```bash
rg -n 'provider_reconnect_tap_' src/local_model_runtime_evaluation/stage_two_inference.py \
  && exit 1 || echo 'tap events removed from engine'
```

- [ ] **Step 5: Commit**

```bash
git add src/local_model_runtime_evaluation/stage_two_inference.py \
  tests/test_stage_two_inference_engine.py
git commit -m "$(cat <<'EOF'
Rename harness inventory-wait events and accept no-tap activation.

EOF
)"
```

---

### Task 3: Docs supersession + Gate A status

**Files:**
- Modify: `docs/superpowers/notes/2026-07-22-slice-1c-provider-reconnect-note.md`
- Modify: `docs/stage-2-harness-unattended-gate-a.md`
- Modify: `AGENTS.md` (Slice 1c / harness bullet only)
- Modify: `docs/superpowers/specs/2026-07-23-slice-1c-reconnect-tap-elimination-design.md` (status → Gate A landed)

**Interfaces:**
- Consumes: landed r5 + engine behavior from Tasks 1–2
- Produces: supersession banners; no deletions of historical note body

- [ ] **Step 1: Update reconnect note**

At top of `docs/superpowers/notes/2026-07-22-slice-1c-provider-reconnect-note.md`, after the title, add:

```markdown
> **Supersession (2026-07-23):** Profile revision `5` uses
> `verify_routed_id_only_no_tap` with wait-and-verify only (no operator tap).
> Design: `docs/superpowers/specs/2026-07-23-slice-1c-reconnect-tap-elimination-design.md`.
> Historical `3.5.0` / revision `4` / sealed `stage2-20260723-003` body below
> remains evidence for the ≤1-tap policy era.
```

Keep the historical locked-policy table intact.

- [ ] **Step 2: Update Gate A + AGENTS pointers**

In `docs/stage-2-harness-unattended-gate-a.md`, add under Current Decision (status-only):

```markdown
**Follow-on Design 1 (Gate A):** reconnect-tap elimination landed (profile
revision `5`, `verify_routed_id_only_no_tap`). Live inventory-wait proof and
schema `3.6.0` harness benchmark remain separately gated — see
`docs/superpowers/specs/2026-07-23-slice-1c-reconnect-tap-elimination-design.md`.
```

In `AGENTS.md` harness-unattended section, one bullet:

```markdown
- Profile revision `5` (`verify_routed_id_only_no_tap`) is the no-tap harness
  pin for follow-on lanes; sealed smoke `003` remains revision `4`.
```

Set Design 1 spec **Status** to Gate A landed (fake-only; live proof still gated).

- [ ] **Step 3: Run docs-adjacent tests still green**

```bash
PYTHONPATH=src /opt/homebrew/bin/python3 -m unittest \
  tests.test_stage_two_profile \
  tests.test_stage_two_inference_engine \
  tests.test_stage_two_harness_lifecycle \
  tests.test_stage_two_factory \
  -q
```

Expected: OK.

- [ ] **Step 4: Commit**

```bash
git add docs/superpowers/notes/2026-07-22-slice-1c-provider-reconnect-note.md \
  docs/stage-2-harness-unattended-gate-a.md \
  AGENTS.md \
  docs/superpowers/specs/2026-07-23-slice-1c-reconnect-tap-elimination-design.md
git commit -m "$(cat <<'EOF'
Document reconnect-tap elimination Gate A and profile revision 5.

EOF
)"
```

---

### Task 4: Gate A verification sweep

**Files:** none new (verification only)

- [ ] **Step 1: Full focused Python sweep**

```bash
PYTHONPATH=src /opt/homebrew/bin/python3 -m unittest \
  tests.test_stage_two_profile \
  tests.test_stage_two_inference_engine \
  tests.test_stage_two_harness_lifecycle \
  tests.test_stage_two_factory \
  tests.test_stage_two_manifest \
  tests.test_policy \
  -q
```

Expected: OK.

- [ ] **Step 2: Static boundary scans**

```bash
rg -n 'provider_reconnect_tap_' src/local_model_runtime_evaluation --glob '*.py' \
  && exit 1 || echo 'PASS: no tap event symbols in src'
rg -n 'verify_routed_id_only_no_tap' config/runtime-profiles/gemma-4-12b-optiq-4bit-r5.json
rg -n '3\.6\.0|harness_route_benchmark' src/local_model_runtime_evaluation --glob '*.py' \
  && exit 1 || echo 'PASS: no 3.6.0 bench leakage in Design 1'
```

Expected: first and third PASS empty; r5 JSON contains the enum.

- [ ] **Step 3: Confirm no live artifacts created**

```bash
ls manifests/stage-2-optiq-harness-route-00*.json 2>/dev/null | head
# Do not create new live manifests. Existing 001–003 are historical only.
```

- [ ] **Step 4: Final commit only if sweep found fixes**

If Step 1–2 required code fixes, commit them. Otherwise no empty commit.

---

## Spec coverage (self-review)

| Spec requirement | Task |
|---|---|
| Profile r5 + `verify_routed_id_only_no_tap` | Task 1 |
| r4 historical still loadable; reject cross-activation | Task 1 |
| Activation validator for no-tap on harness | Task 2 |
| Inventory wait fail-closed (existing timeout) + rename events | Task 2 |
| No custom reconnect API / no provider edit | Global + Task 2 (behavior unchanged aside from events/enum) |
| Reconnect note supersession | Task 3 |
| Fake-only; no live; no `3.6.0` | Global + Task 4 scans |
| Live inventory proof | **Out of Gate A** (separately gated after this plan) |

## Placeholder scan

No TBD/TODO steps. Event names and enum strings are exact.
