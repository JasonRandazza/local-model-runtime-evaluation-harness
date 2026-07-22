from __future__ import annotations

import argparse
import json
import re
import subprocess
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Protocol

from .matrix_lifecycle import port_is_free
from .omlx_thinking_pin import (
    OmlxThinkingPin,
    PIN_MODEL_ID,
    PIN_OWNERSHIP_MODE,
    PIN_VERSION,
    OmlxThinkingPinError,
    default_pin_path,
)
from .omlx_thinking_transport import matrix_local_credential
from .transport import LoopbackTransport, TransportError

APPROVED_VERSION = PIN_VERSION
APPROVED_OWNERSHIP_MODE = PIN_OWNERSHIP_MODE
APPROVED_MODEL_ID = PIN_MODEL_ID
OMLX_PORT = 8100

_VERSION_PATTERN = re.compile(r"(?:^|\s)(?P<version>\d+\.\d+\.\d+)\s*$")


class GateBReadinessError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class ReadOnlyTransport(Protocol):
    def health(self, base_url: str) -> dict[str, object]: ...

    def list_models(self, base_url: str, credential: object | None) -> tuple[str, ...]: ...


def parse_omlx_version(output: str) -> str | None:
    for line in output.splitlines():
        match = _VERSION_PATTERN.search(line.strip())
        if match is not None:
            return match.group("version")
    match = _VERSION_PATTERN.search(output.strip())
    return match.group("version") if match else None


def _run_version_command(command: list[str]) -> object:
    return subprocess.run(
        command, capture_output=True, text=True, check=False, timeout=30,
    )


def probe_omlx_version(
    *,
    command_runner: Callable[[list[str]], object] = _run_version_command,
) -> str:
    result = command_runner(["omlX", "--version"])
    if getattr(result, "returncode", 1) != 0:
        raise GateBReadinessError("version_probe_failed", "omlX --version failed")
    output = f"{getattr(result, 'stdout', '')}{getattr(result, 'stderr', '')}"
    version = parse_omlx_version(output)
    if version is None:
        raise GateBReadinessError("version_probe_failed", "omlX --version output is unreadable")
    return version


def health_is_ready(payload: Mapping[str, object]) -> bool:
    status = payload.get("status")
    return status in {"ok", "healthy"}


def _pin_is_valid(pin: OmlxThinkingPin) -> bool:
    return (
        pin.version == APPROVED_VERSION
        and pin.ownership_mode == APPROVED_OWNERSHIP_MODE
        and pin.model_id == APPROVED_MODEL_ID
        and "--model-dir" in pin.start_command
    )


