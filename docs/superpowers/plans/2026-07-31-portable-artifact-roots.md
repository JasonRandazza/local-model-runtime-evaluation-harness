# Portable Artifact Roots Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace developer-specific committed model paths with safe fixed-root templates resolved through an ignored, checksummed local machine profile.

**Architecture:** A new stdlib-only `artifact_profile.py` module owns the strict machine-profile schema and token resolver. Matrix loaders preserve committed template validation, then explicitly resolve runtime-facing cells. Managed plans bind the fixed profile through their existing input hashes, preserving plan schema compatibility.

**Tech Stack:** Python 3.11+ standard library, strict JSON, `unittest`, existing LMRE CLI/config/evidence APIs.

## Global Constraints

- No live runtime, listener, process, credential, provider, or model contact.
- No arbitrary CLI path, executable, endpoint, model, or output overrides.
- No cache scanning, downloading, placement, linking, or deletion.
- Keep `MANAGED_PLAN_SCHEMA_VERSION = "1.0.0"` and old sealed plans readable.
- Keep developer-specific profile data under ignored `.lmre/` only.
- Use TDD: every production behavior begins with a focused failing test.
- Do not stage, commit, push, add remotes, or create a PR without separate user authorization.

---

### Task 1: Strict machine profile and resolver

**Files:**

- Create: `src/local_model_runtime_evaluation/artifact_profile.py`
- Create: `tests/test_artifact_profile.py`
- Create: `tests/artifact_profile_fixtures.py`
- Create: `config/machine-profile.example.json`

**Interfaces:**

- Produces `ArtifactProfileError(RuntimeError)`.
- Produces immutable `ArtifactRoots(local_models: Path, huggingface_hub: Path)`.
- Produces `load_artifact_roots(path: Path) -> ArtifactRoots`.
- Produces `resolve_artifact_template(template: str, roots: ArtifactRoots) -> str`.
- Produces `resolve_artifact_text(value: str, artifact_path: str) -> str` for exact `{artifact_path}` substitution.
- Test helper produces a context manager returning a temporary profile path and roots.

- [ ] **Step 1: Add failing profile-schema tests.** Cover valid exact fields, missing/extra fields, missing/extra root keys, relative/tilde roots, missing roots, file roots, and broken symlinks.
- [ ] **Step 2: Run `PYTHONPATH=src python3 -m unittest tests.test_artifact_profile -v`.** Confirm failure because `artifact_profile` does not exist.
- [ ] **Step 3: Implement the smallest strict immutable profile loader.** Use `json`, `dataclasses`, and `pathlib`; never expand `~` or environment variables.
- [ ] **Step 4: Re-run the focused tests and confirm they pass.**
- [ ] **Step 5: Add failing token tests.** Cover both approved roots, unknown roots, missing token, embedded token, absolute/traversal/empty suffixes, root escape, exact artifact substitution, and unknown/unresolved braces.
- [ ] **Step 6: Run the focused tests and confirm the expected resolver failures.**
- [ ] **Step 7: Implement token parsing and normalized descendant checks.**
- [ ] **Step 8: Run focused tests and inspect `git diff` without staging.**

### Task 2: Portable matrix templates

**Files:**

- Modify: `src/local_model_runtime_evaluation/matrix_config.py`
- Modify: `config/matrix/families/gemma-4-12b-qat.json`
- Modify: `config/matrix/families/ornith-35b.json`
- Modify: `config/matrix/families/qwen36-35b-a3b.json`
- Modify: all nine active files under `config/matrix/cells/`
- Modify: three active OptiQ-backed files under `config/overhead/pairs/`
- Modify: `tests/test_matrix_config.py`

**Interfaces:**

