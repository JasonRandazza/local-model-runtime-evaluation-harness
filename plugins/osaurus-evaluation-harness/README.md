# Local Model Evaluation Harness Plugin

## Installed production contract

**Keep using installed `0.3.0` until an operator explicitly installs `0.4.0`.**  
Jason (2026-07-24): build Discovery surface; if install fails, park the new dylib aside and continue on `0.3.0`.

## Source tree (`0.4.0`)

Source in this directory targets version `0.4.0`: six Stage tools plus `discover` (`dry-config` | `propose` only; no `execute` via plugin). It does not add routes, configuration UI, arbitrary shell, filesystem access beyond the fixed runners, network callbacks, or service lifecycle control.

Build and review do not install the plugin. Installation requires explicit operator approval.

Tools:

- `inventory`
- `preflight`
- `run_scenario`
- `status`
- `cancel`
- `cleanup`
- `discover` (fixed `bin/lmre-discover` only)

Every tool uses per-call approval. The plugin has no routes, web content, configuration UI, secrets, network client, inference callback, agent dispatch, memory access, or user-selected executable path. It invokes only the fixed repository wrapper at `bin/lmre-stage0`. The `cleanup` tool returns bounded host-validated evidence so the agent never needs direct access to the artifact directory.

```bash
swift package clean --package-path plugins/osaurus-evaluation-harness
swift test --package-path plugins/osaurus-evaluation-harness
swift build -c release --package-path plugins/osaurus-evaluation-harness
cp plugins/osaurus-evaluation-harness/.build/release/libOsaurusEvaluationHarness.dylib \
  plugins/osaurus-evaluation-harness/libOsaurusEvaluationHarness.dylib
shasum -a 256 \
  plugins/osaurus-evaluation-harness/.build/release/libOsaurusEvaluationHarness.dylib \
  plugins/osaurus-evaluation-harness/libOsaurusEvaluationHarness.dylib
```

The copy step is mandatory. `osaurus tools install .` installs the plugin-root dylib; it does not replace that file with the newer SwiftPM artifact under `.build/release`. The two hashes must match before installation.

Building and packaging do not install the plugin. Installation remains a separate human-approved operator step. After installation, compare the installed dylib hash to the reviewed release hash, fully restart Osaurus so its in-memory tool registry reloads the plugin schema, and inspect the live schemas before authorizing a run.

## Parked `0.4.0` (when install is skipped)

If `osaurus tools install` is not approved or fails, copy the reviewed release dylib to:

`plugins/osaurus-evaluation-harness/parked/0.4.0/libOsaurusEvaluationHarness.dylib`

Keep the installed Osaurus tool on **`0.3.0`**. Stage 2 Gate B still expects installed `0.3.0` until a separate install authorization.
