from __future__ import annotations

import json
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from local_model_runtime_evaluation.evidence_bundle import EvidenceBundle
from local_model_runtime_evaluation.managed_run_cli import main
from local_model_runtime_evaluation.managed_run_types import (
    ManagedStep,
    StepState,
)


ROOT = Path(__file__).resolve().parents[1]
RECIPE = ROOT / "config" / "managed-runs" / "complete-native-quality-v1.json"
POLICY = (
    ROOT
    / "config"
    / "operator-policies"
    / "local-managed-v1.example.json"
)


def _main_json(argv: list[str]) -> tuple[int, dict[str, object]]:
    output = StringIO()
    with redirect_stdout(output):
        code = main(argv)
    return code, json.loads(output.getvalue())


class ManagedRunCliTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.state_root = self.root / ".lmre"
        self.results_root = self.root / "results"

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _global(self) -> list[str]:
        return [
            "--state-dir",
            str(self.state_root),
            "--results-dir",
            str(self.results_root),
        ]

    def _adopt(self) -> dict[str, object]:
        code, payload = _main_json(
            self._global()
            + ["policy", "adopt", "--from", str(POLICY)]
        )
        self.assertEqual(code, 0)
        return payload

    def _plan(self) -> dict[str, object]:
        code, payload = _main_json(
            self._global()
            + [
                "plan",
                "--family",
                "gemma-4-12b-qat",
                "--recipe",
                str(RECIPE),
                "--name",
                "gemma baseline",
            ]
        )
        self.assertEqual(code, 0)
        return payload

    def test_plan_fails_when_policy_is_not_adopted(self) -> None:
        code, payload = _main_json(
            self._global()
            + [
                "plan",
                "--family",
                "gemma-4-12b-qat",
                "--recipe",
                str(RECIPE),
                "--name",
                "gemma baseline",
            ]
        )
        self.assertEqual(code, 1)
        self.assertEqual(
            payload["error"]["kind"],  # type: ignore[index]
            "operator_policy_missing",
        )

    def test_policy_adopt_then_plan_writes_no_live_activity(self) -> None:
        with patch(
            "local_model_runtime_evaluation.managed_run_cli.execute_managed_run",
            side_effect=AssertionError("planning must not execute"),
        ), patch(
            "local_model_runtime_evaluation.matrix_lifecycle.spawn_pinned",
            side_effect=AssertionError("planning must not spawn"),
        ):
            adopted = self._adopt()
            planned = self._plan()
        self.assertEqual(adopted["policy_id"], "local-managed-v1")
        self.assertEqual(adopted["reclaim_grace_seconds"], 60)
        self.assertIn("run_id", planned)
        self.assertTrue(
            (
                self.results_root
                / str(planned["run_id"])
                / "plan.json"
            ).is_file()
        )

    def test_status_and_report_read_sealed_evidence(self) -> None:
        self._adopt()
        planned = self._plan()
        run_id = str(planned["run_id"])
        bundle = EvidenceBundle.load(self.results_root / run_id)
        for record in bundle.state.steps:
            bundle.transition_step(record.step, StepState.STOPPED)
        bundle.mark_cleanup_complete()
        bundle.write_summary({"status": "STOPPED"})
        bundle.seal()

        status_code, status = _main_json(
            self._global() + ["status", run_id]
        )
        report_code, report = _main_json(
            self._global() + ["report", run_id]
        )
        self.assertEqual((status_code, report_code), (0, 0))
        self.assertEqual(status["summary_state"], "STOPPED")
        self.assertEqual(report["status"], "STOPPED")

    def test_resume_delegates_after_bundle_validation(self) -> None:
        self._adopt()
        planned = self._plan()
        run_id = str(planned["run_id"])
        bundle = EvidenceBundle.load(self.results_root / run_id)
        for record in bundle.state.steps:
            if record.step is ManagedStep.OVERHEAD:
                bundle.transition_step(record.step, StepState.RUNNING)
                bundle.transition_step(
                    record.step,
                    StepState.BLOCKED_PROVIDER_RECONNECT,
                )
            else:
                bundle.transition_step(record.step, StepState.STOPPED)
        bundle.mark_cleanup_complete()
        bundle.write_summary({"status": "PARTIAL_BLOCKED"})
        bundle.seal()
        with patch(
            "local_model_runtime_evaluation.managed_run_cli.resume_managed_run",
            return_value={"status": "PASS"},
        ) as resume, patch(
            "local_model_runtime_evaluation.managed_run_cli._build_runtime_manager",
            return_value=object(),
        ):
            code, payload = _main_json(
                self._global() + ["resume", run_id]
            )
        self.assertEqual(code, 0)
        self.assertEqual(payload["status"], "PASS")
        resume.assert_called_once()

    def test_run_refuses_unknown_unplanned_id(self) -> None:
        self._adopt()
        code, payload = _main_json(
            self._global() + ["run", "run-20260730-180000-a1b2c3"]
        )
        self.assertEqual(code, 1)
        self.assertEqual(
            payload["error"]["kind"],  # type: ignore[index]
            "evidence_file_missing",
        )

    def test_run_refuses_an_existing_global_active_run_lock(self) -> None:
        self._adopt()
        planned = self._plan()
        self.state_root.mkdir(parents=True, exist_ok=True)
        (self.state_root / "active-run.lock").write_text(
            '{"run_id":"other-run"}\n',
            encoding="utf-8",
        )
        with patch(
            "local_model_runtime_evaluation.managed_run_cli."
            "execute_managed_run",
            return_value={"status": "PASS"},
        ) as execute:
            code, payload = _main_json(
                self._global() + ["run", str(planned["run_id"])]
            )

        self.assertEqual(code, 1)
        self.assertIn(
            "active managed run",
            payload["error"]["message"],  # type: ignore[index]
        )
        execute.assert_not_called()

    def test_help_names_ui_owned_provider_reconnect(self) -> None:
        output = StringIO()
        with self.assertRaises(SystemExit) as context, redirect_stdout(output):
            main(["resume", "--help"])
        self.assertEqual(context.exception.code, 0)
        self.assertIn("Osaurus UI", output.getvalue())


if __name__ == "__main__":
    unittest.main()
