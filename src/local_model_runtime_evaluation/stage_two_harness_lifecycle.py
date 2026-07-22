"""Stage 2 harness-owned OptiQ lifecycle adapter."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from .harness_lifecycle import (
    HarnessLifecycleError,
    LifecycleController,
    PORT_BY_KIND,
    ServerPin,
    Spawner,
    StopRunner,
    WaitPortFree,
    WaitReady,
)
from .stage_two_profiles import RuntimeProfile

OPTIQ_PORT = PORT_BY_KIND["optiq"]


def optiq_server_pin_from_profile(profile: RuntimeProfile) -> ServerPin:
    executable = str(profile.runtime_executable)
    return ServerPin(
        kind="optiq",
        port=OPTIQ_PORT,
        start_command=(executable, *profile.serve_arguments),
        stop_command=(executable, "stop"),
        ready_model_id=profile.direct_model_identities[0]
        if profile.direct_model_identities
        else profile.routed_model_id,
    )


class HarnessOptiQController:
    """Start and stop harness-owned OptiQ via LifecycleController."""

    def __init__(
        self,
        *,
        controller: LifecycleController | None = None,
        memory_floor_percent: int | None = None,
        free_memory: Callable[[], float] | None = None,
        port_free: Callable[[int], bool] | None = None,
        lab_closed: Callable[[], bool] | None = None,
        spawner: Spawner | None = None,
        stop_runner: StopRunner | None = None,
        wait_port_free: WaitPortFree | None = None,
        wait_ready: WaitReady | None = None,
        log_dir: Path | None = None,
    ) -> None:
        if controller is not None:
            self._controller = controller
            self._port_free = controller._port_free
            return

        missing = [
            name
            for name, value in (
                ("free_memory", free_memory),
                ("port_free", port_free),
                ("lab_closed", lab_closed),
            )
            if value is None
        ]
        if missing:
            raise HarnessLifecycleError(
                "HarnessOptiQController requires "
                + ", ".join(missing)
                + " when controller is not injected",
                code="missing_probes",
            )

        self._port_free = port_free
        controller_kwargs: dict[str, object] = {
            "free_memory": free_memory,
            "port_free": port_free,
            "lab_closed": lab_closed,
        }
        if memory_floor_percent is not None:
            controller_kwargs["memory_floor_percent"] = memory_floor_percent
        if spawner is not None:
            controller_kwargs["spawner"] = spawner
        if stop_runner is not None:
            controller_kwargs["stop_runner"] = stop_runner
        if wait_port_free is not None:
            controller_kwargs["wait_port_free"] = wait_port_free
        if wait_ready is not None:
            controller_kwargs["wait_ready"] = wait_ready
        if log_dir is not None:
            controller_kwargs["log_dir"] = log_dir
        self._controller = LifecycleController(**controller_kwargs)

    @property
    def lifecycle_actions(self) -> int:
        return self._controller.lifecycle_actions

    def ensure_started(self, pin: ServerPin) -> None:
        if pin.kind != "optiq":
            raise HarnessLifecycleError(
                f"expected optiq pin, got {pin.kind}",
                code="pin_kind_mismatch",
            )
        self._controller.start(pin)

    def ensure_stopped(self) -> None:
        self._controller.stop()
        if not self._port_free(OPTIQ_PORT) or not self._port_free(OPTIQ_PORT):
            raise HarnessLifecycleError(
                f"port {OPTIQ_PORT} must be free twice after harness stop",
                code="port_not_free",
            )
