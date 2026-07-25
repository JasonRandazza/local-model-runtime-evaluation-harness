# Session handoff — Discovery / Stage 2 / Approach 3 (2026-07-24 night)

**Audience:** Any agent or human who has never seen this repo.  
**Operator:** Jason Randazza  
**Branch:** `main` (push as work lands)  
**This file is living:** update it whenever meaningful work lands tonight.

---

## 0. What this harness is

**local-model-runtime-evaluation-harness (LMRE)** evaluates **local** MLX / Osaurus / oMLX / OptiQ stacks with **fail-closed** contracts: pinned models, loopback-only routes, short-lived manifests, and evidence under `results/` + `docs/superpowers/verification/`.

It is **not** a cloud eval platform. Stage 0 never loads models. Stage 1/2 and Discovery have strict boundaries in `AGENTS.md`.

**North star (product direction):** install → connect Osaurus/oMLX/OptiQ → **discover** → run sealed tests → read results → later freer mixes under honest rules.  
See: `docs/superpowers/specs/2026-07-24-harness-north-star-vision.md`

---

## 1. Read these first (orientation map)

| Priority | Path | Why |
|----------|------|-----|
| 1 | `AGENTS.md` | Executable stage boundaries (Stage 0/1/2A/2B/harness-unattended). **Law of the land.** |
| 2 | `README.md` | Entry points, CLIs, approval boundaries |
| 3 | `docs/architecture.md` | Durable architecture |
| 4 | This handoff | Tonight’s state + unfinished work |
| 5 | `docs/superpowers/specs/2026-07-24-discovery-mvp-design.md` | Discovery MVP design (APPROVED) |
| 6 | `docs/superpowers/plans/2026-07-24-discovery-mvp-gate-a.md` | Discovery Gate A plan (implemented) |
| 7 | `docs/discovery.md` / `docs/stage-discovery-gate-a.md` | Operator Discovery docs (`GATE_A_PASSED`) |
| 8 | `docs/superpowers/notes/2026-07-24-optiq-osaurus-model-switch-investigation.md` | OptiQ A+C vs B spike; **prefer C+A, defer B** |
| 9 | `docs/matrix.md`, `docs/preference.md`, `docs/rag.md`, `docs/overhead.md` | Native-triple eval lanes |
| 10 | `docs/stage-2-harness-unattended-gate-a.md` (+ Stage 2B docs as needed) | Harness-owned OptiQ Stage 2 |

**Deep Wiki:** Obsidian Tier 5 notes exist historically; tonight’s handoff is **repo-only** (Jason: no Deep Wiki write).

---

## 2. Machine / runtime assumptions

- macOS, Apple Silicon, Metal required for OptiQ/MLX (sandbox without GPU fails).
- Prefer `/opt/homebrew/bin/python3` with `PYTHONPATH=src`.
- Loopback only: Osaurus `1337`, oMLX `8100`, OptiQ `8080`.
- Osaurus Keychain: `local.jrazz.lmre.osaurus` / `benchmark-harness` (see `docs/matrix.md`).
- oMLX matrix key: `lmre-matrix-local` (not a shared secret).
- OptiQ cells: `--no-auth`, model ids often `…:no-think` for content streaming.
- **Do not commit:** `.harness-lifecycle/`, `config/matrix/omlx-roots/**` model trees, egg-info, secrets, raw huge artifacts.

**Tonight’s live constraint (Jason):** Only **Gemma** available on OptiQ / OptiQ→Osaurus provider. Ornith/Qwen OptiQ not available for live. oMLX may flap — check health before Discovery.

---

## 3. Jason’s authorizations this session (2026-07-24 night)

