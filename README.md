# Local Model Runtime Evaluation Harness

LMRE is a local-first evaluation toolkit for discovering and comparing model
families across Osaurus, oMLX, and OptiQ on Apple Silicon.

The active product is managed-run led:

```text
adopt reviewed local policy
  -> create and inspect an immutable plan
  -> manage exact local runtime leases
  -> run the native quality sequence
  -> seal or safely resume honest evidence
```

The repository no longer carries the retired Stage 0–2 orchestration,
Package 2 thinking experiments, personal-selection prototype, consumed
manifests, or native plugin source. Those are preserved in the checksummed
sibling archive:

```text
/Users/jrazz/Dev/archive/local-model-runtime-evaluation-harness-history-2026-07-30
```

See [docs/history.md](docs/history.md) for the historical lane summary and
[docs/status.md](docs/status.md) for the current state.

## Active Commands

| Command | Purpose |
| --- | --- |
| `./bin/lmre` | Normal managed policy, plan, run, resume, status, and report path |
| `./bin/lmre-discover` | Discover ready native triples and execute one approved family |
| `./bin/lmre-approach3` | Run explicit free-form recipes; live evidence remains unsealed |
| `./bin/lmre-matrix` | Measure one family’s native control triple |
| `./bin/lmre-preference` | Collect, review, judge, and tally pairwise preference |
| `./bin/lmre-rag` | Run oracle or keyword RAG evaluation |
| `./bin/lmre-overhead` | Compare direct and Osaurus-routed latency for native backends |
| `./bin/lmre browse` | Generate the read-only static HTML browser for sealed evidence |

For a complete managed run, start with:

```bash
./bin/lmre --help
```

The other CLIs are retained low-level diagnostic and dry-config surfaces. Use
the managed `lmre` workflow for normal live evaluation.

Operator documentation:

- [Discovery](docs/discovery.md)
- [Managed local runs](docs/managed-runs.md)
- [Native matrix](docs/matrix.md)
- [Preference](docs/preference.md)
- [RAG](docs/rag.md)
- [Routing overhead](docs/overhead.md)
- [Results browser](docs/results-browser.md)
- [Architecture](docs/architecture.md)

## Safety Boundary

- Dry-config and unit tests are non-live.
- Policy adoption and initiating live execution each require an explicit user
  request. Once adopted, the standing policy authorizes matching plans without
  a new per-request manifest or confirmation prompt.
- Local runtime contact is loopback-only.
- One model/server lane runs at a time under the configured memory floor.
- Credentials remain in approved local stores and must not enter Git, prompts,
  reports, or generated artifacts.
- The managed harness may attach to an exact compatible process or start and
  reclaim only fixed configured runtimes under the adopted policy. Reclaim
  gives a 60-second notice and uses exact PID identity with `SIGINT`, then
  bounded `SIGTERM`; broad kill and force kill are forbidden.
- Osaurus provider edits and external plugin changes are outside this active
  repository workflow.
- Model-cache deletion is a separate explicitly authorized storage task.

## Non-Live Verification

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v

./bin/lmre-discover dry-config
./bin/lmre-approach3 dry-config \
  config/approach3/gemma-freeform-native-triple-v1.json
./bin/lmre-matrix --dry-config \
  --campaign config/matrix/gemma-4-12b-qat-campaign.json
./bin/lmre-preference collect --dry-config
./bin/lmre-rag collect --dry-config
./bin/lmre-overhead run --dry-config
```

These checks must not contact Osaurus, oMLX, OptiQ, Keychain, or a real model.
