"""Fixed-loopback HTTP boundary for the functional LMRE run console."""

from __future__ import annotations

import re
import secrets
from collections.abc import Callable
from http import cookies
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from .results_browser_html import render_run
from .run_console import (
    ACTION_RESUME,
    ACTION_START,
    ConsoleError,
    RunConsoleController,
)
from .run_console_html import render_console, render_console_error

CONSOLE_HOST = "127.0.0.1"
CONSOLE_PORT = 8765
MAX_FORM_BYTES = 16_384
_RUN_ROUTE = re.compile(
    r"/runs/(?P<run_id>run-[0-9]{8}-[0-9]{6}-[a-z0-9]{6})"
    r"(?:/(?P<action>report|start|resume|cancel))?"
)


def validate_host(observed: str | None, expected: str) -> bool:
    return observed == expected


def validate_post_origin(
    origin: str | None,
    referer: str | None,
    expected_origin: str,
) -> bool:
    if origin is not None:
        return origin == expected_origin
    if referer is None:
        return False
    return referer == expected_origin or referer.startswith(expected_origin + "/")


def validate_csrf(
    cookie_header: str | None,
    form_token: str | None,
    expected_token: str,
) -> bool:
    if cookie_header is None or form_token is None:
        return False
    jar = cookies.SimpleCookie()
    try:
        jar.load(cookie_header)
    except cookies.CookieError:
        return False
    morsel = jar.get("lmre_csrf")
    return (
        morsel is not None
        and secrets.compare_digest(morsel.value, expected_token)
        and secrets.compare_digest(form_token, expected_token)
    )


class RunConsoleServer(HTTPServer):
    controller: RunConsoleController
    csrf_token: str
    expected_host: str
    expected_origin: str


class RunConsoleHandler(BaseHTTPRequestHandler):
    server: RunConsoleServer

    def log_message(self, format: str, *args: object) -> None:
        del format, args

    def _headers(self, *, content_length: int, status: int = 200) -> None:
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(content_length))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Pragma", "no-cache")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'none'; style-src 'unsafe-inline'; "
            "form-action 'self'; frame-ancestors 'none'; base-uri 'none'",
        )
        self.send_header(
            "Set-Cookie",
            f"lmre_csrf={self.server.csrf_token}; Path=/; HttpOnly; SameSite=Strict",
        )
        self.end_headers()

    def _send_html(self, body: str, *, status: int = 200) -> None:
        encoded = body.encode("utf-8")
        self._headers(content_length=len(encoded), status=status)
        self.wfile.write(encoded)

    def _redirect(self, location: str) -> None:
        self.send_response(303)
        self.send_header("Location", location)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _fail(self, status: int, message: str) -> None:
        self._send_html(render_console_error(status, message), status=status)

    def _host_ok(self) -> bool:
        return validate_host(self.headers.get("Host"), self.server.expected_host)

    def _read_form(self) -> dict[str, str]:
        content_type = self.headers.get("Content-Type", "")
        if content_type.split(";", 1)[0].strip() != "application/x-www-form-urlencoded":
            raise ConsoleError("Unsupported form content type.", status=415)
        try:
            length = int(self.headers.get("Content-Length", ""))
        except ValueError as error:
            raise ConsoleError("Invalid form length.", status=400) from error
        if length < 0 or length > MAX_FORM_BYTES:
            raise ConsoleError("Form payload is too large.", status=413)
        try:
            raw = self.rfile.read(length).decode("utf-8")
        except UnicodeDecodeError as error:
            raise ConsoleError("Form payload is invalid.", status=400) from error
        parsed = parse_qs(raw, keep_blank_values=True, strict_parsing=True)
        if any(len(values) != 1 for values in parsed.values()):
            raise ConsoleError("Duplicate form fields are not accepted.", status=400)
        return {key: values[0] for key, values in parsed.items()}

    def _validate_post(self, form: dict[str, str]) -> None:
        if not self._host_ok():
            raise ConsoleError("Request host is not allowed.", status=403)
        if not validate_post_origin(
            self.headers.get("Origin"),
            self.headers.get("Referer"),
            self.server.expected_origin,
        ):
            raise ConsoleError("Cross-origin request was rejected.", status=403)
        if not validate_csrf(
            self.headers.get("Cookie"),
            form.get("csrf"),
            self.server.csrf_token,
        ):
            raise ConsoleError("Request verification failed.", status=403)

    def do_GET(self) -> None:
        if not self._host_ok():
            self._fail(403, "Request host is not allowed.")
            return
        path = urlsplit(self.path).path
        if path == "/":
            dashboard = self.server.controller.dashboard()
            self._send_html(
                render_console(dashboard, csrf_token=self.server.csrf_token)
            )
            return
        match = _RUN_ROUTE.fullmatch(path)
        if match is None:
            self._fail(404, "Console page was not found.")
            return
        run_id = match.group("run_id")
        action = match.group("action")
        try:
            dashboard = self.server.controller.dashboard(run_id)
        except ConsoleError as error:
            self._fail(error.status, str(error))
            return
        if action == "report":
            detail = dashboard["detail"]
            if detail is None:
                self._fail(404, "Managed run report was not found.")
                return
            self._send_html(render_run(detail))
            return
        if action is not None:
            self._fail(405, "Live actions require POST.")
            return
        self._send_html(render_console(dashboard, csrf_token=self.server.csrf_token))

    def do_POST(self) -> None:
        path = urlsplit(self.path).path
        match = _RUN_ROUTE.fullmatch(path)
        if match is None or match.group("action") not in (
            ACTION_START,
            ACTION_RESUME,
            "cancel",
        ):
            self._fail(404, "Console action was not found.")
            return
        run_id = match.group("run_id")
        action = str(match.group("action"))
        try:
            form = self._read_form()
            self._validate_post(form)
            if action == "cancel":
                self.server.controller.cancel(run_id)
            else:
                self.server.controller.start_action(
                    action=action,
                    run_id=run_id,
                    nonce=form.get("grant", ""),
                    confirmed_plan_hash=form.get("plan_hash", ""),
                    acknowledged=form.get("acknowledged") == "yes",
                )
        except (ConsoleError, ValueError) as error:
            status = error.status if isinstance(error, ConsoleError) else 400
            try:
                dashboard = self.server.controller.dashboard(run_id)
            except ConsoleError:
                self._fail(status, str(error))
                return
            self._send_html(
                render_console(
                    dashboard,
                    csrf_token=self.server.csrf_token,
                    error=str(error),
                ),
                status=status,
            )
            return
        self._redirect(f"/runs/{run_id}")


def make_console_server(
    controller: RunConsoleController,
    *,
    host: str = CONSOLE_HOST,
    port: int = CONSOLE_PORT,
) -> RunConsoleServer:
    if host != CONSOLE_HOST or port != CONSOLE_PORT:
        raise ValueError("run console address is fixed to 127.0.0.1:8765")
    server = RunConsoleServer((host, port), RunConsoleHandler)
    server.controller = controller
    server.csrf_token = secrets.token_urlsafe(32)
    server.expected_host = f"{host}:{port}"
    server.expected_origin = f"http://{host}:{port}"
    return server


def serve_console(
    *,
    results_root: Path,
    state_root: Path,
    on_ready: Callable[[str], None] | None = None,
) -> None:
    controller = RunConsoleController(results_root, state_root)
    server = make_console_server(controller)
    origin = server.expected_origin
    if on_ready is not None:
        on_ready(origin)
    try:
        server.serve_forever(poll_interval=0.25)
    except KeyboardInterrupt:
        pass
    finally:
        controller.shutdown()
        server.server_close()
