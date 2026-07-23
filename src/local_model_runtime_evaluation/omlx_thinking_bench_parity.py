from __future__ import annotations

from local_model_runtime_evaluation.omlx_admin_bench_client import BenchMetricRow

REFERENCE_MEASURE_RUN_ID = "omlx-thinking-measure-20260722-004"
COMPARISON_CLASS = "omlx-thinking-external-bench-parity-v1"


def decide_parity_outcome(
    *,
    bench_completed: bool,
    cleanup_ok: bool,
    cross_check_written: bool,
) -> str:
    """Return PASS | FAIL | FAIL_CLEANUP per design."""
    if not bench_completed or not cross_check_written:
        return "FAIL"
    if not cleanup_ok:
        return "FAIL_CLEANUP"
    return "PASS"


def _format_metric(value: float | int | None) -> str:
    if value is None:
        return "—"
    if isinstance(value, float):
        return f"{value:g}"
    return str(value)


def _format_rows_table(rows: tuple[BenchMetricRow, ...]) -> str:
    if not rows:
        return "_No bench metric rows recorded._\n"
    header = (
        "| prompt_tokens | completion_tokens | ttft_ms | tpot_ms | gen_tps | "
        "e2e_latency_s | status |\n"
        "|---:|---:|---:|---:|---:|---:|---|\n"
    )
    lines = [
        "| "
        + " | ".join(
            (
                _format_metric(row.prompt_tokens),
                _format_metric(row.completion_tokens),
                _format_metric(row.ttft_ms),
                _format_metric(row.tpot_ms),
                _format_metric(row.gen_tps),
                _format_metric(row.e2e_latency_s),
                row.status,
            )
        )
        + " |"
        for row in rows
    ]
    return header + "\n".join(lines) + "\n"


def build_cross_check_markdown(
    *,
    run_id: str,
    decision: str,
    bench_status: str,
    rows: tuple[BenchMetricRow, ...],
    reference_run_id: str = REFERENCE_MEASURE_RUN_ID,
) -> str:
    """Must include TTFT semantic divergence, viability, informational throughput."""
    viability_ok = bench_status == "completed" and any(row.status == "ok" for row in rows)
    viability_note = (
        "External preflight completed and the single 1024-token test finished without "
        "a false thinking failure."
        if viability_ok
        else "External bench did not reach a completed ok row for the 1024-token cohort."
    )
    return f"""# D3 External-Bench Parity Cross-Check — `{run_id}`

## Verdict

**{decision}**

| Field | Value |
|---|---|
| Run ID | `{run_id}` |
| Comparison class | `{COMPARISON_CLASS}` |
| Reference measure | `{reference_run_id}` |
| Bench status | `{bench_status}` |

## TTFT semantics (do not equate)

oMLX external throughput bench times TTFT from the first streamed **`content`**
*or* **`reasoning_content`** token. Harness D4 measure (`{reference_run_id}`)
records TTFT as **content-only** after reasoning split decode. Expect
systematic skew between these cohorts; **metric equality is not a PASS
criterion** for this parity cohort.

## Viability

{viability_note}

## Informational throughput (external bench)

{_format_rows_table(rows)}

Compare `completion_tokens`, `gen_tps`, and related fields against harness
measure completion-token-class totals in `{reference_run_id}` for context only.
Discrepancies are expected given TTFT and decode-path differences above.
"""
