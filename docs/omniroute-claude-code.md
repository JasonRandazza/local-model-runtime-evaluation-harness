# OmniRoute MCP setup for Claude Code

This guide connects Claude Code to the local OmniRoute MCP server without
placing its bearer credential in this repository, the Deep Wiki, a prompt, or
shell history.

## Current verified boundary

- Recommended transport: streamable HTTP
- Loopback endpoint: `http://127.0.0.1:20128/api/mcp/stream`
- Latest MCP health observed during the LMRE UI slice: OmniRoute `3.8.49`,
  healthy cryptography, no open circuit breaker, and no active rate limit
- Do not use the stdio transport for this setup; it was not verified for this
  OmniRoute release.
- The registered `chatgpt-lmre-context` skill currently has a drift condition:
  its fixed MCP wrapper returned `Skill not found` in the latest check. This is
  not a blocker to generic OmniRoute tools, but Claude must not claim the named
  context skill loaded until a live call succeeds.

The credential belongs in an approved local secret store or a temporary shell
environment. Never copy it into `.mcp.json`, `~/.claude.json`, command-line
arguments, repository files, vault notes, logs, or model prompts.

## One-time Claude registration

Claude Code supports environment expansion in MCP configuration, including
HTTP headers. Register a local-scope server with the placeholder intact:

```bash
claude mcp add-json --scope local omniroute \
'{"type":"http","url":"http://127.0.0.1:20128/api/mcp/stream","headers":{"Authorization":"Bearer ${OMNIROUTE_MCP_TOKEN}"}}'
```

Equivalent configuration shape:

```json
{
  "mcpServers": {
    "omniroute": {
      "type": "http",
      "url": "http://127.0.0.1:20128/api/mcp/stream",
      "headers": {
        "Authorization": "Bearer ${OMNIROUTE_MCP_TOKEN}"
      }
    }
  }
}
```

Use local scope unless Jason deliberately wants a user-wide configuration.
Do not commit a project-scoped `.mcp.json` for this personal loopback service.

## Start a Claude session safely

1. Confirm OmniRoute is running locally using its ordinary health/status
   workflow. Do not reveal keys while diagnosing it.
2. Load the MCP token from the approved local secret store into
   `OMNIROUTE_MCP_TOKEN` in the same shell that will launch Claude Code. The
   exact secret-store lookup is machine-specific and intentionally not
   documented here.
3. Confirm only that the variable is populated, never its value.
4. Launch Claude Code from that shell.

If a one-session hidden prompt is needed instead of an existing secret-store
loader, use:

```bash
read -s "OMNIROUTE_MCP_TOKEN?OmniRoute MCP token: "
export OMNIROUTE_MCP_TOKEN
printf '\n'
claude
```

The token remains in that process environment. Unset it when the session is
finished:

```bash
unset OMNIROUTE_MCP_TOKEN
```

## Verify inside and outside Claude

Before delegating real work:

```bash
claude mcp get omniroute
claude mcp list
```

Then open `/mcp` inside Claude Code, approve the local server if prompted, and
perform only read-only checks:

1. request OmniRoute health;
2. list available skills/tools and current cost state;
3. call the desired tool with a harmless synthetic packet;
4. if using `chatgpt-lmre-context`, require an actual successful invocation
   before treating it as available.

Installed or registered is not the same as behaviorally verified.

## Safe LMRE delegation pattern

OmniRoute workers do not inherit Claude's filesystem or tools. Send a small,
self-contained packet containing only the information needed for the bounded
question. Treat every worker response as advisory and verify it locally.

For LMRE, obtain explicit current-session authorization before external model
transmission. Unless the authorization says otherwise, exclude:

- credentials, tokens, headers, or secret-store details;
- source code and local filesystem paths;
- run IDs, raw evidence, model outputs, or private prompts;
- machine-specific model locations and provider configuration;
- GitHub authentication or unpublished personal data.

Suitable sanitized material can include abstract CLI stages, lifecycle and
ownership rules, evidence states, safety gates, and UI requirements. Give each
request a narrow question, expected output shape, and size limit. Use several
small independent reviews rather than one repository-sized prompt.

No OmniRoute worker receives Git, filesystem, process, provider, evidence-write,
or live-run authority. Claude remains responsible for reading the actual diff,
running local verification, and rejecting unsafe suggestions.

## Failure recovery

