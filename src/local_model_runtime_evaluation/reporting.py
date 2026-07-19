from __future__ import annotations

from typing import Mapping


def render_draft_report(run_id: str, summary: Mapping[str, object]) -> str:
    return (
        f"# Stage 1 Route-Overhead Draft Report\n\n"
        f"Run: `{run_id}`\n\n"
        "This is generated evidence pending manager review. It does not update model policy.\n\n"
        f"Measured samples: {summary.get('measured_sample_count', 0)}\n\n"
        f"TTFT: {summary.get('overall', {}).get('ttft_metric_status', 'UNKNOWN')}\n\n"
        f"Decode: {summary.get('overall', {}).get('decode_metric_status', 'UNKNOWN')}\n\n"
        f"Token accounting: {summary.get('overall', {}).get('token_accounting_status', 'UNKNOWN')}\n\n"
        f"Response contracts: {summary.get('overall', {}).get('response_contract_validation', 'UNKNOWN')}\n"
    )
