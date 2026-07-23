# Cursor Handoff: Personal Model Selection MVP

> **ARCHIVE BANNER (2026-07-23):** Keep this handoff; do not delete. Personal
> selection remains **paused** per
> `docs/personal-selection-temporary-closeout-2026-07-16.md`. Phase B
> (Qwen AgentWorld / daily-driver selection) stays deferred until the Gemma
> harness frame is fully built out — then discuss reopen with an explicit
> bounded question. Not current Stage 2 / Package 2 operator guidance.

Use the following prompt in Cursor with this repository open:

```text
You are onboarding as the next coding manager for Jason Randazza's local model
evaluation project. Your first job is to understand the existing work and
propose the smallest practical path to answer one question:

Which local models are the best daily choices for Jason's personal Deep Wiki and
agent workflows on an M2 Max MacBook Pro with 64 GB unified memory?

This is a home-lab decision tool, not a research-grade benchmark platform.

REPOSITORY

/Users/jrazz/Dev/active/local-model-runtime-evaluation-harness

DEEP WIKI

/Users/jrazz/Documents/ObsidianNotes

MANDATORY SCOPE RESET

The project became substantially more elaborate than the original goal. Preserve
the existing Stage 0, Stage 1, Stage 2A, and stopped Stage 2B-1 work, but do not
continue hardening the automated Stage 2B-1 live harness now.

The five Stage 2B-1 architecture-review findings are valid future work, but they
are deferred. Do not fix them unless Jason explicitly reopens the future lab
lane. Do not run Gate B, create a manifest or run ID, contact an endpoint, load a
model, start or stop a service, reconnect a provider, reinstall a plugin, or run
any benchmark during this onboarding pass.

READ-ONLY ONBOARDING ORDER

1. Read repository AGENTS.md.
2. Read the Deep Wiki onboarding contract:
   /Users/jrazz/Documents/ObsidianNotes/00 System/Policies/Agent Onboarding Contract.md
3. Follow every required policy and authority check before any vault write.
4. Read the scope-reset record:
   /Users/jrazz/Documents/ObsidianNotes/20 Records/Projects/Local Model Stack/Tier 5/Local Model Benchmark Overhaul Scope Reset and Cursor Handoff - 2026-07-15.md
5. Read the canonical project note and board:
   /Users/jrazz/Documents/ObsidianNotes/10 Wiki/Projects/Local Model Benchmark Overhaul/Local Model Benchmark Overhaul.md
   /Users/jrazz/Documents/ObsidianNotes/10 Wiki/Projects/Local Model Benchmark Overhaul/Local Model Benchmark Overhaul Board.md
6. Read these history records only for context:
   - Stage 0 acceptance review
   - Stage 1 follow-up Gate C review
   - Stage 2 revision 3 acceptance review
   - Stage 2B-1 Gate A review
7. Inspect repository README.md, docs/architecture.md, docs/stage-1.md,
   docs/stage-2b1-gate-a.md, legacy/README.md, and
   legacy/benchmark_local_endpoints_v1.py.

The repository defines current executable truth. The Deep Wiki explains intent,
history, and decisions. When they disagree, inspect the repository first and
then propose a bounded Wiki correction.

WHAT ALREADY EXISTS

- Stage 0 proved the non-inference coordinator and evidence path.
- Stage 1 produced useful oMLX-direct versus Osaurus-routed timing evidence for
  one VibeThinker model and qualified unreliable streaming metrics.
- Stage 2A proved OptiQ service and route identity without inference.
- Stage 2B-1 implemented a highly governed eight-request inference acceptance
  path, but final review stopped it on five safety findings.
- A legacy manual endpoint benchmark already contains scenarios, prompts,
  warm-ups, repeated runs, aggregation, and report generation. It is reference
  material, not automatically production-ready: it uses fuzzy model matching,
  writes directly into the vault, and mixes broader cross-runtime ambitions into
  a personal model-choice task.

ACTIVE MVP HYPOTHESIS

Recommend a small, manual-first Personal Model Selection v1 rather than
continuing Stage 2B automation.

The likely MVP should:

- run one model and one serving lane at a time;
- let Jason start and stop the serving application manually;
- support a quick screening mode with 1 warm-up plus 3 measured repetitions;
- support a finalist mode with 1 warm-up plus 5 measured repetitions;
- use only 3 compact, synthetic, non-sensitive workloads:
  1. short instruction following;
  2. strict structured JSON output;
  3. Deep Wiki-style summarization and constraint following;
- record total response time, completion status, reliable visible-token evidence
  when available, formatting/contract success, and memory before/after;
- leave TTFT and decode throughput null when streaming or token evidence is not
  trustworthy;
- compare models first in their natural runtime for practical daily use;
- defer same-artifact cross-runtime science until it would answer a real decision;
- write raw JSON or CSV evidence under an ignored repository results directory;
- generate a reviewable Markdown summary in the repository;
- write durable conclusions to the Deep Wiki only after human review;
- use existing Keychain-backed credential handling and never copy secrets into a
  .env file, report, prompt, log, or vault note.

Prefer reusing small, already-tested measurement or reporting components when
that is genuinely simpler. A small separate MVP module is acceptable. Do not
force the MVP through the Stage 2B lifecycle, manifest, plugin, Sandbox, or
Coordinator machinery.

MODELS AND ORDER

Start with only the already-understood small candidates, probably VibeThinker 3B
and the existing Gemma model. Do not plan all downloaded models at once. After
the runner works, screen models in small batches and advance only promising
finalists. Models around 35B must run alone, with no simultaneous strong local
agent residency.

OUT OF SCOPE NOW

- fixing the five Stage 2B-1 review findings;
- automated service lifecycle or provider management;
- Osaurus Sandbox orchestration;
- Agent DB integration;
- plugin or MCP changes;
- subagent orchestration;
- remote-provider benchmarking;
- broad compatibility across future Osaurus, oMLX, and mlx-optiq releases;
- a definitive cross-framework suite;
- dashboards, databases, web apps, packaging, or productization;
- large model matrices;
- new live runs during onboarding.

FIRST DELIVERABLE - STOP BEFORE IMPLEMENTATION

Produce a concise proposal for Jason containing:

1. A current-state map of reusable assets versus frozen lab assets.
2. The minimum files you would create or modify for Personal Model Selection v1.
3. A simple operator flow written for a non-expert.
4. The exact three workloads and metrics.
5. A two-step test plan: quick screening, then finalists.
6. A definition of done that directly answers the personal model-choice question.
7. An estimate of implementation effort in small/medium/large terms, with the
   largest sources of uncertainty.
8. Explicit confirmation that Stage 2B-1 and its five findings remain deferred.

Do not edit code or the Deep Wiki until Jason approves that proposal. Keep the
proposal under 1000 words. Do not dispatch subagents for this onboarding review.

DEFINITION OF DONE FOR THE FUTURE MVP

The MVP is done when Jason can manually select one configured local model,
confirm its serving lane is ready, run a bounded serial screen, receive a
sanitized comparable report, and use that report plus a brief subjective check
to choose daily-driver and specialist candidates. It does not need autonomous
orchestration, exhaustive framework parity, or research-grade failure recovery.
```