| Item | Authorization |
|------|----------------|
| Commit + push to `origin/main` | **Yes** |
| Discovery live Gemma propose/execute | **Yes** (already evidenced) |
| **New Stage 2 Gemma runs** (unused IDs + short-lived manifests) | **Yes** — invent unused IDs in-session |
| Edit Osaurus providers | **No** — OptiQ provider stays Gemma-only |
| Pathway B (`--allow-model-switch`) | **No** (spike deferred) |
| Approach 3 free-form mixes | **Start / build as far as possible**; live test may be incomplete; Gemma-only |
| Plugin | Rebuild Discovery-related surface (**B**); if install fails, **park aside**, keep using installed `0.3.0` |
| Deep Wiki | **No** — repo handoff only |

---

## 4. What was already built before this night push

### Discovery MVP Gate A (merged on `main`)

- CLI: `bin/lmre-discover` — `propose` / `show` / `execute` / `dry-config`
- Modules: `discovery_types.py`, `discovery_match.py`, `discovery_execute.py`, `discovery_cli.py`
- Fake-only unit tests under `tests/test_discovery_*.py`
- Decision: `GATE_A_PASSED` in `docs/stage-discovery-gate-a.md`
- Squash commit: `43340d0` (+ acceptance checkbox `6e8454e`)

### Live Discovery evidence (Gemma)

| Proposal | Result |
|----------|--------|
| `discovery-20260724-002` | Execute **FAIL** — preference `port 8080 is busy` (pre-A+C) |
| `discovery-20260724-004` | Execute **PASS** — preference + RAG oracle + RAG keyword (~13 min) |

Run dirs (examples):  
`results/preference/gemma-4-12b-qat-preference-20260724-153621`  
`results/rag/gemma-4-12b-qat-rag-20260724-154644`  
`results/rag/gemma-4-12b-qat-rag-20260724-154757`

### OptiQ pathway spike

- Note: `docs/superpowers/notes/2026-07-24-optiq-osaurus-model-switch-investigation.md`
- **Verdict: pathway C (pinned restart) + A (attach-if-match); defer B**
- Log: `results/discovery/spike-b-vs-c-20260724.log`

### A+C implementation (was uncommitted at handoff start — commit in progress)

In `matrix_servers.py` for OptiQ:

- **A:** busy port + inventory contains `cell.model_id` → attach (`owned=False`)
- **C:** busy + mismatch → `pkill -INT -f 'optiq serve'`, wait, spawn cell `start_command`
- Tests: `tests/test_matrix_servers.py`
- Propose uses preference `_credential_for` for honest inventory

---

## 5. Build priority tonight (agent order)

1. Handoff doc + commit/push A+C + docs  
2. Stage 2 **Gemma** new unused run(s) if stack allows  
3. Approach 3 free-form **Gemma** — push code as far as possible  
4. Plugin Discovery surface — build; install if possible else park  
5. Keep this handoff updated; push often  

---

## 6. Risky decisions (testing deferred / incomplete)

Documented for the next agent — **do not treat as fully verified**:

1. **OptiQ reclaim via `pkill -INT -f 'optiq serve'`** — may kill operator foreground OptiQ; attach path avoids kill when identity matches. Live reclaim under wrong-model not fully exercised tonight beyond unit tests.  
2. **Approach 3** — may ship Gate A / partial wiring without full live suite.  
3. **Plugin** — new build may not install; production remains `0.3.0` until someone installs.  
4. **Stage 2 new IDs** — only Gemma; provider must already route Gemma OptiQ; no provider edit if reconnect fails.  
5. **oMLX down at handoff start** (`8100` failed health) — Discovery multi-server propose may need oMLX restarted by operator.  
6. Burning tokens / incomplete tests — prefer shipping code + honest “UNTESTED” markers over silent claims.

---

## 7. How to run common commands

