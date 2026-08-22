# Local Model Runtime Evaluation

LMRE measures local model runtimes against each other under controlled,
reproducible conditions, and preserves the result as tamper-evident evidence.
This file is the project's glossary: what the words mean, not how anything
works. Mechanism lives in [docs/architecture.md](docs/architecture.md).

## Language

### Models and cells

**Family**:
A model lineage evaluated as a single unit, identified by a `family_id`. Its
quants are the same model at different precisions, not different models.
_Avoid_: model, model group, variant set

**Quant**:
One quantization of a family's weights, together with the artifact that holds
it. A quant is declared, not run; the runnable form is a cell.
_Avoid_: precision, format, build

**Native server**:
The local runtime a quant was built for — Osaurus, oMLX, or OptiQ.
_Avoid_: backend, provider, engine, host

**Cell**:
One quant bound to exactly one native server, with the fixed commands and
endpoint needed to run it. The smallest thing that can be executed and
measured.
_Avoid_: target, endpoint, instance, config

**Native diagonal**:
The rule that a family exposes exactly one cell per capable native server, and
that a quant is never run on a server it was not built for.
_Avoid_: matrix diagonal, native triple

**Baseline cell**:
A cell on a family's native diagonal. A comparison may append to the baseline
but never replace or reorder it.

### Lineups

**Lineup**:
An ordered set of cells that run together as one comparison. Every lineup is
declared in exactly one of four ways below, which differ in provenance and in
who may author them, not in what they produce.
_Avoid_: set, group, selection, mix

**Comparison class**:
A checked-in, same-family declaration that appends reviewed native cells to a
family's baseline.
_Avoid_: expansion, class

**Binding**:
An operator-selected ordering of existing same-family native cells, proposed
and adopted offline. A binding records a choice; it grants no live authority.
_Avoid_: free-bind, selection, pinning

**Open mix**:
A checked-in heterogeneous declaration binding two to six ordered native cells
drawn from at least two families to one shared suite contract.
_Avoid_: mixed run, cross-family comparison

**Recipe**:
An explicit declaration of which cells a family's collection uses, written
free-form rather than derived from the diagonal.
_Avoid_: preset, profile

### Runs and evidence

**Operator**:
The human who holds local authority. Some actions are reserved to the operator
and may only ever be reported by an agent, never performed.
_Avoid_: user, owner, admin

**Live authority**:
Permission to contact a runtime, start a process, or record real measurements.
Inspection, proposal, planning, and adoption all deliberately withhold it.
_Avoid_: permission, access, live mode

**Adopted policy**:
The standing record of the operator's authority and exact limits, captured at
planning time and bound to the run.
_Avoid_: settings, config, policy file

**Plan**:
The immutable description of exactly what a run will do, with every executable
input bound by hash. A plan is fixed at creation; a changed input is a
different plan.
_Avoid_: job, spec, schedule

**Plan hash**:
The identity of a plan. Two runs are the same run only if their plan hashes
match.

**Managed run**:
One execution of a plan through the fixed collector order, holding one model
lane at a time.
_Avoid_: job, session, experiment

**Attempt**:
One execution of one step within a run. A step may be attempted again after a
block without invalidating earlier evidence.

**Evidence bundle**:
The complete, checksummed record of a run: its plan, policy snapshot,
environment, journals, per-step attempts, and outcome.
_Avoid_: results, output, artifacts

**Seal**:
The single act of closing an evidence bundle and committing its checksums,
after which it is trusted for reporting and never mutated. Integrity and
finality are not separable here: an unsealed bundle is neither.
_Avoid_: finalize, commit, lock

**Resume**:
Continuing a blocked run after the operator clears the block, re-verifying the
sealed attempt and running only what remains.
_Avoid_: retry, restart

### Outcomes

**PASS** / **FAIL**:
The step ran and its evidence is sound, or it ran and it is not.

**N/A**:
The step does not apply to this cell at all — there was nothing to measure.
Distinct from a failure: nothing went wrong.
_Avoid_: skipped, none, empty

**INCOMPARABLE**:
The step ran and produced evidence, but that evidence cannot honestly be set
beside the other cells' — most often because token accounting differs. The
measurement is real; the comparison is not.
_Avoid_: invalid, unusable, failed

**PARTIAL_BLOCKED**:
The run completed every step it could and sealed, with at least one step
waiting on an operator action it may not perform itself.
_Avoid_: incomplete, paused

**EXECUTED_UNSEALED**:
Collection ran but no sealed bundle exists, so the result is excluded from
reporting rather than trusted.

**Lease**:
The harness's relationship to a backend process for the duration of a run:
attached to one it did not start, owning one it started, or having reclaimed
one under policy. Attached processes are never stopped.
_Avoid_: handle, connection, ownership

### Measurement

**Campaign**:
The set of cells a measurement runs across.

**Suite**:
The fixed set of requests a campaign issues, identical across every cell being
compared.
_Avoid_: benchmark, test set

**Corpus**:
The document set that RAG collection retrieves against.

**Overhead pair**:
Two runs of the same cell — one direct, one routed through Osaurus — that
exist only to be differenced.
_Avoid_: A/B, control pair

**Routing tax**:
The measured cost of going through Osaurus rather than direct, obtained from
an overhead pair.
_Avoid_: overhead, latency penalty

**Preference**:
A judged comparison of two cells' responses to the same request, collected as
pairs, judged locally, and tallied.
_Avoid_: rating, vote, eval

**Exact tokens**:
A token count reported by the runtime itself. A count the harness derived is
_estimated_, and the two are never compared as if equal.

### Workspace and artifacts

**Workspace root**:
The single tree holding every operator-owned input and output. A source
checkout is itself a workspace.
_Avoid_: project root, working directory

**Machine profile**:
The local, uncommitted record of where this machine keeps model artifacts.
_Avoid_: local config, environment, paths file

**Artifact root**:
One of the two declared logical locations a `{LMRE_ROOT:...}` template may
resolve to. Nothing else is ever scanned or accepted.
_Avoid_: model directory, cache, weights path
