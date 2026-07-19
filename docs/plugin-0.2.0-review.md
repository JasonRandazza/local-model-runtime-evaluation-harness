# Plugin 0.2.0 Pre-Installation Review

Plugin `local.jrazz.model-runtime-evaluation-harness` version `0.2.0` is built and reviewed. The first installation on 2026-07-13 exposed a stale packaged-binary problem: Osaurus recorded version `0.2.0`, but the copied dylib matched the `0.1.2` checksum and accepted only Stage 0 run IDs. The packaged dylib was rebuilt from a clean isolated copy, tested, ad-hoc signed, and replaced in the source directory. A manual reinstall is required before Gate B can pass.

## Contract

- Exactly six tools: `inventory`, `preflight`, `run_scenario`, `status`, `cancel`, `cleanup`
- Every tool uses `permission_policy: ask`
- Only Stage 0 and Stage 1 run-ID shapes are accepted
- The only public argument is `run_id` where required
- No routes, configuration UI, arbitrary paths, commands, endpoints, credentials, host callbacks, memory, or agent dispatch
- One fixed executable: `/Users/jrazz/Dev/active/local-model-runtime-evaluation-harness/bin/lmre-stage0`

## Verification

- Four Swift tests passed from isolated scratch path `/private/tmp/lmre-swift-gatea-20260713`
- Release build passed from the same scratch path
- Building did not install the plugin

## Reviewed SHA-256 Values

```text
c1c88b2f301327e92993ed2b3c61542558db6a09da1c41ae0900116e2c3817e9  Package.swift
1c84a35c989171846d9b3c5c854679c7dd1153edfcd7364818840035db4fbbcb  osaurus-plugin.json
edc93b6401ceb986695d6ffb29a9312482e71ca40f72eaf9ad5628e8dd19979b  Sources/OsaurusEvaluationHarness/HarnessCore.swift
45ffcd36e060c264253749bb409e4042be02196a10d892b16bd50036f4c8559b  Sources/OsaurusEvaluationHarness/Plugin.swift
49336c055cfeb7af68ecb8cc848e4fed4c6df52c1f4f15c06c455c1fcd120564  clean isolated release before signing
5b2f828cb20bec01736ffe2610f8a9ab77b2b446a35fd9d95cd845e41c5ff177  packaged ad-hoc-signed libOsaurusEvaluationHarness.dylib
```

The corrected binary contains the Stage 1 pattern `^stage[01]-[0-9]{8}-[0-9]{3}$`. The stale installed copy has checksum `b0ff2924123c5e1ff03c3c2f4978f90ba36eecb01621e72766608811dc440bec` and must not be used for Stage 1.

## Rollback Baseline

`osaurus tools list` confirmed installed version `0.1.2` before upgrade preparation. It remains at:

```text
/Users/jrazz/.osaurus/Tools/local.jrazz.model-runtime-evaluation-harness/0.1.2/
```

Baseline checksums:

```text
f4e429b2ecfa7130e4d94c4f060298352dd7339c1413bdfca819e904cceb914b  0.1.2/osaurus-plugin.json
b0ff2924123c5e1ff03c3c2f4978f90ba36eecb01621e72766608811dc440bec  0.1.2/libOsaurusEvaluationHarness.dylib
```

Do not uninstall `0.1.2` before installing `0.2.0`. On upgrade trouble, deny tool calls, disable the Benchmark Coordinator, leave both version directories untouched, and return to manager review. Do not improvise a version-directory deletion.