- `FamilyQuant.resolve(roots: ArtifactRoots) -> FamilyQuant` returns absolute artifact paths and resolved model IDs.
- `ModelFamily.resolve(roots: ArtifactRoots) -> ModelFamily` resolves every quant.
- `Cell.resolve(roots: ArtifactRoots) -> Cell` resolves artifact path, model ID, and fixed command arguments.
- `OverheadPair.resolve(artifact_path: str) -> OverheadPair` resolves its fixed routed model ID through the backend artifact path.
- `Campaign.resolve(roots: ArtifactRoots) -> Campaign` returns a campaign with resolved family/cells available through existing paths and loaders.

- [ ] **Step 1: Add failing matrix tests using synthetic roots.** Assert Gemma, Ornith, and Qwen absolute paths, OptiQ `:no-think` IDs, fixed OptiQ commands, and family/cell agreement after resolution.
- [ ] **Step 2: Run `PYTHONPATH=src python3 -m unittest tests.test_matrix_config -v`.** Confirm failures arise from missing resolve APIs/templates.
- [ ] **Step 3: Add minimal immutable resolve methods while keeping existing unresolved cross-file validation.**
- [ ] **Step 4: Convert committed family/cell/overhead model paths to approved root and artifact tokens.** Preserve every logical model, quant, server, alias, port, and command flag.
- [ ] **Step 5: Re-run matrix tests until green.**
- [ ] **Step 6: Add negative tests proving runtime adapters reject an unresolved cell and accept its resolved counterpart.**
- [ ] **Step 7: Run matrix and runtime-adapter focused tests, then inspect the diff without staging.**

### Task 3: Wire explicit resolution through retained products

**Files:**

- Modify: `src/local_model_runtime_evaluation/discovery_cli.py`
- Modify: `src/local_model_runtime_evaluation/discovery_match.py`
- Modify: `src/local_model_runtime_evaluation/approach3.py`
- Modify: `src/local_model_runtime_evaluation/approach3_cli.py`
- Modify: `src/local_model_runtime_evaluation/matrix_runner.py`
- Modify: `src/local_model_runtime_evaluation/preference_cli.py`
- Modify: `src/local_model_runtime_evaluation/preference_collect.py`
- Modify: `src/local_model_runtime_evaluation/preference_judge.py`
- Modify: `src/local_model_runtime_evaluation/rag_cli.py`
- Modify: `src/local_model_runtime_evaluation/rag_collect.py`
- Modify: `src/local_model_runtime_evaluation/overhead_cli.py`
- Modify: `src/local_model_runtime_evaluation/overhead_runner.py`
- Modify focused CLI/collector tests for injected temporary roots.

**Interfaces:**

- Production entry points load only fixed `.lmre/machine-profile.json`.
- Python `main`/dry-config helpers may accept keyword-only injected `profile_path` values for tests; argparse exposes no path override.
- Collectors receive resolved `Cell` objects or explicit `ArtifactRoots`; no module reads environment variables.

- [ ] **Step 1: Add one failing dry-config test proving a temporary profile controls resolved artifact checks without network/process calls.**
- [ ] **Step 2: Run the focused CLI test and confirm it fails because the profile is unused.**
- [ ] **Step 3: Thread the fixed/injected profile through discovery, Approach 3, matrix, preference, RAG, and overhead load boundaries.** Resolve once per command and reuse the immutable value.
- [ ] **Step 4: Run all affected CLI/config/collector tests.** Fix only resolution regressions.
- [ ] **Step 5: Add a tripwire test proving dry-config does not invoke transport, process inspection, credentials, runtime adapters, or subprocess execution while loading the profile.**
- [ ] **Step 6: Re-run affected tests and inspect the diff without staging.**

### Task 4: Bind the profile to managed plans and execution

**Files:**

- Modify: `src/local_model_runtime_evaluation/run_identity.py`
- Modify: `src/local_model_runtime_evaluation/managed_run.py`
- Modify: `src/local_model_runtime_evaluation/managed_run_cli.py`
- Modify: `tests/test_run_identity.py`
- Modify: `tests/test_managed_run.py`
- Modify: `tests/test_managed_run_cli.py`
- Modify: `tests/test_evidence_bundle.py`
- Modify: `tests/results_browser_fixtures.py`

