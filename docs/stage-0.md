# Stage 0 Developer Runbook

Stage 0 proves control and evidence handling without inference.

## Verify Python

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

## Verify Plugin

```bash
swift package clean --package-path plugins/osaurus-evaluation-harness
swift test --package-path plugins/osaurus-evaluation-harness
swift build -c release --package-path plugins/osaurus-evaluation-harness
```

These commands compile but do not install the plugin.

## Expected Acceptance Sequence

For the current acceptance run `stage0-20260713-002`:

1. `inventory` performs passive path lookup only.
2. `preflight` validates the fixed manifest and enters `ready`.
3. `run_scenario` enters simulated `running` and deliberately pauses.
4. `status` confirms the persisted state.
5. `cancel` enters `cancelled` without sending a process signal.
6. `cleanup` enters `cleaned`, finalizes and validates checksums, releases the owned lock, and returns a bounded evidence summary.

The final disposition is `STOPPED` because cancellation is the behavior under test. A valid `STOPPED` result is expected evidence, not a failed Stage 0 run.

The Coordinator must validate the cleanup summary returned by the native tool. It does not inspect the host artifact directory through Sandbox file tools.

## Prohibited Activity

Do not run `osaurus bench`, contact ports 1337, 8100, or 8080, load a model, start or stop a server, edit a provider, expose a listener, or write into the Deep Wiki from the harness.
