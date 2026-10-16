"""The next portal (R20): a React app built in the kit's CI into portal/app-build (committed, so users never run npm)
and served by the live portal at /next. The old portal stays the default."""
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
    refs = re.findall(r'(?:src|href)="/next/([^"]+)"', html)
    assert refs and all((BUILD / r).is_file() for r in refs)
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


def test_the_live_portal_serves_the_app_at_next(server):
    status, ctype, body = get(f"{server}/next/")
    assert status == 200 and "text/html" in ctype and b'id="root"' in body
    asset = re.search(rb'src="(/next/assets/[^"]+\.js)"', body).group(1).decode()
    status, ctype, _ = get(server + asset)
    assert status == 200 and "javascript" in ctype
    status, _, again = get(f"{server}/next/pipeline")                 # app routes fall back to the app
    assert status == 200 and again == body


def test_the_classic_portal_stays_the_default(server):
    status, _, body = get(f"{server}/")
    assert status == 200 and b"app.js" in body


def test_the_classic_portal_links_to_the_pipeline_in_live_mode(kit):
    app = (kit.kit_dir / "portal" / "live" / "app.js").read_text(encoding="utf-8")
    core = (kit.kit_dir / "portal" / "live" / "core.js").read_text(encoding="utf-8")
    assert '(!STATIC ? `<a href="/next/#/pipeline"' in app                               # the static export has no /next
    assert core.count("pipelineTab:") == 2                                                # en + es


def test_status_without_check_answers_fast_and_check_has_its_own_endpoint(server, kit, monkeypatch):
    import json
    calls = []
    monkeypatch.setattr(kit.serve.docs, "check", lambda *a, **k: calls.append(1) or (["e"], ["w"]))
    s = json.loads(get(f"{server}/api/status?check=0")[2])
    assert s["check"] is None and "plan" in s and calls == []
    c = json.loads(get(f"{server}/api/check")[2])
    assert c == {"errors": ["e"], "warnings": ["w"]} and calls == [1]
    assert json.loads(get(f"{server}/api/status")[2])["check"]["errors"] == ["e"]       # old callers unchanged
