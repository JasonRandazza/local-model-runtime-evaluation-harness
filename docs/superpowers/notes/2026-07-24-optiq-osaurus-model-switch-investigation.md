# Investigation: OptiQ / Osaurus model switching for Discovery + overhead

**Date:** 2026-07-24  
**Status:** INVESTIGATION + SPIKE B vs C (live OptiQ)  
**Context:** Discovery MVP Gate A passed. Live `execute` for `gemma-4-12b-qat` failed because preference collect tried to spawn OptiQ while an operator `optiq serve` already owned `:8080` (`port 8080 is busy`). Separately, propose marked Ornith/Qwen OptiQ cells `identity_ok: false` while OptiQ was up with only Gemma inventory. Jason asked whether CLI/HTTP can switch models so Discovery and overhead lanes can automate without silent copies or endless reconnect pain.

**Does not authorize:** Stage 2 run IDs, provider file edits, plugin rebuild, or changing sealed suite semantics.

## What we already knew

- Matrix OptiQ cells pin `optiq serve --model <artifact> …` (single boot model) and `:no-think` client ids for content streaming (`docs/matrix.md`).
- Stage 2 / overhead often need the **exact** OptiQ-resident model to match the routed Osaurus provider id.
- Osaurus provider **edit** remains forbidden; reconnect/verify is a separate north-star track (`docs/superpowers/notes/2026-07-22-slice-1c-provider-reconnect-note.md`).
- Harness `SubprocessServerHandle` for OptiQ: if port busy → hard fail (`matrix_servers.py`). Osaurus may start only if port free; oMLX may `omlX stop` then restart.

## OptiQ CLI / serve findings (2026-07-24)

Installed entry: `~/.local/bin/optiq` (mlx-optiq). Top-level commands: `serve`, `convert`, `lab`, `eval`, … — **no** `load` / `unload` / `switch` subcommand.

Relevant `optiq serve` flags:

| Flag | Behavior |
|------|----------|
| `--model PATH` | Boot / default model (required for normal matrix cells). |
| `--single-model` (**default**) | Request `model` field is a **label**; every request serves boot `--model`. |
| `--allow-model-switch` | Request `model` may **hot-swap** to another cached model (stock mlx-lm behavior). |
| `--models-dir DIR` | Advertise extra local quants in `/v1/models`; **implies** `--allow-model-switch`. |
| `--idle-timeout N` | Unload after N idle seconds; lazy reload on next request (default `0` = off). |

Live baseline (operator Gemma serve, single-model default):

- Process: `optiq serve --model …/gemma-4-12B-it-qat-OptiQ-4bit --host 127.0.0.1 --port 8080 --no-anthropic --no-responses --no-auth`
- `GET /v1/models`: only Gemma path + `:think` / `:no-think` / `:precise` / `:creative` variants — **no** Ornith/Qwen ids.

Implication: Discovery identity for non-boot OptiQ families will fail under current cell start commands until we either restart with another `--model` or enable allow-model-switch / models-dir and prove inventory + swap.

## Osaurus CLI findings (2026-07-24)

