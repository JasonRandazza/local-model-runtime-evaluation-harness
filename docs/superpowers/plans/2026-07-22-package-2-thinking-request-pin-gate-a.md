# Package 2 Thinking Request-Pin + Gate B Observe Gate A Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Land fake-only Gate A for Package 2 thinking request-pin (pin revision `2` with required `chat_template_kwargs.enable_thinking=true` on every POST) plus diagnostic Gate B `~/.omlx` profile observe — without live POSTs, new run IDs, D3, or D4.

**Architecture:** New pin JSON r2 + fail-closed loader field. `OmlxThinkingTransport` always forwards pin kwargs into optional `LoopbackTransport.chat(chat_template_kwargs=…)`. Gate B adds soft `omlx_profile_observe` from `model_settings.json` / optional `model_profiles.json` without changing READY decisions. Docs name D4 beside D3.

**Tech Stack:** Python 3 stdlib, `unittest`. Prefer `/opt/homebrew/bin/python3`. Plugin `0.3.0` unchanged.

## Global Constraints

- Design: `docs/superpowers/specs/2026-07-22-package-2-thinking-request-pin-design.md`
- Do **not** rewrite `config/omlx-pins/omlx-0.5.3-thinking-r1.json` or sealed Gate C/D/D2 evidence
- No live oMLX/OptiQ contact, no new run IDs, no D3/D4 implementation
- Never open or echo `~/.omlx/settings.json` (secrets)
- Stage 2 OptiQ `LoopbackTransport.chat` callers must keep working with kwargs omitted

## File map

| Area | Files |
|---|---|
| Pin | Create `config/omlx-pins/omlx-0.5.3-thinking-r2.json`; modify `omlx_thinking_pin.py` |
| Transport | Modify `transport.py`, `omlx_thinking_transport.py` |
| Gate B | Modify `omlx_thinking_gate_b_check.py` |
| Tests | `tests/test_omlx_thinking_pin.py`, `tests/test_omlx_thinking_transport.py`, `tests/test_omlx_thinking_runner.py` (FakeLoopback signature), `tests/test_omlx_thinking_gate_b_check.py`, `tests/test_transport.py` |
| Docs | `docs/package-2-omlx-thinking-gate-b.md`, `docs/package-2-omlx-thinking-gate-d.md`, `docs/package-2-omlx-thinking-d2.md`, `docs/architecture.md` |

---

### Task 1: Pin revision 2 + loader

**Files:**
- Create: `config/omlx-pins/omlx-0.5.3-thinking-r2.json`
- Modify: `src/local_model_runtime_evaluation/omlx_thinking_pin.py`
- Test: `tests/test_omlx_thinking_pin.py`

**Interfaces:**
- Consumes: existing pin constants / `OmlxThinkingPin.load`
- Produces:
  - `PIN_REVISION = "2"`
  - `REQUIRED_CHAT_TEMPLATE_KWARGS = {"enable_thinking": True}` (frozen mapping / exact dict)
  - `OmlxThinkingPin.required_chat_template_kwargs: tuple[tuple[str, object], ...]` **or** `Mapping` frozen as `dict[str, object]` — prefer `dict[str, object]` returned as a new `dict` copy from a module constant so callers cannot mutate pin state; simplest approved shape: `tuple` of pairs is awkward for JSON bool — use `Mapping[str, object]` via `types.MappingProxyType` **or** store `dict[str, bool]` on the dataclass as `required_chat_template_kwargs: dict[str, object]` built once in `load` from validated JSON (frozen dataclass still allows mutating the dict — so return `MappingProxyType(dict(...))` typed as `Mapping[str, object]`)
  - `default_pin_path()` → `…/omlx-0.5.3-thinking-r2.json`
  - `_PIN_REQUIRED` includes `"required_chat_template_kwargs"`

- [ ] **Step 1: Write the failing tests**

In `tests/test_omlx_thinking_pin.py`, update `test_loads_canonical_pin` expectations to revision `"2"` and assert kwargs; add rejection tests:

