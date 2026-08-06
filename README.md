# Local Model Runtime Evaluation Harness

LMRE is a local-first evaluation toolkit for discovering and comparing model
families across Osaurus, oMLX, and OptiQ on Apple Silicon.

The active product is managed-run led:

```text
adopt reviewed local policy
  -> inspect checked-in comparison-class and artifact readiness
  -> optionally propose, validate, and adopt an offline free binding
  -> inspect a checked-in heterogeneous open mix when needed
  -> create and inspect an immutable family, binding, or open-mix plan
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
| `./bin/lmre-approach3` | Run explicit low-level recipes; output is collector evidence, not a managed seal |
| `./bin/lmre-matrix` | Measure one family’s native control triple |
| `./bin/lmre-preference` | Collect, review, judge, and tally pairwise preference |
| `./bin/lmre-rag` | Run oracle or keyword RAG evaluation |
| `./bin/lmre-overhead` | Compare direct and Osaurus-routed latency for native backends |
| `./bin/lmre browse` | Generate the read-only static HTML browser for sealed evidence |
| `./bin/lmre doctor` | Report offline readiness of local config, artifacts, and policy |
| `./bin/lmre binding` | Propose, inspect, validate, and adopt a non-live same-family cell declaration |
| `./bin/lmre open-mix inspect` | Validate a checked-in heterogeneous comparison set and its local artifacts without live contact |

For a complete managed run, start with:

```bash
./bin/lmre --help
```

## One-Time Machine Profile

Committed model configuration is portable and contains logical roots instead
of developer-specific absolute paths. Create the fixed, gitignored local
profile before using dry-config, discovery, planning, or collection commands:

```bash
mkdir -p .lmre
cp config/machine-profile.example.json .lmre/machine-profile.json
```

Edit only the two absolute directory values in
`.lmre/machine-profile.json`: `local_models` for curated local builds and
`huggingface_hub` for the Hugging Face hub root. Both directories must already
exist. LMRE does not scan caches, expand environment variables, accept a
profile-path CLI override, or relocate model weights.

Model entries use only `{LMRE_ROOT:local_models}/...` or
`{LMRE_ROOT:huggingface_hub}/...`. Runtime model IDs and fixed start commands
may derive from the resolved artifact through `{artifact_path}`. Unknown,
embedded, relative, traversing, or malformed tokens fail closed.

The other CLIs are retained low-level diagnostic and dry-config surfaces. Use
the managed `lmre` workflow for normal live evaluation.

Operator documentation:

- [Discovery](docs/discovery.md)
- [Managed local runs](docs/managed-runs.md)
- [Controlled expansion](docs/superpowers/specs/2026-08-05-controlled-expansion-comparison-class.md)
- [Offline comparison-class inspection](docs/superpowers/specs/2026-08-05-comparison-class-offline-inspection.md)
- [Managed free-bind declarations](docs/superpowers/specs/2026-08-05-managed-free-bind-declarations.md)
- [Managed free-bind execution](docs/superpowers/specs/2026-08-05-managed-free-bind-execution.md)
- [Heterogeneous open-mix contract](docs/superpowers/specs/2026-08-05-heterogeneous-open-mix-contract.md)
- [Native matrix](docs/matrix.md)
- [Preference](docs/preference.md)
- [RAG](docs/rag.md)
- [Routing overhead](docs/overhead.md)
- [Results browser](docs/results-browser.md)
- [Offline doctor](docs/doctor.md)
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
./bin/lmre open-mix inspect qwen-ornith-capability-v1
```

These checks must not contact Osaurus, oMLX, OptiQ, Keychain, or a real model.
They read the local machine profile and report missing artifacts without
starting services.
Open-mix inspection and planning are implemented as non-live surfaces; `run`
and `resume` reject open-mix plans until the separately reviewed live adapter
slice is implemented.
