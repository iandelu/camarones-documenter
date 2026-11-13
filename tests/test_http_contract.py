"""What the project server answers around its handlers: the order of its gates, how it reads a path, unknown paths,
the static mode, HEAD and PUT, foreign hosts. Written against lib/serve.py before the router existed; the router keeps
every answer (docs/superpowers/plans/2026-11-13-hexagonal-f3-http.md, Review Focus)."""
from __future__ import annotations

import importlib
import json

from fixtures.http_probe import APP_TOKEN, arm, request, serving


def test_a_body_that_is_not_json_is_a_400_before_the_portal_token(kit, monkeypatch):
    arm(monkeypatch)
    with serving(kit.serve.Handler) as base:
        assert request(base, "POST", "/api/kanban/add", b"{")[0] == 400
        assert request(base, "POST", "/api/nope", b"{")[0] == 400
        status, _, raw = request(base, "POST", "/api/nope", b"{}")
    assert (status, json.loads(raw)) == (404, {"error": "not found"})


def test_get_matches_the_decoded_path_and_post_the_path_as_sent(kit, monkeypatch):
    kit.common.DOCS.mkdir(parents=True, exist_ok=True)
    (kit.common.DOCS / "a b.txt").write_text("hi", encoding="utf-8", newline="")
    arm(monkeypatch)
    with serving(kit.serve.Handler) as base:
        status, _, raw = request(base, "GET", "/raw/a%20b.txt")
        assert (status, raw) == (200, b"hi")
        status, _, raw = request(base, "POST", "/api/app/units/a%2Fb/stop", b"{}", APP_TOKEN)
    assert (status, json.loads(raw)) == (404, {"error": "no unit a/b"})


def test_unknown_paths_answer_by_their_place(kit, monkeypatch):
    arm(monkeypatch)
    with serving(kit.serve.Handler) as base:
        for method, body in (("GET", None), ("POST", b"{}")):
            status, _, raw = request(base, method, "/api/app/nope", body)
            assert (status, json.loads(raw).get("app")) == (403, True)
            status, _, raw = request(base, method, "/api/app/nope", body, APP_TOKEN)
            assert (status, json.loads(raw)) == (404, {"error": "not found"})
        status, _, raw = request(base, "GET", "/api/nope")
        assert (status, json.loads(raw)) == (404, {"error": "not found"})
        status, headers, raw = request(base, "GET", "/some/page")
        assert (status, raw) == (200, (kit.kit_dir / "portal" / "app-build" / "index.html").read_bytes())
        assert headers["content-type"].startswith("text/html")
        assert request(base, "GET", "/missing.js")[::2] == (404, b"not found")


def test_a_decoded_newline_stays_inside_the_path(kit, monkeypatch):
    """A route `X{rest:.*}` stands for a `p.startswith(X)` branch, which took any tail, a decoded %0A included."""
    arm(monkeypatch)
    with serving(kit.serve.Handler) as base:
        status, headers, raw = request(base, "GET", "/x%0A")
        assert (status, raw) == (200, (kit.kit_dir / "portal" / "app-build" / "index.html").read_bytes())
        assert headers["content-type"].startswith("text/html")
        status, _, raw = request(base, "GET", "/desktop/x%0A")
    assert (status, raw) == (200, (kit.kit_dir / "desktop" / "renderer-build" / "index.html").read_bytes())


def test_static_mode_reads_the_export_and_refuses_writes(kit, monkeypatch):
    site = kit.common.CACHE / "site"
    site.mkdir(parents=True, exist_ok=True)
    (site / "index.html").write_text("<html>site</html>", encoding="utf-8", newline="")
    arm(monkeypatch, static=True)
    with serving(kit.serve.Handler) as base:
        status, _, raw = request(base, "POST", "/api/doc", b"{}", marked=False)
        assert (status, json.loads(raw)) == (405, {"error": "read-only portal — run `camaron up` to edit"})
        assert request(base, "GET", "/api/app/info", token=APP_TOKEN)[0] == 200
        assert request(base, "GET", "/api/tree")[::2] == (200, b"<html>site</html>")


def test_head_put_and_foreign_hosts(kit, monkeypatch):
    arm(monkeypatch)
    with serving(kit.serve.Handler) as base:
        got = request(base, "GET", "/api/tree")
        head = request(base, "HEAD", "/api/tree")
        assert (head[0], head[1]["content-type"], head[2]) == (200, got[1]["content-type"], b"")
        assert request(base, "PUT", "/api/new", b"{}", marked=False)[0] == 403
        assert request(base, "PUT", "/api/new", b"{")[0] == 400
        status, _, raw = request(base, "GET", "/api/tree", host="evil.test")
        assert (status, json.loads(raw)) == (403, {"error": "forbidden host"})
        status, _, raw = request(base, "POST", "/api/new", b"{}", host="evil.test")
    assert (status, json.loads(raw)) == (403, {"error": "forbidden"})