```bash
cd /Users/jrazz/Dev/active/local-model-runtime-evaluation-harness
export PYTHONPATH=src
export PATH="/Users/jrazz/.local/bin:/opt/homebrew/bin:$PATH"

# Discovery
./bin/lmre-discover dry-config
./bin/lmre-discover propose
./bin/lmre-discover show <proposal_id>
./bin/lmre-discover execute <proposal_id> --family gemma-4-12b-qat

# Unit tests (Discovery + OptiQ lifecycle)
/opt/homebrew/bin/python3 -m unittest \
  tests.test_discovery_types tests.test_discovery_match \
  tests.test_discovery_execute tests.test_discovery_cli \
  tests.test_matrix_servers -v
```

OptiQ Gemma (operator), same as cell JSON:

```bash
optiq serve \
  --model /Users/jrazz/.cache/huggingface/hub/mlx-community/gemma-4-12B-it-qat-OptiQ-4bit \
  --host 127.0.0.1 --port 8080 \
  --no-anthropic --no-responses --no-auth
```

---

## 8. Progress log (append-only tonight)

### 2026-07-24 ~21:36 ET — Handoff created; starting commit A+C

- Servers at check: Osaurus `1337` OK, OptiQ `8080` OK, **oMLX `8100` DOWN**
- Next: commit A+C + investigation note + discovery.md; push; Stage 2 Gemma

### 2026-07-24 ~21:40 ET — Server guidance + Approach 3 + Stage 2 manifest + plugin 0.4.0 source

**Operator question answered — leave stack how?**

| Service | For Stage 2 harness smoke (`3.5.0`) | For Discovery / Approach 3 matrix |
|---------|--------------------------------------|-----------------------------------|
| **Osaurus `:1337`** | **Leave ON** | Leave ON |
| **OptiQ `:8080`** | **STOP (Ctrl+C)** before preflight — harness fails closed on busy port (no OptiQ attach in Stage 2 lifecycle) | Leave ON (A+C attach) |
| **oMLX `:8100`** | Optional / can stay off | Restart if propose needs inventory |

At this check: Osaurus OK, OptiQ still UP (awaiting operator stop for Stage 2), oMLX still down.

**Landed (code):**

- Approach 3 Gate A scaffold: design, recipes, `approach3.py` / `approach3_cli.py`, `bin/lmre-approach3`, `tests/test_approach3.py` (PASS). Live collect gated by `--i-understand-live` + marked UNTESTED.
- Stage 2 short-lived manifest: `manifests/stage-2-optiq-harness-route-20260724-003.json` (`stage2-20260724-003`, schema `3.5.0`, expires EOD Eastern). **Do not run until OptiQ is stopped.**
- Plugin source `0.4.0` adds `discover` tool (`dry-config`|`propose` only). Park under `plugins/osaurus-evaluation-harness/parked/0.4.0/` if install skipped; **production remains installed `0.3.0`**.

**Blocked on operator:** Stop OptiQ, then agent runs `./bin/lmre-stage0 preflight stage2-20260724-003` → `run-scenario` → `cleanup` (Metal/`all` perms).

### 2026-07-24 ~21:48 ET — `stage2-20260724-003` FAILED; starting `004`

- OptiQ was off; harness started Gemma OptiQ (`lifecycle_actions: 1`).
- Preflight waited ~300s for routed ID `optiq//…/gemma-4-12B-it-qat-OptiQ-4bit:no-think`.
- Osaurus `/v1/models` never listed any OptiQ IDs (local models only) → `route_identity_failed` / preflight error: *OptiQ routed model identity is missing or ambiguous*.
- `003` is **consumed** (bundle under canonical output; status `failed`). Cleanup then hit `evidence_incomplete` (wait-loop GETs bloated `request-evidence.jsonl`) — leftover OptiQ later gone; port `8080` free.
- New unused ID **`stage2-20260724-004`** manifest written. Preflight started; **needs one Optiq provider reconnect tap** (no edit) once OptiQ is up.

### 2026-07-24 ~21:49 ET — `stage2-20260724-004` sealed PASS

