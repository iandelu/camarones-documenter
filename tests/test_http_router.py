"""The project server's router (lib/interfaces/http/router.py): patterns, precedence, the declarations it refuses, and
which area module serves each route of tests/snapshots/routes.json once that area has moved
(docs/superpowers/plans/2026-11-13-hexagonal-f3-http.md, Areas)."""
from __future__ import annotations

import importlib
import json
import re
from pathlib import Path

import pytest

SNAP = {(r["method"], r["path"]): r["access"]
        for r in json.loads((Path(__file__).parent / "snapshots" / "routes.json").read_text(encoding="utf-8"))}

AREA: dict[tuple[str, str], str] = {
    **dict.fromkeys([
        ("GET", "/api/ask"), ("POST", "/api/ask/answer"), ("GET", "/api/check"), ("POST", "/api/commit"),
        ("POST", "/api/confirm"), ("GET", "/api/doc"), ("POST", "/api/doc"), ("POST", "/api/feedback"),
        ("POST", "/api/new"), ("POST", "/api/review/decide"), ("GET", "/api/reviews"), ("GET", "/api/search"),
        ("GET", "/api/status"), ("GET", "/api/tree"),
    ], "docs"),
    **dict.fromkeys([
        ("GET", "/api/kanban"), ("POST", "/api/kanban/add"), ("POST", "/api/kanban/archive"),
        ("POST", "/api/kanban/assign"), ("POST", "/api/kanban/init"), ("GET", "/api/kanban/item"),
        ("POST", "/api/kanban/link"), ("POST", "/api/kanban/move"), ("GET", "/api/kanban/next"),
        ("GET", "/api/kanban/waves"), ("GET", "/api/stories"), ("POST", "/api/stories/analyze"),
        ("GET", "/api/stories/files"), ("GET", "/api/stories/item"), ("POST", "/api/stories/lint"),
        ("POST", "/api/stories/save"), ("POST", "/api/stories/suggest"),
    ], "board"),
    **dict.fromkeys([
        ("POST", "/api/app/onboard/arch"), ("POST", "/api/app/onboard/done"), ("POST", "/api/app/onboard/repos"),
        ("POST", "/api/app/onboard/scan"), ("POST", "/api/app/onboard/setup"), ("GET", "/api/app/onboard/stack"),
        ("POST", "/api/app/onboard/stack"), ("GET", "/api/app/onboard/state"), ("POST", "/api/app/onboard/step"),
        ("GET", "/api/app/onboard/tools"),
    ], "onboard"),
    **dict.fromkeys([
        ("POST", "/api/build"), ("GET", "/api/ci"), ("POST", "/api/ci"), ("GET", "/api/codemap"),
        ("GET", "/api/health"), ("GET", "/api/inventory"), ("POST", "/api/inventory"), ("GET", "/api/schemas"),
        ("POST", "/api/schemas"), ("GET", "/api/viewers"), ("POST", "/api/wiki"), ("GET", "/api/wikis"),
    ], "analysis"),
    **dict.fromkeys([
        ("GET", "/api/app/creds"), ("POST", "/api/app/creds"), ("POST", "/api/app/creds/delete"),
        ("POST", "/api/app/creds/test"), ("GET", "/api/app/doctor"), ("POST", "/api/app/doctor"),
        ("GET", "/api/app/guide"), ("GET", "/api/app/kitdev"), ("POST", "/api/app/kitdev"),
        ("GET", "/api/app/machine"), ("GET", "/api/app/summary"), ("POST", "/api/app/tour-offered"),
    ], "machine"),
    **dict.fromkeys([
        ("POST", "/api/app/agent"), ("GET", "/api/app/agents"), ("GET", "/api/app/terminals"),
        ("POST", "/api/app/terminals"), ("GET", "/api/app/terminals/stream"),
        ("POST", "/api/app/terminals/t-a-1/close"), ("POST", "/api/app/terminals/t-a-1/input"),
        ("POST", "/api/app/terminals/t-a-1/resize"), ("POST", "/api/app/units/u1/handback"),
        ("POST", "/api/app/units/u1/stop"), ("POST", "/api/app/units/u1/takeover"),
    ], "terminals"),
    **dict.fromkeys([
        ("GET", "/api/pipeline"), ("GET", "/api/plan/cost"), ("POST", "/api/plan/cost"), ("GET", "/api/runs"),
        ("POST", "/api/runs"), ("GET", "/api/runs/r1"), ("POST", "/api/runs/r1/cancel"),
        ("GET", "/api/runs/r1/events"), ("POST", "/api/units/approve"), ("POST", "/api/units/retry"),
    ], "runs"),
    **dict.fromkeys([
        ("GET", "/api/interview"), ("POST", "/api/interview/answer"), ("GET", "/api/kpis"),
        ("POST", "/api/kpis/miss"), ("GET", "/api/sync"), ("POST", "/api/sync/share"),
    ], "team"),
    **dict.fromkeys([
        ("POST", "/api/c4/confirm"), ("POST", "/api/c4/element"), ("POST", "/api/c4/relation"),
        ("POST", "/api/c4/remove"), ("GET", "/api/c4/view"),
    ], "architecture"),
    **dict.fromkeys([
        ("GET", "/api/app/adr"), ("GET", "/api/app/adr/0001"), ("GET", "/api/app/adr/0001/pack"),
        ("POST", "/api/app/adr/accept"), ("POST", "/api/app/adr/attendees"), ("GET", "/api/app/adr/candidates"),
        ("POST", "/api/app/adr/new"), ("POST", "/api/app/adr/pack"), ("POST", "/api/app/adr/part"),
        ("POST", "/api/app/adr/point"), ("POST", "/api/app/adr/reject"), ("POST", "/api/app/adr/review"),
        ("POST", "/api/app/adr/write"),
    ], "adr"),
    **dict.fromkeys([
        ("GET", "/api/app/catalog"), ("POST", "/api/app/cmd"), ("GET", "/api/app/info"),
    ], "app_cmd"),
    **dict.fromkeys([
        ("POST", "/api/app/jobs/j1/cancel"), ("GET", "/api/app/jobs/j1/events"), ("GET", "/api/jobs"),
        ("GET", "/api/jobs/j1"),
    ], "jobs"),
}

