"""The server runs declared routes: the Request it builds, the gates it applies before a handler, and how it writes a
Response. Each test serves a router holding only its own routes (`router.load` patched)."""
from __future__ import annotations

import contextlib
import importlib
import json
from types import SimpleNamespace

import pytest

from fixtures.http_probe import APP_TOKEN, PORTAL_TOKEN, arm, request, serving


@pytest.fixture
def http(kit, monkeypatch):
    """`http.serve(*handlers)` → the base URL of a server whose router holds those handlers' routes."""
    router = importlib.import_module("lib.interfaces.http.router")
    arm(monkeypatch)
    with contextlib.ExitStack() as stack:
        def serve(*handlers):
            monkeypatch.setattr(router, "load", lambda: router.Router([r for h in handlers for r in h.__routes__]))
            return stack.enter_context(serving(kit.serve.Handler))
        yield SimpleNamespace(serve=serve, route=router.route, Access=router.Access,
                              m=importlib.import_module("lib.interfaces.http.messages"))


def body(answer):
    return json.loads(answer[2])


def test_a_declared_route_answers_through_the_server(http):
    @http.route("GET", "/api/zz")
    def h(req):
        return http.m.json_response(req.query)
    base = http.serve(h)
    got = request(base, "GET", "/api/zz?a=1&a=2")
    assert (got[0], body(got)) == (200, {"a": "1"})


def test_a_portal_route_refuses_with_its_own_message(http):
    @http.route("POST", "/api/zz/save", access=http.Access.PORTAL, refusal="need the token")
    def h(req):
        return http.m.json_response({"ok": True})
    base = http.serve(h)
    got = request(base, "POST", "/api/zz/save", b"{}")
    assert (got[0], body(got)) == (403, {"error": "need the token", "token": True})
    assert request(base, "POST", "/api/zz/save", b"{}", PORTAL_TOKEN)[0] == 200


def test_an_app_route_outside_api_app_needs_the_app_token(http):
    @http.route("POST", "/api/zz/run", access=http.Access.APP)
    def h(req):
        return http.m.json_response({"ok": True})
    base = http.serve(h)
    for token in (None, PORTAL_TOKEN):
        got = request(base, "POST", "/api/zz/run", b"{}", token)
        assert (got[0], body(got).get("app")) == (403, True)
    assert request(base, "POST", "/api/zz/run", b"{}", APP_TOKEN)[0] == 200


def test_by_is_resolved_only_where_the_route_asks(http):
    @http.route("POST", "/api/zz/by")
    def who(req):
        return http.m.json_response({"by": req.by})

    @http.route("POST", "/api/app/zz/keys", access=http.Access.APP, by=False)
    def keys(req):
        return http.m.json_response({"by": req.by})
    base = http.serve(who, keys)
    assert body(request(base, "POST", "/api/zz/by", b'{"by": " ana "}')) == {"by": "ana"}
    assert body(request(base, "POST", "/api/app/zz/keys", b'{"by": "ana"}', APP_TOKEN)) == {"by": ""}


def test_post_parameters_come_from_the_path_as_sent(http):
    @http.route("POST", "/api/zz/{id}/x")
    def h(req):
        return http.m.json_response(req.params)
    assert body(request(http.serve(h), "POST", "/api/zz/a%2Fb/x", b"{}")) == {"id": "a%2Fb"}


def test_a_response_without_a_type_has_neither_type_nor_length(http):
    @http.route("GET", "/api/zz")
    def h(req):
        return http.m.Response(204, ctype=None)
    status, headers, raw = request(http.serve(h), "GET", "/api/zz")
    assert (status, raw) == (204, b"")
    assert "content-type" not in headers and "content-length" not in headers


def test_an_event_stream_answers_with_its_headers(http):
    @http.route("GET", "/api/zz")
    def h(req):
        return http.m.event_stream(lambda out: out.write(b"data: 1\n\n"))
    status, headers, raw = request(http.serve(h), "GET", "/api/zz")
    assert (status, headers["content-type"], raw) == (200, "text/event-stream; charset=utf-8", b"data: 1\n\n")


def test_head_on_a_routed_get_has_no_body(http):
    @http.route("GET", "/api/zz")
    def h(req):
        return http.m.json_response({"a": 1})
    status, headers, raw = request(http.serve(h), "HEAD", "/api/zz")
    assert (status, headers["content-length"], raw) == (200, "8", b"")


def test_handler_errors_map_as_today(http):
    @http.route("GET", "/api/zz/key")
    def key(req):
        raise KeyError("k")

    @http.route("POST", "/api/zz/value")
    def value(req):
        raise ValueError("bad")

    @http.route("GET", "/api/zz/os")
    def os_error(req):
        raise OSError("x")
    base = http.serve(key, value, os_error)
    got = request(base, "GET", "/api/zz/key")
    assert (got[0], body(got)) == (404, {"error": "missing or unknown: 'k'"})
    got = request(base, "POST", "/api/zz/value", b"{}")
    assert (got[0], body(got)) == (400, {"error": "bad"})
    got = request(base, "GET", "/api/zz/os")
    assert (got[0], body(got)) == (500, {"error": "OSError: x"})
