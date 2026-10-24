"""Boards (Excalidraw whiteboards) were removed in 4.49: their API is gone, and the board files a project already has
in docs/boards/ are left exactly as they were."""
from __future__ import annotations

import json, threading, urllib.error, urllib.request
from http.server import ThreadingHTTPServer

import pytest


@pytest.fixture
def portal(kit):
    srv = ThreadingHTTPServer(("127.0.0.1", 0), kit.serve.Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


def get(url):
    with urllib.request.urlopen(url, timeout=30) as r:
        return json.loads(r.read())


def status(url):
    try:
        with urllib.request.urlopen(url, timeout=30) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code


def post_status(url, body):
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST",
                                 headers={"Content-Type": "application/json", "X-Camarones": "1"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code


def test_board_routes_are_gone(portal):
    for path in ("boards", "board?name=ideas", "sketch?view=index"):
        assert status(f"{portal}/api/{path}") == 404, path
    assert post_status(f"{portal}/api/board", {"name": "x", "scene": {"type": "excalidraw", "elements": []}}) == 404


def test_old_board_files_are_left_alone(kit, portal):
    old = kit.root / "docs" / "boards" / "team-map.excalidraw"
    old.parent.mkdir(parents=True, exist_ok=True)
    old.write_bytes(b'{"type": "excalidraw", "elements": []}\n')
    before = old.read_bytes()
    assert status(f"{portal}/api/tree") == 200
    assert "boards" not in json.dumps(get(f"{portal}/api/check"))
    assert old.read_bytes() == before
