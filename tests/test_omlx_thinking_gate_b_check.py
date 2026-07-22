from __future__ import annotations

import dataclasses
import json
import unittest
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from local_model_runtime_evaluation import omlx_thinking_gate_b_check as gate_b_mod
from local_model_runtime_evaluation.omlx_thinking_gate_b_check import (
    build_gate_b_report,
    collect_readiness,
    health_is_ready,
    main,
    parse_omlx_version,
    probe_omlx_version,
)
from local_model_runtime_evaluation.omlx_thinking_pin import (
    OmlxThinkingPin,
    PIN_MODEL_ID,
    PIN_OWNERSHIP_MODE,
    PIN_VERSION,
    default_pin_path,
)


class FakeTransport:
    def __init__(
        self,
        *,
        health: dict[str, object] | None = None,
        models: tuple[str, ...] = (),
        health_error: Exception | None = None,
        inventory_error: Exception | None = None,
    ) -> None:
        self.health_payload = health or {"status": "healthy"}
        self.models = models
        self.health_error = health_error
        self.inventory_error = inventory_error
        self.health_calls = 0
        self.list_models_calls = 0

    def health(self, _base_url: str) -> dict[str, object]:
        self.health_calls += 1
        if self.health_error is not None:
            raise self.health_error
        return dict(self.health_payload)

    def list_models(self, _base_url: str, _credential: object | None) -> tuple[str, ...]:
        self.list_models_calls += 1
        if self.inventory_error is not None:
            raise self.inventory_error
        return self.models