```python
def test_loads_canonical_pin(self) -> None:
    pin = OmlxThinkingPin.load(self.path)
    self.assertEqual(pin.revision, "2")
    self.assertEqual(dict(pin.required_chat_template_kwargs), {"enable_thinking": True})
    # …retain other r1 identity assertions (pin_id, version, model, start_command)…


def test_rejects_historical_r1_pin_path(self) -> None:
    r1 = Path("config/omlx-pins/omlx-0.5.3-thinking-r1.json")
    with self.assertRaises(OmlxThinkingPinError):
        OmlxThinkingPin.load(r1)


def test_rejects_missing_required_chat_template_kwargs(self) -> None:
    data = json.loads(self.path.read_text(encoding="utf-8"))
    del data["required_chat_template_kwargs"]
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "pin.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        with self.assertRaises(OmlxThinkingPinError):
            OmlxThinkingPin.load(path)


def test_rejects_enable_thinking_false(self) -> None:
    data = json.loads(self.path.read_text(encoding="utf-8"))
    data["required_chat_template_kwargs"] = {"enable_thinking": False}
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "pin.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        with self.assertRaises(OmlxThinkingPinError):
            OmlxThinkingPin.load(path)


def test_rejects_extra_chat_template_kwarg_keys(self) -> None:
    data = json.loads(self.path.read_text(encoding="utf-8"))
    data["required_chat_template_kwargs"] = {
        "enable_thinking": True,
        "foo": True,
    }
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "pin.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        with self.assertRaises(OmlxThinkingPinError):
            OmlxThinkingPin.load(path)
```

Keep `test_accepts_allowlisted_extra_body_keys` working: when mutating a temp copy of the canonical r2 pin, leave `required_chat_template_kwargs` intact.

- [ ] **Step 2: Run tests to verify they fail**

```bash
PYTHONPATH=src /opt/homebrew/bin/python3 -m unittest \
  tests.test_omlx_thinking_pin.OmlxThinkingPinTest.test_loads_canonical_pin \
  tests.test_omlx_thinking_pin.OmlxThinkingPinTest.test_rejects_historical_r1_pin_path -v
```

Expected: FAIL (revision still `1` / r1 still loads / kwargs missing).

- [ ] **Step 3: Create r2 pin JSON**

`config/omlx-pins/omlx-0.5.3-thinking-r2.json` — copy r1, set `"revision": "2"`, add:

```json
"required_chat_template_kwargs": {
  "enable_thinking": true
}
```

Do **not** modify r1.

- [ ] **Step 4: Implement loader**

In `omlx_thinking_pin.py`:

```python
from types import MappingProxyType
from collections.abc import Mapping

PIN_REVISION = "2"
REQUIRED_CHAT_TEMPLATE_KWARGS: Mapping[str, object] = MappingProxyType(
    {"enable_thinking": True}
)

# add "required_chat_template_kwargs" to _PIN_REQUIRED

def default_pin_path() -> Path:
    return REPOSITORY_ROOT / "config" / "omlx-pins" / "omlx-0.5.3-thinking-r2.json"


@dataclass(frozen=True)
class OmlxThinkingPin:
    # …existing fields…
    required_chat_template_kwargs: Mapping[str, object]

    @classmethod
    def load(cls, path: Path) -> OmlxThinkingPin:
        # …existing validation…
        kwargs = _required_chat_template_kwargs(data["required_chat_template_kwargs"])
        return cls(
            # …existing args…,
            kwargs,
        )


def _required_chat_template_kwargs(value: object) -> Mapping[str, object]:
    if not isinstance(value, dict):
        raise OmlxThinkingPinError("pin required_chat_template_kwargs must be an object")
    if set(value) != {"enable_thinking"}:
        raise OmlxThinkingPinError("pin required_chat_template_kwargs keys are invalid")
    if value.get("enable_thinking") is not True:
        raise OmlxThinkingPinError("pin required_chat_template_kwargs.enable_thinking must be true")
    return MappingProxyType({"enable_thinking": True})
```

