"""Offline regression tests for the fixed-loopback LMRE run console."""

from __future__ import annotations

import signal
import subprocess
import unittest
from http import cookies
from pathlib import Path
from tempfile import TemporaryDirectory

from local_model_runtime_evaluation.managed_run_cli import build_parser
from local_model_runtime_evaluation.run_console import (
    ACTION_RESUME,
    ACTION_START,
    ConsoleError,
    RunConsoleController,
)
from local_model_runtime_evaluation.run_console_html import render_console
from local_model_runtime_evaluation.run_console_server import (
    validate_csrf,
    validate_host,
    validate_post_origin,
)
from tests.results_browser_fixtures import (
    make_partial_blocked_with_attempts,
    make_pending_plan,
    make_sealed_pass,
)


class FakeProcess:
    def __init__(self, pid: int = 4242) -> None:
        self.pid = pid
        self.returncode: int | None = None
        self.signals: list[int] = []

    def poll(self) -> int | None:
        return self.returncode

    def send_signal(self, sig: int) -> None:
        self.signals.append(sig)

    def wait(self, timeout: float | None = None) -> int:
        del timeout
        if self.returncode is None:
            raise subprocess.TimeoutExpired("fake", 30)
        return self.returncode


class FakeFactory:
    def __init__(self) -> None:
        self.arguments: list[list[str]] = []
        self.processes: list[FakeProcess] = []

    def __call__(self, arguments: list[str]) -> FakeProcess:
        process = FakeProcess(pid=4242 + len(self.processes))
        self.arguments.append(arguments)
        self.processes.append(process)
        return process


class RunConsoleControllerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.results_root = self.root / "results"
        self.state_root = self.root / ".lmre"
        self.factory = FakeFactory()
        self.clock_value = [100.0]
        self.controller = RunConsoleController(
            self.results_root,
            self.state_root,
            process_factory=self.factory,
            clock=lambda: self.clock_value[0],
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_dashboard_lists_existing_plans_and_issues_start_grant(self) -> None:
        run_dir = make_pending_plan(self.root)
        dashboard = self.controller.dashboard(run_dir.name)
        self.assertEqual(dashboard["selected_run_id"], run_dir.name)
        self.assertEqual(len(dashboard["entries"]), 1)
        self.assertTrue(dashboard["detail"]["can_start"])
        self.assertFalse(dashboard["detail"]["can_resume"])
        self.assertIn(ACTION_START, dashboard["grants"])

    def test_exact_grant_starts_fixed_cli_child_then_cancels_by_sigint(self) -> None:
        run_dir = make_pending_plan(self.root)
        dashboard = self.controller.dashboard(run_dir.name)
        identity = dashboard["detail"]["identity"]
        self.controller.start_action(
            action=ACTION_START,
            run_id=run_dir.name,
            nonce=dashboard["grants"][ACTION_START],
            confirmed_plan_hash=identity["plan_hash"],
            acknowledged=True,
        )
        arguments = self.factory.arguments[0]
        self.assertEqual(arguments[-2:], [ACTION_START, run_dir.name])
        self.assertEqual(
            arguments[1:3], ["-m", "local_model_runtime_evaluation.managed_run_cli"]
        )
        self.assertNotIn("shell=True", arguments)
        active = self.controller.dashboard(run_dir.name)["detail"]["active_action"]
        self.assertEqual(active["run_id"], run_dir.name)
        self.controller.cancel(run_dir.name)
        self.assertEqual(self.factory.processes[0].signals, [signal.SIGINT])
        with self.assertRaisesRegex(ConsoleError, "already requested"):
            self.controller.cancel(run_dir.name)

    def test_wrong_hash_consumes_single_use_grant(self) -> None:
        run_dir = make_pending_plan(self.root)
        dashboard = self.controller.dashboard(run_dir.name)
        grant = dashboard["grants"][ACTION_START]
        with self.assertRaisesRegex(ConsoleError, "did not match"):
            self.controller.start_action(
                action=ACTION_START,
                run_id=run_dir.name,
                nonce=grant,
                confirmed_plan_hash="0" * 64,
                acknowledged=True,
            )
        with self.assertRaisesRegex(ConsoleError, "did not match"):
            self.controller.start_action(
                action=ACTION_START,
                run_id=run_dir.name,
                nonce=grant,
                confirmed_plan_hash=dashboard["detail"]["identity"]["plan_hash"],
                acknowledged=True,
            )
        self.assertEqual(self.factory.arguments, [])

    def test_expired_grant_fails_closed(self) -> None:
        run_dir = make_pending_plan(self.root)
        dashboard = self.controller.dashboard(run_dir.name)
        self.clock_value[0] += 601
        with self.assertRaisesRegex(ConsoleError, "did not match"):
            self.controller.start_action(
                action=ACTION_START,
                run_id=run_dir.name,
                nonce=dashboard["grants"][ACTION_START],
                confirmed_plan_hash=dashboard["detail"]["identity"]["plan_hash"],
                acknowledged=True,
            )

    def test_new_page_invalidates_older_grant_for_same_action(self) -> None:
        run_dir = make_pending_plan(self.root)
        first = self.controller.dashboard(run_dir.name)
        second = self.controller.dashboard(run_dir.name)
        with self.assertRaisesRegex(ConsoleError, "did not match"):
            self.controller.start_action(
                action=ACTION_START,
                run_id=run_dir.name,
                nonce=first["grants"][ACTION_START],
                confirmed_plan_hash=first["detail"]["identity"]["plan_hash"],
                acknowledged=True,
            )
        self.controller.start_action(
            action=ACTION_START,
            run_id=run_dir.name,
            nonce=second["grants"][ACTION_START],
            confirmed_plan_hash=second["detail"]["identity"]["plan_hash"],
            acknowledged=True,
        )

    def test_acknowledgement_is_required_before_grant_consumption(self) -> None:
        run_dir = make_pending_plan(self.root)
        dashboard = self.controller.dashboard(run_dir.name)
        with self.assertRaisesRegex(ConsoleError, "acknowledgement"):
            self.controller.start_action(
                action=ACTION_START,
                run_id=run_dir.name,
                nonce=dashboard["grants"][ACTION_START],
                confirmed_plan_hash=dashboard["detail"]["identity"]["plan_hash"],
                acknowledged=False,
            )
        self.controller.start_action(
            action=ACTION_START,
            run_id=run_dir.name,
            nonce=dashboard["grants"][ACTION_START],
            confirmed_plan_hash=dashboard["detail"]["identity"]["plan_hash"],
            acknowledged=True,
        )

    def test_second_action_is_rejected_while_child_active(self) -> None:
        first = make_pending_plan(self.root, entropy="aaaaa1")
        second = make_pending_plan(self.root, entropy="aaaaa2")
        first_view = self.controller.dashboard(first.name)
        self.controller.start_action(
            action=ACTION_START,
            run_id=first.name,
            nonce=first_view["grants"][ACTION_START],
            confirmed_plan_hash=first_view["detail"]["identity"]["plan_hash"],
            acknowledged=True,
        )
        self.assertIsNone(self.controller.issue_grant(second.name, ACTION_START))
        second_view = self.controller.dashboard(second.name)
        self.assertFalse(second_view["detail"]["can_start"])

    def test_completed_child_is_presentation_only_and_evidence_remains_truth(
        self,
    ) -> None:
        run_dir = make_pending_plan(self.root)
        view = self.controller.dashboard(run_dir.name)
        self.controller.start_action(
            action=ACTION_START,
            run_id=run_dir.name,
            nonce=view["grants"][ACTION_START],
            confirmed_plan_hash=view["detail"]["identity"]["plan_hash"],
            acknowledged=True,
        )
        self.factory.processes[0].returncode = 1
        refreshed = self.controller.dashboard(run_dir.name)
        self.assertIsNone(refreshed["detail"]["active_action"])
        self.assertEqual(refreshed["detail"]["last_action"]["return_code"], 1)
        self.assertEqual(refreshed["detail"]["summary"], None)

    def test_partial_blocked_bundle_is_resume_eligible(self) -> None:
        run_dir = make_partial_blocked_with_attempts(self.root)
        dashboard = self.controller.dashboard(run_dir.name)
        self.assertTrue(dashboard["detail"]["can_resume"])
        self.assertIn(ACTION_RESUME, dashboard["grants"])

    def test_sealed_pass_is_neither_start_nor_resume_eligible(self) -> None:
        run_dir = make_sealed_pass(self.root)
        dashboard = self.controller.dashboard(run_dir.name)
        self.assertFalse(dashboard["detail"]["can_start"])
        self.assertFalse(dashboard["detail"]["can_resume"])
        self.assertEqual(dashboard["grants"], {})

    def test_unrecognized_run_id_is_rejected(self) -> None:
        with self.assertRaisesRegex(ConsoleError, "not recognized"):
            self.controller.dashboard("../outside")

    def test_shutdown_uses_exact_sigint_then_bounded_sigterm_without_kill(self) -> None:
        run_dir = make_pending_plan(self.root)
        dashboard = self.controller.dashboard(run_dir.name)
        self.controller.start_action(
            action=ACTION_START,
            run_id=run_dir.name,
            nonce=dashboard["grants"][ACTION_START],
            confirmed_plan_hash=dashboard["detail"]["identity"]["plan_hash"],
            acknowledged=True,
        )
        self.controller.shutdown(timeout=0.01)
        self.assertEqual(
            self.factory.processes[0].signals,
            [signal.SIGINT, signal.SIGTERM],
        )


class RunConsoleRenderingTests(unittest.TestCase):
    def test_render_escapes_plan_values_and_contains_no_script(self) -> None:
        dashboard = {
            "entries": [
                {
                    "run_id": "run-20260731-043000-ababab",
                    "run_name": "<script>alert(1)</script>",
                    "run_status": "PENDING",
                    "created_at": "2026-07-31T04:30:00+00:00",
                }
            ],
            "selected_run_id": "run-20260731-043000-ababab",
            "grants": {},
            "detail": {
                "identity": {
                    "run_id": "run-20260731-043000-ababab",
                    "run_name": "<script>alert(1)</script>",
                    "plan_hash": "a" * 64,
                    "comparison_scope": "family",
                    "family_id": "fake-family",
                    "open_mix_id": None,
                    "recipe_id": "fixture",
                    "created_at": "2026-07-31T04:30:00+00:00",
                    "request_count": 1,
                    "estimated_minutes": 1,
                    "runtimes": ["fake"],
                },
                "summary": None,
                "policy": {"policy_id": "fixture"},
                "steps": [],
                "lifecycle": {"leases": []},
                "health": "UNSEALED",
                "active_action": None,
            },
        }
        text = render_console(dashboard, csrf_token="csrf")
        self.assertNotIn("<script>", text)
        self.assertIn("&lt;script&gt;", text)
        self.assertNotIn("javascript:", text.lower())
        self.assertIn("Live authority: not granted", text)

        dashboard["detail"]["active_action"] = {
            "run_id": "run-20260731-043000-cdcdcd",
            "cancel_requested": False,
        }
        blocked_text = render_console(dashboard, csrf_token="csrf")
        self.assertIn("Another plan has a console-owned managed action", blocked_text)
        self.assertIn("not granted; another plan is active", blocked_text)
        self.assertNotIn("Cancel run", blocked_text)


class RunConsoleSecurityTests(unittest.TestCase):
    def test_host_is_exact(self) -> None:
        self.assertTrue(validate_host("127.0.0.1:8765", "127.0.0.1:8765"))
        self.assertFalse(validate_host("evil.example", "127.0.0.1:8765"))
        self.assertFalse(validate_host("127.0.0.1:9999", "127.0.0.1:8765"))

    def test_origin_or_referer_must_match(self) -> None:
        expected = "http://127.0.0.1:8765"
        self.assertTrue(validate_post_origin(expected, None, expected))
        self.assertTrue(validate_post_origin(None, expected + "/runs/x", expected))
        self.assertFalse(validate_post_origin(None, None, expected))
        self.assertFalse(
            validate_post_origin("https://evil.example", expected + "/", expected)
        )

    def test_csrf_requires_cookie_and_form_match(self) -> None:
        token = "known-token"
        jar = cookies.SimpleCookie()
        jar["lmre_csrf"] = token
        header = jar.output(header="").strip()
        self.assertTrue(validate_csrf(header, token, token))
        self.assertFalse(validate_csrf(header, "wrong", token))
        self.assertFalse(validate_csrf(None, token, token))

    def test_cli_parser_exposes_ui_without_path_or_port_options(self) -> None:
        args = build_parser().parse_args(["ui"])
        self.assertEqual(args.command, "ui")
        with self.assertRaises(SystemExit):
            build_parser().parse_args(["ui", "--port", "9000"])


if __name__ == "__main__":
    unittest.main()
