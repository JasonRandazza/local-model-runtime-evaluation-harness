# Local Model Evaluation Harness Plugin

Version `0.3.0` preserves the six approval-gated tools and adds only Stage 2 run-ID support. It does not add routes, configuration, arbitrary arguments, filesystem access, network callbacks, or service lifecycle control.

Build and review do not install the plugin. Installation requires explicit operator approval.

This native Osaurus plugin exposes exactly six Stage 0, Stage 1, and Stage 2A tools:

- `inventory`
- `preflight`
- `run_scenario`
- `status`
- `cancel`
- `cleanup`

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