**Interfaces:**

- Fixed logical plan input key: `.lmre/machine-profile.json`.
- `build_plan(..., machine_profile_path: Path = REPOSITORY_ROOT / ".lmre" / "machine-profile.json")` loads roots and hashes the actual profile bytes under that fixed logical key.
- `verify_plan_inputs(..., machine_profile_path: Path | None = None)` resolves only that exact logical key through the injected/default profile path; all other entries remain repository-relative.
- Managed collectors accept the already verified `ArtifactRoots` loaded from the same fixed profile.

- [ ] **Step 1: Add failing plan tests.** Assert the fixed profile key exists in `input_hashes`, a profile edit produces `plan_input_changed`, and schema version/old plan serialization remain unchanged.
- [ ] **Step 2: Run `PYTHONPATH=src python3 -m unittest tests.test_run_identity tests.test_evidence_bundle tests.test_results_browser -v`.** Confirm expected profile-binding failures.
- [ ] **Step 3: Extend input hashing/verification for only the fixed logical profile key.** Reject any other external mapping.
- [ ] **Step 4: Resolve managed campaign/cells from the verified profile before preflight or runtime-manager use.** Do not move policy authorization or live boundaries.
- [ ] **Step 5: Inject temporary profiles into managed/evidence/browser fixtures.**
- [ ] **Step 6: Run managed-plan, execution, evidence, and browser tests until green.**
- [ ] **Step 7: Inspect the plan/evidence diff specifically for schema drift or path leakage; do not stage.**

### Task 5: Operator migration and current documentation

**Files:**

- Create locally, ignored: `.lmre/machine-profile.json`
- Modify: `README.md`
- Modify: `docs/architecture.md`
- Modify: `docs/managed-runs.md`
- Modify: `docs/matrix.md`
- Modify: `docs/discovery.md`
- Modify: `docs/preference.md`
- Modify: `docs/rag.md`
- Modify: `docs/overhead.md`
- Modify: `docs/status.md`

**Interfaces:**

- Documentation names the fixed profile path, exact keys, safe copy/edit workflow, validation behavior, and Fable-doctor reuse point.
- The local ignored profile maps `local_models` and `huggingface_hub` to the
  operator's actual absolute directories; those values never enter tracked
  files.

- [ ] **Step 1: Add the ignored local profile using the developer's current roots and read it back.**
- [ ] **Step 2: Update current operator documentation and status.** Explain that profile setup is manual and does not grant live authority.
- [ ] **Step 3: Search tracked active product files for `/Users/jrazz` model paths, unsafe interpolation, and arbitrary path flags.** Historical sibling-archive references and handoff workspace paths are not model configuration.
- [ ] **Step 4: Correct every active-product match and inspect the documentation diff without staging.**

### Task 6: Full non-live verification and Graphify refresh

**Files:**

- Update ignored: `graphify-out/`

- [ ] **Step 1: Run `PYTHONPATH=src python3 -m unittest discover -s tests -v` with permission only for existing ephemeral loopback test fixtures.** Require zero failures.
- [ ] **Step 2: Run all six retained dry-config commands with the ignored local profile.** Require exit zero and no live contact.
- [ ] **Step 3: Run targeted searches for committed developer model paths, unresolved tokens at runtime boundaries, credential leakage, and accidental live calls.**
- [ ] **Step 4: Review the complete diff against every design acceptance criterion.**
- [ ] **Step 5: Run the repository's Graphify post-commit/update mechanism so the ignored graph matches the worktree source.**
- [ ] **Step 6: Run `graphify explain` for the artifact resolver and confirm the new source appears in the graph.**
- [ ] **Step 7: Report modified/untracked paths, verification evidence, migration requirements, and the Fable-doctor adaptation. Do not stage, commit, push, or create a PR.**
