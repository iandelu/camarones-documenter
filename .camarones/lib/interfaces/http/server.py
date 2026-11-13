"""The Camarones portal server (stdlib, no Docker, no npm build).

Live mode (`camaron up`): people read the docs as they are right now, edit, confirm, comment and commit — the same
actions as the CLI, on the same files — and browse / rebuild the C4 explorer, the code graphs and the OpenWiki wikis.
Static mode (`up --static`): serves the read-only export (`portal`) exactly like nginx would.
Binds 127.0.0.1 only. Mutating calls need the X-Camarones header, which a cross-site page cannot send without a
CORS preflight this server never grants.

The portal is the team's viewer. Work that starts a process or calls a model (runs, wikis, builds, scans, CI files,
Ask's AI answer) belongs to the desktop app: it starts this server with CAMARONES_APP_TOKEN and sends the token on
each request (lib/interfaces/http/routes/app_cmd.py); without it those calls answer 403 with `"app": true`. With a
token set, a request whose Host is not this server is refused (a DNS-rebinding page would otherwise be same-origin).

This module is the transport: it reads a request into a `Request`, `router.dispatch` applies those rules and runs the
route, and the `Response` goes back as written here."""
from __future__ import annotations

import atexit, hmac, json, os, signal, sys, threading, time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from lib.common import kill_tree
from lib.interfaces.http import router
from lib.interfaces.http.messages import Request, Response
from lib.interfaces.http.routes import files
from lib.interfaces.http.routes.terminals import shutdown

STATIC = False
APP_GONE_GRACE = 10                          # seconds the normal stop has once the app is gone (watch_app)
APP_TOKEN = ""                               # set by the desktop app (CAMARONES_APP_TOKEN); empty: browser portal only
PORTAL_TOKEN = ""                            # set by `camaron up` (CAMARONES_PORTAL_TOKEN): lets this machine's browser write the board


def token_matches(got: str, want: str) -> bool:
    """Constant-time compare on bytes: a non-ASCII header makes compare_digest raise on str."""
    return hmac.compare_digest(got.encode("utf-8"), want.encode("utf-8"))


class Handler(BaseHTTPRequestHandler):
    server_version = "camarones"

    def log_message(self, fmt, *args):         # quiet: the server runs detached
        pass

    def reply(self, resp: Response) -> None:
        """Write a route's Response: an event stream after its headers (what it raises answers as dispatch maps it),
        anything else with its type and length."""
        if resp.stream is not None:
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            try:
                resp.stream(self.wfile)
            except Exception as e:  # noqa: BLE001
                self.reply(router.error_response("GET" if self.command in ("GET", "HEAD") else "POST", e))
            return
        self.send_response(resp.status)
        if resp.ctype is not None:
            self.send_header("Content-Type", resp.ctype)
            self.send_header("Content-Length", str(len(resp.body)))
        self.send_header("Cache-Control", "no-store")
        for k, v in resp.headers.items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD" and resp.body:
            self.wfile.write(resp.body)

    def answer(self, method: str, path: str, query: dict, raw: bytes = b"") -> None:
        req = Request(method, path, query, self.headers, raw=raw, is_app=self.is_app(), can_write=self.can_write(),
                      foreign=self.foreign_host(), marked=self.headers.get("X-Camarones") == "1", static=STATIC)
        self.reply(router.dispatch(req, files.static_site))

    def do_HEAD(self):
        self.do_GET()

    def is_app(self) -> bool:
        return bool(APP_TOKEN) and token_matches(self.headers.get("X-Camaron-Token", ""), APP_TOKEN)

    def can_write(self) -> bool:
        """The app, or a browser that got the portal token from `camaron up`. The portal token never unlocks an app
        route."""
        return self.is_app() or (bool(PORTAL_TOKEN) and token_matches(self.headers.get("X-Camaron-Token", ""), PORTAL_TOKEN))

    def foreign_host(self) -> bool:
        if not (APP_TOKEN or PORTAL_TOKEN):
            return False
        port = self.server.server_address[1]
        ok = {f"127.0.0.1:{port}", f"localhost:{port}"} | ({"127.0.0.1", "localhost"} if port == 80 else set())
        return self.headers.get("Host", "") not in ok          # on port 80 the browser leaves the port out

    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        q = {k: v[0] for k, v in urllib.parse.parse_qs(u.query).items()}
        self.answer("GET", urllib.parse.unquote(u.path), q)

    def do_PUT(self):
        self.do_POST()

    def do_POST(self):
        try:                    # read the body first: answering before it is read resets the connection on Windows
            raw = self.rfile.read(int(self.headers.get("Content-Length") or 0))
        except ValueError:
            raw = b""
        self.answer("POST", urllib.parse.urlparse(self.path).path, {}, raw)


def take_tokens() -> None:
    """Read this server's tokens and take them out of the environment, so no command, run or agent it starts inherits them."""
    global APP_TOKEN, PORTAL_TOKEN
    APP_TOKEN = os.environ.pop("CAMARONES_APP_TOKEN", "")
    PORTAL_TOKEN = os.environ.pop("CAMARONES_PORTAL_TOKEN", "")


def watch_app() -> None:
    """Stops this server when the app that started it is gone. A crash or a force-quit runs none of the app's code, so
    the app holds the other end of our stdin, the system closes it, and the read here returns. The stop is the app's own,
    what the server started included; one that hangs ends with the process after APP_GONE_GRACE s. What this server
    starts reads nothing from stdin, as before: nobody writes to this pipe, so a child inheriting it would wait for the
    app to end (`claude -p` reads its stdin)."""
    pipe = os.dup(0)
    nothing = os.open(os.devnull, os.O_RDONLY)
    os.dup2(nothing, 0)
    os.close(nothing)

    def wait() -> None:
        try:
            while os.read(pipe, 4096):
                pass
        except OSError:
            pass
        kill_tree(os.getpid())
        time.sleep(APP_GONE_GRACE)
        os._exit(1)
    threading.Thread(target=wait, daemon=True, name="app lifeline").start()


def run_server(port: int = 8080, static: bool = False) -> None:
    global STATIC
    STATIC = static
    take_tokens()
    if static and not (files.SITE / "index.html").exists():
        raise RuntimeError("the portal is not exported yet — run `camaron portal` first")
    httpd = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    atexit.register(shutdown)                   # no agent outlives its server: the app's stop, Ctrl+C, an error
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))       # how the app stops it on POSIX; SystemExit runs atexit
    if os.environ.pop("CAMARONES_LIFELINE", ""):
        watch_app()
    if APP_TOKEN:                            # the app reads the port (0 = any free one) from this first line
        print(json.dumps({"ready": True, "port": httpd.server_address[1]}), flush=True)
        sys.stdout.flush()
    try:
        httpd.serve_forever()
    finally:
        httpd.server_close()