MOVED: set[str] = {"docs", "board", "onboard", "analysis", "machine"}


@pytest.fixture
def router():
    return importlib.import_module("lib.interfaces.http.router")


def make(router, method, pattern, **kw):
    def handler(req):
        return None
    return router.route(method, pattern, **kw)(handler)


def routes_of(*fns):
    return [r for f in fns for r in f.__routes__]


def test_parameters_come_from_the_path(router):
    r = router.Router(routes_of(make(router, "POST", "/api/app/units/{uid}/{action:takeover|handback|stop}",
                                     access=router.Access.APP, by=False)))
    assert r.match("POST", "/api/app/units/a%2Fb/stop").params == {"uid": "a%2Fb", "action": "stop"}
    assert r.match("POST", "/api/app/units/a/b/stop") is None
    assert r.match("POST", "/api/app/units/a/rename") is None


@pytest.mark.parametrize("winner, loser, path", [
    ("/api/x/candidates", "/api/x/{id}", "/api/x/candidates"),
    ("/", "/{rest:.*}", "/"),
    ("/raw/wikis/{rest:.*}", "/raw/{rest:.*}", "/raw/wikis/api/a.png"),
    ("/next/{rest:.*}", "/{rest:.*}", "/next/a"),
])
def test_the_most_specific_route_wins(router, winner, loser, path):
    r = router.Router(routes_of(make(router, "GET", loser), make(router, "GET", winner)))
    assert r.match("GET", path).route.pattern == winner
    assert [m.route.pattern for m in r.candidates("GET", path)] == [winner, loser]


def test_a_path_under_api_matches_only_api_patterns(router):
    r = router.Router(routes_of(make(router, "GET", "/{rest:.*}")))
    assert r.match("GET", "/api/x") is None
    assert r.match("GET", "/x").params == {"rest": "x"}


def test_the_method_is_part_of_the_route(router):
    r = router.Router(routes_of(make(router, "GET", "/api/x")))
    assert r.match("POST", "/api/x") is None
    assert r.match("GET", "/api/x").params == {}


@pytest.mark.parametrize("method, pattern, kw", [
    ("PUT", "/api/x", {}),
    ("GET", "/api/x", {"access": "nobody"}),
    ("GET", "api/x", {}),
    ("GET", "/api/app/x", {}),
    ("POST", "/api/x", {"access": "portal"}),
    ("POST", "/api/x", {"refusal": "no"}),
    ("GET", "/api/x", {"by": False}),
    ("POST", "/api/x", {"static": True}),
    ("GET", "/api/{x", {}),
    ("GET", "/api/x}", {}),
    ("GET", "/api/{a{b}}", {}),
])
def test_bad_declarations_are_refused(router, method, pattern, kw):
    with pytest.raises(ValueError, match=re.escape(pattern)):
        make(router, method, pattern, **kw)


def test_a_repeated_route_is_refused(router):
    with pytest.raises(ValueError, match="/api/x"):
        router.Router(routes_of(make(router, "GET", "/api/x"), make(router, "GET", "/api/x")))


def test_one_function_carries_several_routes(router):
    @router.route("POST", "/api/app/terminals", access=router.Access.APP)
    @router.route("POST", "/api/app/agent", access=router.Access.APP)
    def handler(req):
        return None
    assert {(r.pattern, r.handler) for r in handler.__routes__} == {("/api/app/terminals", handler),
                                                                    ("/api/app/agent", handler)}


def test_the_table_is_sorted(router):
    r = router.Router(routes_of(make(router, "POST", "/api/b"), make(router, "GET", "/api/b"),
                                make(router, "GET", "/api/a")))
    assert r.table() == [{"method": "GET", "pattern": "/api/a", "access": "public"},
                         {"method": "GET", "pattern": "/api/b", "access": "public"},
                         {"method": "POST", "pattern": "/api/b", "access": "public"}]


def test_every_snapshot_route_has_an_area():
    assert set(AREA) == set(SNAP)


def test_moved_areas_are_routed(kit):
    loaded = importlib.import_module("lib.interfaces.http.router").load()
    for (method, path), area in sorted(AREA.items()):
        if area not in MOVED:
            continue
        hit = loaded.match(method, path)
        assert hit, f"{method} {path} is not routed"
        assert (hit.route.access, hit.route.handler.__module__) == (
            SNAP[(method, path)], f"lib.interfaces.http.routes.{area}"), f"{method} {path}"


def test_every_declared_api_route_is_in_the_snapshot(kit):
    router = importlib.import_module("lib.interfaces.http.router")
    for route in router.load().routes:
        if not route.pattern.startswith("/api/"):
            continue
        one = router.Router([route])
        access = {a for (m, p), a in SNAP.items() if m == route.method and one.match(m, p)}
        assert access == {route.access}, f"{route.method} {route.pattern}: the snapshot says {access or 'nothing'}"