- Jason confirmed Optiq provider in Osaurus; port `8080` free; lock released after `003` cleanup (`STOPPED`).
- Preflight **PASS** (`route_identity: PASS`, lifecycle_actions 1).
- Worker completed 8/8 POSTs → `awaiting_review` → cleanup **PASS** (`inference_path_acceptance` + `behavioral_contract_acceptance` PASS; `checksum_validation` PASS; lifecycle_actions 2).
- Evidence: `docs/superpowers/verification/2026-07-24-slice-1c-stage2-20260724-004-pass.md`
- Do not reuse `001`–`004` (2026-07-24 Stage 2 IDs).

### 2026-07-24 ~21:50 ET — Plugin 0.4.0 parked; installed remains 0.3.0

- Source adds `discover` (`dry-config`|`propose`). Built release dylib parked at `plugins/osaurus-evaluation-harness/parked/0.4.0/` — **not installed** (gitignore `*.dylib`; rebuild from source).
- Parked sha256: `9c2f744a2ee8731e3e0b8fa1192b36c29a338b84ef5447c2166565c25adaff72`
- Root `libOsaurusEvaluationHarness.dylib` left as reviewed `0.3.0` artifact; `osaurus tools list` still `version=0.3.0`.
- Swift tests: 5/5 PASS for 0.4.0 surface. Approach3 unit tests: 7/7 PASS.

### 2026-07-24 ~21:58 ET — Non-live coding authorization (Jason leaving keyboard)

Jason authorized **non-live coding only**: finish as much as possible, **do not commit untested work**, document often. No live OptiQ start/stop or inference from the agent while he is away. No plugin install without later explicit approval.

**Queue (non-live):**
1. Fix Stage 2 harness inventory-wait `request-evidence.jsonl` bloat (caused `003` cleanup failure)
2. Approach 3 RAG collect stubs + tests (preference already scaffolded)
3. Docs backlog / r5 reconnect-tap note for future harness smoke
4. Commit+push only after unit tests pass for each slice

### 2026-07-24 ~22:05 ET — Stage 2 wait-loop request-evidence fix (tested)

**Bug:** harness inventory wait appended every failed poll’s GETs into `request-evidence.jsonl`, bloating failed preflights (`003` cleanup `evidence_incomplete`).

**Fix:** `_observe_routes_for_preflight` probes with `record_evidence=False`, then commits one successful observe (`record_evidence=True`). Timeout leaves zero durable GET evidence. Applied to smoke (`stage_two_inference.py`) and benchmark (`stage_two_benchmark.py`).

**Tests:** full `test_stage_two_inference_engine` + `test_stage_two_benchmark_engine` (66) PASS, including new evidence assertions.

### 2026-07-24 ~22:15 ET — Approach 3 RAG CLI + require_native_server plumbing (tested)

- `collect-rag --mode oracle|keyword` with `--i-understand-live` gate
- Recipes list `preference` + `rag`
- `preference_collect.run_collect` / `rag_collect.run_collect` take `require_native_server` (Approach 3 remaps)
- `tests/test_approach3.py` 9/9 PASS
- Backlog note: `docs/superpowers/notes/2026-07-24-non-live-backlog.md`

### 2026-07-24 ~22:20 ET — Docs + overhead stub (tested)

- README lists `lmre-approach3`
- `docs/stage-2-harness-unattended-gate-a.md` records `004` PASS, `003` STOPPED, evidence fix
- `collect-overhead` present but fail-closed `not_implemented` (11 Approach3 tests PASS)

**Non-live session pause point:** further live work needs Jason back for OptiQ/oMLX/provider or new IDs. Coding backlog remains in `2026-07-24-non-live-backlog.md`.

### 2026-07-24 ~22:06 ET — Jason returned: plugin 0.4.0 + collectors + run IDs

Jason authorized:
- Install plugin **0.4.0**
- As many unused Stage 2 / Discovery run IDs as needed
- Approach 3 **overhead collector** implementation
- oMLX is up (`8100` OK); Osaurus up; OptiQ down (harness may start)

