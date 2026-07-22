from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from local_model_runtime_evaluation.omlx_thinking_measure import THINKING_PREFLIGHT_MAX_TOKENS
from local_model_runtime_evaluation.omlx_thinking_pin import (
    OmlxThinkingPin,
    OmlxThinkingPinError,
    OmlxThinkingSuite,
    default_pin_path,
    default_suite_path,
)


class OmlxThinkingPinTest(unittest.TestCase):
    def setUp(self) -> None:
        self.path = default_pin_path()

    def test_loads_canonical_pin(self) -> None:
        pin = OmlxThinkingPin.load(self.path)
        self.assertEqual(pin.pin_id, "omlx-0.5.2-thinking")
        self.assertEqual(pin.revision, "1")
        self.assertEqual(pin.version, "0.5.2")
        self.assertEqual(pin.base_url, "http://127.0.0.1:8100/v1")
        self.assertEqual(pin.comparison_class, "omlx-thinking-measure-v1")
        self.assertEqual(pin.model_id, "Qwen3.6-35B-A3B-OptiQ-4bit")
        self.assertEqual(
            pin.model_dir,
            "/Users/jrazz/.cache/huggingface/hub/mlx-community/Qwen3.6-35B-A3B-OptiQ-4bit",
        )
        self.assertEqual(pin.ownership_mode, "dedicated_serve")
        self.assertEqual(pin.api_key_source, "matrix_local")
        self.assertEqual(pin.extra_body_allowlist, ())
        self.assertEqual(
            pin.start_command,
            (
                "omlX",
                "serve",
                "--model-dir",
                "/Users/jrazz/.cache/huggingface/hub/mlx-community/Qwen3.6-35B-A3B-OptiQ-4bit",
                "--host",
                "127.0.0.1",
                "--port",
                "8100",
            ),
        )
        self.assertEqual(pin.stop_command, ("omlX", "stop"))

    def test_rejects_wrong_version(self) -> None:
        data = json.loads(self.path.read_text(encoding="utf-8"))
        data["version"] = "0.5.1"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "pin.json"
            path.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaises(OmlxThinkingPinError):
                OmlxThinkingPin.load(path)

    def test_rejects_missing_required_field(self) -> None:
        data = json.loads(self.path.read_text(encoding="utf-8"))
        del data["base_url"]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "pin.json"
            path.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaises(OmlxThinkingPinError):
                OmlxThinkingPin.load(path)

    def test_rejects_wrong_base_url(self) -> None:
        data = json.loads(self.path.read_text(encoding="utf-8"))
        data["base_url"] = "http://127.0.0.1:8080/v1"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "pin.json"
            path.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaises(OmlxThinkingPinError):
                OmlxThinkingPin.load(path)

    def test_rejects_wrong_model_id(self) -> None:
        data = json.loads(self.path.read_text(encoding="utf-8"))
        data["model_id"] = "ThinkingCap-Qwen3.6-27B-OptiQ-4bit"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "pin.json"
            path.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaises(OmlxThinkingPinError):
                OmlxThinkingPin.load(path)

    def test_rejects_attach_pool_ownership_mode(self) -> None:
        data = json.loads(self.path.read_text(encoding="utf-8"))
        data["ownership_mode"] = "attach_pool"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "pin.json"
            path.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaises(OmlxThinkingPinError):
                OmlxThinkingPin.load(path)

    def test_rejects_wrong_api_key_source(self) -> None:
        data = json.loads(self.path.read_text(encoding="utf-8"))
        data["api_key_source"] = "none"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "pin.json"
            path.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaises(OmlxThinkingPinError):
                OmlxThinkingPin.load(path)

    def test_rejects_start_command_missing_model_dir(self) -> None:
        data = json.loads(self.path.read_text(encoding="utf-8"))
        data["start_command"] = [
            "omlX",
            "serve",
            "--host",
            "127.0.0.1",
            "--port",
            "8100",
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "pin.json"
            path.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaises(OmlxThinkingPinError):
                OmlxThinkingPin.load(path)

    def test_accepts_allowlisted_extra_body_keys(self) -> None:
        data = json.loads(self.path.read_text(encoding="utf-8"))
        data["extra_body_allowlist"] = ["enable_thinking"]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "pin.json"
            path.write_text(json.dumps(data), encoding="utf-8")
            pin = OmlxThinkingPin.load(path)
            self.assertEqual(pin.extra_body_allowlist, ("enable_thinking",))


class OmlxThinkingSuiteTest(unittest.TestCase):
    def setUp(self) -> None:
        self.path = default_suite_path()

    def test_loads_canonical_suite(self) -> None:
        suite = OmlxThinkingSuite.load(self.path)
        self.assertEqual(suite.suite_id, "omlx-thinking-smoke-v1")
        self.assertEqual(suite.revision, "1")
        self.assertEqual(len(suite.workloads), 2)
        self.assertTrue(all(item.max_tokens >= THINKING_PREFLIGHT_MAX_TOKENS for item in suite.workloads))

    def test_rejects_workload_below_max_tokens_floor(self) -> None:
        data = json.loads(self.path.read_text(encoding="utf-8"))
        data["workloads"][0]["max_tokens"] = THINKING_PREFLIGHT_MAX_TOKENS - 1
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "suite.json"
            path.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaises(OmlxThinkingPinError):
                OmlxThinkingSuite.load(path)


if __name__ == "__main__":
    unittest.main()
