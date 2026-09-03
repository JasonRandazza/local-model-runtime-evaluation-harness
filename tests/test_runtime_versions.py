from __future__ import annotations

import json
import subprocess
import unittest
from typing import Callable

from local_model_runtime_evaluation.runtime_versions import (
    ALL_RUNTIMES,
    RUNTIME_OMLX,
    RUNTIME_OPTIQ,
    RUNTIME_OSAURUS,
    CommandResult,
    capture_runtime_versions,
)


class FakeResult:
    """A fake CommandResult for testing."""

    def __init__(self, returncode: int, stdout: str, stderr: str = "") -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


class FakeRunner:
    """A configurable fake command runner.

    Maps command prefixes to results or exceptions. Each command is matched
    by its first element (the executable name) and second element (the
    subcommand/flag).
    """

    def __init__(self) -> None:
        self._responses: dict[tuple[str, ...], FakeResult | Exception] = {}

    def set(
        self,
        command: list[str],
        response: FakeResult | Exception,
    ) -> None:
        self._responses[tuple(command)] = response

    def __call__(self, command: list[str]) -> CommandResult:
        key = tuple(command)
        if key not in self._responses:
            raise AssertionError(f"unexpected command: {command}")
        response = self._responses[key]
        if isinstance(response, Exception):
            raise response
        return response


def _osaurus_ok() -> FakeResult:
    return FakeResult(
        0,
        json.dumps({
            "apps": [{"version": "0.24.4", "build": "0.24.4"}],
            "cliPath": "/usr/local/bin/osaurus",
            "configuredPort": 1337,
            "modelRoot": "/models",
            "modelCount": 3,
            "serverHealthy": True,
            "diagnosis": [],
            "generatedAt": "2026-09-03T00:00:00Z",
        }),
    )


def _omlx_ok() -> FakeResult:
    return FakeResult(0, "0.6.4\n")


def _optiq_ok() -> FakeResult:
    return FakeResult(0, "mlx-optiq, version 0.4.2\n")


def _all_ok_runner() -> FakeRunner:
    runner = FakeRunner()
    runner.set(["osaurus", "doctor", "--json", "--redact"], _osaurus_ok())
    runner.set(["omlx", "--version"], _omlx_ok())
    runner.set(["optiq", "--version"], _optiq_ok())
    return runner


class RuntimeVersionsParseTests(unittest.TestCase):
    """Each runtime parsed correctly."""

    def test_osaurus_parsed_from_doctor_json(self) -> None:
        runner = _all_ok_runner()
        result = capture_runtime_versions(runner)
        self.assertEqual(
            result[RUNTIME_OSAURUS],
            {
                "version": "0.24.4",
                "method": "osaurus doctor --json --redact",
                "available": True,
                "app_bundles_seen": 1,
                "selected_running_bundle": False,
            },
        )

    def test_omlx_parsed_from_version_flag(self) -> None:
        runner = _all_ok_runner()
        result = capture_runtime_versions(runner)
        self.assertEqual(
            result[RUNTIME_OMLX],
            {
                "version": "0.6.4",
                "method": "omlx --version",
                "available": True,
            },
        )

    def test_optiq_parsed_from_version_flag(self) -> None:
        runner = _all_ok_runner()
        result = capture_runtime_versions(runner)
        self.assertEqual(
            result[RUNTIME_OPTIQ],
            {
                "version": "mlx-optiq, version 0.4.2",
                "method": "optiq --version",
                "available": True,
            },
        )

    def test_all_runtimes_present(self) -> None:
        runner = _all_ok_runner()
        result = capture_runtime_versions(runner)
        for name in ALL_RUNTIMES:
            self.assertIn(name, result)


