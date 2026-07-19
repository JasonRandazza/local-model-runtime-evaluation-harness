import json
import re
import shlex
import unittest
from pathlib import Path

import local_model_runtime_evaluation


class PackageTest(unittest.TestCase):
    def test_package_version_is_exposed(self) -> None:
        self.assertEqual(local_model_runtime_evaluation.__version__, "0.3.0")

    def test_stage_two_operator_launcher_is_fixed_foreground_exec(self) -> None:
        root = Path(__file__).parents[1]
        profile = json.loads((
            root / "config" / "runtime-profiles" / "vibethinker-3b-optiq-4bit-r3.json"
        ).read_text(encoding="utf-8"))
        launcher = root / "bin" / "lmre-stage2-operator-serve"
        content = launcher.read_text(encoding="utf-8")
        command = next(line for line in content.splitlines() if line.startswith("exec "))

        self.assertEqual(content.splitlines()[0], "#!/bin/zsh")
        self.assertNotIn("$@", content)
        self.assertNotIn("eval", content)
        self.assertEqual(
            shlex.split(command),
            ["exec", profile["runtime_executable"], *profile["serve_arguments"]],
        )
        self.assertTrue(launcher.stat().st_mode & 0o111)

    def test_stage_two_template_cannot_authorize_a_run(self) -> None:
        root = Path(__file__).parents[1]
        template = json.loads((
            root / "manifests" / "stage-2-optiq-operator-route.json.template"
        ).read_text(encoding="utf-8"))

        self.assertEqual(template["run_id"], "stage2-YYYYMMDD-NNN")
        self.assertEqual(template["approved_by"], "REQUIRES_CURRENT_SESSION_APPROVAL")
        self.assertEqual(template["approved_at"], "REPLACE_AFTER_APPROVAL")
        self.assertEqual(template["expires_at"], "REPLACE_AFTER_APPROVAL")
        self.assertEqual(template["runtime_profile_revision"], "3")
        self.assertEqual(template["mode"], "operator_route_probe")

    def test_stage_two_inference_template_is_non_authorizing_and_plugin_is_unchanged(self) -> None:
        root = Path(__file__).parents[1]
        template = json.loads((
            root / "manifests" / "stage-2-optiq-inference-smoke.json.template"
        ).read_text(encoding="utf-8"))
        plugin = json.loads((
            root / "plugins" / "osaurus-evaluation-harness" / "osaurus-plugin.json"
        ).read_text(encoding="utf-8"))
        plugin_source = (
            root
            / "plugins"
            / "osaurus-evaluation-harness"
            / "Sources"
            / "OsaurusEvaluationHarness"
            / "HarnessCore.swift"
        ).read_text(encoding="utf-8")

        self.assertEqual(template["schema_version"], "3.2.0")
        self.assertEqual(template["run_id"], "stage2-YYYYMMDD-NNN")
        self.assertEqual(template["approved_by"], "REQUIRES_CURRENT_SESSION_APPROVAL")
        self.assertEqual(template["approved_at"], "REPLACE_AFTER_APPROVAL")
        self.assertEqual(template["expires_at"], "REPLACE_AFTER_APPROVAL")
        self.assertEqual(template["routes"], {
            "direct": "http://127.0.0.1:8080/v1",
            "routed": "http://127.0.0.1:1337/v1",
        })
        self.assertEqual(template["limits"], {
            "request_timeout_seconds": 120,
            "memory_stop_level": "warning",
            "maximum_in_flight_requests": 1,
            "total_request_limit": 8,
        })

        self.assertEqual(plugin["version"], "0.3.0")
        match = re.search(r"static let toolIDs = \[(.*?)\]", plugin_source)
        self.assertIsNotNone(match)
        self.assertEqual(re.findall(r'"([^\"]+)"', match.group(1)), [
            "inventory", "preflight", "run_scenario", "status", "cancel", "cleanup",
        ])


if __name__ == "__main__":
    unittest.main()