### 2026-07-24 ~22:09 ET — Broad live authorization

Jason authorized every needed run ID and full live authority to complete the discussed harness work (plugin already at 0.4.0; Approach 3 overhead collector in tree).

### 2026-07-24 ~22:10–22:18 ET — Stage 2 `006` PASS + Approach 3 preference live

- Abandoned incomplete `005` (lock released; forced `failed`).
- `stage2-20260724-006` sealed **PASS** (8/8) — `docs/superpowers/verification/2026-07-24-slice-1c-stage2-20260724-006-pass.md`
- Approach 3 preference live **COLLECT_FINISHED** → `results/preference/gemma-4-12b-qat-preference-20260724-221046` (EXECUTED_UNSEALED)
- Plugin installed `0.4.0` with consent; Gate B pin updated in tree (`59bce25`)
- Restarted oMLX serve after preference stopped prior listener; RAG/overhead/Discovery propose in flight

### 2026-07-24 ~22:19–22:23 ET — Approach 3 RAG + overhead live; Discovery propose empty

| Collect | Result dir | Status |
|---------|------------|--------|
| RAG oracle | `results/rag/gemma-4-12b-qat-rag-20260724-221912` | COLLECT_FINISHED / EXECUTED_UNSEALED |
| RAG keyword | `results/rag/gemma-4-12b-qat-rag-20260724-222023` | COLLECT_FINISHED / EXECUTED_UNSEALED |
| Overhead | `results/overhead/overhead-20260724-222140` | COLLECT_FINISHED / EXECUTED_UNSEALED |

- `discovery-20260725-002` propose: empty `executable_families` (OptiQ+oMLX stopped by collectors).

### 2026-07-24 ~22:26 ET — Servers restored; Discovery propose `004` executable

- Restarted OptiQ Gemma `:8080` + oMLX oQ4 `:8100` as lasting background serves.
- `discovery-20260725-004` propose: `executable_families: ["gemma-4-12b-qat"]`.
- Execute in flight: `./bin/lmre-discover execute discovery-20260725-004 --family gemma-4-12b-qat`

### 2026-07-24 ~22:31 ET — Discovery execute FAIL (oMLX port reclaim)

- Preference step failed: `missing answer content … cell 'oq4_fp16__omlx'` — root cause `port 8100 did not free in time` (`omlX stop` does not kill Cursor-started `omlx-server`).
- Osaurus + OptiQ preference answers were complete; oMLX cell empty.
- Fix in tree: oMLX A+C attach (model present) / `pkill -INT -f omlx-server` reclaim (tests green).
- Freed `:8100`; OptiQ left up; re-execute `004` in flight.

### 2026-07-24 ~22:45 ET — Discovery `004` execute PASS; session live stack closed

- `discovery-20260725-004` execute **PASS** (preference + rag_oracle + rag_keyword).
  Evidence: `docs/superpowers/verification/2026-07-24-discovery-20260725-004-pass.md`
- Approach 3 live collects (all `EXECUTED_UNSEALED` / `COLLECT_FINISHED`): preference, RAG oracle, RAG keyword, overhead — see table above.
- Stage 2 harness smoke: `004` + `006` sealed PASS; `005` abandoned; IDs `001`–`006` consumed.
- Code fix landed: oMLX A+C attach/reclaim (`matrix_servers.py` + tests).
- Plugin `0.4.0` installed; Gate B pin expects `0.4.0`.
- Design-2 72-POST (`3.6.0` / r5) **not** run tonight (authorized but optional).
- Stack at close: Osaurus ON; OptiQ may still be ON; oMLX often stopped by collectors after execute.

**Honest seal note:** Approach 3 live results are `EXECUTED_UNSEALED` — not product-sealed PASS until a separate review pass.

_(End of 2026-07-24 live marathon log.)_
