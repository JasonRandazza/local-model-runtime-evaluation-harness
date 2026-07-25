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

_(Subsequent sections appended below as work completes.)_
