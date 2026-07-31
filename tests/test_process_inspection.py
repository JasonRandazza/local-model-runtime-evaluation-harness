from __future__ import annotations

import subprocess
import unittest

from local_model_runtime_evaluation.process_inspection import (
    ProcessIdentity,
    ProcessInspectionError,
    ProcessInspector,
)


class FakeRunner:
    def __init__(
        self,
        outputs: dict[tuple[str, ...], tuple[int, str, str] | str],
    ) -> None:
        self.outputs = outputs
        self.calls: list[tuple[str, ...]] = []

    def __call__(
        self,
        command: tuple[str, ...],
    ) -> subprocess.CompletedProcess[str]:
        self.calls.append(command)
        result = self.outputs[command]
        if isinstance(result, str):
            return subprocess.CompletedProcess(command, 0, result, "")
        return subprocess.CompletedProcess(
            command,
            result[0],
            result[1],
            result[2],
        )


def _outputs(
    *,
    listener: str = "p321\nn127.0.0.1:8100\n",
    executable: str = "n/Users/test/.venv/bin/python3.11\n",
    ppid: str = "100\n",
    started: str = "Thu Jul 30 18:00:00 2026\n",
    command: str = "omlx-server --host 127.0.0.1 --port 8100\n",
) -> dict[tuple[str, ...], str]:
    return {
        (
            "/usr/sbin/lsof",
            "-nP",
            "-iTCP:8100",
            "-sTCP:LISTEN",
            "-Fpn",
        ): listener,
        (
            "/usr/sbin/lsof",
            "-a",
            "-p",
            "321",
            "-d",
            "txt",
            "-Fn",
        ): executable,
        ("/bin/ps", "-p", "321", "-o", "ppid="): ppid,
        ("/bin/ps", "-p", "321", "-o", "lstart="): started,
        ("/bin/ps", "-p", "321", "-o", "command="): command,
    }


class ProcessInspectionTests(unittest.TestCase):
    def test_inspect_listener_builds_exact_identity(self) -> None:
        runner = FakeRunner(_outputs())
        identity = ProcessInspector(runner=runner).inspect_listener(
            "127.0.0.1",
            8100,
        )
        self.assertIsNotNone(identity)
        assert identity is not None
        self.assertEqual(identity.pid, 321)
        self.assertEqual(identity.ppid, 100)
        self.assertEqual(
            identity.executable,
            "/Users/test/.venv/bin/python3.11",
        )
        self.assertEqual(identity.argv[-2:], ("--port", "8100"))
        self.assertEqual(identity.listener_host, "127.0.0.1")
        self.assertEqual(identity.listener_port, 8100)

    def test_no_listener_returns_none(self) -> None:
        command = (
            "/usr/sbin/lsof",
            "-nP",
            "-iTCP:8100",
            "-sTCP:LISTEN",
            "-Fpn",
        )
        inspector = ProcessInspector(
            runner=FakeRunner({command: (1, "", "")})
        )
        self.assertIsNone(inspector.inspect_listener("127.0.0.1", 8100))

    def test_wildcard_listener_fails_closed(self) -> None:
        runner = FakeRunner(_outputs(listener="p321\nn*:8100\n"))
        with self.assertRaises(ProcessInspectionError) as context:
            ProcessInspector(runner=runner).inspect_listener(
                "127.0.0.1",
                8100,
            )
        self.assertEqual(
            context.exception.code,
            "runtime_listener_not_loopback",
        )

    def test_multiple_listener_processes_fail_closed(self) -> None:
        runner = FakeRunner(
            _outputs(
                listener=(
                    "p321\nn127.0.0.1:8100\n"
                    "p654\nn127.0.0.1:8100\n"
                )
            )
        )
        with self.assertRaises(ProcessInspectionError) as context:
            ProcessInspector(runner=runner).inspect_listener(
                "127.0.0.1",
                8100,
            )
        self.assertEqual(
            context.exception.code,
            "runtime_process_ambiguous",
        )

    def test_missing_absolute_executable_fails_closed(self) -> None:
        runner = FakeRunner(_outputs(executable="nomlx-server\n"))
        with self.assertRaises(ProcessInspectionError):
            ProcessInspector(runner=runner).inspect_listener(
                "127.0.0.1",
                8100,
            )

    def test_unparseable_command_fails_closed(self) -> None:
        runner = FakeRunner(_outputs(command="omlx-server 'unterminated\n"))
        with self.assertRaises(ProcessInspectionError):
            ProcessInspector(runner=runner).inspect_listener(
                "127.0.0.1",
                8100,
            )

    def test_still_matches_compares_complete_fingerprint(self) -> None:
        expected = ProcessIdentity(
            pid=321,
            ppid=100,
            executable="/Users/test/.venv/bin/python3.11",
            argv=(
                "omlx-server",
                "--host",
                "127.0.0.1",
                "--port",
                "8100",
            ),
            started_at="Thu Jul 30 18:00:00 2026",
            listener_host="127.0.0.1",
            listener_port=8100,
        )
        self.assertTrue(
            ProcessInspector(runner=FakeRunner(_outputs())).still_matches(
                expected
            )
        )
        changed = _outputs(started="Thu Jul 30 18:01:00 2026\n")
        self.assertFalse(
            ProcessInspector(runner=FakeRunner(changed)).still_matches(
                expected
            )
        )

    def test_rejects_non_loopback_request_before_command(self) -> None:
        runner = FakeRunner({})
        with self.assertRaises(ProcessInspectionError) as context:
            ProcessInspector(runner=runner).inspect_listener(
                "0.0.0.0",
                8100,
            )
        self.assertEqual(
            context.exception.code,
            "runtime_listener_not_loopback",
        )
        self.assertEqual(runner.calls, [])


if __name__ == "__main__":
    unittest.main()
