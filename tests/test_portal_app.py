"""The portal (R20, R29): one app built in the kit's CI into portal/app-build (committed, so users never run npm) and
served at /: the React views (Pipeline, Ask…) plus the docs views (public/legacy/, plain scripts). /next, the
preview address of earlier versions, redirects to it."""
from __future__ import annotations

import json, re, threading, urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
BUILD = REPO / ".camarones" / "portal" / "app-build"
SOURCE = REPO / ".camarones" / "portal" / "app"


def test_the_build_is_committed_and_complete():
    html = (BUILD / "index.html").read_text(encoding="utf-8")
    refs = [r.removeprefix("./") for r in re.findall(r'(?:src|href)="((?:\./)?(?:assets|legacy|theme)/[^"]+)"', html)]
    assert refs and all((BUILD / r).is_file() for r in refs)
    theme = '<link rel="stylesheet" href="theme/tokens.css">'
    assert theme in html and html.index(theme) < html.index('href="legacy/app.css"')     # the theme applies first
    assert '="/' not in html.replace('href="#/', '')                     # relative: the export works under a sub-path
    for script in ("core", "doc", "c4", "app"):
        assert f'<script defer src="legacy/{script}.js">' in html
    manifest = json.loads((BUILD / ".vite" / "manifest.json").read_text(encoding="utf-8"))
    assert all((BUILD / entry["file"]).is_file() for entry in manifest.values())


def test_dependencies_are_pinned_exactly():
    pkg = json.loads((SOURCE / "package.json").read_text(encoding="utf-8"))
    versions = {**pkg["dependencies"], **pkg["devDependencies"]}
    assert all(re.fullmatch(r"\d+\.\d+\.\d+", v) for v in versions.values()), versions
    assert (SOURCE / "package-lock.json").is_file()


def test_the_installer_ships_the_build_but_not_the_sources_modules():
    from conftest import KIT_DIR  # noqa: F401  (kit path on sys.path)
    import importlib
    install = importlib.import_module("lib.install")
    files = install.payload(REPO)
    assert any(p.startswith(".camarones/portal/app-build/assets/") for p in files)
    assert not any("node_modules" in p for p in files)


@pytest.fixture
def server(kit):
    srv = ThreadingHTTPServer(("127.0.0.1", 0), kit.serve.Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


def get(url):
    with urllib.request.urlopen(url, timeout=10) as r:
        return r.status, r.headers.get("Content-Type", ""), r.read()


def test_the_portal_is_served_at_the_root(server):
    status, ctype, body = get(f"{server}/")
    assert status == 200 and "text/html" in ctype and b'id="app"' in body and b"legacy/app.js" in body
    asset = re.search(rb'src="\./(assets/[^"]+\.js)"', body).group(1).decode()
    status, ctype, _ = get(f"{server}/{asset}")
    assert status == 200 and "javascript" in ctype
    assert get(f"{server}/legacy/doc.js")[0] == 200
    assert get(f"{server}/anything-without-a-suffix")[2] == body


def test_the_theme_and_its_fonts_are_served(server):
    status, ctype, _ = get(f"{server}/theme/tokens.css")
    assert status == 200 and "text/css" in ctype
    status, ctype, body = get(f"{server}/theme/fonts/Inter.woff2")
    assert status == 200 and ctype == "font/woff2" and body[:4] == b"wOF2"      # whatever this OS's registry says


def test_the_old_next_address_redirects(server):
    import urllib.error
    req = urllib.request.Request(f"{server}/next/")

    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *a, **k):
            return None
    try:
        urllib.request.build_opener(NoRedirect).open(req, timeout=10)
        raise AssertionError("expected a redirect")
    except urllib.error.HTTPError as e:
        assert e.code == 301 and e.headers["Location"] == "/"


def test_the_react_views_are_reached_through_zones(kit):
    """No tab bar since 4.42: the shell's sidebar, breadcrumbs and ⌘K reach every view (src/zones.js); the shell's
    router (src/router.js) shows them, and a zone's address opens its first view."""
    app_dir = kit.kit_dir / "portal" / "app"
    home = (app_dir / "src" / "views" / "home.js").read_text(encoding="utf-8")
    core = (app_dir / "public" / "legacy" / "core.js").read_text(encoding="utf-8")
    zones = (app_dir / "src" / "zones.js").read_text(encoding="utf-8")
    router = (app_dir / "src" / "router.js").read_text(encoding="utf-8")
    for href in ("#/pipeline", "#/kpis", "#/ci", "#/libs", "#/data"):      # Ask is reached from the Home hero
        assert f"'{href}'" in zones
    assert "'#/boards'" not in zones                                              # boards were removed in 4.49
    assert "if (view === 'boards') return { kind: 'redirect', to: '#/arch' }" in router
    assert "'#/ask/'" in home                                                    # Home's question goes to Ask
    assert "return { kind: 'native', view, arg: rest }" in router
    assert 'id="tabs"' not in (app_dir / "index.html").read_text(encoding="utf-8")
    for key in ("'zone.arch'", "'home.title'"):
        assert core.count(key) == 2                                                   # en + es


def test_status_without_check_answers_fast_and_check_has_its_own_endpoint(server, kit, monkeypatch):
    import json
    calls = []
    monkeypatch.setattr(kit.serve.docs, "check", lambda *a, **k: calls.append(1) or (["e"], ["w"]))
    s = json.loads(get(f"{server}/api/status?check=0")[2])
    assert s["check"] is None and "plan" in s and calls == []
    c = json.loads(get(f"{server}/api/check")[2])
    assert c == {"errors": ["e"], "warnings": ["w"]} and calls == [1]
    assert json.loads(get(f"{server}/api/status")[2])["check"]["errors"] == ["e"]       # old callers unchanged


def test_the_business_view_uses_real_page_types():
    """core.js keeps the Business view's page types; each must be a type CONVENTIONS §2 defines."""
    core = (REPO / ".camarones" / "portal" / "app" / "public" / "legacy" / "core.js").read_text(encoding="utf-8")
    types = re.findall(r"'([\w-]+)'", re.search(r"BUSINESS_TYPES = \[(.*?)\]", core).group(1))
    conventions = (REPO / ".camarones" / "CONVENTIONS.md").read_text(encoding="utf-8")
    known = re.search(r"type: [\w-]+\s+# ([\w|-]+)", conventions).group(1).split("|")
    assert types and set(types) <= set(known), (types, known)
