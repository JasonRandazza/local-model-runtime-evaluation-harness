# Stage 2B-1 Gate A Finding Remediation Verification

> **Supersession (2026-07-23):** Present-tense `GATE_A_STOPPED` below is
> historical for this dated record. Gate A findings closed; Stage 2B-1 sealed
> PASS `stage2-20260721-005`. See `docs/stage-2b1-gate-a.md`. Do not rewrite
> this verification body.

Verification ran against commit `8525df8df0b3c009755f3344fa0a54c2c4e35c8d`
on 2026-07-20. The implementation remains `GATE_A_STOPPED` pending an
independent architecture review; this record grants no Gate B or live authority.

## Deterministic tests

| Command | Result |
|---|---|
| `PYTHONPATH=src python3 -m unittest tests.test_stage_two_gate_a_e2e -v` | PASS: 1 test. The fake end-to-end lifecycle produced the redacted eight-POST bundle, four warm-ups, four measured requests, independent acceptance decisions, checksum validation, and lock retention through successful cleanup. |
| `PYTHONPATH=src python3 -m unittest discover -s tests -v` | ENVIRONMENTAL FAILURE: 432 tests run; 430 passed, 1 skipped, 1 error. `test_host_validator_uses_structured_config_and_never_returns_header_values` failed because the pinned OptiQ snapshot was unavailable (`artifact_identity_failed`), not because of a Gate A remediation. |
| `swift test` (from `plugins/osaurus-evaluation-harness`) | ENVIRONMENTAL FAILURE: SwiftPM could not apply its manifest `sandbox-exec` sandbox (`Operation not permitted`). No plugin build, copy, installation, replacement, or reinstallation was performed. |

The full-suite skip was `test_matrix_measure.MatrixMeasureTest`: port `1337`
was already in use. The snapshot-dependent host-test error and this occupied
port are environment dependencies outside the deterministic Gate A cohort.

## Static boundary scans

| Check | Command | Result |
|---|---|---|
| Manifest directory and template exclusion | `rg --files manifests tests/fixtures | sort` followed by `rg -n '"schema_version"\s*:\s*"3\.2\.0"|"mode"\s*:\s*"operator_inference_probe"' manifests --glob '*.json' --glob '!*.json.template'` | PASS: `manifests/` exists and contains only live JSON records for schemas `1.0.0`–`3.1.0`; the Stage 2B-1 template is `manifests/stage-2-optiq-inference-smoke.json.template`, and the excluded live-JSON scan returned no matches. |
| Stage 2B-1 usable-ID separation | The explicit Python check below scans `manifests/*.json`, `manifests/*.json.template`, and `tests/fixtures/*.json` for schema `3.2.0` plus mode `operator_inference_probe`, then asserts no matching live manifest and no matching live run ID. | PASS: live manifests `[]`; template `['stage-2-optiq-inference-smoke.json.template']`; fixtures `['valid-stage-2-inference.json']`. The concrete fixture ID `stage2-20260715-901` is test data, not a live manifest or authorization. |
| Provider mutation | `rg -n -i '(create|update|delete|mutate|configure|reconnect).*provider|provider.*(create|update|delete|mutate|configure|reconnect)' src/local_model_runtime_evaluation --glob '*.py'` | PASS: no provider mutation helper; matches only declare the operator-required reconnect policy. |
| Credential serialization | `rg -n -i '(write|dump|serialize|persist|record).*(credential|api[_-]?key|authorization|token|secret)|(credential|api[_-]?key|authorization|token|secret).*(write|dump|serialize|persist|record)' src/local_model_runtime_evaluation --glob '*.py'` | PASS: no credential serialization match. |
| Stage 2B-2 authority | `rg -n -i '(stage.?2b.?2|stage_two_b_two|StageTwoB2)' src/local_model_runtime_evaluation --glob '*.py'` | PASS: no executable authority symbols found. |

The usable-ID validation was run from the repository root:

```sh
python3 - <<'PY'
import json
from pathlib import Path

def stage_2b1(paths):
    matches = []
    for path in paths:
        data = json.loads(path.read_text())
        if (data.get("schema_version") == "3.2.0"
                and data.get("mode") == "operator_inference_probe"):
            matches.append((path.name, data.get("run_id")))
    return matches

live = stage_2b1(Path("manifests").glob("*.json"))
templates = stage_2b1(Path("manifests").glob("*.json.template"))
fixtures = stage_2b1(Path("tests/fixtures").glob("*.json"))
assert not live
assert not any(run_id and "YYYYMMDD" not in run_id for _, run_id in live)
print("live:", live)
print("templates:", templates)
print("fixtures:", fixtures)
PY
```

It printed `live: []`, `templates: [('stage-2-optiq-inference-smoke.json.template',
'stage2-YYYYMMDD-NNN')]`, and `fixtures: [('valid-stage-2-inference.json',
'stage2-20260715-901')]`. The fixture's concrete ID is therefore proven to be
outside the live-manifest directory; it is not a usable authorized run.

## Residual live-only risks

- Strict SSE behavior still requires confirmation under real endpoint load.
- The operator-owned existing-provider reconnect can still be flaky in the live
  Osaurus environment.
- Snapshot availability, the foreground service, and port ownership are
  operator/environment prerequisites for a later separately authorized Gate B.
