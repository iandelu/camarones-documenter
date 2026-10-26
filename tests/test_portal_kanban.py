"""The board over the portal: reads for anyone on localhost, writes with the machine token (spec §7). The portal token
never unlocks what only the desktop app may do."""
from __future__ import annotations

import json, re, shutil, threading, urllib.error, urllib.request
from http.server import ThreadingHTTPServer

import pytest

APP, PORTAL = "app-token", "portal-token"


@pytest.fixture
def server(wired, monkeypatch):
    monkeypatch.setattr(wired.serve, "APP_TOKEN", "")
    monkeypatch.setattr(wired.serve, "PORTAL_TOKEN", PORTAL)
    srv = ThreadingHTTPServer(("127.0.0.1", 0), wired.serve.Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


def call(url, body=None, token=None, method="POST", host=None):
    h = {"Content-Type": "application/json"}
    if method == "POST":
        h["X-Camarones"] = "1"
    if token:
        h["X-Camaron-Token"] = token
    if host:
        h["Host"] = host
    req = urllib.request.Request(url, data=json.dumps(body or {}).encode() if method == "POST" else None,
                                 method=method, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


def test_board_writes_need_a_token(wired, server, monkeypatch):
    shutil.rmtree(wired.root / "backlog")                  # a new project starts with a board; this one opts in
    code, body = call(server + "/api/kanban/init")
    assert code == 403 and body["token"] is True
    assert not (wired.root / "backlog" / "board.yaml").exists()
    assert call(server + "/api/kanban/init", token=PORTAL)[0] == 200
    assert (wired.root / "backlog" / "board.yaml").exists()
    assert call(server + "/api/kanban/add", {"type": "task", "title": "x"}, token="nope")[0] == 403
    monkeypatch.setattr(wired.serve, "APP_TOKEN", APP)
    code, row = call(server + "/api/kanban/add", {"type": "task", "title": "from the app"}, token=APP)
    assert code == 200 and row["id"] == "WI-1"


def test_portal_token_does_not_unlock_app_only(server):
    code, body = call(server + "/api/runs", token=PORTAL)
    assert code == 403 and body["app"] is True


APP_ONLY_POSTS = ["/api/runs", "/api/runs/r-1/cancel", "/api/wiki", "/api/build", "/api/inventory", "/api/schemas",
                  "/api/ci", "/api/ask/answer", "/api/app/cmd", "/api/app/onboard/start"]


def test_the_app_servers_portal_token_writes_the_board_and_nothing_app_only(wired, server, monkeypatch):
    """The desktop app starts its project server with both tokens (desktop/main.cjs): the portal it opens in the
    browser carries the portal one, which writes the board as `camaron up`'s does, and never what needs the app."""
    monkeypatch.setattr(wired.serve, "APP_TOKEN", APP)
    call(server + "/api/kanban/init", token=PORTAL)
    code, row = call(server + "/api/kanban/add", {"type": "task", "title": "from the browser"}, token=PORTAL)
    assert code == 200 and row["id"] == "WI-1"
    assert call(server + "/api/kanban", method="GET", token=PORTAL)[1]["writable"] is True
    for path in APP_ONLY_POSTS:
        code, body = call(server + path, {"repo": "api", "what": "c4"}, token=PORTAL)
        assert code == 403 and body["app"] is True, path
    for path in ("/api/app/info", "/api/app/onboard/state", "/api/app/jobs"):
        assert call(server + path, method="GET", token=PORTAL)[0] == 403, path
    assert call(server + "/api/app/info", method="GET", token=APP)[0] == 200


def test_read_only_without_token(wired, server):
    from lib.kanban import ops
    ops.init(log=lambda *_: None)
    ops.add("task", "first")
    code, b = call(server + "/api/kanban", method="GET")
    assert code == 200 and b["enabled"] is True and b["writable"] is False
    assert [c["id"] for c in b["cards"]] == ["WI-1"]
    assert "Backlog" in b["statuses"] and "epic" in b["types"] and "P0" in b["priorities"]
    assert call(server + "/api/kanban", method="GET", token=PORTAL)[1]["writable"] is True


def test_get_does_not_write_and_works_without_a_board(wired, server):
    shutil.rmtree(wired.root / "backlog")
    code, b = call(server + "/api/kanban", method="GET")
    assert code == 200 and b["enabled"] is False and b["cards"] == []
    assert not (wired.root / "backlog").exists()


def test_item_and_derived_lists(wired, server):
    from lib.kanban import ops
    ops.init(log=lambda *_: None)
    ops.add("epic", "Payments")
    ops.add("story", "Retry", epic="WI-1", repos=["api"], labels=["pay"])
    b = call(server + "/api/kanban", method="GET")[1]
    assert b["epics"] and b["repos"] == ["api"] and b["labels"] == ["pay"]
    code, it = call(server + "/api/kanban/item?id=WI-2", method="GET")
    assert code == 200 and it["id"] == "WI-2" and "history" in it
    assert call(server + "/api/kanban/item?id=WI-99", method="GET")[0] == 400


def test_move_and_errors(wired, server):
    call(server + "/api/kanban/init", token=PORTAL)
    call(server + "/api/kanban/add", {"type": "task", "title": "x"}, token=PORTAL)
    code, row = call(server + "/api/kanban/move", {"id": "WI-1", "status": "Done"}, token=PORTAL)
    assert code == 200 and row["status"] == "Done"
    code, b = call(server + "/api/kanban/move", {"id": "WI-1", "status": "Nope"}, token=PORTAL)
    assert code == 400 and "error" in b
    assert call(server + "/api/kanban/bogus", token=PORTAL)[0] == 404


def test_foreign_host_refused_with_portal_token(server):
    assert call(server + "/api/kanban", method="GET", host="evil.test")[0] == 403
    assert call(server + "/api/kanban/init", token=PORTAL, host="evil.test")[0] == 403


def test_add_from_doc_section_gives_page_an_xid(wired, server):
    from test_kanban_xid import PAYMENTS, page, raw
    f = page(wired, "flows/payments.md", PAYMENTS)
    call(server + "/api/kanban/init", token=PORTAL)
    code, row = call(server + "/api/kanban/add", {"type": "task", "title": "docs",
                     "docs": [{"path": "flows/payments.md", "section": "retries"}]}, token=PORTAL)
    assert code == 200
    assert re.search(r"^x-id: FLOW-", raw(f), re.M)
    assert re.fullmatch(r"FLOW-\w{4}#retries@\w+", row["docs"][0])


def test_board_cards_carry_their_link_states(wired, server):
    """The Board's docs filter (suspect / unconfirmed) runs in the page: each card brings its links' trust."""
    from test_kanban_xid import PAYMENTS, page
    page(wired, "flows/payments.md", PAYMENTS)
    from lib.kanban import ops
    ops.init(log=lambda *_: None)
    ops.add("task", "docs", docs=["flows/payments.md#retries"])
    ops.add("task", "no docs")
    cards = {c["id"]: c for c in call(server + "/api/kanban", method="GET")[1]["cards"]}
    [state] = cards["WI-1"]["links"]
    assert state["path"] == "flows/payments.md" and state["missing"] is False and "trust" in state and "fresh" in state
    assert cards["WI-2"]["links"] == []


def test_a_broken_item_file_is_reported_by_path(wired, server):
    from lib.kanban import ops
    ops.init(log=lambda *_: None)
    ops.add("task", "fine")
    (wired.root / "backlog" / "tasks" / "wi-9 - broken.md").write_text("---\ntitle: [unclosed\n---\n", encoding="utf-8")
    code, b = call(server + "/api/kanban", method="GET")
    assert code == 200 and [c["id"] for c in b["cards"]] == ["WI-1"]
    [p] = b["problems"]
    assert p["path"].endswith("wi-9 - broken.md") and p["error"]


def test_serve_editor_url_carries_token(wired, monkeypatch):
    seen = {}

    class Pr:
        pid = 4242

        def poll(self):
            return None

    def popen(cmd, **kw):
        seen["env"] = kw["env"]
        return Pr()

    class Sock:
        n = 0

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def connect_ex(self, addr):
            Sock.n += 1
            return 1 if Sock.n == 1 else 0

    import socket
    monkeypatch.setattr(wired.env.subprocess, "Popen", popen)
    monkeypatch.setattr(socket, "socket", lambda *a, **k: Sock())
    monkeypatch.setattr("time.sleep", lambda *_: None)
    url = wired.env.serve_editor(port=8099, log=lambda *_: None)
    m = re.search(r"#cam-token=([\w-]{20,})$", url)
    assert m and url.startswith("http://localhost:8099/")
    assert seen["env"]["CAMARONES_PORTAL_TOKEN"] == m.group(1)


def raw_call(url, headers):
    """A POST with exact raw header bytes (urllib refuses non-latin-1 values)."""
    import http.client, urllib.parse
    u = urllib.parse.urlparse(url)
    c = http.client.HTTPConnection(u.hostname, u.port, timeout=10)
    c.putrequest("POST", u.path)
    c.putheader("X-Camarones", "1")
    c.putheader("Content-Type", "application/json")
    c.putheader("Content-Length", "2")
    for k, v in headers.items():
        c.putheader(k, v)
    c.endheaders(b"{}")
    return c.getresponse().status


def test_non_ascii_token_is_403_not_500(wired, server, monkeypatch):
    monkeypatch.setattr(wired.serve, "APP_TOKEN", APP)
    for url in ("/api/kanban/init", "/api/runs"):
        assert raw_call(server + url, {"X-Camaron-Token": "caf\xe9".encode("latin-1")}) == 403


def test_empty_token_header_with_no_tokens_is_403(wired, server, monkeypatch):
    monkeypatch.setattr(wired.serve, "PORTAL_TOKEN", "")
    assert raw_call(server + "/api/kanban/add", {"X-Camaron-Token": ""}) == 403
    assert call(server + "/api/kanban/add", {"type": "task", "title": "x"})[0] == 403


@pytest.mark.parametrize("body", [{"repos": "api"}, {"labels": [{"a": 1}]}, {"repos": [1]}, {"epic": 5},
                                  {"docs": [5]}, {"docs": [{"section": "x"}]}, {"docs": [{"path": "a.md", "section": 3}]},
                                  {"priority": 1}, {"title": 5}])
def test_wrong_typed_add_is_400_and_writes_nothing(wired, server, body):
    call(server + "/api/kanban/init", token=PORTAL)
    code, b = call(server + "/api/kanban/add", {"type": "task", "title": "x", **body}, token=PORTAL)
    assert code == 400 and "error" in b
    assert call(server + "/api/kanban", method="GET")[1]["cards"] == []


def test_wrong_typed_move_fields_are_400(wired, server):
    call(server + "/api/kanban/init", token=PORTAL)
    call(server + "/api/kanban/add", {"type": "task", "title": "x"}, token=PORTAL)
    for act, body in (("move", {"id": "WI-1", "status": "Done", "before": 5}), ("move", {"id": ["WI-1"], "status": "Done"}),
                      ("assign", {"id": "WI-1", "who": 3}), ("link", {"id": "WI-1", "ref": 4})):
        assert call(f"{server}/api/kanban/{act}", body, token=PORTAL)[0] == 400


def test_hand_written_dict_label_does_not_break_the_view(wired, server):
    from lib.kanban import ops
    ops.init(log=lambda *_: None)
    ops.add("task", "x")
    f = next((wired.root / "backlog" / "tasks").glob("*.md"))
    t = f.read_text(encoding="utf-8")
    assert "labels: []" in t
    f.write_text(t.replace("labels: []", "labels:\n  - a: 1"), encoding="utf-8", newline="\n")
    assert call(server + "/api/kanban", method="GET")[0] == 200


def test_portal_url_has_one_fragment(wired):
    assert wired.env.portal_url(8080, "TOK", "#/c4") == "http://localhost:8080/#/c4&cam-token=TOK"
    assert wired.env.portal_url(8080, "TOK") == "http://localhost:8080/#cam-token=TOK"
    assert wired.env.portal_url(8080, None, "#/c4") == "http://localhost:8080/#/c4"
    assert wired.env.portal_url(8080) == "http://localhost:8080/"


def test_open_portal_keeps_route_and_token(wired, monkeypatch):
    opened = []
    monkeypatch.setattr(wired.env, "open_url", opened.append)
    monkeypatch.setattr(wired.env, "serve_editor", lambda port, log=print, static=False: wired.env.portal_url(port, "T" * 24))
    import socket

    class Down:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def connect_ex(self, a):
            return 1
    monkeypatch.setattr(socket, "socket", lambda *a, **k: Down())
    w = wired.wizard.W.__new__(wired.wizard.W)
    w.prefs = {"port": 8099}
    w.safe = lambda busy, fn, *a, **kw: fn(*a)
    w.busy = None
    w.open_portal("#/c4")
    assert opened == ["http://localhost:8099/#/c4&cam-token=" + "T" * 24]


# --- final review ---

def test_the_wizard_reopens_its_portal_with_its_token(wired, monkeypatch):
    """R14: the same wizard opening the portal a second time (the server already up) keeps it writable."""
    opened, up = [], set()
    monkeypatch.setattr(wired.env, "open_url", opened.append)

    def serve(port, log=print, static=False):
        up.add(port)
        return wired.env.portal_url(port, "T" * 24)
    monkeypatch.setattr(wired.env, "serve_editor", serve)
    import socket

    class Sock:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def connect_ex(self, a):
            return 0 if a[1] in up else 1
    monkeypatch.setattr(socket, "socket", lambda *a, **k: Sock())
    w = wired.wizard.W.__new__(wired.wizard.W)
    w.prefs = {"port": 8099}
    w.safe = lambda busy, fn, *a, **kw: fn(*a)
    w.busy = None
    w.open_portal()
    w.open_portal("#/board")
    assert opened[1] == "http://localhost:8099/#/board&cam-token=" + "T" * 24
    up.add(8100)                                       # a server this wizard did not start: no token to give
    w.prefs = {"port": 8100}
    w.open_portal("#/board")
    assert opened[2] == "http://localhost:8100/#/board"


def test_port_80_accepts_a_host_without_port(wired):
    """On port 80 the browser sends `Host: localhost`, with no port."""
    from types import SimpleNamespace
    H = wired.serve.Handler

    def foreign(host, port):
        return H.foreign_host(SimpleNamespace(server=SimpleNamespace(server_address=("127.0.0.1", port)),
                                              headers={"Host": host}))
    old = wired.serve.PORTAL_TOKEN
    wired.serve.PORTAL_TOKEN = PORTAL
    try:
        assert not foreign("localhost", 80) and not foreign("127.0.0.1", 80) and not foreign("localhost:80", 80)
        assert foreign("localhost", 8080) and foreign("evil.example", 80) and not foreign("localhost:8080", 8080)
    finally:
        wired.serve.PORTAL_TOKEN = old


def test_a_static_portal_gets_no_token(wired, monkeypatch):
    """`up --static` serves the read-only export: no machine token is minted, printed or passed on."""
    seen = {}

    class Pr:
        pid = 4242

        def poll(self):
            return None

    def popen(cmd, **kw):
        seen["env"] = kw["env"]
        return Pr()

    class Sock:
        n = 0

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def connect_ex(self, addr):
            Sock.n += 1
            return 1 if Sock.n == 1 else 0

    import socket
    monkeypatch.setattr(wired.env.subprocess, "Popen", popen)
    monkeypatch.setattr(socket, "socket", lambda *a, **k: Sock())
    monkeypatch.setattr("time.sleep", lambda *_: None)
    said = []
    url = wired.env.serve_editor(port=8099, log=said.append, static=True)
    assert url == "http://localhost:8099/" and "cam-token" not in " ".join(said)
    assert "CAMARONES_PORTAL_TOKEN" not in seen["env"]
