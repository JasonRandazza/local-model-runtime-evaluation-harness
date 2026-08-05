"""Self-contained HTML rendering for results_browser view models.

Consumes the plain-dict shapes returned by `results_browser.build_index` and
`results_browser.build_run_view` and never reads evidence files itself,
except through those two boundary functions in `write_browser`. Every
interpolated value is HTML-escaped; report.md content is rendered
structurally (pipe tables, headings, paragraphs) with no value
transformation -- labels like "N/A (...)", "est.", and "-" pass through
verbatim. Pages are plain HTML5 with one inline <style> block: no
JavaScript, no external assets, no network access.
"""

from __future__ import annotations

import html
import re
from pathlib import Path

from .results_browser import (
    HEALTH_SEALED_CORRUPT,
    HEALTH_SEALED_VERIFIED,
    HEALTH_UNRECOGNIZED,
    HEALTH_UNREADABLE,
    HEALTH_UNSEALED,
    HEALTH_UNSUPPORTED_SCHEMA,
    VERDICT_COMPARABLE,
    VERDICT_INCOMPARABLE,
    build_comparisons,
    build_index,
    build_run_view,
)


_EM_DASH = "—"

_STYLE = (
    "body{font-family:system-ui,sans-serif;margin:1.5rem;color:#111;"
    "background:#fff;}"
    "table{border-collapse:collapse;margin:0.75rem 0;width:100%;}"
    "th,td{border:1px solid #999;padding:0.35rem 0.6rem;text-align:left;"
    "vertical-align:top;}"
    "caption{text-align:left;font-weight:bold;margin-bottom:0.4rem;}"
    "h1,h2,h3,h4,h5{line-height:1.25;}"
    ".health-SEALED_VERIFIED{color:#0a6b1f;}"
    ".health-SEALED_CORRUPT,.health-UNREADABLE,"
    ".health-UNSUPPORTED_SCHEMA,.health-UNRECOGNIZED{color:#a30000;}"
    ".health-UNSEALED{color:#8a6100;}"
)

_HEALTH_BANNER = {
    HEALTH_SEALED_VERIFIED: "Sealed and verified. This evidence is trusted.",
    HEALTH_SEALED_CORRUPT: (
        "Sealed but FAILED VERIFICATION. Fail-closed: this evidence is not "
        "trusted; step report content is withheld."
    ),
    HEALTH_UNSEALED: (
        "Unsealed -- not accepted evidence. Step report content is withheld."
    ),
    HEALTH_UNSUPPORTED_SCHEMA: (
        "Unsupported schema. Fail-closed: this bundle cannot be read."
    ),
    HEALTH_UNREADABLE: "Unreadable. Fail-closed: this bundle cannot be read.",
    HEALTH_UNRECOGNIZED: "Unrecognized directory. This is not a run bundle.",
}

_IDENTITY_LABELS = {
    "run_name": "Run name",
    "run_id": "Run ID",
    "comparison_id": "Comparison ID",
    "parent_run_id": "Parent run ID",
    "attempt": "Attempt",
    "family_id": "Family",
    "recipe_id": "Recipe",
    "comparison_class_id": "Comparison class",
    "binding_id": "Managed binding",
    "binding_revision": "Binding revision",
    "binding_hash": "Binding hash",
    "binding_proposal_hash": "Binding proposal hash",
    "matrix_mode": "Matrix mode",
    "schema_version": "Plan schema version",
    "plan_hash": "Plan hash",
    "created_at": "Created",
    "request_count": "Request count",
    "estimated_minutes": "Estimated minutes",
    "runtimes": "Runtimes",
    "endpoints": "Endpoints",
    "cell_ids": "Cell IDs",
    "pair_ids": "Pair IDs",
}

_INDEX_COLUMNS = (
    ("run_name", "Run name"),
    ("run_id", "Run ID"),
    ("comparison_id", "Comparison ID"),
    ("family_id", "Family"),
    ("recipe_id", "Recipe"),
    ("comparison_class_id", "Comparison class"),
    ("binding_id", "Managed binding"),
    ("attempt", "Attempt"),
    ("run_status", "Run status"),
    ("created_at", "Created"),
    ("health", "Health"),
)


def _text(value: object) -> str:
    """Stringify a view-model value verbatim (no rounding/reformatting)."""
    if value is None:
        return _EM_DASH
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (list, tuple)):
        return ", ".join(_text(item) for item in value) if value else _EM_DASH
    return str(value)