class OmlxThinkingGateBCheckTest(unittest.TestCase):
    def setUp(self) -> None:
        self.pin = OmlxThinkingPin.load(default_pin_path())

    def test_parse_omlx_version_accepts_plain_and_prefixed_output(self) -> None:
        self.assertEqual(parse_omlx_version("0.5.3\n"), "0.5.3")
        self.assertEqual(parse_omlx_version("omlX version 0.5.3"), "0.5.3")
        self.assertIsNone(parse_omlx_version("unknown"))

    def test_probe_omlx_version_uses_injected_runner(self) -> None:
        version = probe_omlx_version(
            command_runner=lambda _command: SimpleNamespace(
                returncode=0,
                stdout="omlX version 0.5.3\n",
                stderr="",
            ),
        )
        self.assertEqual(version, "0.5.3")

    def test_health_is_ready_accepts_ok_and_healthy(self) -> None:
        self.assertTrue(health_is_ready({"status": "ok"}))
        self.assertTrue(health_is_ready({"status": "healthy"}))
        self.assertFalse(health_is_ready({"status": "degraded"}))

    def test_ready_when_pin_version_ok_and_port_free(self) -> None:
        readiness = collect_readiness(
            self.pin,
            installed_version="0.5.3",
            port_free=lambda _port: True,
            transport=FakeTransport(),
            observe_busy_port=False,
        )
        report = build_gate_b_report(readiness)
        self.assertEqual(report["decision"], "READY_FOR_LIVE_AUTHORIZATION")
        self.assertTrue(report["checks"]["pin_valid"])
        self.assertTrue(report["checks"]["version_match"])
        self.assertTrue(report["checks"]["port_8100_free"])

    def test_version_mismatch_is_fail_closed(self) -> None:
        readiness = collect_readiness(
            self.pin,
            installed_version="0.5.1",
            port_free=lambda _port: True,
            transport=FakeTransport(),
        )
        report = build_gate_b_report(readiness)
        self.assertEqual(report["decision"], "version_mismatch")
        self.assertFalse(report["checks"]["version_match"])

    def test_observe_mode_not_ready_when_port_busy_and_model_present(self) -> None:
        transport = FakeTransport(
            health={"status": "healthy"},
            models=(PIN_MODEL_ID, "other-model"),
        )
        readiness = collect_readiness(
            self.pin,
            installed_version="0.5.3",
            port_free=lambda _port: False,
            transport=transport,
            observe_busy_port=True,
        )
        report = build_gate_b_report(readiness)
        self.assertEqual(report["decision"], "port_busy_foreign_pool")
        self.assertFalse(readiness["port_8100_free"])
        self.assertTrue(readiness["health_ready"])
        self.assertTrue(readiness["model_present"])
        self.assertEqual(transport.health_calls, 1)
        self.assertEqual(transport.list_models_calls, 1)

    def test_port_busy_without_observe_is_fail_closed(self) -> None:
        readiness = collect_readiness(
            self.pin,
            installed_version="0.5.3",
            port_free=lambda _port: False,
            transport=FakeTransport(),
            observe_busy_port=False,
        )
        report = build_gate_b_report(readiness)
        self.assertEqual(report["decision"], "port_busy")
        self.assertFalse(readiness["model_present"])

    def test_model_missing_when_port_busy_and_inventory_lacks_pin_model(self) -> None:
        transport = FakeTransport(
            health={"status": "healthy"},
            models=("other-model",),
        )
        readiness = collect_readiness(
            self.pin,
            installed_version="0.5.3",
            port_free=lambda _port: False,
            transport=transport,
            observe_busy_port=True,
        )
        report = build_gate_b_report(readiness)
        self.assertEqual(report["decision"], "model_missing")
        self.assertTrue(readiness["health_ready"])

    def test_health_unavailable_when_port_busy_and_health_not_ready(self) -> None:
        transport = FakeTransport(health={"status": "degraded"})
        readiness = collect_readiness(
            self.pin,
            installed_version="0.5.3",
            port_free=lambda _port: False,
            transport=transport,
            observe_busy_port=True,
        )
        report = build_gate_b_report(readiness)
        self.assertEqual(report["decision"], "health_unavailable")

    def test_pin_invalid_when_ownership_mode_wrong(self) -> None:
        wrong_pin = dataclasses.replace(self.pin, ownership_mode="attach_pool")
        readiness = collect_readiness(
            wrong_pin,
            installed_version="0.5.3",
            port_free=lambda _port: True,
            transport=FakeTransport(),
        )
        report = build_gate_b_report(readiness)
        self.assertEqual(report["decision"], "pin_invalid")

    def test_report_never_includes_post_or_run_id_fields(self) -> None:
        readiness = collect_readiness(
            self.pin,
            installed_version="0.5.3",
            port_free=lambda _port: True,
            transport=FakeTransport(),
        )
        report = build_gate_b_report(readiness)
        self.assertEqual(report["http_post_attempts"], 0)
        self.assertEqual(report["inference_request_attempts"], 0)
        self.assertEqual(report["service_lifecycle_actions"], 0)
        self.assertNotIn("run_id", report)

    def test_main_prints_json_with_decision(self) -> None:
        with patch.object(
            gate_b_mod,
            "run_gate_b_check",
            return_value={"decision": "READY_FOR_LIVE_AUTHORIZATION", "checks": {}},
        ):
            buffer = StringIO()
            with patch("sys.stdout", buffer):
                exit_code = main([])
        payload = json.loads(buffer.getvalue())
        self.assertEqual(payload["decision"], "READY_FOR_LIVE_AUTHORIZATION")
        self.assertEqual(exit_code, 0)

    def test_main_exit_code_one_on_fail_closed_decision(self) -> None:
        with patch.object(
            gate_b_mod,
            "run_gate_b_check",
            return_value={"decision": "version_mismatch", "checks": {}},
        ):
            with patch("sys.stdout", new=StringIO()):
                exit_code = main([])
        self.assertEqual(exit_code, 1)

    def test_gate_b_pins_match_approved_contract(self) -> None:
        self.assertEqual(gate_b_mod.APPROVED_VERSION, PIN_VERSION)
        self.assertEqual(gate_b_mod.APPROVED_OWNERSHIP_MODE, PIN_OWNERSHIP_MODE)
        self.assertEqual(gate_b_mod.APPROVED_MODEL_ID, PIN_MODEL_ID)
        pin = OmlxThinkingPin.load(default_pin_path())
        self.assertEqual(pin.version, "0.5.3")
        self.assertEqual(pin.ownership_mode, "dedicated_serve")
        self.assertEqual(pin.model_id, "Qwen3.6-35B-A3B-OptiQ-4bit")


if __name__ == "__main__":
    unittest.main()
