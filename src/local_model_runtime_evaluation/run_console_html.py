"""Escaped, server-rendered HTML for the local LMRE run console."""

from __future__ import annotations

import html

from .run_console import ACTION_RESUME, ACTION_START

_EM_DASH = "—"

_STYLE = """
:root{color-scheme:light;--bg:#fff;--surface:#f7f8fa;--text:#15171a;
--muted:#5e6470;--rule:#d9dde4;--blue:#1558d6;--blue-soft:#edf3ff;
--green:#147a4b;--amber:#9a5b00;--red:#b42318;--focus:#0b6cff;
font-family:Inter,ui-sans-serif,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);
font-size:15px;line-height:1.45}a{color:var(--blue)}a:focus-visible,
button:focus-visible,input:focus-visible{outline:3px solid var(--focus);
outline-offset:2px}.topbar{display:flex;align-items:baseline;gap:1rem;padding:1rem 1.4rem;
border-bottom:1px solid var(--rule)}.topbar h1{font-size:1.35rem;margin:0}
.local{color:var(--muted)}.shell{display:grid;grid-template-columns:21rem minmax(0,1fr);
min-height:calc(100vh - 4rem)}.rail{border-right:1px solid var(--rule);padding:1.25rem}
.rail{max-height:calc(100vh - 4rem);overflow-y:auto;position:sticky;top:4rem;
align-self:start;scrollbar-gutter:stable}
.rail h2,.content h2{font-size:1rem;margin:.2rem 0 .8rem}.plan-list{list-style:none;
padding:0;margin:1rem 0}.plan-list li{border-top:1px solid var(--rule)}
.plan-list a{display:block;color:inherit;text-decoration:none;padding:.85rem .65rem}
.plan-list a:hover,.plan-list a[aria-current=page]{background:var(--blue-soft)}
.plan-name{display:block;font-weight:650;overflow-wrap:anywhere}.plan-meta{display:flex;justify-content:space-between;
gap:.75rem;color:var(--muted);font-size:.82rem;margin-top:.25rem}.content{padding:1.4rem 2rem;
min-width:0}.content-head{display:flex;align-items:flex-start;justify-content:space-between;
gap:1rem;border-bottom:1px solid var(--rule);padding-bottom:1rem}.content-head>div:first-child{
min-width:0}.content h2.run-title{font-size:1.35rem;margin:0;overflow-wrap:anywhere}.status{
font-weight:750;letter-spacing:.02em}.status-PASS,
.status-SEALED_VERIFIED{color:var(--green)}.status-FAIL,.status-SEALED_CORRUPT{color:var(--red)}
.status-PARTIAL_BLOCKED,.status-STOPPED{color:var(--amber)}.status-PENDING,
.status-RUNNING{color:var(--blue)}.toolbar{display:flex;flex-wrap:wrap;gap:.6rem}
.button,button{appearance:none;border:1px solid #aeb5c0;background:#fff;color:var(--text);
border-radius:.3rem;padding:.58rem .82rem;font:650 .9rem/1.2 inherit;text-decoration:none;
cursor:pointer}.button.primary,button.primary{background:var(--blue);border-color:var(--blue);
color:#fff}.button.danger,button.danger{border-color:var(--red);color:var(--red)}
section{margin:1.4rem 0}.facts{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));
gap:0;border-top:1px solid var(--rule);border-left:1px solid var(--rule)}
.fact{padding:.65rem .8rem;border-right:1px solid var(--rule);border-bottom:1px solid var(--rule)}
.fact dt{color:var(--muted);font-size:.78rem}.fact dd{margin:.15rem 0 0;overflow-wrap:anywhere}
.table-wrap{overflow-x:auto}table{border-collapse:collapse;width:100%;font-size:.88rem}
th,td{text-align:left;vertical-align:top;border-bottom:1px solid var(--rule);padding:.55rem .6rem}
th{color:#343942;font-weight:700}.notice,.error{padding:.8rem 1rem;border-left:4px solid var(--amber);
background:#fff8ed}.error{border-color:var(--red);background:#fff1f0}.authority{max-width:46rem;
border:1px solid var(--rule);padding:1rem 1.1rem}.authority label{display:block;font-weight:650;
margin:.8rem 0 .3rem}.authority input[type=text]{width:100%;padding:.65rem;border:1px solid #9aa2ae;
font:inherit}.check{display:flex!important;align-items:flex-start;gap:.55rem;font-weight:400!important}
.check input{margin-top:.3rem}.authority .actions{display:flex;gap:.6rem;margin-top:1rem}
.muted{color:var(--muted)}.empty{padding:3rem 1rem;text-align:center;color:var(--muted)}
@media(max-width:850px){.shell{grid-template-columns:1fr}.rail{border-right:0;
border-bottom:1px solid var(--rule);max-height:42vh;position:static}.content{padding:1.2rem}.content-head{display:block}
.toolbar{margin-top:1rem}.facts{grid-template-columns:1fr}.plan-meta{justify-content:flex-start;
flex-wrap:wrap}}
"""