def _cell(value: object) -> str:
    return html.escape(_text(value))


def _page(title: str, body: str) -> str:
    return (
        "<!DOCTYPE html>\n"
        '<html lang="en">\n'
        "<head>\n"
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, '
        'initial-scale=1">\n'
        f"<title>{html.escape(title)}</title>\n"
        f"<style>{_STYLE}</style>\n"
        "</head>\n"
        "<body>\n"
        f"{body}\n"
        "</body>\n"
        "</html>\n"
    )


def render_index(index: dict) -> str:
    root_text = html.escape(str(index["results_root"]))
    body = ["<h1>Results Browser</h1>"]

    if index["missing_root"]:
        body.append(f"<p>Results root does not exist: {root_text}.</p>")
        return _page("Results Browser", "\n".join(body))

    body.append(
        '<p><a href="comparisons/index.html">Cross-run comparisons</a> '
        "(sealed verified evidence only)</p>"
    )

    entries = index["entries"]
    if not entries:
        body.append(
            f"<p>Results root: {root_text}. "
            "No evidence bundles found beneath this results root.</p>"
        )
        return _page("Results Browser", "\n".join(body))

    header = "".join(
        f'<th scope="col">{html.escape(label)}</th>' for _key, label in _INDEX_COLUMNS
    )
    rows = []
    for entry in entries:
        link = f"runs/{html.escape(str(entry['run_dir_name']))}.html"
        cells = []
        for key, _label in _INDEX_COLUMNS:
            if key == "run_id":
                cells.append(f'<td><a href="{link}">{_cell(entry[key])}</a></td>')
            else:
                cells.append(f"<td>{_cell(entry[key])}</td>")
        rows.append(f"<tr>{''.join(cells)}</tr>")

    caption = f"Results root: {root_text} — {len(entries)} run(s)."
    table = (
        "<table>"
        f"<caption>{caption}</caption>"
        f"<tr>{header}</tr>" + "".join(rows) + "</table>"
    )
    body.append(table)
    return _page("Results Browser", "\n".join(body))


def _kv_table(data: dict, labels: dict[str, str] | None = None) -> str:
    rows = []
    for key, value in data.items():
        label = (labels or {}).get(key, key.replace("_", " "))
        rows.append(
            f'<tr><th scope="row">{html.escape(label)}</th><td>{_cell(value)}</td></tr>'
        )
    return "<table>" + "".join(rows) + "</table>"


def _steps_table(steps: list) -> str:
    header = "".join(
        f'<th scope="col">{label}</th>'
        for label in ("Step", "State", "Attempt", "Output directory", "Report files")
    )
    rows = []
    for step in steps:
        report_files = step["report_files"]
        report_text = ", ".join(report_files) if report_files else "unavailable"
        output_text = "present" if step["has_output_dir"] else "absent"
        rows.append(
            "<tr>"
            f"<td>{_cell(step['step'])}</td>"
            f"<td>{_cell(step['state'])}</td>"
            f"<td>{_cell(step['attempt'])}</td>"
            f"<td>{html.escape(output_text)}</td>"
            f"<td>{html.escape(report_text)}</td>"
            "</tr>"
        )
    return f"<table><tr>{header}</tr>" + "".join(rows) + "</table>"


def _attempts_table(attempts: list) -> str:
    header = "".join(
        f'<th scope="col">{label}</th>'
        for label in ("Attempt", "Status", "Steps", "Has checksums")
    )
    rows = []
    for entry in attempts:
        if "error" in entry:
            status_text = f"invalid: {entry['error']}"
            steps_text = _EM_DASH
            checks_text = _EM_DASH
        else:
            status_text = _text(entry["status"])
            steps_text = (
                ", ".join(f"{s['step']}:{s['state']}" for s in entry["steps"])
                or _EM_DASH
            )
            checks_text = "true" if entry["has_checksums"] else "false"
        rows.append(
            "<tr>"
            f"<td>{_cell(entry['attempt'])}</td>"
            f"<td>{html.escape(status_text)}</td>"
            f"<td>{html.escape(steps_text)}</td>"
            f"<td>{html.escape(checks_text)}</td>"
            "</tr>"
        )
    return f"<table><tr>{header}</tr>" + "".join(rows) + "</table>"


