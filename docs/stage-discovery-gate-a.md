# Discovery MVP Gate A

## Current Decision

`GATE_A_PASSED` (Jason, 2026-07-24). Gate A fake-only implementation and review are closed. Live propose/execute remain separately gated.

Gate A is non-authorizing. It does not grant live loopback contact, Stage 2 manifests or run IDs, provider edits, plugin rebuild, or silent model copies.

Design: `docs/superpowers/specs/2026-07-24-discovery-mvp-design.md` (**Status:** APPROVED (Jason, 2026-07-24))  
Implementation plan: `docs/superpowers/plans/2026-07-24-discovery-mvp-gate-a.md`  
Operator docs: `docs/discovery.md`

## Implemented (Gate A scope)

- Proposal types, content hash, and disk IO (`discovery_types.py`)
- Match rules: recipe agreement, artifact check, server health + identity, fail-closed partial triples (`discovery_match.py`)
- Execute pipeline: preference then RAG oracle/keyword in-process; judge cell = first recipe cell; stop on first failure (`discovery_execute.py`)
- CLI: `lmre-discover` — `propose` (default), `show`, `execute`, `dry-config` (`discovery_cli.py`, `bin/lmre-discover`)
- Fake-only unit tests for types, match, execute, and CLI wiring

## Explicit non-goals (not implemented)

- No live `propose` or `execute` against real Osaurus, oMLX, or OptiQ
- No `lmre-discover place` or silent copy/move/relocate of model weights
- No Stage 2 manifests, run IDs, or inference authority
- No Osaurus provider edit or OptiQ reconnect automation
- No `confirm_policy: auto_when_ready`, all-ready-families execute, or custom any-three mixes
- No matrix measure in default execute
- Plugin `0.3.0` unchanged

## Verification (fake-only)

Discovery unit tests — no real loopback, Keychain, or live servers:

From repository root:

```bash
PYTHONPATH=src /opt/homebrew/bin/python3 -m unittest \
  tests.test_discovery_types \
  tests.test_discovery_match \
  tests.test_discovery_execute \
  tests.test_discovery_cli -v
```

Expected: all tests PASS.

Config smoke (no network), from repository root:

```bash
./bin/lmre-discover dry-config
```

Expected: JSON with `"ok": true`.

## Exit criteria

- [ ] All discovery unit tests PASS
- [ ] `./bin/lmre-discover dry-config` succeeds
- [ ] Design spec status APPROVED (Jason, 2026-07-24)
- [x] Jason accepts Gate A → decision line becomes `GATE_A_PASSED`

Live propose/execute remains separately gated after Gate A closes.

## Deferred north-star tracks

| Track | Intent |
|---|---|
| `confirm_policy: auto_when_ready` | Auto-run on same proposal object |
| Execute all ready families | Sequential loop over `executable_families` |
| Custom any-3 mix | Separate fail-closed rules |
| Osaurus CLI provider prep | Reduce reconnect tap |
| Explicit `place` / relocate UX | Informed consent for disk operations |
| Matrix measure in default execute | Optional suite slot |
