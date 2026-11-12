"""Who may call each route of the project server, probed over HTTP without running a handler: the gates answer
before any handler does (the app token, the portal token, a body that is not JSON). tests/snapshots/routes.json
is written by hand from lib/serve.py; the hexagonal router must keep every entry's access."""
from __future__ import annotations

import ast
import json
import os
import re
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

SNAPSHOT = Path(__file__).parent / "snapshots" / "routes.json"
SERVE = Path(__file__).resolve().parents[1] / ".camarones" / "lib" / "serve.py"
ROUTES = json.loads(SNAPSHOT.read_text(encoding="utf-8")) if SNAPSHOT.is_file() else []
APP_TOKEN = "app-token"
PORTAL_TOKEN = "portal-token"


@pytest.fixture(scope="module")
def server(tmp_path_factory):
    """One server for every probe: the gates answer before any handler touches the project, so one workspace serves."""
    from conftest import GITCONFIG, UNSET, isolated_vars, load_kit, purge_kit_modules
    from fixtures.builder import make_workspace
    from fixtures.host_tools import hidden_tools
    saved = dict(os.environ)
    tmp = tmp_path_factory.mktemp("routes")
    home = tmp / "home"
    home.mkdir()
    (tmp / "gitconfig").write_text(GITCONFIG, encoding="utf-8")
    ws = make_workspace(tmp)
    try:
        with pytest.MonkeyPatch.context() as mp:
            for k, v in isolated_vars(home, tmp / "gitconfig", os.environ.get("PATH", ""), hidden_tools()).items():
                mp.setenv(k, v)
            for k in UNSET:
                mp.delenv(k, raising=False)
            kit = load_kit(ws / "cam-docs", home, ws)
            mp.setattr(kit.serve, "APP_TOKEN", APP_TOKEN)
            mp.setattr(kit.serve, "PORTAL_TOKEN", PORTAL_TOKEN)
            srv = ThreadingHTTPServer(("127.0.0.1", 0), kit.serve.Handler)
            threading.Thread(target=srv.serve_forever, daemon=True).start()
            yield f"http://127.0.0.1:{srv.server_address[1]}"
            srv.shutdown()
            srv.server_close()
            purge_kit_modules()
    finally:
        os.environ.clear()
        os.environ.update(saved)


def probe(base: str, method: str, path: str, body: bytes | None = None, token: str | None = None):
    headers = {"Content-Type": "application/json", "X-Camarones": "1"}
    if token:
        headers["X-Camaron-Token"] = token
    req = urllib.request.Request(base + path, data=body if method == "POST" else None, headers=headers, method=method)
    try:
        resp = urllib.request.urlopen(req, timeout=10)
        status, raw = resp.status, None
        resp.close()
    except urllib.error.HTTPError as e:
        status, raw = e.code, e.read()
        e.close()
    return status, (json.loads(raw) if raw else {})


def test_the_snapshot_is_sorted_and_well_formed():
    assert ROUTES
    assert ROUTES == sorted(ROUTES, key=lambda r: (r["path"], r["method"]))
    assert all(set(r) == {"method", "path", "access"} for r in ROUTES)
    assert all(r["method"] in ("GET", "POST") and r["access"] in ("public", "portal", "app") for r in ROUTES)
    assert len({(r["method"], r["path"]) for r in ROUTES}) == len(ROUTES)


@pytest.mark.parametrize("route", ROUTES, ids=[f"{r['method']} {r['path']}" for r in ROUTES])
def test_route_access(server, route):
    method, path, access = route["method"], route["path"], route["access"]
    if access == "app":
        body = b"{" if method == "POST" else None
        status, answer = probe(server, method, path, body)
        assert (status, answer.get("app")) == (403, True)
        status, answer = probe(server, method, path, body, token=PORTAL_TOKEN)
        assert (status, answer.get("app")) == (403, True)
        status, _ = probe(server, method, path, body, token=APP_TOKEN)
        if method == "POST":
            assert status == 400
        else:
            assert status != 403
    elif access == "portal":
        status, answer = probe(server, method, path, b"{}" if method == "POST" else None)
        assert (status, answer.get("token")) == (403, True)
    elif method == "GET":
        status, _ = probe(server, method, path)
        assert status != 403
    else:
        status, _ = probe(server, method, path, b"{")
        assert status == 400


def literal_paths() -> set[str]:
    tree = ast.parse(SERVE.read_text(encoding="utf-8"))
    found = {n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str)
             and re.fullmatch(r"/api/[\w/.-]*\w", n.value)}
    for fn in ast.walk(tree):
        if not (isinstance(fn, ast.FunctionDef) and fn.name in ("api_get", "api_app_get")):
            continue
        prefix = "/api/" if fn.name == "api_get" else "/api/app/"
        for cmp in ast.walk(fn):
            if not (isinstance(cmp, ast.Compare) and isinstance(cmp.left, ast.Name) and cmp.left.id == "name"):
                continue
            for side in cmp.comparators:
                for c in ast.walk(side):
                    if isinstance(c, ast.Constant) and isinstance(c.value, str):
                        found.add(prefix + c.value)
    return found


def test_every_literal_route_in_serve_is_listed():
    listed = {r["path"] for r in ROUTES}
    assert sorted(literal_paths() - listed) == []