def _lifecycle_section(lifecycle: dict) -> str:
    leases = lifecycle["leases"]
    if not leases:
        body = "<p>No lifecycle leases recorded for this bundle.</p>"
    else:
        header = "".join(
            f'<th scope="col">{label}</th>'
            for label in ("Runtime", "Ownership", "Terminal action")
        )
        rows = "".join(
            "<tr>"
            f"<td>{_cell(lease['runtime'])}</td>"
            f"<td>{_cell(lease['ownership'])}</td>"
            f"<td>{_cell(lease['terminal_action'])}</td>"
            "</tr>"
            for lease in leases
        )
        body = f"<table><tr>{header}</tr>{rows}</table>"
    if lifecycle["unparsed_lines"] > 0:
        body += (
            f"<p>Unparsed lifecycle journal lines: {lifecycle['unparsed_lines']}.</p>"
        )
    return body


_HEADING_RE = re.compile(r"^(#{1,3})\s+(.*)$")
_SEPARATOR_CELL_RE = re.compile(r"^:?-+:?$")


def _split_row(line: str) -> list[str]:
    trimmed = line.strip()
    if trimmed.startswith("|"):
        trimmed = trimmed[1:]
    if trimmed.endswith("|"):
        trimmed = trimmed[:-1]
    return [cell.strip() for cell in trimmed.split("|")]


def _is_separator_row(cells: list[str]) -> bool:
    non_empty = [cell for cell in cells if cell]
    return bool(non_empty) and all(_SEPARATOR_CELL_RE.match(cell) for cell in non_empty)


def _render_table(lines: list[str]) -> str:
    rows = [_split_row(line) for line in lines]
    if not rows:
        return ""
    header = rows[0]
    body_rows = [row for row in rows[1:] if not _is_separator_row(row)]
    head = "".join(f'<th scope="col">{html.escape(cell)}</th>' for cell in header)
    body = "".join(
        "<tr>" + "".join(f"<td>{html.escape(cell)}</td>" for cell in row) + "</tr>"
        for row in body_rows
    )
    return f"<table><tr>{head}</tr>{body}</table>"


def _render_report(text: str) -> str:
    """Structural, non-transforming Markdown-ish rendering of report.md.

    Consecutive '|' lines become a real table (cell-for-cell, separator rows
    dropped); '#'/'##'/'###' lines become h3/h4/h5; everything else becomes
    escaped paragraphs, with blank lines separating them. No value is
    parsed, rounded, or substituted.
    """
    lines = text.split("\n")
    out: list[str] = []
    paragraph: list[str] = []

    def flush() -> None:
        if paragraph:
            out.append(f"<p>{html.escape(' '.join(paragraph))}</p>")
            paragraph.clear()

    index = 0
    while index < len(lines):
        stripped = lines[index].strip()
        if not stripped:
            flush()
            index += 1
            continue
        heading = _HEADING_RE.match(stripped)
        if heading is not None:
            flush()
            # Reports render beneath an <h3> step name, so "#" -> h4 keeps
            # the document outline strictly nested for screen readers.
            level = min(len(heading.group(1)) + 3, 6)
            heading_text = html.escape(heading.group(2))
            out.append(f"<h{level}>{heading_text}</h{level}>")
            index += 1
            continue
        if stripped.startswith("|"):
            flush()
            block: list[str] = []
            while index < len(lines) and lines[index].strip().startswith("|"):
                block.append(lines[index].strip())
                index += 1
            out.append(_render_table(block))
            continue
        paragraph.append(stripped)
        index += 1
    flush()
    return "\n".join(out)