- [ ] **Step 5: Run pin tests**

```bash
PYTHONPATH=src /opt/homebrew/bin/python3 -m unittest tests.test_omlx_thinking_pin -v
```

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add config/omlx-pins/omlx-0.5.3-thinking-r2.json \
  src/local_model_runtime_evaluation/omlx_thinking_pin.py \
  tests/test_omlx_thinking_pin.py
git commit -m "$(cat <<'EOF'
Add oMLX thinking pin revision 2 with required enable_thinking kwargs.

EOF
)"
```

---

### Task 2: Transport request-pin plumbing

**Files:**
- Modify: `src/local_model_runtime_evaluation/transport.py`
- Modify: `src/local_model_runtime_evaluation/omlx_thinking_transport.py`
- Modify: `tests/test_omlx_thinking_transport.py`
- Modify: `tests/test_omlx_thinking_runner.py` (FakeLoopbackTransport.chat signature)
- Modify: `tests/test_transport.py` (one body-capture test)

**Interfaces:**
- Consumes: `OmlxThinkingPin.required_chat_template_kwargs`
- Produces:
  - `LoopbackTransport.chat(..., chat_template_kwargs: Mapping[str, object] | None = None)`
  - `LoopbackClient` Protocol updated with the same optional kw-only-or-positional-optional arg
  - `OmlxThinkingTransport` stores `chat_template_kwargs: Mapping[str, object]` from pin in `for_pin`; `chat()` always forwards it

- [ ] **Step 1: Write the failing transport tests**

Update `FakeLoopback` / runner fake to accept and record kwargs:

```python
def chat(
    self,
    base_url: str,
    model_id: str,
    prompt: str,
    max_tokens: int,
    credential: object | None,
    cancel: object | None = None,
    chat_template_kwargs: object | None = None,
) -> TransportResult:
    self.chat_calls.append(
        (base_url, model_id, prompt, max_tokens, credential, chat_template_kwargs)
    )
    # …same return…
```

Add:

```python
def test_chat_forwards_required_chat_template_kwargs(self) -> None:
    transport = OmlxThinkingTransport.for_pin(self.pin, loopback=self.loopback)
    transport.chat("hello", 512)
    kwargs = self.loopback.chat_calls[0][5]
    self.assertEqual(dict(kwargs), {"enable_thinking": True})
```

In `tests/test_transport.py`, extend `Handler` to store the last POST body, then:

```python
def test_chat_includes_optional_chat_template_kwargs_in_body(self) -> None:
    LoopbackTransport({self.base_url}).chat(
        self.base_url,
        "VibeThinker-3B-MLX-oQ4",
        "hello",
        16,
        None,
        chat_template_kwargs={"enable_thinking": True},
    )
    self.assertEqual(
        Handler.last_post_body.get("chat_template_kwargs"),
        {"enable_thinking": True},
    )


def test_chat_omits_chat_template_kwargs_when_absent(self) -> None:
    LoopbackTransport({self.base_url}).chat(
        self.base_url, "VibeThinker-3B-MLX-oQ4", "hello", 16, None,
    )
    self.assertNotIn("chat_template_kwargs", Handler.last_post_body)
```

In `Handler.do_POST`, replace the ignored `json.loads(...)` with:

```python
Handler.last_post_body = json.loads(self.rfile.read(length))
```

and reset `last_post_body = {}` in test `setUp` alongside other Handler resets.

- [ ] **Step 2: Run tests to verify they fail**

```bash
PYTHONPATH=src /opt/homebrew/bin/python3 -m unittest \
  tests.test_omlx_thinking_transport.OmlxThinkingTransportTest.test_chat_forwards_required_chat_template_kwargs \
  tests.test_transport.TransportTest.test_chat_includes_optional_chat_template_kwargs_in_body -v