class RuntimeVersionsFailureTests(unittest.TestCase):
    """Each failure mode yields an explicit unavailable record."""

    def test_osaurus_not_installed(self) -> None:
        runner = FakeRunner()
        runner.set(
            ["osaurus", "doctor", "--json", "--redact"],
            FileNotFoundError(2, "No such file or directory"),
        )
        runner.set(["omlx", "--version"], _omlx_ok())
        runner.set(["optiq", "--version"], _optiq_ok())
        result = capture_runtime_versions(runner)
        self.assertFalse(result[RUNTIME_OSAURUS]["available"])
        self.assertIsNone(result[RUNTIME_OSAURUS]["version"])
        self.assertIn("command failed", result[RUNTIME_OSAURUS]["reason"])

    def test_omlx_not_installed(self) -> None:
        runner = FakeRunner()
        runner.set(["osaurus", "doctor", "--json", "--redact"], _osaurus_ok())
        runner.set(
            ["omlx", "--version"],
            FileNotFoundError(2, "No such file or directory"),
        )
        runner.set(["optiq", "--version"], _optiq_ok())
        result = capture_runtime_versions(runner)
        self.assertFalse(result[RUNTIME_OMLX]["available"])
        self.assertIsNone(result[RUNTIME_OMLX]["version"])
        self.assertIn("command failed", result[RUNTIME_OMLX]["reason"])

    def test_optiq_not_installed(self) -> None:
        runner = FakeRunner()
        runner.set(["osaurus", "doctor", "--json", "--redact"], _osaurus_ok())
        runner.set(["omlx", "--version"], _omlx_ok())
        runner.set(
            ["optiq", "--version"],
            FileNotFoundError(2, "No such file or directory"),
        )
        result = capture_runtime_versions(runner)
        self.assertFalse(result[RUNTIME_OPTIQ]["available"])
        self.assertIsNone(result[RUNTIME_OPTIQ]["version"])
        self.assertIn("command failed", result[RUNTIME_OPTIQ]["reason"])

    def test_osaurus_exits_nonzero(self) -> None:
        runner = FakeRunner()
        runner.set(
            ["osaurus", "doctor", "--json", "--redact"],
            FakeResult(1, "", "error: not connected"),
        )
        runner.set(["omlx", "--version"], _omlx_ok())
        runner.set(["optiq", "--version"], _optiq_ok())
        result = capture_runtime_versions(runner)
        self.assertFalse(result[RUNTIME_OSAURUS]["available"])
        self.assertIn("exited with code 1", result[RUNTIME_OSAURUS]["reason"])

    def test_omlx_exits_nonzero(self) -> None:
        runner = FakeRunner()
        runner.set(["osaurus", "doctor", "--json", "--redact"], _osaurus_ok())
        runner.set(["omlx", "--version"], FakeResult(1, "", "error"))
        runner.set(["optiq", "--version"], _optiq_ok())
        result = capture_runtime_versions(runner)
        self.assertFalse(result[RUNTIME_OMLX]["available"])
        self.assertIn("exited with code 1", result[RUNTIME_OMLX]["reason"])

    def test_optiq_exits_nonzero(self) -> None:
        runner = FakeRunner()
        runner.set(["osaurus", "doctor", "--json", "--redact"], _osaurus_ok())
        runner.set(["omlx", "--version"], _omlx_ok())
        runner.set(["optiq", "--version"], FakeResult(1, "", "error"))
        result = capture_runtime_versions(runner)
        self.assertFalse(result[RUNTIME_OPTIQ]["available"])
        self.assertIn("exited with code 1", result[RUNTIME_OPTIQ]["reason"])

    def test_osaurus_unparseable_json(self) -> None:
        runner = FakeRunner()
        runner.set(
            ["osaurus", "doctor", "--json", "--redact"],
            FakeResult(0, "not json at all"),
        )
        runner.set(["omlx", "--version"], _omlx_ok())
        runner.set(["optiq", "--version"], _optiq_ok())
        result = capture_runtime_versions(runner)
        self.assertFalse(result[RUNTIME_OSAURUS]["available"])
        self.assertIn("unparseable JSON", result[RUNTIME_OSAURUS]["reason"])

    def test_omlx_empty_output(self) -> None:
        runner = FakeRunner()
        runner.set(["osaurus", "doctor", "--json", "--redact"], _osaurus_ok())
        runner.set(["omlx", "--version"], FakeResult(0, "   \n  "))
        runner.set(["optiq", "--version"], _optiq_ok())
        result = capture_runtime_versions(runner)
        self.assertFalse(result[RUNTIME_OMLX]["available"])
        self.assertIn("empty output", result[RUNTIME_OMLX]["reason"])

    def test_optiq_empty_output(self) -> None:
        runner = FakeRunner()
        runner.set(["osaurus", "doctor", "--json", "--redact"], _osaurus_ok())
        runner.set(["omlx", "--version"], _omlx_ok())
        runner.set(["optiq", "--version"], FakeResult(0, "   \n  "))
        result = capture_runtime_versions(runner)
        self.assertFalse(result[RUNTIME_OPTIQ]["available"])
        self.assertIn("empty output", result[RUNTIME_OPTIQ]["reason"])

    def test_osaurus_timeout(self) -> None:
        runner = FakeRunner()
        runner.set(
            ["osaurus", "doctor", "--json", "--redact"],
            subprocess.TimeoutExpired(cmd="osaurus", timeout=30),
        )
        runner.set(["omlx", "--version"], _omlx_ok())
        runner.set(["optiq", "--version"], _optiq_ok())
        result = capture_runtime_versions(runner)
        self.assertFalse(result[RUNTIME_OSAURUS]["available"])
        self.assertIn("command failed", result[RUNTIME_OSAURUS]["reason"])

    def test_omlx_timeout(self) -> None:
        runner = FakeRunner()
        runner.set(["osaurus", "doctor", "--json", "--redact"], _osaurus_ok())
        runner.set(
            ["omlx", "--version"],
            subprocess.TimeoutExpired(cmd="omlx", timeout=30),
        )
        runner.set(["optiq", "--version"], _optiq_ok())
        result = capture_runtime_versions(runner)
        self.assertFalse(result[RUNTIME_OMLX]["available"])
        self.assertIn("command failed", result[RUNTIME_OMLX]["reason"])

    def test_optiq_timeout(self) -> None:
        runner = FakeRunner()
        runner.set(["osaurus", "doctor", "--json", "--redact"], _osaurus_ok())
        runner.set(["omlx", "--version"], _omlx_ok())
        runner.set(
            ["optiq", "--version"],
            subprocess.TimeoutExpired(cmd="optiq", timeout=30),
        )
        result = capture_runtime_versions(runner)
        self.assertFalse(result[RUNTIME_OPTIQ]["available"])
        self.assertIn("command failed", result[RUNTIME_OPTIQ]["reason"])