If Claude cannot connect:

1. confirm OmniRoute is running and the loopback endpoint is healthy;
2. confirm `OMNIROUTE_MCP_TOKEN` is set in the same parent shell without
   printing it;
3. inspect `claude mcp get omniroute` for the placeholder and endpoint;
4. use `/mcp` to inspect the connection error;
5. if the entry is malformed, remove and recreate only that local entry:

```bash
claude mcp remove --scope local omniroute
```

Do not respond to a connection failure by exporting credentials to logs,
embedding a literal token in configuration, using a remote endpoint, or
changing LMRE provider configuration. The current named-context-skill drift is
an OmniRoute integration issue and can be bypassed with approved, directly
sanitized prompts; it is not a reason to modify LMRE.

Claude Code MCP reference: <https://code.claude.com/docs/en/mcp>

## Verified delegation playbook (2026-08-07)

Behaviorally verified in a live Claude Code session against OmniRoute 3.8.49.
Companion skill for Claude Code sessions: `.claude/skills/omniroute-offload/SKILL.md`.

### What actually works

- `omniroute_route_request` with an explicit `model` is the working
  delegation path. Verified round-trip on `kimi-k3`: correct response,
  `cost: 0`, ~5–7 s latency.
- No combos are configured. `omniroute_pick_fastest_model`,
  `omniroute_best_combo_for_task`, and combo-scoped tools return
  "No matching combos" — pass `model` directly instead.
- Zero-cost model lanes observed in the catalog:
  - `opencode-go` provider: `kimi-k3`, `kimi-k2.7-code`, `glm-5.2`,
    `deepseek-v4-pro`, `deepseek-v4-flash`, `qwen3.8-max`, `minimax-m3`
  - `openrouter` provider: any `:free`-suffixed model
  - The `CheaperInference` proxy reports `cost: 0` per its own accounting.
- `chatgpt-lmre-context` skill drift is still present: it appears in
  `omniroute_skills_list` but `omniroute_skills_execute` returns
  `Skill not found` (re-verified 2026-08-07). Use direct sanitized packets;
  do not claim the skill loaded without a successful live call.
- `omniroute_ccr_store` / `omniroute_ccr_retrieve` provide a caller-isolated
  in-memory scratch store (2 MiB/block, default TTL 24 h). Useful for parking
  a large sanitized packet once and referencing it across calls instead of
  resending it.
- `omniroute_web_search` and `omniroute_web_fetch` are multi-provider
  gateways with failover — prefer them over manager-side scraping for
  release-readiness research (packaging norms, changelog conventions, etc.).
- `omniroute_cost_report` (period `session`/`day`/`week`) confirms spend;
  `route_request` accepts a per-request `budget` in USD as a hard cap.

### Measured limitation: long generations time out

Re-tested 2026-08-07 during the release-readiness slice. A trivial prompt
(one-line echo) round-trips in about 5–7 s. Three separate attempts to
generate a ~40-line checklist — on `kimi-k3`, `glm-5.2`, and
`gemini-3-5-flash` — all aborted on timeout at the MCP call boundary, and
none of the three even registered in `omniroute_cost_report`, so they
expired before the provider accounted for them.

Practical consequence: this transport is currently reliable for **short**
exchanges, not for bulk drafting. Do not plan a slice around offloading
long-form generation until this is retested and shown fixed. Ask for small
outputs (a handful of lines), or split one large ask into several small
ones and assemble locally. When a delegation times out, write the content
yourself rather than retrying the same prompt — three retries cost more
wall-clock than drafting it.

### What to delegate vs. keep

Delegate (sanitized packets only): draft prose for docs/checklists,
independent second-opinion review of abstract design questions, boilerplate
and test-scaffold generation, summarization of public text, web research.

Keep with the manager (Anthropic side): reading the actual diff, running
tests, safety and boundary decisions, integration, staging plans, and final
acceptance. Worker output is advisory discovery evidence, never acceptance.

Token economics: a worker response still enters the manager's context, so
savings come from offloading generation-heavy or knowledge-heavy asks, not
from shipping large context out and back. Keep packets small and questions
narrow; request bounded output ("≤40 lines", "bulleted findings only").

The sanitization boundary above (no credentials, source paths, run IDs, raw
evidence, model outputs, machine-specific configuration) remains in force for
every packet unless Jason explicitly changes it in the current session.
