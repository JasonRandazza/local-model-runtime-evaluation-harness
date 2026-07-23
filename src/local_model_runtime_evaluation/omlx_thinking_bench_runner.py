from __future__ import annotations

from typing import Callable, Protocol

from .harness_lifecycle import LifecycleController
from .omlx_admin_bench_client import (
    BenchMetricRow,
    OmlxAdminBenchClient,
    build_external_bench_request,
)
from .omlx_thinking_bench_parity import (
    COMPARISON_CLASS,
    build_cross_check_markdown,
    decide_parity_outcome,
)
from .omlx_thinking_pin import OmlxThinkingPin
from .omlx_thinking_runner import OMLX_THINKING_PORT, omlx_server_pin_from_pin

GATE_A_PLACEHOLDER_RUN_ID = "(unauthorized-gate-a)"


class ThinkingBenchParityError(RuntimeError):
    def __init__(self, message: str, *, code: str) -> None:
        super().__init__(message)
        self.code = code


class AdminBenchClient(Protocol):
    def login(self, api_key: str) -> None: ...

    def start_external_bench(self, body: dict[str, object]) -> str: ...

    def fetch_results(self, bench_id: str) -> tuple[str, tuple[BenchMetricRow, ...]]: ...


class ThinkingBenchParityRunner:
    def __init__(
        self,
        pin: OmlxThinkingPin,
        *,
        controller: LifecycleController,
        admin_client: OmlxAdminBenchClient | AdminBenchClient,
        api_key: str,
        port_free: Callable[[int], bool],
    ) -> None:
        self._pin = pin
        self._controller = controller
        self._admin_client = admin_client
        self._api_key = api_key
        self._port_free = port_free

    @property
    def lifecycle_actions(self) -> int:
        return self._controller.lifecycle_actions

    def run_parity(self) -> dict[str, object]:
        """start → login → start bench → fetch results → build note fields.

        Does not write files or authorize run IDs. Raises on fail-closed errors.
        Caller owns evidence persistence and cleanup invocation.
        """
        self._controller.start(omlx_server_pin_from_pin(self._pin))
        self._admin_client.login(self._api_key)
        body = build_external_bench_request(
            model_id=self._pin.model_id,
            base_url=self._pin.base_url,
            api_key=self._api_key,
        )
        bench_id = self._admin_client.start_external_bench(body)
        bench_status, rows = self._admin_client.fetch_results(bench_id)
        decision = decide_parity_outcome(
            bench_completed=bench_status == "completed",
            cleanup_ok=False,
            cross_check_written=True,
        )
        cross_check_markdown = build_cross_check_markdown(
            run_id=GATE_A_PLACEHOLDER_RUN_ID,
            decision=decision,
            bench_status=bench_status,
            rows=rows,
        )
        return {
            "comparison_class": COMPARISON_CLASS,
            "rows": rows,
            "cross_check_markdown": cross_check_markdown,
            "bench_status": bench_status,
        }

    def cleanup(self) -> None:
        self._controller.stop()
        if not self._port_free(OMLX_THINKING_PORT):
            raise ThinkingBenchParityError(
                f"port {OMLX_THINKING_PORT} is still busy after stop",
                code="port_busy",
            )