```

Expected: FAIL (signature / body missing kwargs).

- [ ] **Step 3: Implement transport changes**

`transport.py` — extend `chat`:

```python
def chat(
    self, base_url: str, model_id: str, prompt: str, max_tokens: int,
    credential: Credential | None, cancel: threading.Event | None = None,
    chat_template_kwargs: Mapping[str, object] | None = None,
) -> TransportResult:
    body: dict[str, object] = {
        "model": model_id,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0,
        "max_tokens": max_tokens,
        "stream": True,
        "stream_options": {"include_usage": True},
    }
    if chat_template_kwargs:
        body["chat_template_kwargs"] = dict(chat_template_kwargs)
    payload = json.dumps(body).encode()
    # …remainder unchanged…
```

Add `from collections.abc import Mapping` if missing.

`omlx_thinking_transport.py`:

```python
@dataclass(repr=False)
class OmlxThinkingTransport:
    base_url: str
    model_id: str
    credential: Credential
    loopback: LoopbackClient
    chat_template_kwargs: Mapping[str, object] = field(default_factory=dict)

    @classmethod
    def for_pin(...) -> OmlxThinkingTransport:
        # …
        return cls(
            pin.base_url,
            pin.model_id,
            resolved,
            client,
            dict(pin.required_chat_template_kwargs),
        )

    def chat(self, prompt: str, max_tokens: int) -> ThinkingChatResponse:
        result = self.loopback.chat(
            self.base_url,
            self.model_id,
            prompt,
            max_tokens,
            self.credential,
            chat_template_kwargs=self.chat_template_kwargs or None,
        )
        # …map result unchanged…
```

Update `LoopbackClient` Protocol `chat` signature to include optional `chat_template_kwargs`.

Update existing transport unit tests that unpack `chat_calls[0]` tuples to the new 6-tuple shape (kwargs may be `None` for direct `OmlxThinkingTransport(...)` construction without `for_pin` — prefer requiring kwargs on the dataclass so direct construction in older tests passes `chat_template_kwargs=dict(self.pin.required_chat_template_kwargs)` or relies on default empty and assert `for_pin` path for the pin requirement).

- [ ] **Step 4: Run related tests**

```bash
PYTHONPATH=src /opt/homebrew/bin/python3 -m unittest \
  tests.test_omlx_thinking_transport \
  tests.test_omlx_thinking_runner \
  tests.test_transport \
  tests.test_omlx_thinking_pin -q
```

Expected: OK

- [ ] **Step 5: Commit**

```bash
git add src/local_model_runtime_evaluation/transport.py \
  src/local_model_runtime_evaluation/omlx_thinking_transport.py \
  tests/test_omlx_thinking_transport.py \
  tests/test_omlx_thinking_runner.py \
  tests/test_transport.py
git commit -m "$(cat <<'EOF'
Pin thinking enable_thinking into every oMLX chat POST body.

