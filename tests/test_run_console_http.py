"""HTTP-boundary tests for the run console, driven over a real loopback socket.

tests/test_run_console.py covers the controller and calls the header validators
directly. That leaves the boundary itself unproven: nothing there shows the
handler actually invokes those validators, in the right order, before reaching
the controller. These tests drive the real `RunConsoleHandler` through
`http.client` so a regression that skipped a check would fail here.

The server is bound to an ephemeral port. `make_console_server` pins the real
address to 127.0.0.1:8765 and that guard is asserted separately below; binding
the fixed port here would make the suite fail whenever a console is running.

Non-live: fake child processes only. No runtime, provider, credential, or model
is contacted, and no managed run is started.
"""

from __future__ import annotations

import http.client
import signal
import threading
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import urlencode

from local_model_runtime_evaluation.run_console import (
    ACTION_START,
    RunConsoleController,
)
from local_model_runtime_evaluation.run_console_server import (
    CONSOLE_HOST,
    CONSOLE_PORT,
    MAX_FORM_BYTES,
    RunConsoleHandler,
    RunConsoleServer,
    make_console_server,
)
from tests.results_browser_fixtures import make_pending_plan, make_sealed_pass
from tests.test_run_console import FakeFactory

CSRF_TOKEN = "test-csrf-token-value"
FORM_TYPE = "application/x-www-form-urlencoded"


