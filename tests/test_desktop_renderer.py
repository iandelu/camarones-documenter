"""The desktop app's own UI (4.52): React in desktop/renderer, built in the kit's CI into desktop/renderer-build
(committed, like the portal). A project's window loads it from that project's server at /desktop/, same origin as
the API it calls with the app's token; the window without a project loads the same build from disk."""
from __future__ import annotations

import json, re, threading, urllib.error, urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
BUILD = REPO / ".camarones" / "desktop" / "renderer-build"
SOURCE = REPO / ".camarones" / "desktop" / "renderer"


def test_the_build_is_committed_and_complete():
    html = (BUILD / "index.html").read_text(encoding="utf-8")
    refs = [r.removeprefix("./") for r in re.findall(r'(?:src|href)="((?:\./)?(?:assets|theme)/[^"]+)"', html)]
    assert refs and all((BUILD / r).is_file() for r in refs)
    assert '="/' not in html                                  # relative: served at /desktop/ and opened from disk
    assert "Content-Security-Policy" in html
    assert (BUILD / "theme" / "fonts" / "Inter.woff2").is_file()


def test_dependencies_are_pinned_exactly():
    pkg = json.loads((SOURCE / "package.json").read_text(encoding="utf-8"))
    versions = {**pkg["dependencies"], **pkg["devDependencies"]}
    assert all(re.fullmatch(r"\d+\.\d+\.\d+", v) for v in versions.values()), versions
    assert (SOURCE / "package-lock.json").is_file()


@pytest.fixture
def server(kit):
    srv = ThreadingHTTPServer(("127.0.0.1", 0), kit.serve.Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


def get(url):
    with urllib.request.urlopen(url, timeout=10) as r:
        return r.status, r.headers.get("Content-Type", ""), r.read()


def test_the_app_is_served_at_desktop(server):
    status, ctype, body = get(f"{server}/desktop/")
    assert status == 200 and "text/html" in ctype and b'id="app"' in body
    asset = re.search(rb'src="\./(assets/[^"]+\.js)"', body).group(1).decode()
    status, ctype, _ = get(f"{server}/desktop/{asset}")
    assert status == 200 and "javascript" in ctype
    assert get(f"{server}/desktop/theme/tokens.css")[0] == 200
    assert get(f"{server}/desktop/plan")[2] == body                     # a section without its hash: the app
    portal = get(f"{server}/")[2]
    assert portal != body                                               # the portal stays the portal


def test_desktop_without_its_slash_redirects(server):
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *a, **k):
            return None
    try:
        urllib.request.build_opener(NoRedirect).open(f"{server}/desktop", timeout=10)
        raise AssertionError("expected a redirect")
    except urllib.error.HTTPError as e:
        assert e.code == 301 and e.headers["Location"] == "/desktop/"


def test_nothing_outside_the_build(server):
    with pytest.raises(urllib.error.HTTPError) as e:
        get(f"{server}/desktop/..%2F..%2Fcamarones.py")
    assert e.value.code == 404
