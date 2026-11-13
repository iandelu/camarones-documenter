"""What the project server answers around its handlers: the order of its gates, how it reads a path, unknown paths,
the static mode, HEAD and PUT, foreign hosts. Written against lib/serve.py before the router existed; the router keeps
every answer (docs/superpowers/plans/2026-11-13-hexagonal-f3-http.md, Review Focus)."""
from __future__ import annotations

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
