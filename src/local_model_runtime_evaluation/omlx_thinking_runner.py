from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Literal

from .harness_lifecycle import LifecycleController, ServerPin
from .measurement import validate_response_contract
from .omlx_thinking_measure import (
    THINKING_PREFLIGHT_MAX_TOKENS,
    ThinkingOutcome,
    classify_thinking_outcome,
    preflight_budget_ok,
)
from .omlx_thinking_pin import OmlxThinkingPin, OmlxThinkingSuite
from .transport import TransportError

OMLX_THINKING_PORT = 8100
MAX_SMOKE_REQUESTS = 8
THINKING_PREFLIGHT_PROMPT = (
    "Think briefly, then reply in one short sentence confirming the endpoint is ready."
)


@dataclass(frozen=True)
class ThinkingChatResult:
    visible_text: str
    finish_reason: str | None = None


@dataclass(frozen=True)
class ThinkingMeasureRequestOutcome:
    phase: Literal["preflight", "smoke"]
    workload_id: str | None
    repetition: int
    outcome: ThinkingOutcome


class ThinkingMeasureError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        code: str,
        outcome: ThinkingOutcome | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.outcome = outcome


ChatTransport = Callable[[str, str, int], ThinkingChatResult]
ControllerFactory = Callable[[], LifecycleController]


def omlx_server_pin_from_pin(pin: OmlxThinkingPin) -> ServerPin:
    return ServerPin(
        kind="omlx",
        port=OMLX_THINKING_PORT,
        start_command=pin.start_command,
        stop_command=pin.stop_command,
    )


class ThinkingMeasureRunner:
    def __init__(
        self,
        pin: OmlxThinkingPin,
        suite: OmlxThinkingSuite,
        chat: ChatTransport,
        *,
        controller: LifecycleController | None = None,
        controller_factory: ControllerFactory | None = None,
        port_free: Callable[[int], bool] | None = None,
        repetitions_per_workload: int = 1,
    ) -> None:
        if controller is None and controller_factory is None:
            raise ThinkingMeasureError(
                "ThinkingMeasureRunner requires controller or controller_factory",
                code="missing_controller",
            )
        if repetitions_per_workload < 1:
            raise ThinkingMeasureError(
                "repetitions_per_workload must be at least 1",
                code="invalid_repetitions",
            )
        self._pin = pin
        self._suite = suite
        self._chat = chat
        self._controller = controller or controller_factory()
        self._port_free = port_free or self._controller._port_free
        self._repetitions = repetitions_per_workload
        self._preflight_outcome: ThinkingMeasureRequestOutcome | None = None
        self._smoke_outcomes: list[ThinkingMeasureRequestOutcome] = []

    @property
    def lifecycle_actions(self) -> int:
        return self._controller.lifecycle_actions

    @property
    def preflight_outcome(self) -> ThinkingMeasureRequestOutcome | None:
        return self._preflight_outcome

    @property
    def smoke_outcomes(self) -> tuple[ThinkingMeasureRequestOutcome, ...]:
        return tuple(self._smoke_outcomes)

    def _classify_chat(
        self,
        *,
        contract: str,
        result: ThinkingChatResult | None,
        transport_ok: bool,
    ) -> ThinkingOutcome:
        if not transport_ok or result is None:
            return classify_thinking_outcome(
                transport_ok=False,
                visible_text="",
                finish_reason=None,
                contract_ok=False,
            )
        contract_ok, _ = validate_response_contract(contract, result.visible_text)
        return classify_thinking_outcome(
            transport_ok=True,
            visible_text=result.visible_text,
            finish_reason=result.finish_reason,
            contract_ok=contract_ok,
        )

    def _execute_chat(
        self,
        *,
        prompt: str,
        max_tokens: int,
        contract: str,
    ) -> ThinkingOutcome:
        if not preflight_budget_ok(max_tokens):
            raise ThinkingMeasureError(
                f"max_tokens {max_tokens} is below thinking preflight floor",
                code="budget_floor",
            )
        try:
            result = self._chat(self._pin.base_url, prompt, max_tokens)
            transport_ok = True
        except TransportError:
            result = None
            transport_ok = False
        return self._classify_chat(
            contract=contract,
            result=result,
            transport_ok=transport_ok,
        )

    def run_preflight(self) -> ThinkingMeasureRequestOutcome:
        self._controller.start(omlx_server_pin_from_pin(self._pin))
        outcome = self._execute_chat(
            prompt=THINKING_PREFLIGHT_PROMPT,
            max_tokens=THINKING_PREFLIGHT_MAX_TOKENS,
            contract="text",
        )
        record = ThinkingMeasureRequestOutcome("preflight", None, 0, outcome)
        self._preflight_outcome = record
        if outcome != "ok":
            raise ThinkingMeasureError(
                f"preflight failed: {outcome}",
                code="preflight_failed",
                outcome=outcome,
            )
        return record

    def run_smoke(self) -> tuple[ThinkingMeasureRequestOutcome, ...]:
        if self._preflight_outcome is None or self._preflight_outcome.outcome != "ok":
            raise ThinkingMeasureError(
                "preflight must pass before smoke",
                code="preflight_required",
            )
        total = len(self._suite.workloads) * self._repetitions
        if total > MAX_SMOKE_REQUESTS:
            raise ThinkingMeasureError(
                f"smoke would exceed {MAX_SMOKE_REQUESTS} requests",
                code="smoke_budget",
            )
        self._smoke_outcomes.clear()
        for workload in self._suite.workloads:
            for repetition in range(1, self._repetitions + 1):
                outcome = self._execute_chat(
                    prompt=workload.prompt,
                    max_tokens=workload.max_tokens,
                    contract=workload.response_contract,
                )
                self._smoke_outcomes.append(
                    ThinkingMeasureRequestOutcome(
                        "smoke",
                        workload.workload_id,
                        repetition,
                        outcome,
                    )
                )
        return tuple(self._smoke_outcomes)

    def cleanup(self) -> None:
        self._controller.stop()
        if not self._port_free(OMLX_THINKING_PORT):
            raise ThinkingMeasureError(
                f"port {OMLX_THINKING_PORT} is still busy after stop",
                code="port_busy",
            )