class _ConsoleHarness:
    """A running console plus the request helpers the tests need."""

    def __init__(self, root: Path) -> None:
        self.factory = FakeFactory()
        self.controller = RunConsoleController(
            root / "results",
            root / ".lmre",
            process_factory=self.factory,
        )
        self.server = RunConsoleServer((CONSOLE_HOST, 0), RunConsoleHandler)
        self.server.controller = self.controller
        self.server.csrf_token = CSRF_TOKEN
        self.port = self.server.server_address[1]
        self.server.expected_host = f"{CONSOLE_HOST}:{self.port}"
        self.server.expected_origin = f"http://{CONSOLE_HOST}:{self.port}"
        self.thread = threading.Thread(
            target=self.server.serve_forever,
            kwargs={"poll_interval": 0.01},
            daemon=True,
        )
        self.thread.start()

    def close(self) -> None:
        self.server.shutdown()
        self.thread.join(timeout=10)
        self.server.server_close()

    @property
    def origin(self) -> str:
        return self.server.expected_origin

    def request(
        self,
        method: str,
        path: str,
        *,
        body: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> tuple[int, dict[str, str], str]:
        connection = http.client.HTTPConnection(CONSOLE_HOST, self.port, timeout=10)
        try:
            connection.request(method, path, body=body, headers=headers or {})
            response = connection.getresponse()
            payload = response.read().decode("utf-8", errors="replace")
            return response.status, dict(response.getheaders()), payload
        finally:
            connection.close()

    def post(
        self,
        path: str,
        fields: dict[str, str],
        *,
        host: str | None = None,
        origin: str | None = "",
        referer: str | None = None,
        cookie: str | None = "",
        content_type: str = FORM_TYPE,
    ) -> tuple[int, dict[str, str], str]:
        """POST with each header individually overridable to isolate one check."""
        body = urlencode(fields)
        headers = {"Content-Type": content_type, "Content-Length": str(len(body))}
        headers["Host"] = self.server.expected_host if host is None else host
        if origin == "":
            headers["Origin"] = self.origin
        elif origin is not None:
            headers["Origin"] = origin
        if referer is not None:
            headers["Referer"] = referer
        if cookie == "":
            headers["Cookie"] = f"lmre_csrf={CSRF_TOKEN}"
        elif cookie is not None:
            headers["Cookie"] = cookie
        return self.request("POST", path, body=body, headers=headers)

    def live_grant(self, run_id: str) -> tuple[str, str]:
        """Issue a start grant the way rendering the page does."""
        dashboard = self.controller.dashboard(run_id)
        return (
            str(dashboard["grants"][ACTION_START]),
            str(dashboard["detail"]["identity"]["plan_hash"]),
        )


class RunConsoleHttpTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.harness = _ConsoleHarness(self.root)
        self.addCleanup(self.harness.close)
        self.addCleanup(self.temporary.cleanup)

    def _pending_run(self) -> str:
        return make_pending_plan(self.root).name

    def _start_fields(self, run_id: str, **overrides: str) -> dict[str, str]:
        grant, plan_hash = self.harness.live_grant(run_id)
        fields = {
            "csrf": CSRF_TOKEN,
            "grant": grant,
            "plan_hash": plan_hash,
            "acknowledged": "yes",
        }
        fields.update(overrides)
        return fields

    # -- reads --

    def test_index_renders_with_restrictive_headers(self) -> None:
        status, headers, body = self.harness.request(
            "GET", "/", headers={"Host": self.harness.server.expected_host}
        )
        self.assertEqual(status, 200)
        self.assertIn("no-store", headers["Cache-Control"])
        self.assertEqual(headers["X-Content-Type-Options"], "nosniff")
        self.assertIn("frame-ancestors 'none'", headers["Content-Security-Policy"])
        self.assertIn("form-action 'self'", headers["Content-Security-Policy"])
        self.assertIn("default-src 'none'", headers["Content-Security-Policy"])
        self.assertIn("HttpOnly", headers["Set-Cookie"])
        self.assertIn("SameSite=Strict", headers["Set-Cookie"])
        self.assertNotIn("<script", body.lower())

    def test_get_with_foreign_host_is_refused(self) -> None:
        status, _headers, _body = self.harness.request(
            "GET", "/", headers={"Host": "evil.example"}
        )
        self.assertEqual(status, 403)

    def test_unknown_path_is_not_found(self) -> None:
        status, _headers, _body = self.harness.request(
            "GET", "/etc/passwd", headers={"Host": self.harness.server.expected_host}
        )
        self.assertEqual(status, 404)

    def test_get_cannot_mutate(self) -> None:
        run_id = self._pending_run()
        for action in ("start", "resume", "cancel"):
            with self.subTest(action=action):
                status, _headers, _body = self.harness.request(
                    "GET",
                    f"/runs/{run_id}/{action}",
                    headers={"Host": self.harness.server.expected_host},
                )
                self.assertEqual(status, 405)
        self.assertEqual(self.harness.factory.arguments, [])

    # -- write gating --

    def test_post_with_foreign_host_is_refused_before_the_controller(self) -> None:
        run_id = self._pending_run()
        status, _headers, _body = self.harness.post(
            f"/runs/{run_id}/start",
            self._start_fields(run_id),
            host="evil.example",
        )
        self.assertEqual(status, 403)
        self.assertEqual(self.harness.factory.arguments, [])

    def test_post_without_origin_or_referer_is_refused(self) -> None:
        run_id = self._pending_run()
        status, _headers, _body = self.harness.post(
            f"/runs/{run_id}/start",
            self._start_fields(run_id),
            origin=None,
        )
        self.assertEqual(status, 403)
        self.assertEqual(self.harness.factory.arguments, [])

    def test_post_with_foreign_origin_is_refused(self) -> None:
        run_id = self._pending_run()
        status, _headers, _body = self.harness.post(
            f"/runs/{run_id}/start",
            self._start_fields(run_id),
            origin="http://evil.example",
        )
        self.assertEqual(status, 403)
        self.assertEqual(self.harness.factory.arguments, [])

    def test_post_with_foreign_referer_and_no_origin_is_refused(self) -> None:
        run_id = self._pending_run()
        status, _headers, _body = self.harness.post(
            f"/runs/{run_id}/start",
            self._start_fields(run_id),
            origin=None,
            referer="http://evil.example/runs",
        )
        self.assertEqual(status, 403)
        self.assertEqual(self.harness.factory.arguments, [])

    def test_post_without_csrf_cookie_is_refused(self) -> None:
        run_id = self._pending_run()
        status, _headers, _body = self.harness.post(
            f"/runs/{run_id}/start",
            self._start_fields(run_id),
            cookie=None,
        )
        self.assertEqual(status, 403)
        self.assertEqual(self.harness.factory.arguments, [])

    def test_post_with_mismatched_csrf_form_token_is_refused(self) -> None:
        run_id = self._pending_run()
        status, _headers, _body = self.harness.post(
            f"/runs/{run_id}/start",
            self._start_fields(run_id, csrf="not-the-token"),
        )
        self.assertEqual(status, 403)
        self.assertEqual(self.harness.factory.arguments, [])

    def test_post_with_mismatched_csrf_cookie_is_refused(self) -> None:
        run_id = self._pending_run()
        status, _headers, _body = self.harness.post(
            f"/runs/{run_id}/start",
            self._start_fields(run_id),
            cookie="lmre_csrf=not-the-token",
        )
        self.assertEqual(status, 403)
        self.assertEqual(self.harness.factory.arguments, [])

    def test_host_is_checked_before_csrf(self) -> None:
        # Both are wrong. The host check must reject first, so a DNS-rebinding
        # attempt is refused without the handler consulting session state.
        run_id = self._pending_run()
        status, _headers, body = self.harness.post(
            f"/runs/{run_id}/start",
            self._start_fields(run_id, csrf="not-the-token"),
            host="evil.example",
        )
        self.assertEqual(status, 403)
        self.assertIn("host", body.lower())
        self.assertEqual(self.harness.factory.arguments, [])

    def test_unsupported_content_type_is_refused(self) -> None:
        run_id = self._pending_run()
        status, _headers, _body = self.harness.post(
            f"/runs/{run_id}/start",
            self._start_fields(run_id),
            content_type="application/json",
        )
        self.assertEqual(status, 415)
        self.assertEqual(self.harness.factory.arguments, [])

    def test_oversized_form_is_refused(self) -> None:
        run_id = self._pending_run()
        body = urlencode({"csrf": CSRF_TOKEN, "pad": "x" * (MAX_FORM_BYTES + 1)})
        status, _headers, _body = self.harness.request(
            "POST",
            f"/runs/{run_id}/start",
            body=body,
            headers={
                "Host": self.harness.server.expected_host,
                "Origin": self.harness.origin,
                "Cookie": f"lmre_csrf={CSRF_TOKEN}",
                "Content-Type": FORM_TYPE,
                "Content-Length": str(len(body)),
            },
        )
        self.assertEqual(status, 413)
        self.assertEqual(self.harness.factory.arguments, [])

    def test_post_to_unknown_action_is_not_found(self) -> None:
        run_id = self._pending_run()
        status, _headers, _body = self.harness.post(
            f"/runs/{run_id}/destroy", {"csrf": CSRF_TOKEN}
        )
        self.assertEqual(status, 404)
        self.assertEqual(self.harness.factory.arguments, [])

    def test_post_to_malformed_run_id_is_not_found(self) -> None:
        status, _headers, _body = self.harness.post(
            "/runs/../../etc/start", {"csrf": CSRF_TOKEN}
        )
        self.assertEqual(status, 404)
        self.assertEqual(self.harness.factory.arguments, [])

    # -- the one path that is allowed to start work --

    def test_fully_valid_start_reaches_the_controller_exactly_once(self) -> None:
        run_id = self._pending_run()
        status, headers, _body = self.harness.post(
            f"/runs/{run_id}/start", self._start_fields(run_id)
        )
        self.assertEqual(status, 303)
        self.assertEqual(headers["Location"], f"/runs/{run_id}")
        self.assertEqual(len(self.harness.factory.arguments), 1)
        argv = self.harness.factory.arguments[0]
        self.assertIn("local_model_runtime_evaluation.managed_run_cli", argv)
        self.assertEqual(argv[-2:], ["start", run_id])

    def test_referer_is_accepted_when_origin_is_absent(self) -> None:
        run_id = self._pending_run()
        status, _headers, _body = self.harness.post(
            f"/runs/{run_id}/start",
            self._start_fields(run_id),
            origin=None,
            referer=f"{self.harness.origin}/runs/{run_id}",
        )
        self.assertEqual(status, 303)
        self.assertEqual(len(self.harness.factory.arguments), 1)

    def test_missing_acknowledgement_starts_nothing(self) -> None:
        run_id = self._pending_run()
        fields = self._start_fields(run_id)
        del fields["acknowledged"]
        status, _headers, _body = self.harness.post(f"/runs/{run_id}/start", fields)
        self.assertEqual(status, 400)
        self.assertEqual(self.harness.factory.arguments, [])

    def test_wrong_plan_hash_starts_nothing(self) -> None:
        run_id = self._pending_run()
        status, _headers, _body = self.harness.post(
            f"/runs/{run_id}/start",
            self._start_fields(run_id, plan_hash="0" * 64),
        )
        self.assertEqual(status, 403)
        self.assertEqual(self.harness.factory.arguments, [])

    def test_replayed_grant_starts_only_one_child(self) -> None:
        run_id = self._pending_run()
        fields = self._start_fields(run_id)
        first, _headers, _body = self.harness.post(f"/runs/{run_id}/start", fields)
        second, _headers2, _body2 = self.harness.post(f"/runs/{run_id}/start", fields)
        self.assertEqual(first, 303)
        self.assertNotEqual(second, 303)
        self.assertEqual(len(self.harness.factory.arguments), 1)

    def test_sealed_run_cannot_be_started_over_http(self) -> None:
        run_dir = make_sealed_pass(self.root)
        status, _headers, _body = self.harness.post(
            f"/runs/{run_dir.name}/start",
            {
                "csrf": CSRF_TOKEN,
                "grant": "forged-grant",
                "plan_hash": "0" * 64,
                "acknowledged": "yes",
            },
        )
        self.assertEqual(status, 403)
        self.assertEqual(self.harness.factory.arguments, [])

    def test_cancel_signals_the_exact_child(self) -> None:
        run_id = self._pending_run()
        self.harness.post(f"/runs/{run_id}/start", self._start_fields(run_id))
        status, _headers, _body = self.harness.post(
            f"/runs/{run_id}/cancel", {"csrf": CSRF_TOKEN}
        )
        self.assertEqual(status, 303)
        process = self.harness.factory.processes[0]
        self.assertEqual(process.signals, [signal.SIGINT])

    def test_cancel_requires_csrf(self) -> None:
        run_id = self._pending_run()
        self.harness.post(f"/runs/{run_id}/start", self._start_fields(run_id))
        status, _headers, _body = self.harness.post(
            f"/runs/{run_id}/cancel", {"csrf": "not-the-token"}
        )
        self.assertEqual(status, 403)
        self.assertEqual(self.harness.factory.processes[0].signals, [])


class FixedAddressTests(unittest.TestCase):
    """The real console address is not configurable."""

    def _controller(self, root: Path) -> RunConsoleController:
        return RunConsoleController(
            root / "results", root / ".lmre", process_factory=FakeFactory()
        )

    def test_alternate_host_is_refused(self) -> None:
        with TemporaryDirectory() as tmp, self.assertRaises(ValueError):
            make_console_server(
                self._controller(Path(tmp)), host="0.0.0.0", port=CONSOLE_PORT
            )

    def test_alternate_port_is_refused(self) -> None:
        with TemporaryDirectory() as tmp, self.assertRaises(ValueError):
            make_console_server(
                self._controller(Path(tmp)), host=CONSOLE_HOST, port=9000
            )

    def test_default_address_is_the_fixed_loopback(self) -> None:
        self.assertEqual(CONSOLE_HOST, "127.0.0.1")
        self.assertEqual(CONSOLE_PORT, 8765)


if __name__ == "__main__":
    unittest.main()