def _text(value: object) -> str:
    if value is None:
        return _EM_DASH
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, (list, tuple)):
        return ", ".join(_text(item) for item in value) or _EM_DASH
    return str(value)


def _cell(value: object) -> str:
    return html.escape(_text(value))


def _page(title: str, body: str) -> str:
    return (
        '<!doctype html>\n<html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f"<title>{html.escape(title)}</title><style>{_STYLE}</style></head>"
        f"<body>{body}</body></html>\n"
    )


def _status(value: object) -> str:
    text = _text(value)
    css = "".join(
        character for character in text if character.isalnum() or character in "-_"
    )
    return f'<span class="status status-{css}">{html.escape(text)}</span>'


def _plan_rail(entries: list[dict], selected_run_id: str | None) -> str:
    rows = []
    for entry in entries:
        run_id = str(entry["run_id"])
        current = ' aria-current="page"' if run_id == selected_run_id else ""
        rows.append(
            "<li>"
            f'<a href="/runs/{html.escape(run_id)}"{current}>'
            f'<span class="plan-name">{_cell(entry["run_name"])}</span>'
            '<span class="plan-meta">'
            f"<span>{_status(entry['run_status'])}</span>"
            f"<span>{_cell(entry['created_at'])}</span>"
            "</span></a></li>"
        )
    empty = '<p class="muted">No managed plans found.</p>' if not rows else ""
    return (
        '<aside class="rail"><h2>Plans</h2>'
        '<p class="muted">Select an existing immutable plan.</p>'
        f'<ul class="plan-list">{"".join(rows)}</ul>{empty}</aside>'
    )


def _facts(identity: dict, policy: dict | None) -> str:
    values = (
        ("Plan hash", identity.get("plan_hash")),
        ("Comparison scope", identity.get("comparison_scope")),
        ("Family", identity.get("family_id") or identity.get("open_mix_id")),
        ("Recipe", identity.get("recipe_id")),
        ("Policy", (policy or {}).get("policy_id")),
        ("Created", identity.get("created_at")),
        ("Requests", identity.get("request_count")),
        ("Estimated minutes", identity.get("estimated_minutes")),
        ("Runtimes", identity.get("runtimes")),
    )
    return (
        '<dl class="facts">'
        + "".join(
            f'<div class="fact"><dt>{html.escape(label)}</dt><dd>{_cell(value)}</dd></div>'
            for label, value in values
        )
        + "</dl>"
    )


def _steps(steps: list[dict] | None) -> str:
    if not steps:
        return '<p class="muted">Step state is unavailable.</p>'
    rows = "".join(
        "<tr>"
        f"<td>{_cell(step.get('step'))}</td>"
        f"<td>{_status(step.get('state'))}</td>"
        f"<td>{_cell(step.get('attempt'))}</td>"
        "</tr>"
        for step in steps
    )
    return (
        '<div class="table-wrap"><table><thead><tr><th>Stage</th><th>Status</th>'
        f"<th>Attempt</th></tr></thead><tbody>{rows}</tbody></table></div>"
    )


def _lifecycle(lifecycle: dict) -> str:
    leases = lifecycle.get("leases", [])
    if not leases:
        return '<p class="muted">No runtime ownership has been recorded.</p>'
    rows = "".join(
        "<tr>"
        f"<td>{_cell(item.get('attempt'))}</td>"
        f"<td>{_cell(item.get('runtime'))}</td>"
        f"<td>{_cell(item.get('ownership'))}</td>"
        f"<td>{_cell(item.get('terminal_action'))}</td>"
        "</tr>"
        for item in leases
    )
    return (
        '<div class="table-wrap"><table><thead><tr><th>Attempt</th><th>Runtime</th>'
        "<th>Ownership</th><th>Terminal action</th></tr></thead>"
        f"<tbody>{rows}</tbody></table></div>"
    )


def _authority_form(
    *,
    run_id: str,
    plan_hash: str,
    action: str,
    grant: str,
    csrf_token: str,
) -> str:
    title = "Authorize and start" if action == ACTION_START else "Resume overhead"
    button = "Start exact plan" if action == ACTION_START else "Resume exact plan"
    return (
        '<section class="authority" aria-labelledby="authority-title">'
        f'<h2 id="authority-title">{html.escape(title)}</h2>'
        "<p>Confirm the immutable plan hash exactly. This authority is single-use "
        "and is not remembered.</p>"
        f'<form method="post" action="/runs/{html.escape(run_id)}/{action}">'
        f'<input type="hidden" name="csrf" value="{html.escape(csrf_token)}">'
        f'<input type="hidden" name="grant" value="{html.escape(grant)}">'
        '<label for="plan-hash">Plan hash (SHA-256)</label>'
        f'<p class="muted"><code>{html.escape(plan_hash)}</code></p>'
        '<input id="plan-hash" name="plan_hash" type="text" required '
        'autocomplete="off" spellcheck="false">'
        '<label class="check"><input type="checkbox" name="acknowledged" value="yes" '
        "required><span>I authorize local inference for this exact plan and understand "
        "that an incompatible process may be reclaimed after the 60-second notice.</span>"
        '</label><div class="actions">'
        f'<button class="primary" type="submit">{html.escape(button)}</button>'
        '<a class="button" href="/">Cancel</a></div></form></section>'
    )


