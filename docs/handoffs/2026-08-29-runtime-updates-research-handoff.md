# LMRE side-step handoff — runtime updates research — 2026-08-29

**Side-step, not a continuation.** This supersedes nothing. For branch state,
authority boundary, reading order, and the main line of work, read
`docs/handoffs/2026-08-22-continuation-handoff.md` first — all of it still
applies. This document covers one bounded investigation that interrupted that
line: Osaurus, oMLX, and mlx-optiq all shipped significant updates, and we
stopped to find out whether the harness still holds.

Authority: begin read-only. This document grants nothing. No live model runs,
no commits, no policy adoption without explicit current-session permission.

---

## 1. Why this exists

The concern was that upstream updates would force a structural change to the
harness. **They did not.** Phase 0 is complete and the answer is no. What the
updates *did* introduce is a set of new upstream defaults that silently change
what the harness measures, plus some upstream tooling that may make part of the
harness redundant. Those two things are the remaining work.

## 2. The coupling surface (verified 2026-08-29)

The harness touches these runtimes in exactly four places. Nothing else in the
codebase talks to them.

| What | Where |
|---|---|
| osaurus argv, fixed | `src/local_model_runtime_evaluation/runtime_adapters/osaurus.py:16` |
| optiq argv, fixed | `src/local_model_runtime_evaluation/runtime_adapters/optiq.py:21` |
| omlx argv, validated | `src/local_model_runtime_evaluation/runtime_adapters/omlx.py:50` |
| base URL shape | `src/local_model_runtime_evaluation/runtime_adapters/base.py:234` |

Adapter sizes: osaurus 42 lines, optiq 62, omlx 197, base 419. The blast radius
is three argv tuples, three fixed ports, one URL shape, and the oMLX temp
catalog format.

## 3. Phase 0 — DONE. Every hardcoded flag still exists.

Verified against locally installed CLIs on 2026-08-29.

| Adapter | Hardcoded | Result |
|---|---|---|
| osaurus | `serve --port 1337 --yes` | all valid |
| optiq | `--no-anthropic`, `--no-responses`, `--no-auth` | all three present |
| optiq | `--model`, `--host`, `--port` | still forwarded to `mlx_lm.server` |
| omlx | `--model-dir`, `--host`, `--port`, `--base-path`, `--api-key` | all present |

Versions seen: `mlx-optiq 0.4.2`; osaurus app `0.24.1` but CLI `--version`
reports the string `dev`; omlx has no working `--version` (it tracebacks).

Endpoint probe against a live osaurus on 1337: `/v1/models` 200, `/health` 200,
`/v1/health` 200, `/metrics` 404, `/v1/metrics` 404. No Prometheus scrape path.

**Footgun found:** `osaurus serve --help` is not recognised as help — it starts
the server. Use `osaurus --help` and read the `serve` usage line. If you trip
it, `osaurus stop`.

**No adapter rewrite is needed.** Do not start tomorrow by refactoring adapters.

## 4. Phase 1 — NOT STARTED. Pin the volatile defaults.

This is the real risk Phase 0 surfaced. These upstream defaults are not pinned
in any cell config under `config/matrix/cells/`, so runs inherit whatever
upstream decided. Ranked by how much they threaten a comparable result:

1. **`optiq --max-context auto` is ON by default.** It engages a memory-safe KV
   cap *only when the model's native context would not fit RAM* — which makes
   it **machine-dependent**. The same cell can produce different results on a
   64GB vs a 32GB Mac, with nothing in the artifact explaining why. This is the
   most serious finding in the whole investigation. Decide on an explicit value
   (`off`, or a hard integer cap) and pin it.
2. **oMLX cache and concurrency defaults** — paged SSD cache is on (`--no-cache`
   disables it), `--initial-cache-blocks` 256, `--max-concurrent-requests` 8,
   `--memory-guard` is tiered (`off|safe|balanced|aggressive`). All four move
   TTFT and throughput directly. None are pinned.
3. **`optiq --single-model` is now the default.** The request `model` field is
   treated as a label, so a wrong model id is served the loaded model instead of
   404ing. Check whether any test asserted on that 404 — if so it is now
   silently passing and proving nothing.
4. **No version pins anywhere.** `grep` for version capture across `src/` found
   nothing that records the runtime version into a run's provenance. Combined
   with osaurus reporting `dev`, an artifact currently cannot say what it ran
   against.

   **Tread carefully here.** Jason explicitly rejected runtime-version
   regression (measuring a model across Osaurus 0.22.10 vs 0.22.11) and the
   whole version-capture subtree was built and then deliberately dropped. Do
   not resurrect it. What is proposed here is narrower and different in kind:
   recording *what the run ran against*, as provenance on the artifact, so a
   result is interpretable later. It is not a comparison axis and must not grow
   into one. If implementing it starts to look like the dropped subtree, stop
   and ask rather than rebuilding what was killed.

Note that pinning flags means changing the fixed argv tuples in the adapters,
which is the one place the harness deliberately refuses to be configurable.
Read `AGENTS.md` on the non-live boundary before deciding how — this may want an
ADR rather than an edit.

## 5. Phase 2 — NOT STARTED. Does upstream tooling replace ours?

The updates shipped measurement tooling that overlaps what we built:

- **`osaurus bench --model <id> --prompt-tokens ... --runs N --json <path>`** —
  emits TTFT / prefill / decode, tagged with hardware info. This is the one
  worth real scrutiny: it overlaps a meaningful part of our own measurement
  path. It needs an actual comparison run against our numbers, not a reading of
  its docs. Do not adopt it on the strength of its flag list.
- **`osaurus doctor --json [--redact]`** — machine-readable environment capture
  (app version, model root, port owner, health). We have our own
  `src/local_model_runtime_evaluation/doctor.py` and `docs/doctor.md`; check
  whether ours is now partly redundant.
- `optiq benchmark`, `optiq eval`, `optiq latency`, and `omlx diagnose` — same
  category, unexamined.

The honest question for each: does it measure what we measure, under conditions
we control? A tool that reports TTFT under its own defaults is not a substitute
for a harness that pins them.

## 6. Token discipline (this was an explicit constraint)

Phase 0 cost almost nothing because the CLIs are installed locally and answer
the question directly. Keep that shape:

- Ground truth first: `--help` output and live endpoint probes beat changelogs,
  and they cannot be wrong by omission.
- `Context7` MCP is connected — targeted library-doc excerpts, cheaper than
  `WebFetch` on a long changelog.
- For anything that genuinely needs reading a large document: `curl` it to a
  file, hand the file to `pi-bonsai-direct -p "..."` ($0, omarchy) or
  `dsh --profile headless`, and pull back only the summary. Do not read a
  3000-line changelog into the orchestrator's context.
- Web research is now mostly unnecessary. The only open web-shaped question is
  *why* optiq changed the model-switch default, and only if it matters.

## 7. Suggested order tomorrow

1. Re-read section 3 so you do not re-verify what is already verified.
2. Phase 1, item 3 first — it is a five-minute check and it may mean a test is
   currently lying.
3. Phase 1, item 1 — decide and pin `--max-context`. Likely wants an ADR.
4. Phase 1, items 2 and 4 together — pin the oMLX defaults and add version
   capture to provenance in the same slice.
5. Phase 2 only after the above. It is a comparison study, not a config change,
   and it deserves its own session.

None of this blocks the discovery-as-proposer slice described in the
2026-08-22 continuation handoff. If tomorrow is short, Phase 1 item 1 is the
one thing that should not wait.