class OsaurusAppsEdgeCases(unittest.TestCase):
    """Osaurus apps-array edge cases."""

    def _runner_with_osaurus(self, osaurus_response: FakeResult | Exception) -> FakeRunner:
        runner = FakeRunner()
        runner.set(["osaurus", "doctor", "--json", "--redact"], osaurus_response)
        runner.set(["omlx", "--version"], _omlx_ok())
        runner.set(["optiq", "--version"], _optiq_ok())
        return runner

    def test_empty_apps_array(self) -> None:
        runner = self._runner_with_osaurus(
            FakeResult(0, json.dumps({"apps": []})),
        )
        result = capture_runtime_versions(runner)
        self.assertFalse(result[RUNTIME_OSAURUS]["available"])
        self.assertIn("no apps array", result[RUNTIME_OSAURUS]["reason"])

    def test_missing_apps_key(self) -> None:
        runner = self._runner_with_osaurus(
            FakeResult(0, json.dumps({"cliPath": "/usr/local/bin/osaurus"})),
        )
        result = capture_runtime_versions(runner)
        self.assertFalse(result[RUNTIME_OSAURUS]["available"])
        self.assertIn("no apps array", result[RUNTIME_OSAURUS]["reason"])

    def test_apps_is_not_a_list(self) -> None:
        runner = self._runner_with_osaurus(
            FakeResult(0, json.dumps({"apps": "not a list"})),
        )
        result = capture_runtime_versions(runner)
        self.assertFalse(result[RUNTIME_OSAURUS]["available"])
        self.assertIn("no apps array", result[RUNTIME_OSAURUS]["reason"])

    def test_apps_entry_is_not_an_object(self) -> None:
        runner = self._runner_with_osaurus(
            FakeResult(0, json.dumps({"apps": ["just a string"]})),
        )
        result = capture_runtime_versions(runner)
        self.assertFalse(result[RUNTIME_OSAURUS]["available"])
        self.assertIn("apps entry is not an object", result[RUNTIME_OSAURUS]["reason"])

    def test_apps_entry_missing_version(self) -> None:
        runner = self._runner_with_osaurus(
            FakeResult(0, json.dumps({"apps": [{"build": "0.24.4"}]})),
        )
        result = capture_runtime_versions(runner)
        self.assertFalse(result[RUNTIME_OSAURUS]["available"])
        self.assertIn("no version in apps entry", result[RUNTIME_OSAURUS]["reason"])

    def test_apps_entry_empty_version(self) -> None:
        runner = self._runner_with_osaurus(
            FakeResult(0, json.dumps({"apps": [{"version": "  "}]})),
        )
        result = capture_runtime_versions(runner)
        self.assertFalse(result[RUNTIME_OSAURUS]["available"])
        self.assertIn("no version in apps entry", result[RUNTIME_OSAURUS]["reason"])

    def test_apps_entry_version_not_a_string(self) -> None:
        runner = self._runner_with_osaurus(
            FakeResult(0, json.dumps({"apps": [{"version": 42}]})),
        )
        result = capture_runtime_versions(runner)
        self.assertFalse(result[RUNTIME_OSAURUS]["available"])
        self.assertIn("no version in apps entry", result[RUNTIME_OSAURUS]["reason"])

    def test_multiple_apps_records_how_many_were_seen(self) -> None:
        runner = self._runner_with_osaurus(
            FakeResult(
                0,
                json.dumps({
                    "apps": [
                        {"version": "0.24.4"},
                        {"version": "0.25.0"},
                    ],
                }),
            ),
        )
        result = capture_runtime_versions(runner)
        self.assertTrue(result[RUNTIME_OSAURUS]["available"])
        self.assertEqual(result[RUNTIME_OSAURUS]["version"], "0.24.4")
        # Duplicate bundles must be visible, not silently collapsed.
        self.assertEqual(result[RUNTIME_OSAURUS]["app_bundles_seen"], 2)
        self.assertFalse(result[RUNTIME_OSAURUS]["selected_running_bundle"])

    def test_running_bundle_wins_over_first_listed(self) -> None:
        runner = self._runner_with_osaurus(
            FakeResult(
                0,
                json.dumps({
                    "apps": [
                        {"version": "0.24.4", "isRunning": False},
                        {"version": "0.25.0", "isRunning": True},
                    ],
                }),
            ),
        )
        result = capture_runtime_versions(runner)
        # The bundle actually serving is the one the run ran against.
        self.assertEqual(result[RUNTIME_OSAURUS]["version"], "0.25.0")
        self.assertTrue(result[RUNTIME_OSAURUS]["selected_running_bundle"])


class RuntimeVersionsCliTests(unittest.TestCase):
    """The runtime-versions CLI command emits JSON on stdout."""

    def test_cli_emits_json_with_runtimes(self) -> None:
        from unittest.mock import patch
        from io import StringIO
        from contextlib import redirect_stdout

        from local_model_runtime_evaluation.managed_run_cli import main as _main

        fake_result = {
            "osaurus": {
                "version": "0.24.4",
                "method": "osaurus doctor --json --redact",
                "available": True,
            },
            "omlx": {
                "version": "0.6.4",
                "method": "omlx --version",
                "available": True,
            },
            "optiq": {
                "version": "mlx-optiq, version 0.4.2",
                "method": "optiq --version",
                "available": True,
            },
        }
        output = StringIO()
        with patch(
            "local_model_runtime_evaluation.managed_run_cli.capture_runtime_versions",
            return_value=fake_result,
        ):
            with redirect_stdout(output):
                code = _main(["runtime-versions"])
        self.assertEqual(code, 0)
        body = json.loads(output.getvalue())
        self.assertTrue(body["ok"])
        self.assertEqual(body["runtimes"], fake_result)


if __name__ == "__main__":
    unittest.main()