def render_run(view: dict) -> str:
    health = view["health"]
    title = f"Run: {view['run_dir_name']}"
    parts = [
        f"<h1>{html.escape(title)}</h1>",
        '<p><a href="../index.html">Back to index</a></p>',
    ]

    banner_text = _HEALTH_BANNER.get(health, "Unrecognized health state.")
    detail = view["health_detail"]
    banner = (
        f'<p class="health-{html.escape(str(health))}">'
        f"<strong>{html.escape(banner_text)}</strong>"
    )
    if detail:
        banner += f" ({html.escape(detail)})"
    banner += "</p>"
    parts.append(banner)

    parts.append("<h2>Identity</h2>")
    if view["identity"] is None:
        parts.append("<p>Identity is not available for this bundle.</p>")
    else:
        parts.append(_kv_table(view["identity"], _IDENTITY_LABELS))

    parts.append("<h2>Policy</h2>")
    if view["policy"] is None:
        parts.append("<p>Policy snapshot is not available for this bundle.</p>")
    else:
        parts.append(_kv_table(view["policy"]))

    parts.append("<h2>Summary</h2>")
    if view["summary"] is None:
        parts.append("<p>Summary is not written for this bundle.</p>")
    else:
        parts.append(_kv_table(view["summary"]))

    parts.append("<h2>Steps</h2>")
    if view["steps"] is None:
        parts.append("<p>Steps are not available for this bundle.</p>")
    else:
        parts.append(_steps_table(view["steps"]))

    parts.append("<h2>Attempt history</h2>")
    if not view["attempts"]:
        parts.append("<p>No preserved earlier attempts.</p>")
    else:
        parts.append(_attempts_table(view["attempts"]))

    parts.append("<h2>Lifecycle ownership</h2>")
    parts.append(_lifecycle_section(view["lifecycle"]))

    parts.append("<h2>Step reports</h2>")
    if health != HEALTH_SEALED_VERIFIED:
        parts.append(
            "<p>Step reports are withheld: this bundle is not verified evidence.</p>"
        )
    elif not view["step_reports"]:
        parts.append("<p>No step reports are available for this bundle.</p>")
    else:
        for step_name, report_text in view["step_reports"].items():
            parts.append(f"<h3>{html.escape(step_name)}</h3>")
            parts.append(_render_report(report_text))

    return _page(title, "\n".join(parts))


_MEMBER_COLUMNS = (
    ("run_name", "Run name"),
    ("run_id", "Run ID"),
    ("attempt", "Attempt"),
    ("created_at", "Created"),
    ("run_status", "Run status"),
    ("health", "Health"),
    ("exclusion_reason", "Comparison standing"),
)


def _verdict_text(group: dict) -> str:
    reason = group["verdict_reason"]
    verdict = group["verdict"]
    return f"{verdict} ({reason})" if reason else verdict


def render_comparisons_index(comparisons: dict) -> str:
    root_text = html.escape(str(comparisons["results_root"]))
    body = [
        "<h1>Cross-Run Comparisons</h1>",
        '<p><a href="../index.html">Back to index</a></p>',
        "<p>Groups are formed only by persisted comparison IDs. Only "
        "sealed verified bundles contribute accepted comparison data; all "
        "other members are listed as excluded.</p>",
    ]
    if comparisons["missing_root"]:
        body.append(f"<p>Results root does not exist: {root_text}.</p>")
        body.append(
            _render_unattributed_exclusions(comparisons["unattributed_exclusions"])
        )
        return _page("Cross-Run Comparisons", "\n".join(body))
    groups = comparisons["groups"]
    if not groups:
        body.append(
            f"<p>Results root: {root_text}. "
            "No comparison groups were found beneath this results root.</p>"
        )
        body.append(
            _render_unattributed_exclusions(comparisons["unattributed_exclusions"])
        )
        return _page("Cross-Run Comparisons", "\n".join(body))
    header = "".join(
        f'<th scope="col">{html.escape(label)}</th>'
        for label in ("Comparison ID", "Members", "Accepted", "Excluded", "Verdict")
    )
    rows = []
    for group in groups:
        link = f"{html.escape(group['comparison_id'])}.html"
        rows.append(
            "<tr>"
            f'<td><a href="{link}">{_cell(group["comparison_id"])}</a></td>'
            f"<td>{_cell(len(group['members']))}</td>"
            f"<td>{_cell(group['accepted_count'])}</td>"
            f"<td>{_cell(group['excluded_count'])}</td>"
            f"<td>{_cell(_verdict_text(group))}</td>"
            "</tr>"
        )
    caption = f"Results root: {root_text} — {len(groups)} comparison group(s)."
    body.append(
        f"<table><caption>{caption}</caption><tr>{header}</tr>"
        + "".join(rows)
        + "</table>"
    )
    body.append(_render_unattributed_exclusions(comparisons["unattributed_exclusions"]))
    return _page("Cross-Run Comparisons", "\n".join(body))


