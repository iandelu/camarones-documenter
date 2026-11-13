"""A real project server on port 0 for HTTP-level tests, and a request helper that keeps the status, the headers and
the raw body (redirects are not followed, so a 301 stays a 301)."""
from __future__ import annotations

import contextlib
import importlib
import threading
import urllib.error
import urllib.request
from collections.abc import Iterator
from http.server import ThreadingHTTPServer

SERVER = "lib.serve"                # the module that holds the server's tokens and its static mode
APP_TOKEN = "app-token"
PORTAL_TOKEN = "portal-token"


def arm(mp, *, static: bool = False) -> None:
    """Both tokens set (so the Host check is on) and the static mode as asked, on the server module."""
    mod = importlib.import_module(SERVER)
    mp.setattr(mod, "APP_TOKEN", APP_TOKEN)
    mp.setattr(mod, "PORTAL_TOKEN", PORTAL_TOKEN)
    mp.setattr(mod, "STATIC", static)


@contextlib.contextmanager
def serving(handler_cls) -> Iterator[str]:
    srv = ThreadingHTTPServer(("127.0.0.1", 0), handler_cls)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        yield f"http://127.0.0.1:{srv.server_address[1]}"
    finally:
        srv.shutdown()
        srv.server_close()


class _Stay(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


_OPENER = urllib.request.build_opener(_Stay)


def request(base: str, method: str, path: str, body: bytes | None = None, token: str | None = None, *,
            marked: bool = True, host: str | None = None) -> tuple[int, dict[str, str], bytes]:
    headers = {"Content-Type": "application/json"}
    if marked:
        headers["X-Camarones"] = "1"
    if token:
        headers["X-Camaron-Token"] = token
    if host:
        headers["Host"] = host
    req = urllib.request.Request(base + path, data=body if method in ("POST", "PUT") else None, headers=headers,
                                 method=method)
    try:
        resp = _OPENER.open(req, timeout=20)
    except urllib.error.HTTPError as e:
        with e:
            return e.code, {k.lower(): v for k, v in e.headers.items()}, e.read()
    with resp:
        return resp.status, {k.lower(): v for k, v in resp.headers.items()}, resp.read()