def put(f, text):
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(text, encoding="utf-8", newline="")
    return f


def test_the_code_graph_serves_the_repo_the_portal_asks_for(kit, monkeypatch):
    put(kit.env.GRAPHS / "api" / "graph.html", "<html>api graph</html>")
    put(kit.common.CACHE / "graph" / "graph.html",
        '<script src="https://cdn.jsdelivr.net/npm/vis-network@9.1.9/dist/vis.js"></script>all graph')
    arm(monkeypatch)
    with serving(kit.serve.Handler) as base:
        for path in ("/code-graph/api/", "/code-graph/api"):    # the portal asks `code-graph/<name>/`
            status, headers, raw = request(base, "GET", path)
            assert (status, raw) == (200, b"<html>api graph</html>"), path
            assert headers["content-type"] == "text/html; charset=utf-8"
        for path in ("/code-graph/",):
            status, _, raw = request(base, "GET", path)
            assert status == 200 and raw.endswith(b"all graph"), path
            assert b"/vendor/vis-network@9.1.9/dist/vis.js" in raw and b"cdn.jsdelivr.net" not in raw
        assert request(base, "GET", "/code-graph/web/")[::2] == (404, b"not found")


def test_vendor_serves_the_cached_file_else_redirects_to_the_cdn(kit, monkeypatch):
    put(kit.common.CACHE / "vendor-cache" / "@scope__pkg@1.2.3" / "package" / "dist" / "lib.js", "var cached = 1;")
    monkeypatch.setattr(kit.docs, "vendor_file", lambda pkg, ver, file: None)   # a miss would run `npm pack`
    arm(monkeypatch)
    with serving(kit.serve.Handler) as base:
        status, headers, raw = request(base, "GET", "/vendor/other@2.0.0/dist/a.min.js")
        assert (status, raw) == (302, b"")
        assert headers["location"] == "https://cdn.jsdelivr.net/npm/other@2.0.0/dist/a.min.js"
        status, headers, _ = request(base, "GET", "/vendor/@scope/pkg@1.2.3/dist/lib.js")
        assert (status, headers["location"]) == (302, "https://cdn.jsdelivr.net/npm/@scope/pkg@1.2.3/dist/lib.js")
        monkeypatch.undo()
        arm(monkeypatch)
        status, headers, raw = request(base, "GET", "/vendor/@scope/pkg@1.2.3/dist/lib.js")
    assert (status, raw) == (200, b"var cached = 1;")
    assert headers["content-type"].startswith("text/javascript")


def test_the_viewers_are_served_from_the_cache(kit, monkeypatch):
    put(kit.env.VIEWERS / "wiki-graph" / "api" / "index.html", '<html><script src="https://unpkg.com/d3@7.9.0/dist/d3.min.js"></script></html>')
    put(kit.env.VIEWERS / "wiki-graph" / "api" / "data.json", "{}")
    put(kit.env.VIEWERS / "architecture" / "index.html", "<html>c4</html>")
    arm(monkeypatch)
    with serving(kit.serve.Handler) as base:
        assert request(base, "GET", "/wiki-graph/api/")[::2] == (
            200, b'<html><script src="/vendor/d3@7.9.0/dist/d3.min.js"></script></html>')
        assert request(base, "GET", "/wiki-graph/api/data.json")[::2] == (200, b"{}")
        assert request(base, "GET", "/wiki-graph/web/")[::2] == (404, b"not found")
        assert request(base, "GET", "/architecture/")[::2] == (200, b"<html>c4</html>")
        assert request(base, "GET", "/architecture/view/overview")[::2] == (200, b"<html>c4</html>")


def test_firstlook_is_the_one_route_static_mode_still_routes(kit, monkeypatch):
    onboard = importlib.import_module("lib.onboard")
    put(kit.common.CACHE / "site" / "index.html", "<html>site</html>")
    draft = put(kit.common.CACHE / "draft.html", "<html>draft</html>")
    monkeypatch.setattr(onboard, "LAST_DRAFT", {"html": str(draft)})
    arm(monkeypatch, static=True)
    with serving(kit.serve.Handler) as base:
        assert request(base, "GET", "/firstlook")[::2] == (200, b"<html>draft</html>")
        assert request(base, "GET", "/desktop")[::2] == (200, b"<html>site</html>")   # every other path: the export