`osaurus --help` exposes: `serve`, `stop`, `status`, `doctor`, `list`, `show`, `pull`, `run`, `bench`, tools/*, `coord`, …  

**No** documented `load` / `unload` / `switch` for the HTTP server.

Observed live `/health` fields (server was resident):

- `current_model`, `loaded[]`, `resident_models[]` (includes idle unload timers)

So residency is real and idle-unload exists **inside the app**, but the CLI does not currently give the harness a first-class “make this model current” verb. `osaurus run <model_id>` is interactive chat, not server orchestration. `osaurus coord` remains foundation-only.

Routed OptiQ for overhead still depends on provider attach/reconnect — orthogonal to OptiQ-local hot-swap.

## Pathway menu (Discovery / multi-family OptiQ)

| Path | Idea | Pros | Cons |
|------|------|------|------|
| **A** | Attach when port busy if health+identity already match; else start | Fixes tonight’s busy-port false fail for same model | Does not help multi-family OptiQ alone |
| **B** | Long-lived `optiq serve --allow-model-switch` (+ optional `--models-dir`) | One process; HTTP `model` swaps; closer to hands-off Discovery | Inventory/timing/RAM behavior must be proven; may surprise Stage 2 single-model pins; swap cost unknown |
| **C** | Per-family (or per-cell) restart with pinned `--model` | Matches today’s cell JSON; exact identity; fail-closed | Slow; busy-port conflicts with operator serve; Discovery must own stop/start |
| **D** | Osaurus CLI/API spike for residency + provider reconnect | Needed for overhead/routed honesty | Separate from OptiQ-local switch; incomplete CLI today |

**A is still required plumbing** regardless of B vs C (Discovery execute vs operator-owned port).

## Spike protocol: B vs C (OptiQ only)

**Goal:** Decide which OptiQ multi-model pathway to prefer *for now* for Discovery family switching.

**Models:**  
- Boot / control: Gemma OptiQ-4bit (already pinned)  
- Switch target: Ornith OptiQ-4bit (`config/matrix/cells/ornith_optiq_4bit__optiq.json`)

**Metrics:**

1. Wall time to usable `/health` + inventory containing target `:no-think` id  
2. Whether `GET /v1/models` lists the target **before** any chat (identity for Discovery propose)  
3. Whether a minimal streaming chat returns non-empty `delta.content` on `:no-think`  
4. RAM / failure modes (OOM, hang, 404)  
5. Operational fit: conflict with operator foreground serve; restore Gemma single-model after spike

**B steps:**

1. Stop current OptiQ on `:8080`  
2. Start: same argv as Gemma cell **plus** `--allow-model-switch`  
3. Record inventory  
4. Issue one short chat with `model` = Ornith `:no-think` id (or path); time to first token / completion  
5. Record inventory again  
6. Stop OptiQ  

**C steps:**

1. Start: Ornith cell `start_command` exactly (single-model)  
2. Time to health + inventory containing Ornith `:no-think`  
3. One short `:no-think` chat  
4. Stop; restart Gemma cell command; confirm Gemma inventory restored  

**Decision rule (for now):**

- Prefer **B** if Ornith becomes usable via hot-swap **and** Discovery can see the target id in inventory (or we add a cheap post-swap inventory refresh) without multi-minute full restarts per family.  
- Prefer **C** if B fails identity/chat, OOMs, or inventory never lists non-boot models so propose stays fail-closed.  
- Keep **A** either way.

## Spike results

Live run log: `results/discovery/spike-b-vs-c-20260724.log`  
Serve logs: `results/discovery/spike-b-optiq.log`, `spike-c-optiq.log`, `spike-b2-optiq.log`

**Note:** First pass’s chat helper failed (`bad substitution` under zsh). Path **B** chat was retested with a fixed Python client (`B2_*` lines in the log). Path **C** chat was not retested; C’s inventory result stands.

| Metric | B (`--allow-model-switch`, boot Gemma) | C (restart `--model` Ornith) |
|--------|----------------------------------------|------------------------------|
| Stop→`/health` 200 (boot) | ~2.1s (model loads on **first request**, not at listen) | ~2.1s (same lazy-load behavior) |
| Inventory lists Ornith **before** chat? | **No** — only Gemma path + variants | **Yes** — Ornith path + `:think` / `:no-think` / … |
| Hot-swap / cold start evidence | Chat with `model=…Ornith…:no-think` returned `content: "ready"` in **26.3s**, but `/v1/models` **still only Gemma** afterward; serve log never mentions Ornith → almost certainly **served boot Gemma under the requested id** (swap not proven) | Inventory proves boot model identity for Discovery propose without a prior chat |
| Short `:no-think` chat OK? | Ambiguous / likely false positive for Ornith | Not re-run after helper bug (inventory already decisive) |
| Notes / errors | `--allow-model-switch` alone does **not** advertise non-boot families in `/v1/models`; Discovery propose identity would still fail for Ornith/Qwen | Matches today’s cell `start_command`; multi-family needs stop/start per OptiQ model |

**OptiQ serve behavior confirmed:** listener comes up fast; weights load on first request (“Expect a one-time pause…”). Discovery `list_models` can pass while weights are still cold — ready-wait must still demand the target id (and preferably a real generation for execute).

### Verdict

**Prefer pathway C for now** (per-family / per-OptiQ-model restart with pinned `--model`), plus pathway **A** (attach when port busy **and** inventory already matches the pinned id).

**Do not adopt B yet** for Discovery multi-family OptiQ:

1. Inventory stays boot-model-only without a proven advertise path (`--models-dir` not spiked).  
2. A successful chat on a non-boot `model` id is **not** proof of swap under current evidence.  
3. Fail-closed propose needs the target id in `/v1/models` before execute.

Revisit **B** later only with an explicit advertise+swap proof (e.g. `--models-dir` or documented mlx-lm inventory update after swap) and a response that cannot be Gemma-answering-under-wrong-label.

**Osaurus (path D):** still no CLI load/switch; overhead/routed work remains a separate spike.

Gemma single-model OptiQ on `:8080` was restored after the spike (`RESTORE` / `RESTORE_FINAL`).

## Recommended follow-ups (after verdict)

1. **Done (2026-07-24):** Pathway **A+C** in `matrix_servers.SubprocessServerHandle` for OptiQ — attach when busy+inventory matches `cell.model_id`; otherwise `pkill -INT -f 'optiq serve'`, wait for free port, spawn pinned `start_command`. Attach leaves `owned=False` so stop does not kill an operator-matched serve.  
2. Defer **B** until inventory advertise + real swap are proven (optional `--models-dir` spike).  
3. Separate spike **D** for Osaurus residency + provider reconnect (overhead).  
4. Commit Discovery `credential_for` propose wiring + this OptiQ lifecycle change together when Jason asks.

## References

- Design: `docs/superpowers/specs/2026-07-24-discovery-mvp-design.md`  
- Busy-port failure: `results/discovery/discovery-20260724-002/execution.json`  
- Cells: `config/matrix/cells/optiq_4bit__optiq.json`, `ornith_optiq_4bit__optiq.json`  
- Lifecycle: `src/local_model_runtime_evaluation/matrix_servers.py`