def render_console(
    dashboard: dict[str, object],
    *,
    csrf_token: str,
    message: str | None = None,
    error: str | None = None,
) -> str:
    entries = dashboard["entries"]
    selected = dashboard["selected_run_id"]
    detail = dashboard["detail"]
    rail = _plan_rail(entries, selected)
    notices = ""
    if message:
        notices += f'<p class="notice" role="status">{html.escape(message)}</p>'
    if error:
        notices += f'<p class="error" role="alert">{html.escape(error)}</p>'

    if detail is None:
        content = (
            '<main class="content"><div class="empty">No plan selected.</div></main>'
        )
    else:
        identity = detail["identity"] or {}
        run_id = str(identity.get("run_id") or selected)
        run_status = (detail.get("summary") or {}).get("status") or next(
            (
                entry.get("run_status")
                for entry in entries
                if entry.get("run_id") == run_id
            ),
            None,
        )
        active = detail.get("active_action")
        active_for_selected = active and active.get("run_id") == run_id
        toolbar = [f'<a class="button" href="/runs/{html.escape(run_id)}">Refresh</a>']
        if active_for_selected:
            cancel_label = (
                "Cancellation requested"
                if active.get("cancel_requested")
                else "Cancel run"
            )
            toolbar.append(
                f'<form method="post" action="/runs/{html.escape(run_id)}/cancel">'
                f'<input type="hidden" name="csrf" value="{html.escape(csrf_token)}">'
                f'<button class="danger" type="submit">{html.escape(cancel_label)}</button>'
                "</form>"
            )
        if detail.get("health") == "SEALED_VERIFIED":
            toolbar.append(
                f'<a class="button" href="/runs/{html.escape(run_id)}/report">'
                "View sealed report</a>"
            )
        authority = ""
        for action in (ACTION_START, ACTION_RESUME):
            grant = dashboard["grants"].get(action)
            if grant:
                authority += _authority_form(
                    run_id=run_id,
                    plan_hash=str(identity.get("plan_hash") or ""),
                    action=action,
                    grant=grant,
                    csrf_token=csrf_token,
                )
        active_notice = ""
        if active:
            subject = "This plan has" if active_for_selected else "Another plan has"
            active_notice = (
                f'<p class="notice" role="status">{subject} a console-owned managed action '
                "in progress. Use Refresh for current evidence state. Closing this browser "
                "tab does not cancel it.</p>"
            )
        if active_for_selected:
            authority_state = "consumed for this active action"
        elif active:
            authority_state = "not granted; another plan is active"
        else:
            authority_state = "not granted"
        content = (
            '<main class="content">'
            f"{notices}{active_notice}"
            '<div class="content-head"><div>'
            f'<h2 class="run-title">{_cell(identity.get("run_name"))}</h2>'
            f"<p>Plan status: {_status(run_status)} · Live authority: "
            f"{html.escape(authority_state)}</p></div>"
            f'<div class="toolbar">{"".join(toolbar)}</div></div>'
            "<section><h2>Immutable plan</h2>"
            f"{_facts(identity, detail.get('policy'))}</section>"
            "<section><h2>Run progress</h2>"
            f"{_steps(detail.get('steps'))}</section>"
            "<section><h2>Runtime ownership</h2>"
            f"{_lifecycle(detail.get('lifecycle') or {})}</section>"
            '<p class="notice">Starting services may reclaim an incompatible process after '
            "the policy-defined 60-second notice. Provider reconnection remains external.</p>"
            f"{authority}</main>"
        )
    body = (
        '<header class="topbar"><h1>LMRE Run Console</h1>'
        '<span class="local">Local only</span></header>'
        f'<div class="shell">{rail}{content}</div>'
    )
    return _page("LMRE Run Console", body)


def render_console_error(status: int, message: str) -> str:
    body = (
        '<header class="topbar"><h1>LMRE Run Console</h1>'
        '<span class="local">Local only</span></header>'
        '<main class="content">'
        f'<p class="error" role="alert">{html.escape(message)}</p>'
        '<p><a class="button" href="/">Return to plans</a></p>'
        f'<p class="muted">HTTP {status}</p></main>'
    )
    return _page("LMRE Run Console error", body)
