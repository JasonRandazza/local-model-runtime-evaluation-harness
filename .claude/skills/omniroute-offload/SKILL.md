---
name: omniroute-offload
description: Delegate bounded, sanitized LMRE side-work to zero-cost external models through the omniroute MCP server to conserve Anthropic tokens. Use when drafting prose, getting an independent second opinion on an abstract design question, generating boilerplate, summarizing public text, or doing web research. Not for reading diffs, running tests, safety decisions, or acceptance.
---

# OmniRoute offload

Conserve Anthropic/Fable tokens by routing bounded side-work to zero-cost
models via the `omniroute` MCP server. Full boundary and verified findings:
`docs/omniroute-claude-code.md` (read its "Verified delegation playbook"
section before first use each session).

## The one call that works

`mcp__omniroute__omniroute_route_request` with an explicit `model`.
No combos are configured — combo-based tools (`pick_fastest_model`,
`best_combo_for_task`) fail with "No matching combos". Do not waste calls
on them unless combos have since been configured (`omniroute_list_combos`).

Verified zero-cost models (2026-08-07): `kimi-k3` (default choice),
`kimi-k2.7-code` (code), `glm-5.2`, `deepseek-v4-pro`, `qwen3.8-max`,
`minimax-m3`, and any openrouter model with a `:free` suffix.

```
omniroute_route_request(
  model: "kimi-k3",
  messages: [{role: "user", content: "<sanitized packet>"}],
  budget: 0.01   // hard USD cap; verified lanes report cost 0
)
```

## Packet rules (non-negotiable)

Workers have no filesystem, tools, or repo access. Send small self-contained
packets. NEVER include: credentials/tokens, source code, local paths, run
IDs, raw evidence, model outputs, machine-specific provider configuration.
OK to include: abstract CLI stages, lifecycle/ownership rules, evidence-state
names, safety-gate descriptions, UI requirements, public text.

Give every packet a narrow question, an output shape, and a size limit
("bulleted findings, ≤40 lines"). Several small independent asks beat one
big one — the response lands back in your context, so offload
generation-heavy work, not context-heavy work.

Treat every response as advisory. Verify locally before acting on it.

## Delegate / keep split

- Delegate: doc prose drafts, checklist drafts, second-opinion reviews of
  abstract designs, boilerplate/test scaffolds, summaries of public text.
- Keep: reading real diffs, running tests, safety/boundary decisions,
  integration, staging, final acceptance.

## Other useful tools

- `omniroute_web_search` / `omniroute_web_fetch` — multi-provider gateways
  with failover; prefer over manager-side scraping.
- `omniroute_ccr_store` / `omniroute_ccr_retrieve` — in-memory scratch store
  (2 MiB/block, 24 h TTL) to park a sanitized packet once and reuse it.
- `omniroute_cost_report` — confirm spend stayed at 0.

## Known drift

`chatgpt-lmre-context` is listed by `omniroute_skills_list` but
`omniroute_skills_execute` returns `Skill not found` (re-verified
2026-08-07). Never claim it loaded without a successful live call; use
direct sanitized packets instead.