EOF
)"
```

---

### Task 3: Gate B profile observe + follow-on docs

**Files:**
- Modify: `src/local_model_runtime_evaluation/omlx_thinking_gate_b_check.py`
- Modify: `tests/test_omlx_thinking_gate_b_check.py`
- Modify: `docs/package-2-omlx-thinking-gate-b.md`
- Modify: `docs/package-2-omlx-thinking-gate-d.md`
- Modify: `docs/package-2-omlx-thinking-d2.md`
- Modify: `docs/architecture.md` (Package 2 sentence only — name pin r2 Gate A + D4 deferred)

**Interfaces:**
- Consumes: pin `model_id`
- Produces:
  - `observe_omlx_profile(model_id: str, *, omlx_home: Path | None = None) -> dict[str, object]`
  - `collect_readiness(..., omlx_home: Path | None = None)` includes `omlx_profile_observe`
  - `build_gate_b_report` copies `omlx_profile_observe` into the report **without** using it for `decision`

- [ ] **Step 1: Write the failing Gate B tests**

```python
def test_observe_omlx_profile_ok_from_temp_home(self) -> None:
    with tempfile.TemporaryDirectory() as directory:
        home = Path(directory)
        (home / "model_settings.json").write_text(
            json.dumps({
                "version": 1,
                "models": {
                    PIN_MODEL_ID: {
                        "enable_thinking": True,
                        "active_profile_name": "thinking",
                    }
                },
            }),
            encoding="utf-8",
        )
        (home / "model_profiles.json").write_text(
            json.dumps({
                "version": 1,
                "profiles": {
                    PIN_MODEL_ID: {
                        "thinking": {
                            "settings": {"enable_thinking": True},
                        }
                    }
                },
            }),
            encoding="utf-8",
        )
        observed = gate_b_mod.observe_omlx_profile(PIN_MODEL_ID, omlx_home=home)
        self.assertEqual(observed["status"], "ok")
        self.assertIs(observed["enable_thinking"], True)
        self.assertEqual(observed["active_profile_name"], "thinking")
        self.assertIs(observed["profile_enable_thinking"], True)


def test_observe_omlx_profile_file_missing(self) -> None:
    with tempfile.TemporaryDirectory() as directory:
        observed = gate_b_mod.observe_omlx_profile(
            PIN_MODEL_ID, omlx_home=Path(directory),
        )
        self.assertEqual(observed["status"], "file_missing")


def test_ready_decision_ignores_profile_observe_mismatch(self) -> None:
    with tempfile.TemporaryDirectory() as directory:
        home = Path(directory)
        (home / "model_settings.json").write_text(
            json.dumps({
                "version": 1,
                "models": {
                    PIN_MODEL_ID: {
                        "enable_thinking": False,
                        "active_profile_name": None,
                    }
                },
            }),
            encoding="utf-8",
        )
        readiness = collect_readiness(
            self.pin,
            installed_version="0.5.3",
            port_free=lambda _port: True,
            transport=FakeTransport(),
            observe_busy_port=False,
            omlx_home=home,
        )
        report = build_gate_b_report(readiness)
        self.assertEqual(report["decision"], "READY_FOR_LIVE_AUTHORIZATION")
        self.assertIs(report["omlx_profile_observe"]["enable_thinking"], False)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
PYTHONPATH=src /opt/homebrew/bin/python3 -m unittest \
  tests.test_omlx_thinking_gate_b_check.OmlxThinkingGateBCheckTest.test_observe_omlx_profile_ok_from_temp_home -v
