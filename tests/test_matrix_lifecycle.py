from __future__ import annotations

import socket
import signal
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from local_model_runtime_evaluation.matrix_lifecycle import (
    LifecycleError,
    ManagedProcess,
    interrupt_process_group,
    port_is_free,
    spawn_pinned,
    terminate_process_group,
    wait_port_free,
)


class MatrixLifecycleTests(unittest.TestCase):
    def test_spawn_and_stop_frees_port(self) -> None:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            try:
                probe.bind(("127.0.0.1", 0))
            except PermissionError:
                self.skipTest(
                    "sandbox does not permit binding an ephemeral loopback port"
                )
            port = probe.getsockname()[1]
        self.assertTrue(port_is_free(port))
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "server.log"
            code = (
                "import http.server, socketserver\n"
                "class H(http.server.BaseHTTPRequestHandler):\n"
                "    def log_message(self, *args): pass\n"
                "    def do_GET(self):\n"
                "        self.send_response(200)\n"
                "        self.end_headers()\n"
                "socketserver.TCPServer.allow_reuse_address = True\n"
                f"httpd = socketserver.TCPServer(('127.0.0.1', {port}), H)\n"
                "httpd.serve_forever()\n"
            )
            proc = spawn_pinned(("python3", "-c", code), log)
            deadline = time.time() + 10
            while time.time() < deadline and port_is_free(port):
                time.sleep(0.05)
            self.assertFalse(port_is_free(port))
            proc.stop(timeout_seconds=2)
            wait_port_free(port, timeout_seconds=5)
            self.assertTrue(port_is_free(port))

    def test_rejects_empty_command(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(LifecycleError):
                spawn_pinned((), Path(tmp) / "x.log")

    def test_signal_helpers_never_force_kill(self) -> None:
        with patch("os.killpg") as killpg:
            interrupt_process_group(321)
            terminate_process_group(321)
        self.assertEqual(
            killpg.call_args_list,
            [
                unittest.mock.call(321, signal.SIGINT),
                unittest.mock.call(321, signal.SIGTERM),
            ],
        )
        for call in killpg.call_args_list:
            self.assertNotEqual(call.args[1], signal.SIGKILL)

    def test_managed_process_stop_interrupts_then_terminates(self) -> None:
        child = MagicMock()
        child.poll.return_value = None
        child.wait.side_effect = [
            __import__("subprocess").TimeoutExpired(("server",), 1),
            0,
        ]
        process = ManagedProcess(
            pid=321,
            process_group_id=321,
            command=("server",),
            _child=child,
        )
        with patch("os.killpg") as killpg:
            process.stop(timeout_seconds=1)
        self.assertEqual(
            killpg.call_args_list,
            [
                unittest.mock.call(321, signal.SIGINT),
                unittest.mock.call(321, signal.SIGTERM),
            ],
        )

    def test_managed_process_stop_fails_without_force_kill(self) -> None:
        child = MagicMock()
        child.poll.return_value = None
        timeout = __import__("subprocess").TimeoutExpired(("server",), 1)
        child.wait.side_effect = [timeout, timeout]
        process = ManagedProcess(
            pid=321,
            process_group_id=321,
            command=("server",),
            _child=child,
        )
        with patch("os.killpg") as killpg:
            with self.assertRaises(LifecycleError):
                process.stop(timeout_seconds=1)
        self.assertNotIn(
            signal.SIGKILL,
            [call.args[1] for call in killpg.call_args_list],
        )


if __name__ == "__main__":
    unittest.main()
