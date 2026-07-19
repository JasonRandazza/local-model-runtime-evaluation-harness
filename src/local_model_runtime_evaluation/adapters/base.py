from __future__ import annotations


class LiveExecutionDisabled(RuntimeError):
    code = "live_execution_disabled"


class DisabledAdapter:
    runtime = "unknown"

    def describe(self) -> dict[str, object]:
        return {"runtime": self.runtime, "stage0_status": "disabled"}

    def execute(self) -> None:
        raise LiveExecutionDisabled(f"{self.runtime} execution is disabled in Stage 0")

