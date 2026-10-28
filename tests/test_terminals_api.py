"""The terminals over HTTP (lib/serve.py): app token only, and one server-sent stream for every terminal."""
from __future__ import annotations

import base64, json, os, signal, subprocess, sys, threading, urllib.error, urllib.request
from http.server import ThreadingHTTPServer
from types import SimpleNamespace

import pytest

from test_agents import ready_agent_unit, term  # noqa: F401  (fixture)
from test_terminals import ECHO, until

TOKEN, PORTAL = "app-tok", "portal-tok"
ROUTES = [("GET", "/api/app/terminals"), ("GET", "/api/app/terminals/stream"), ("POST", "/api/app/terminals"),
          ("POST", "/api/app/terminals/t-x-1/input"), ("POST", "/api/app/terminals/t-x-1/resize"),
          ("POST", "/api/app/terminals/t-x-1/close")]


@pytest.fixture
def app(wired, term, monkeypatch):                                       # noqa: F811
    from lib import terminals
    from lib.adapters.runners.claude import Claude
    from lib.harness.ports import Invocation
    monkeypatch.setattr(Claude, "build", lambda self, req: Invocation([sys.executable, str(ECHO)], req.cwd, req.env))
    monkeypatch.setattr(wired.serve, "APP_TOKEN", TOKEN)
    monkeypatch.setattr(wired.serve, "PORTAL_TOKEN", PORTAL)
    srv = ThreadingHTTPServer(("127.0.0.1", 0), wired.serve.Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield SimpleNamespace(url=f"http://127.0.0.1:{srv.server_address[1]}", term=term, t=terminals)
    srv.shutdown()
    terminals.shutdown()


def call(url, body=None, token=TOKEN) -> tuple[int, dict]:
    """As `call` in tests/test_machine.py: GET without a body, POST with one, X-Camarones always."""
    req = urllib.request.Request(url, data=None if body is None else json.dumps(body).encode(),
                                 method="GET" if body is None else "POST",
                                 headers={"Content-Type": "application/json", "X-Camarones": "1",
                                          **({"X-Camaron-Token": token} if token else {})})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


def sse(url, until_, timeout=20) -> list[tuple[str, dict]]:
    """The stream's messages as (id, data), read line by line with the app token, until `until_(messages)` holds;
    AssertionError when the stream ends first. `timeout` is the socket's: the stream sends a keep-alive every 15 s."""
    req = urllib.request.Request(url, headers={"X-Camarones": "1", "X-Camaron-Token": TOKEN})
    msgs, ident, data = [], "", []
    with urllib.request.urlopen(req, timeout=timeout) as r:
        for raw in r:
            line = raw.decode("utf-8").rstrip("\r\n")
            if line.startswith("id: "):
                ident = line[4:]
            elif line.startswith("data: "):
                data.append(line[6:])
            elif not line and data:
                msgs.append((ident, json.loads("\n".join(data))))
                ident, data = "", []
                if until_(msgs):
                    return msgs
    raise AssertionError(f"the stream ended first, after {len(msgs)} messages")


def out(msgs, tid) -> bytes:
    return b"".join(base64.b64decode(d["d"]) for _, d in msgs if d["t"] == tid and "d" in d)


def open_unit(app, wired, **extra):
    u = ready_agent_unit(wired)
    code, r = call(app.url + "/api/app/terminals", {"unit": u["id"], "agent": "claude", **extra})
    assert code == 200, r
    return u, r


@pytest.mark.parametrize("method,path", ROUTES)
def test_terminals_answer_only_the_app(app, method, path):
    for token in (None, PORTAL):
        assert call(app.url + path, {} if method == "POST" else None, token=token)[0] == 403


def test_a_unit_opens_on_the_canvas_and_answers_through_the_stream(app, wired):
    u, r = open_unit(app, wired, cols=90, rows=30)
    tid = r["terminal"]["id"]
    assert r["where"] == "canvas" and app.term["cmds"] == []
    assert call(f"{app.url}/api/app/terminals/{tid}/input", {"data": "hola\r"}) == (200, {"ok": True})
    msgs = sse(app.url + "/api/app/terminals/stream", lambda m: b"echo hola (4)" in out(m, tid))
    assert all(i == f"{d['t']}:{d['o']}" for i, d in msgs if "d" in d)
    assert call(app.url + "/api/app/terminals")[1]["terminals"][0]["id"] == tid
    row = next(x for x in call(app.url + "/api/pipeline")[1]["units"] if x["id"] == u["id"])
    assert row["terminal"] == tid and row["session"]["live"] is True


def test_the_stream_replays_each_terminal_from_its_offset_in_base64(app, wired):
    _, r = call(app.url + "/api/app/terminals", {"unit": "update", "agent": "claude"})
    tid = r["terminal"]["id"]
    call(f"{app.url}/api/app/terminals/{tid}/input", {"data": "accents\r"})
    until(lambda: "año".encode() in app.t.read(tid, 0)[0])
    data, end = app.t.read(tid, 0)
    cut = data.index("ñ".encode()) + 1                                  # inside the ñ
    msgs = sse(f"{app.url}/api/app/terminals/stream?from={tid}:{cut}", lambda m: out(m, tid).endswith(data[-8:]))
    assert out(msgs, tid)[: end - cut] == data[cut:]


def test_a_terminal_opened_while_streaming_joins_the_stream(app, wired):
    got = {}
    threading.Thread(target=lambda: got.setdefault("m", sse(app.url + "/api/app/terminals/stream",
                                                            lambda m: any(d["t"].startswith("t-update-") for _, d in m))),
                     daemon=True).start()
    call(app.url + "/api/app/terminals", {"unit": "update", "agent": "claude"})
    until(lambda: "m" in got)


def test_a_long_replay_comes_in_pieces_of_64_kb_at_most(app, wired):
    _, r = call(app.url + "/api/app/terminals", {"unit": "update", "agent": "claude"})
    tid = r["terminal"]["id"]
    call(f"{app.url}/api/app/terminals/{tid}/input", {"data": "bytes 200000\r"})
    until(lambda: app.t.read(tid, 0)[0].count(b"x") >= 200000)
    data, end = app.t.read(tid, 0)
    msgs = sse(app.url + "/api/app/terminals/stream", lambda m: len(out(m, tid)) >= end)
    assert out(msgs, tid)[:end] == data
    assert max(len(base64.b64decode(d["d"])) for _, d in msgs if d["t"] == tid and "d" in d) <= 64 * 1024


def test_a_stream_ends_once_its_client_goes(app, wired, monkeypatch):
    monkeypatch.setattr(wired.serve, "KEEP_ALIVE", 0.2)
    gone, stream = threading.Event(), wired.serve.Handler.stream_terminals
    monkeypatch.setattr(wired.serve.Handler, "stream_terminals", lambda self, q: (stream(self, q), gone.set()))
    req = urllib.request.Request(app.url + "/api/app/terminals/stream", headers={"X-Camarones": "1",
                                                                                 "X-Camaron-Token": TOKEN})
    with urllib.request.urlopen(req, timeout=20) as r:
        assert r.readline() == b": keep-alive\n"           # nothing to send: it writes anyway, to find out
    until(gone.is_set)


def test_an_ended_terminal_says_its_code_after_its_last_bytes(app, wired):
    _, r = call(app.url + "/api/app/terminals", {"unit": "update", "agent": "claude"})
    tid = r["terminal"]["id"]
    call(f"{app.url}/api/app/terminals/{tid}/input", {"data": "exit\r"})
    msgs = sse(app.url + "/api/app/terminals/stream", lambda m: any(d.get("end") is not None for _, d in m))
    mine = [d for _, d in msgs if d["t"] == tid]
    assert mine[-1]["end"] == 3 and all("d" in d for d in mine[:-1])
    assert call(f"{app.url}/api/app/terminals/{tid}/input", {"data": "x"})[0] == 409


# A terminal the person closed is never shown again: the stream says where it ended, so the app keeps its offset,
# and replays none of it (no screen to parse it into on every canvas mount).
def test_a_closed_terminal_streams_its_end_and_none_of_its_bytes(app, wired):
    _, r = call(app.url + "/api/app/terminals", {"unit": "update", "agent": "claude"})
    tid = r["terminal"]["id"]
    until(lambda: b"ready" in app.t.read(tid, 0)[0])
    call(f"{app.url}/api/app/terminals/{tid}/close", {})
    until(lambda: app.t.get(tid)["ended"])
    msgs = sse(app.url + "/api/app/terminals/stream", lambda m: any(d["t"] == tid and "end" in d for _, d in m))
    assert [d for _, d in msgs if d["t"] == tid] == [{"t": tid, "end": app.t.get(tid)["code"], "o": app.t.read(tid, 0)[1]}]


def test_bad_input_is_a_400_and_an_unknown_terminal_a_404(app, wired):
    _, r = call(app.url + "/api/app/terminals", {"unit": "update", "agent": "claude"})
    tid = r["terminal"]["id"]
    for path, body in [("resize", {"cols": 9, "rows": 30}), ("resize", {"cols": True, "rows": 30}),
                       ("input", {"data": 5}), ("input", {"data": "y" * (256 * 1024 + 1)})]:
        assert call(f"{app.url}/api/app/terminals/{tid}/{path}", body)[0] == 400
    assert call(app.url + "/api/app/terminals", {"unit": "update", "agent": "claude", "rows": "x"})[0] == 400
    assert call(app.url + "/api/app/terminals/t-nope-1/input", {"data": "x"})[0] == 404
    assert call(app.url + "/api/app/terminals/stream?from=garbage")[0] == 400


def test_opening_twice_or_a_ninth_is_a_409_that_says_why(app, wired, monkeypatch):
    u, r = open_unit(app, wired)
    code, body = call(app.url + "/api/app/terminals", {"unit": u["id"], "agent": "claude"})
    assert code == 409 and body["terminal"] == r["terminal"]["id"]
    monkeypatch.setattr(app.t, "MAX_LIVE", 1)
    code, body = call(app.url + "/api/app/terminals", {"unit": "update", "agent": "claude"})
    assert code == 409 and body["limit"] == 1


def test_with_the_window_setting_it_opens_a_window_and_the_old_route_too(app, wired):
    from lib import machine
    machine.set_setting("sessions", "window")
    code, r = call(app.url + "/api/app/agent", {"unit": "update", "agent": "claude"})
    assert code == 200 and r["where"] == "window" and len(app.term["cmds"]) == 1 and app.t.listing() == []


@pytest.mark.skipif(sys.platform == "win32", reason="the app stops the server with taskkill /T /F, which takes the tree")
def test_the_servers_exit_takes_its_terminals_with_it(wired, tmp_path):
    from lib import sessions
    from lib.harness.locks import pid_alive
    wired.plan.sync()
    wired.plan.set_status("setup", "done")
    bin_ = tmp_path / "bin"                    # first on PATH; HOME is a temp folder, so no real agent comes before it
    bin_.mkdir()
    fake = bin_ / "claude"
    fake.write_text(f"#!{sys.executable}\nimport runpy; runpy.run_path({str(ECHO)!r}, run_name='__main__')\n",
                    encoding="utf-8")
    fake.chmod(0o755)
    env = {**os.environ, "CAMARONES_ROOT": str(wired.root), "CAMARONES_APP_TOKEN": TOKEN,
           "PATH": f"{bin_}{os.pathsep}{os.environ['PATH']}"}
    srv = subprocess.Popen([sys.executable, str(wired.kit_dir / "camarones.py"), "up", "--foreground", "--port", "0"],
                           env=env, stdout=subprocess.PIPE, text=True, encoding="utf-8")
    try:
        port = json.loads(srv.stdout.readline())["port"]
        uid = ready_agent_unit(wired)["id"]
        code, r = call(f"http://127.0.0.1:{port}/api/app/terminals", {"unit": uid, "agent": "claude"})
        assert code == 200, r
        until(lambda: sessions.running(sessions.load(uid)))
        srv.send_signal(signal.SIGTERM)
        srv.wait(timeout=20)
    finally:
        srv.kill()
    until(lambda: not pid_alive(r["terminal"]["pid"]))
    assert sessions.load(uid).get("ended") and not sessions.live(sessions.load(uid))