def observe_omlx_profile(
    model_id: str,
    *,
    omlx_home: Path | None = None,
) -> dict[str, object]:
    home = omlx_home if omlx_home is not None else Path.home() / ".omlx"
    settings_path = home / "model_settings.json"
    if not settings_path.is_file():
        return {
            "status": "file_missing",
            "enable_thinking": None,
            "active_profile_name": None,
            "profile_enable_thinking": None,
        }
    try:
        payload = json.loads(settings_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {
            "status": "unreadable",
            "enable_thinking": None,
            "active_profile_name": None,
            "profile_enable_thinking": None,
        }
    models = payload.get("models") if isinstance(payload, dict) else None
    if not isinstance(models, dict) or model_id not in models:
        return {
            "status": "model_missing",
            "enable_thinking": None,
            "active_profile_name": None,
            "profile_enable_thinking": None,
        }
    entry = models[model_id]
    if not isinstance(entry, dict):
        return {
            "status": "unreadable",
            "enable_thinking": None,
            "active_profile_name": None,
            "profile_enable_thinking": None,
        }
    enable = entry.get("enable_thinking")
    active = entry.get("active_profile_name")
    profile_enable = None
    if isinstance(active, str) and active:
        profiles_path = home / "model_profiles.json"
        try:
            profiles_payload = json.loads(profiles_path.read_text(encoding="utf-8"))
            profiles = profiles_payload.get("profiles", {})
            model_profiles = profiles.get(model_id, {}) if isinstance(profiles, dict) else {}
            profile = model_profiles.get(active, {}) if isinstance(model_profiles, dict) else {}
            settings = profile.get("settings", {}) if isinstance(profile, dict) else {}
            if isinstance(settings, dict) and "enable_thinking" in settings:
                profile_enable = settings.get("enable_thinking")
                if not isinstance(profile_enable, bool):
                    profile_enable = None
        except (OSError, json.JSONDecodeError, AttributeError):
            profile_enable = None
    return {
        "status": "ok",
        "enable_thinking": enable if isinstance(enable, bool) else None,
        "active_profile_name": active if isinstance(active, str) else None,
        "profile_enable_thinking": profile_enable,
    }


def collect_readiness(
    pin: OmlxThinkingPin,
    *,
    installed_version: str,
    port_free: Callable[[int], bool],
    transport: ReadOnlyTransport,
    observe_busy_port: bool = True,
    omlx_home: Path | None = None,
) -> dict[str, object]:
    pin_valid = _pin_is_valid(pin)
    version_match = installed_version == APPROVED_VERSION
    port_8100_free = port_free(OMLX_PORT)
    health_ready = False
    model_present = False
    readiness_path = "port_free"
    omlx_profile_observe = observe_omlx_profile(pin.model_id, omlx_home=omlx_home)

    if not pin_valid:
        return {
            "pin_id": pin.pin_id,
            "pin_revision": pin.revision,
            "comparison_class": pin.comparison_class,
            "ownership_mode": pin.ownership_mode,
            "model_id": pin.model_id,
            "pin_valid": pin_valid,
            "version_match": version_match,
            "installed_version": installed_version,
            "port_8100_free": port_8100_free,
            "health_ready": health_ready,
            "model_present": model_present,
            "readiness_path": "pin_invalid",
            "observe_busy_port": observe_busy_port,
            "omlx_profile_observe": omlx_profile_observe,
            "http_post_attempts": 0,
            "inference_request_attempts": 0,
            "service_lifecycle_actions": 0,
        }

    if port_8100_free:
        readiness_path = "port_free"
    elif pin.ownership_mode == "dedicated_serve" and observe_busy_port:
        readiness_path = "observe_busy_port"
        try:
            health_ready = health_is_ready(transport.health(pin.base_url))
        except TransportError:
            health_ready = False
        if health_ready:
            try:
                credential = matrix_local_credential()
                models = transport.list_models(pin.base_url, credential)
                model_present = pin.model_id in models
            except TransportError:
                model_present = False
    # attach_pool is rejected by the pin loader; no READY path for it.

    return {
        "pin_id": pin.pin_id,
        "pin_revision": pin.revision,
        "comparison_class": pin.comparison_class,
        "ownership_mode": pin.ownership_mode,
        "model_id": pin.model_id,
        "pin_valid": pin_valid,
        "version_match": version_match,
        "installed_version": installed_version,
        "port_8100_free": port_8100_free,
        "health_ready": health_ready,
        "model_present": model_present,
        "readiness_path": readiness_path,
        "observe_busy_port": observe_busy_port,
        "omlx_profile_observe": omlx_profile_observe,
        "http_post_attempts": 0,
        "inference_request_attempts": 0,
        "service_lifecycle_actions": 0,
    }


def build_gate_b_report(readiness: Mapping[str, object]) -> dict[str, object]:
    pin_valid = readiness.get("pin_valid") is True
    version_match = readiness.get("version_match") is True
    port_8100_free = readiness.get("port_8100_free") is True
    health_ready = readiness.get("health_ready") is True
    model_present = readiness.get("model_present") is True
    ownership_mode = str(readiness.get("ownership_mode", ""))
    observe_busy_port = readiness.get("observe_busy_port") is True

    if not pin_valid:
        decision = "pin_invalid"
    elif not version_match:
        decision = "version_mismatch"
    elif port_8100_free:
        decision = "READY_FOR_LIVE_AUTHORIZATION"
    elif ownership_mode == "attach_pool":
        # Pin loader rejects attach_pool; treat as invalid if it appears.
        decision = "pin_invalid"
    elif observe_busy_port:
        if not health_ready:
            decision = "health_unavailable"
        elif not model_present:
            decision = "model_missing"
        else:
            decision = "port_busy_foreign_pool"
    else:
        decision = "port_busy"

    checks = {
        "pin_valid": pin_valid,
        "version_match": version_match,
        "port_8100_free": port_8100_free,
        "health_ready": health_ready,
        "model_present": model_present,
    }

    return {
        "package": "omlx-thinking-measure-v1",
        "pin_id": readiness.get("pin_id"),
        "pin_revision": readiness.get("pin_revision"),
        "comparison_class": readiness.get("comparison_class"),
        "ownership_mode": readiness.get("ownership_mode"),
        "model_id": readiness.get("model_id"),
        "installed_version": readiness.get("installed_version"),
        "decision": decision,
        "checks": checks,
        "readiness_path": readiness.get("readiness_path"),
        "observe_busy_port": observe_busy_port,
        "omlx_profile_observe": readiness.get("omlx_profile_observe"),
        "http_post_attempts": readiness.get("http_post_attempts", 0),
        "inference_request_attempts": readiness.get("inference_request_attempts", 0),
        "service_lifecycle_actions": readiness.get("service_lifecycle_actions", 0),
        "manager_review_required": True,
    }


def run_gate_b_check(
    *,
    pin_path: Path,
    observe_busy_port: bool,
    version_probe: Callable[[], str] | None = None,
    port_free: Callable[[int], bool] | None = None,
    transport: ReadOnlyTransport | None = None,
    omlx_home: Path | None = None,
) -> dict[str, object]:
    pin = OmlxThinkingPin.load(pin_path)
    installed_version = (version_probe or probe_omlx_version)()
    check_port = port_free or port_is_free
    loopback = transport or LoopbackTransport({pin.base_url}, timeout_seconds=10)
    readiness = collect_readiness(
        pin,
        installed_version=installed_version,
        port_free=check_port,
        transport=loopback,
        observe_busy_port=observe_busy_port,
        omlx_home=omlx_home,
    )
    return build_gate_b_report(readiness)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="lmre-omlx-thinking-gate-b-check")
    parser.add_argument(
        "--pin-path",
        type=Path,
        default=default_pin_path(),
        help="path to the approved oMLX thinking pin JSON",
    )
    parser.add_argument(
        "--observe-busy-port",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="when port 8100 is busy, probe health and authenticated inventory without reclaim",
    )
    arguments = parser.parse_args(argv)
    try:
        result = run_gate_b_check(
            pin_path=arguments.pin_path,
            observe_busy_port=arguments.observe_busy_port,
        )
        exit_code = 0 if result["decision"] == "READY_FOR_LIVE_AUTHORIZATION" else 1
    except OmlxThinkingPinError as error:
        result = {
            "package": "omlx-thinking-measure-v1",
            "decision": "pin_invalid",
            "error_kind": error.__class__.__name__,
            "http_post_attempts": 0,
            "inference_request_attempts": 0,
            "service_lifecycle_actions": 0,
            "manager_review_required": True,
        }
        exit_code = 1
    except GateBReadinessError as error:
        result = {
            "package": "omlx-thinking-measure-v1",
            "decision": error.code,
            "error_kind": error.code,
            "http_post_attempts": 0,
            "inference_request_attempts": 0,
            "service_lifecycle_actions": 0,
            "manager_review_required": True,
        }
        exit_code = 1
    except Exception as error:
        result = {
            "package": "omlx-thinking-measure-v1",
            "decision": "STOPPED",
            "error_kind": getattr(error, "code", error.__class__.__name__),
            "http_post_attempts": 0,
            "inference_request_attempts": 0,
            "service_lifecycle_actions": 0,
            "manager_review_required": True,
        }
        exit_code = 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
