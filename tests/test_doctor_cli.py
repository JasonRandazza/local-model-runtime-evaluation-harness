"""CLI tests for the `lmre doctor` subcommand.

Non-live: every invocation injects a temporary machine profile path and
state directory; nothing touches the real `.lmre/` or any runtime.
"""

from __future__ import annotations

import io
import json
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from local_model_runtime_evaluation.managed_run_cli import main


class DoctorCliTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.profile = self.root / "machine-profile.json"  # deliberately absent
        self.state_dir = self.root / "state"

    def _run(self, argv: list[str]) -> tuple[int, str]:
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = main(argv, machine_profile_path=self.profile)
        return code, buffer.getvalue()

    def test_json_default_completes_with_action_required(self) -> None:
        code, out = self._run(["--state-dir", str(self.state_dir), "doctor"])
        self.assertEqual(code, 0)
        body = json.loads(out)
        self.assertTrue(body["ok"])
        diagnostic = body["diagnostic"]
        # ok means the diagnostic completed; readiness is separate. With no
        # profile and no adopted policy this machine needs action.
        self.assertEqual(diagnostic["overall_readiness"], "ACTION_REQUIRED")
        self.assertTrue(diagnostic["actions"])
        section_names = [s["section"] for s in diagnostic["sections"]]
        self.assertEqual(
            section_names,
            [
                "harness",
                "commands",
                "machine_profile",
                "configuration",
                "artifacts",
                "policy",
                "families",
            ],
        )

    def test_text_mode_prints_checklist_not_json(self) -> None:
        code, out = self._run(
            ["--state-dir", str(self.state_dir), "doctor", "--format", "text"]
        )
        self.assertEqual(code, 0)
        self.assertIn("Overall readiness:", out)
        self.assertIn("NOT_CHECKED_LIVE", out)
        self.assertIn("were NOT checked here", out)
        with self.assertRaises(json.JSONDecodeError):
            json.loads(out)

    def test_json_and_text_project_the_same_result(self) -> None:
        _, json_out = self._run(["--state-dir", str(self.state_dir), "doctor"])
        _, text_out = self._run(
            ["--state-dir", str(self.state_dir), "doctor", "--format", "text"]
        )
        diagnostic = json.loads(json_out)["diagnostic"]
        for section in diagnostic["sections"]:
            for finding in section["findings"]:
                self.assertIn(finding["check"], text_out)
                self.assertIn(f"[{finding['status']}]", text_out)
        self.assertIn(diagnostic["overall_readiness"], text_out)

    def test_no_live_readiness_claim(self) -> None:
        for argv in (
            ["--state-dir", str(self.state_dir), "doctor"],
            ["--state-dir", str(self.state_dir), "doctor", "--format", "text"],
        ):
            _, out = self._run(argv)
            lowered = out.lower()
            self.assertNotIn("live ready", lowered)
            self.assertNotIn("ready to run live", lowered)

    def test_internal_failure_uses_sanitized_error_path(self) -> None:
        with patch(
            "local_model_runtime_evaluation.managed_run_cli.run_diagnostics",
            side_effect=RuntimeError("boom token=abc123"),
        ):
            code, out = self._run(["--state-dir", str(self.state_dir), "doctor"])
        self.assertEqual(code, 1)
        body = json.loads(out)
        self.assertFalse(body["ok"])
        self.assertNotIn("abc123", out)

    def test_malformed_invocation_exits_nonzero(self) -> None:
        with self.assertRaises(SystemExit) as ctx:
            main(["doctor", "--format", "bogus"], machine_profile_path=self.profile)
        self.assertNotEqual(ctx.exception.code, 0)


if __name__ == "__main__":
    unittest.main()
