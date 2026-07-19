from __future__ import annotations

import socket
import tempfile
import time
import unittest
from pathlib import Path

from local_model_runtime_evaluation.matrix_lifecycle import (
    LifecycleError,
    port_is_free,
    spawn_pinned,
    wait_port_free,
)


class MatrixLifecycleTests(unittest.TestCase):
    def test_spawn_and_stop_frees_port(self) -> None:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            probe.bind(("127.0.0.1", 0))
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


if __name__ == "__main__":
    unittest.main()
