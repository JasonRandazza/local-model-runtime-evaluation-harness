# Native Plugin 0.3.0 Review

## Scope

Version `0.3.0` changes only the accepted run-ID shape and descriptions so the existing six approval-gated tools can request Stage 2 operations from the fixed host runner. It adds no tool, argument, route, configuration field, network callback, secret access, filesystem browser, arbitrary command, or service-lifecycle code to the plugin.

## Packaging Rule

Osaurus installs the dylib located at the plugin root. A successful `swift build -c release` updates `.build/release/libOsaurusEvaluationHarness.dylib` but does not update the root dylib. Every release must therefore copy the reviewed release binary to `libOsaurusEvaluationHarness.dylib`, compare both hashes, install, and compare the installed hash. A version-label change without this copy can install an older implementation under a newer version directory.

Osaurus also retains the loaded plugin schema in memory. Reinstalling the corrected binary while Osaurus is running does not necessarily refresh `/mcp/tools` or an existing chat's tool definitions. Fully restart Osaurus after installation, inspect the live tool registry, and use a fresh agent chat. For `0.3.0`, all run-ID tools must expose `^stage[012]-[0-9]{8}-[0-9]{3}$` before Stage 2A.

## Verification

- clean `swift test`: 4 passed
- release `swift build -c release`: passed
- package-root binary synchronized to the reviewed release build
- operator-approved plugin installation: passed
- installed-binary checksum comparison: passed

## Reviewed SHA-256

```text
d8eee5b01ec4839e6185ea9f1630b5efb35afde0d58bced54297a464666570ba  .build/release/libOsaurusEvaluationHarness.dylib
d8eee5b01ec4839e6185ea9f1630b5efb35afde0d58bced54297a464666570ba  libOsaurusEvaluationHarness.dylib
d8eee5b01ec4839e6185ea9f1630b5efb35afde0d58bced54297a464666570ba  installed 0.3.0/libOsaurusEvaluationHarness.dylib
b6bf220e87d7a0792e7c8a7cad0225ff0642389b3b3965f940fadc0a8bee7c31  osaurus-plugin.json
b28a58186cbadc37ec5b038a3c8e3a9eba636c7cc377565b501606bb1cd68e94  Sources/OsaurusEvaluationHarness/HarnessCore.swift
45ffcd36e060c264253749bb409e4042be02196a10d892b16bd50036f4c8559b  Sources/OsaurusEvaluationHarness/Plugin.swift
```

## Rollback

Plugin `0.3.0` is active. The preserved installed-package directory for `0.2.0` is the immediate rollback source and must not be deleted manually.