def _render_unattributed_exclusions(records: list) -> str:
    parts = ["<h2>Unattributed exclusions</h2>"]
    if not records:
        parts.append("<p>No unattributed exclusions (0).</p>")
        return "\n".join(parts)
    parts.append(
        f"<p>{len(records)} entr"
        + ("y" if len(records) == 1 else "ies")
        + " could not be attributed to a vetted comparison identity. "
        "These records contribute no comparison data and cannot be "
        "assigned to any group.</p>"
    )
    header = "".join(
        f'<th scope="col">{html.escape(label)}</th>'
        for label in ("Run directory", "Health", "Reason")
    )
    rows = "".join(
        "<tr>"
        f"<td>{_cell(record['run_dir_name'])}</td>"
        f"<td>{_cell(record['health'])}</td>"
        f"<td>{_cell(record['reason'])}</td>"
        "</tr>"
        for record in records
    )
    parts.append(f"<table><tr>{header}</tr>{rows}</table>")
    return "\n".join(parts)


def render_comparison_group(group: dict) -> str:
    title = f"Comparison: {group['comparison_id']}"
    parts = [
        f"<h1>{html.escape(title)}</h1>",
        '<p><a href="index.html">Back to comparisons</a></p>',
        f"<p><strong>Verdict: {_cell(_verdict_text(group))}</strong></p>",
    ]
    if group["verdict"] == VERDICT_INCOMPARABLE:
        parts.append(
            "<p>Accepted members disagree on required plan dimensions. "
            "No metrics are aggregated, ranked, or compared for this "
            "group; individual run pages remain available below.</p>"
        )
    elif group["verdict"] != VERDICT_COMPARABLE:
        parts.append(
            "<p>Fewer than two sealed verified members: there is nothing "
            "to compare. Individual run pages remain available below.</p>"
        )

    parts.append("<h2>Shared plan dimensions</h2>")
    if group["dimensions"] is None:
        parts.append("<p>Shared dimensions are shown only for comparable groups.</p>")
    else:
        parts.append(_kv_table(group["dimensions"]))

    parts.append("<h2>Members</h2>")
    header = "".join(
        f'<th scope="col">{html.escape(label)}</th>' for _key, label in _MEMBER_COLUMNS
    )
    rows = []
    for member in group["members"]:
        link = f"../runs/{html.escape(str(member['run_dir_name']))}.html"
        cells = []
        for key, _label in _MEMBER_COLUMNS:
            if key == "run_id":
                cells.append(f'<td><a href="{link}">{_cell(member[key])}</a></td>')
            elif key == "exclusion_reason":
                standing = "accepted" if member["accepted"] else member[key]
                cells.append(f"<td>{_cell(standing)}</td>")
            else:
                cells.append(f"<td>{_cell(member[key])}</td>")
        rows.append(f"<tr>{''.join(cells)}</tr>")
    parts.append(f"<table><tr>{header}</tr>" + "".join(rows) + "</table>")
    return _page(title, "\n".join(parts))


def write_browser(results_root: Path, output_root: Path) -> dict:
    """Render the full browser to output_root. Never raises for bad bundles."""
    resolved_output = output_root.resolve()
    resolved_results = results_root.resolve()
    if resolved_output == resolved_results or resolved_output.is_relative_to(
        resolved_results
    ):
        raise ValueError(
            "browser output must not be written inside the results root; "
            "evidence bundles are read-only"
        )
    index = build_index(results_root)

    output_root.mkdir(parents=True, exist_ok=True)
    runs_dir = output_root / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)

    index_path = output_root / "index.html"
    index_path.write_text(render_index(index), encoding="utf-8")

    pages: list[str] = []
    for entry in index["entries"]:
        run_dir = results_root / entry["run_dir_name"]
        view = build_run_view(run_dir)
        page_path = runs_dir / f"{entry['run_dir_name']}.html"
        page_path.write_text(render_run(view), encoding="utf-8")
        pages.append(str(page_path))

    comparisons = build_comparisons(results_root)
    comparisons_dir = output_root / "comparisons"
    comparisons_dir.mkdir(parents=True, exist_ok=True)
    comparison_index_path = comparisons_dir / "index.html"
    comparison_index_path.write_text(
        render_comparisons_index(comparisons), encoding="utf-8"
    )
    for group in comparisons["groups"]:
        # comparison_id is pre-validated against SAFE_COMPARISON_ID in
        # build_comparisons, so it is always a safe flat filename.
        group_path = comparisons_dir / f"{group['comparison_id']}.html"
        group_path.write_text(render_comparison_group(group), encoding="utf-8")

    return {
        "index": str(index_path),
        "runs": len(index["entries"]),
        "pages": pages,
        "comparison_index": str(comparison_index_path),
        "comparisons": len(comparisons["groups"]),
        "unattributed_exclusions": len(comparisons["unattributed_exclusions"]),
    }
