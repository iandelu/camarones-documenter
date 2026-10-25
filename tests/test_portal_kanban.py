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