```

Expected: FAIL (`observe_omlx_profile` missing).

- [ ] **Step 3: Implement observe helpers**

```python
def observe_omlx_profile(
    model_id: str,
    *,
    omlx_home: Path | None = None,
) -> dict[str, object]:
    home = omlx_home if omlx_home is not None else Path.home() / ".omlx"
    settings_path = home / "model_settings.json"
    if not settings_path.is_file():
        return {
            "status": "file_missing",
            "enable_thinking": None,
            "active_profile_name": None,
            "profile_enable_thinking": None,
        }
    try:
        payload = json.loads(settings_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {
            "status": "unreadable",
            "enable_thinking": None,
            "active_profile_name": None,
            "profile_enable_thinking": None,
        }
    models = payload.get("models") if isinstance(payload, dict) else None
    if not isinstance(models, dict) or model_id not in models:
        return {
            "status": "model_missing",
            "enable_thinking": None,
            "active_profile_name": None,
            "profile_enable_thinking": None,
        }
    entry = models[model_id]
    if not isinstance(entry, dict):
        return {
            "status": "unreadable",
            "enable_thinking": None,
            "active_profile_name": None,
            "profile_enable_thinking": None,
        }
    enable = entry.get("enable_thinking")
    active = entry.get("active_profile_name")
    profile_enable = None
    if isinstance(active, str) and active:
        profiles_path = home / "model_profiles.json"
        try:
            profiles_payload = json.loads(profiles_path.read_text(encoding="utf-8"))
            profiles = profiles_payload.get("profiles", {})
            model_profiles = profiles.get(model_id, {}) if isinstance(profiles, dict) else {}
            profile = model_profiles.get(active, {}) if isinstance(model_profiles, dict) else {}
            settings = profile.get("settings", {}) if isinstance(profile, dict) else {}
            if isinstance(settings, dict) and "enable_thinking" in settings:
                profile_enable = settings.get("enable_thinking")
                if not isinstance(profile_enable, bool):
                    profile_enable = None
        except (OSError, json.JSONDecodeError, AttributeError):
            profile_enable = None
    return {
        "status": "ok",
        "enable_thinking": enable if isinstance(enable, bool) else None,
        "active_profile_name": active if isinstance(active, str) else None,
        "profile_enable_thinking": profile_enable,
    }
```

Wire into `collect_readiness` / `build_gate_b_report` / `run_gate_b_check` with injectable `omlx_home`. **Do not** read `settings.json`.

- [ ] **Step 4: Update docs**

- Gate B contract table: pin revision `2`; default `--pin-path` r2; mention `omlx_profile_observe` diagnostic block; follow-ons D3 + **D4**.
- Gate D follow-on table: add D4 row (Deferred).
- D2 residual: point exact decode qualification at **D4** (keep D3 deferred).
- `architecture.md`: one sentence that thinking request-pin Gate A (pin r2) is landed fake-only; D4 deferred.

- [ ] **Step 5: Run Gate B + Package 2 thinking tests**

```bash
PYTHONPATH=src /opt/homebrew/bin/python3 -m unittest \
  tests.test_omlx_thinking_gate_b_check \
  tests.test_omlx_thinking_pin \
  tests.test_omlx_thinking_transport \
  tests.test_omlx_thinking_runner \
  tests.test_omlx_thinking_measure -q
```

Expected: OK

- [ ] **Step 6: Commit**

```bash
git add src/local_model_runtime_evaluation/omlx_thinking_gate_b_check.py \
  tests/test_omlx_thinking_gate_b_check.py \
  docs/package-2-omlx-thinking-gate-b.md \
  docs/package-2-omlx-thinking-gate-d.md \
  docs/package-2-omlx-thinking-d2.md \
  docs/architecture.md
git commit -m "$(cat <<'EOF'
Add Gate B oMLX profile observe and park decode accounting as D4.

EOF
)"
```

---

## Verification

- [ ] Full related suite:

```bash
PYTHONPATH=src /opt/homebrew/bin/python3 -m unittest \
  tests.test_omlx_thinking_pin \
  tests.test_omlx_thinking_transport \
  tests.test_omlx_thinking_runner \
  tests.test_omlx_thinking_measure \
  tests.test_omlx_thinking_gate_b_check \
  tests.test_transport -q
```

- [ ] `default_pin_path()` ends with `omlx-0.5.3-thinking-r2.json`
- [ ] r1 JSON untouched on disk; loader rejects it
- [ ] No new manifests / run IDs / `.harness-lifecycle` commits
- [ ] Docs list D3 + D4 deferred

## Spec coverage

| Design requirement | Task |
|---|---|
| Pin r2 + required kwargs | 1 |
| Transport POST always pins thinking | 2 |
| Gate B observe diagnostic only | 3 |
| D4 named follow-on + docs | 3 |
| No live / no D3/D4 code | Global |

## Out of scope (explicit)

- Live re-measure / new run ID authorization
- D3 external-bench
- D4 decode / `reasoning_content` adapter
- Editing `~/.omlx` UI profiles

---

## Execution handoff

Plan: `docs/superpowers/plans/2026-07-22-package-2-thinking-request-pin-gate-a.md`.

**Two execution options:**

1. **Subagent-Driven (recommended)** — fresh subagent per task, review between tasks  
2. **Inline Execution** — execute tasks in this session with checkpoints  

Which approach?
