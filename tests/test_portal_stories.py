"""The board's start gate over HTTP: a refused move is a 409 with the blockers, `force` moves it anyway, and the board
carries each card's wave and blockers. Reuses the server of test_portal_kanban."""
from __future__ import annotations

import pytest

from test_portal_kanban import APP, PORTAL, call, server  # noqa: F401  (server is a fixture)


@pytest.fixture
def ops(wired):
    from lib.kanban import ops
    ops.init(log=lambda *_: None)
    return ops


def collide(ops):
    ops.add("task", "First", touches=["api:a.py"])
    ops.add("task", "Second", touches=["api:a.py"])
    ops.move("WI-1", "In Progress")


def cycle(ops):
    ops.add("task", "A")
    ops.add("task", "B", dependencies=["WI-1"])
    item = ops.load_state()[1]["WI-1"]
    item.fm["dependencies"] = ["WI-2"]
    ops.save_item(item)


def get(server, path, token=None):
    return call(server + path, method="GET", token=token)


def test_a_move_into_a_collision_is_a_409_with_the_blockers(ops, server):
    collide(ops)
    code, body = call(server + "/api/kanban/move", {"id": "WI-2", "status": "In Progress"}, token=PORTAL)
    assert code == 409
    assert body["blocked_by"] == [{"id": "WI-1", "kind": "conflict", "files": ["api:a.py"]}]
    assert "WI-1" in body["error"]
    assert ops.show("WI-2")["status"] == "Backlog"                       # a refusal changes nothing on disk
    assert ops.load_state()[0]["WI-2"]["status"] == "Backlog"


def test_the_same_move_with_force_goes_through(ops, server):
    collide(ops)
    code, row = call(server + "/api/kanban/move", {"id": "WI-2", "status": "In Progress", "force": True}, token=PORTAL)
    assert code == 200 and row["status"] == "In Progress"
    assert ops.show("WI-2")["status"] == "In Progress"


def test_the_app_can_force_too(ops, server, wired, monkeypatch):
    monkeypatch.setattr(wired.serve, "APP_TOKEN", APP)
    collide(ops)
    assert call(server + "/api/kanban/move", {"id": "WI-2", "status": "In Progress"}, token=APP)[0] == 409
    code, row = call(server + "/api/kanban/move", {"id": "WI-2", "status": "In Progress", "force": True}, token=APP)
    assert code == 200 and row["status"] == "In Progress"


def test_force_only_counts_when_it_is_true(ops, server):
    collide(ops)
    for odd in ("true", 1, "yes", None, False):
        code, _ = call(server + "/api/kanban/move", {"id": "WI-2", "status": "In Progress", "force": odd}, token=PORTAL)
        assert code == 409, odd


def test_a_move_without_collision_is_unchanged(ops, server):
    ops.add("task", "One")
    code, row = call(server + "/api/kanban/move", {"id": "WI-1", "status": "In Progress"}, token=PORTAL)
    assert code == 200 and row["status"] == "In Progress" and row["ordinal"] == 1000


def test_other_board_errors_stay_400_and_no_token_stays_403(ops, server):
    collide(ops)
    assert call(server + "/api/kanban/move", {"id": "WI-2", "status": "Nope"}, token=PORTAL)[0] == 400
    assert call(server + "/api/kanban/move", {"id": "WI-99", "status": "Done"}, token=PORTAL)[0] == 400
    code, body = call(server + "/api/kanban/move", {"id": "WI-2", "status": "In Progress", "force": True})
    assert code == 403 and body["token"] is True
    assert ops.show("WI-2")["status"] == "Backlog"


def test_board_rows_carry_wave_and_blockers(ops, server):
    ops.add("task", "Running", touches=["api:a.py"])             # WI-1
    ops.add("task", "Collides", touches=["api:a.py"])            # WI-2
    ops.add("task", "Free", touches=["api:b.py"])                # WI-3
    ops.add("task", "Waits", dependencies=["WI-3"])              # WI-4
    ops.add("story", "Story")                                    # WI-5
    ops.add("task", "Child", parent="WI-5", touches=["api:c.py"])    # WI-6
    ops.move("WI-1", "In Progress")
    ops.move("WI-3", "Done")
    code, b = get(server, "/api/kanban")
    assert code == 200
    cards = {c["id"]: c for c in b["cards"]}
    assert cards["WI-2"]["blocked_by"] == [{"id": "WI-1", "kind": "conflict", "files": ["api:a.py"]}]
    assert cards["WI-4"]["blocked_by"] == []                     # its dependency is Done
    assert cards["WI-1"]["blocked_by"] == []                     # In Progress: nothing to gate any more
    assert cards["WI-1"]["wave"] == 0 and cards["WI-2"]["wave"] == 1
    assert cards["WI-3"]["wave"] is None and cards["WI-3"]["blocked_by"] == []        # Done
    assert cards["WI-5"]["wave"] is None and cards["WI-5"]["blocked_by"] == []        # a container
    assert cards["WI-6"]["wave"] == 0
    assert all("wave" in c and "blocked_by" in c for c in b["cards"])


def test_a_waiting_dependency_is_listed_and_waves_after_it(ops, server):
    ops.add("task", "First")
    ops.add("task", "Second", dependencies=["WI-1"])
    cards = {c["id"]: c for c in get(server, "/api/kanban")[1]["cards"]}
    assert cards["WI-2"]["blocked_by"] == [{"id": "WI-1", "kind": "dependency"}]
    assert (cards["WI-1"]["wave"], cards["WI-2"]["wave"]) == (0, 1)


def test_a_cycle_leaves_every_wave_null(ops, server):
    cycle(ops)
    code, b = get(server, "/api/kanban")
    assert code == 200
    assert [c["wave"] for c in b["cards"]] == [None, None]


def test_the_board_loads_when_the_index_cannot_open(ops, server, monkeypatch):
    collide(ops)
    from lib.kanban import index

    def broken():
        raise OSError("disk gone")
    monkeypatch.setattr(index, "connect", broken)
    code, b = get(server, "/api/kanban")
    assert code == 200 and [c["id"] for c in b["cards"]] == ["WI-1", "WI-2"] or code == 200
    assert {c["id"]: (c["wave"], c["blocked_by"]) for c in b["cards"]} == {"WI-1": (None, []), "WI-2": (None, [])}


def test_the_board_loads_when_there_is_no_board(wired, server):
    import shutil
    shutil.rmtree(wired.root / "backlog")
    code, b = get(server, "/api/kanban")
    assert code == 200 and b["enabled"] is False and b["cards"] == []


def test_next_is_the_peoples_view(ops, server):
    ops.add("task", "Running", touches=["api:a.py"])
    ops.add("task", "Collides", touches=["api:a.py"])
    ops.add("task", "Free", touches=["api:b.py"])
    ops.add("task", "Open", repos=["api"])                        # no declared files: an agent would count the whole repo
    ops.move("WI-1", "In Progress")
    code, b = get(server, "/api/kanban/next?n=5")
    assert code == 200
    assert [r["id"] for r in b["ready"]] == ["WI-3", "WI-4"]      # WI-4 would wait for an agent
    assert all(isinstance(r["wave"], int) for r in b["ready"])
    assert b["waiting"] == [{"id": "WI-2", "blocked_by": [{"id": "WI-1", "kind": "conflict", "files": ["api:a.py"]}]}]
    assert [r["id"] for r in get(server, "/api/kanban/next?n=1")[1]["ready"]] == ["WI-3"]
    assert len(get(server, "/api/kanban/next")[1]["ready"]) == 2          # n defaults to 3


def test_next_can_be_scoped_and_bad_input_is_a_400(ops, server):
    ops.add("story", "Story")
    ops.add("task", "Inside", parent="WI-1", touches=["api:a.py"])
    ops.add("task", "Outside", touches=["api:b.py"])
    assert [r["id"] for r in get(server, "/api/kanban/next?story=WI-1")[1]["ready"]] == ["WI-2"]
    assert get(server, "/api/kanban/next?story=WI-99")[0] == 400
    assert get(server, "/api/kanban/next?story=WI-1&epic=WI-1")[0] == 400
    assert get(server, "/api/kanban/next?n=lots")[0] == 400


def test_waves_shape(ops, server):
    ops.add("task", "A", touches=["api:a.py"])
    ops.add("task", "B", touches=["api:a.py"])
    ops.add("task", "C", touches=["api:c.py"])
    code, b = get(server, "/api/kanban/waves")
    assert code == 200
    assert [[r["id"] for r in w] for w in b["waves"]] == [["WI-1", "WI-3"], ["WI-2"]]
    assert get(server, "/api/kanban/waves?story=WI-99")[0] == 400


def test_waves_reports_a_cycle(ops, server):
    cycle(ops)
    code, b = get(server, "/api/kanban/waves")
    assert code == 200 and sorted(b["cycle"]) == ["WI-1", "WI-2"] and "waves" not in b


# ── the stories API (spec §8.1) ──────────────────────────────────────────────────────────────────────────────────

SRC = "src/main/java/demo/"
ORDERS, PAY = f"api:{SRC}Orders.java", f"api:{SRC}Pay.java"
CLAUSES = {"as": "responsable de pedidos", "want": "cobrar los pedidos con tarjeta", "so": "no perder ventas"}
K1 = "change:api:orders"


@pytest.fixture
def world(ops, wired):
    """A board with real files in the `api` repo and a code map with groups; returns the kit."""
    from test_codemap import write_graph
    write_graph(wired)
    for name in ("Orders", "Pay"):
        f = wired.ws / "api" / SRC / f"{name}.java"
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(f"class {name} {{}}\n", encoding="utf-8")
    return wired


def tree(root):
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in (root / "backlog").rglob("*") if p.is_file()}


def story(**kw):
    return {"story": {**CLAUSES, "criteria": ["Dado un pedido, cuando pago, entonces veo el recibo"],
                      "touches": [ORDERS, PAY], **kw}}


def one_task(key=K1, touches=(ORDERS,)):
    return {"key": key, "kind": "change", "title": "Orders: cobrar", "group": "orders", "touches": list(touches),
            "criteria": [], "deps": [], "conflicts": [], "wave": 0, "edited": True, "added": [], "dropped": []}


def post(server, path, body, token=None):
    return call(server + path, body, token=token)


def test_the_list_needs_no_token_and_carries_the_lint_words(world, server):
    code, b = get(server, "/api/stories")
    assert code == 200
    assert b["enabled"] is True and b["writable"] is False and b["stories"] == []
    assert b["ai"] == {"available": False, "runner": None, "model": None}
    from lib import stories
    assert b["lint_words"] == {"es": stories.lint_words("es"), "en": stories.lint_words("en")}
    assert get(server, "/api/stories", token=PORTAL)[1]["writable"] is True


def test_the_list_without_a_board_is_empty(world, server):
    import shutil
    shutil.rmtree(world.root / "backlog")
    code, b = get(server, "/api/stories")
    assert code == 200 and b["enabled"] is False and b["stories"] == []


def test_save_needs_the_token_and_writes_nothing_without_it(world, server):
    before = tree(world.root)
    code, b = post(server, "/api/stories/save", {**story(), "tasks": [one_task()]})
    assert code == 403 and b["token"] is True and "error" in b
    assert post(server, "/api/stories/save", {**story(), "tasks": []}, token="nope")[0] == 403
    assert tree(world.root) == before


def test_analyze_needs_no_token_and_leaves_the_backlog_alone(world, server):
    before = tree(world.root)
    code, b = post(server, "/api/stories/analyze", story())
    assert code == 200
    assert set(b) >= {"hints", "invest", "tasks", "waves", "conflicts", "cycle"}
    assert b["invest"]["verdict"] in ("good", "improve", "poor") and b["tasks"]
    assert tree(world.root) == before


def test_analyze_keeps_the_tasks_a_person_edited(world, server):
    code, b = post(server, "/api/stories/analyze", {**story(), "tasks": [one_task()], "removed": ["change:api:pay"]})
    assert code == 200
    assert K1 in [t["key"] for t in b["tasks"]] and "change:api:pay" not in [t["key"] for t in b["tasks"]]


def test_save_with_the_token_writes_the_story_and_its_tasks(world, server):
    code, b = post(server, "/api/stories/save", {**story(), "tasks": [one_task()], "lang": "es"}, token=PORTAL)
    assert code == 200
    assert b["story"]["id"] == "WI-1" and [t["id"] for t in b["tasks"]] == ["WI-2"]
    files = sorted(p.name for p in (world.root / "backlog" / "tasks").glob("*.md"))
    assert len(files) == 2 and files[0].startswith("wi-1 - ") and files[1].startswith("wi-2 - ")
    code, listed = get(server, "/api/stories")
    assert [s["id"] for s in listed["stories"]] == ["WI-1"] and listed["stories"][0]["progress"] == {"done": 0, "total": 1}


def test_save_by_the_app_works_too(world, server, wired, monkeypatch):
    monkeypatch.setattr(wired.serve, "APP_TOKEN", APP)
    code, b = post(server, "/api/stories/save", {**story(), "tasks": []}, token=APP)
    assert code == 200 and b["story"]["id"] == "WI-1"


def test_the_story_as_the_page_sends_it_also_takes_as_underscore(world, server):
    body = story()
    body["story"]["as_"] = body["story"].pop("as")
    assert post(server, "/api/stories/analyze", body)[0] == 200


def test_item_returns_the_story_with_its_fingerprint(world, server):
    post(server, "/api/stories/save", {**story(), "tasks": [one_task()]}, token=PORTAL)
    code, b = get(server, "/api/stories/item?id=WI-1")
    assert code == 200 and b["id"] == "WI-1" and b["want"] == CLAUSES["want"] and b["sha"]
    assert [s["id"] for s in b["subtasks"]] == ["WI-2"]


def test_an_unknown_item_is_a_404(world, server):
    code, b = get(server, "/api/stories/item?id=WI-99")
    assert code == 404 and "WI-99" in b["error"]
    assert get(server, "/api/stories/item")[0] == 404


def test_a_stale_base_sha_is_a_409(world, server):
    post(server, "/api/stories/save", {**story(), "tasks": []}, token=PORTAL)
    sha = get(server, "/api/stories/item?id=WI-1")[1]["sha"]
    edited = story(id="WI-1", want="cobrar los pedidos con bizum")
    assert post(server, "/api/stories/save", {**edited, "tasks": [], "base_sha": sha}, token=PORTAL)[0] == 200
    before = tree(world.root)
    stale = story(id="WI-1", want="cobrar los pedidos a plazos")
    code, b = post(server, "/api/stories/save", {**stale, "tasks": [], "base_sha": sha}, token=PORTAL)
    assert code == 409 and b["id"] == "WI-1" and "WI-1" in b["error"]
    assert tree(world.root) == before


@pytest.mark.parametrize("path", ["/api/stories/analyze", "/api/stories/save"])
@pytest.mark.parametrize("bad", [{"want": ""}, {"want": "   "}, {"want": None}, {"want": 3}])
def test_a_story_without_a_want_is_a_400(world, server, path, bad):
    s = story()
    s["story"].update(bad)
    s["tasks"] = []
    code, b = post(server, path, s, token=PORTAL)
    assert code == 400 and "want" in b["error"]


def test_bad_bodies_are_400s(world, server):
    for body in ({}, {"story": "text"}, {"story": ["x"]}, {**story(), "tasks": "no"}, {**story(), "tasks": ["x"]},
                 {**story(), "removed": "no"}, story(touches="api:x"), {**story(), "lang": 4}):
        assert post(server, "/api/stories/analyze", body)[0] == 400, body
    assert post(server, "/api/stories/save", {**story(), "tasks": [], "docs": "no"}, token=PORTAL)[0] == 400
    assert post(server, "/api/stories/save", {**story(), "tasks": [], "base_sha": 4}, token=PORTAL)[0] == 400


def test_other_board_errors_on_save_are_400s_and_write_nothing(world, server):
    before = tree(world.root)
    bad = story(touches=["api:src/nope/Missing.java"])
    code, b = post(server, "/api/stories/save", {**bad, "tasks": []}, token=PORTAL)
    assert code == 400 and "error" in b
    assert post(server, "/api/stories/save", {**story(priority="P9"), "tasks": []}, token=PORTAL)[0] == 400
    assert tree(world.root) == before


def test_a_group_touch_in_analyze_is_a_400(world, server):
    code, b = post(server, "/api/stories/analyze", story(touches=[ORDERS, "api:core/payments"]))
    assert code == 400 and "api:core/payments" in b["error"] and "files" in b["error"]
    code, b = post(server, "/api/stories/analyze", {**story(), "tasks": [one_task(touches=["api:web/web"])]})
    assert code == 400 and "api:web/web" in b["error"]
    # a real file is fine, and so is one that does not exist yet
    assert post(server, "/api/stories/analyze", story(touches=[ORDERS, f"api:{SRC}New.java"]))[0] == 200


def test_the_files_search_returns_groups_with_their_files(world, server):
    code, hits = get(server, "/api/stories/files?q=payment")
    assert code == 200
    file_hit = next(h for h in hits if h["kind"] == "file" and h["touch"].endswith("PaymentClient.java"))
    assert "files" not in file_hit
    group = next(h for h in hits if h["kind"] == "group" and h["touch"] == "api:core/payments")
    assert group["files"] == ["api:api-core/src/main/java/demo/shop/payments/PaymentClient.java"]


def test_the_files_search_limit_is_clamped_and_an_empty_query_is_empty(world, server):
    assert get(server, "/api/stories/files")[1] == [] and get(server, "/api/stories/files?q=%20")[1] == []
    assert len(get(server, "/api/stories/files?q=a&limit=1")[1]) == 1
    assert len(get(server, "/api/stories/files?q=a&limit=0")[1]) == 1              # clamped up to 1
    assert len(get(server, "/api/stories/files?q=a&limit=9999")[1]) <= 50
    assert get(server, "/api/stories/files?q=a&limit=many")[0] == 400


def test_lint_returns_what_stories_lint_returns(world, server):
    from lib import stories
    body = {"as": "usuario", "want": "un botón para exportar", "so": "exportar", "touches": [], "lang": "es"}
    code, b = post(server, "/api/stories/lint", body)
    want = stories.lint("usuario", "un botón para exportar", "exportar", "es", touches=[])
    assert code == 200 and b == {"hints": want} and want
    empty = post(server, "/api/stories/lint", {"as": "", "want": "", "so": "", "lang": "en"})[1]["hints"]
    assert [h["code"] for h in empty] == [h["code"] for h in stories.lint("", "", "", "en")]
    assert post(server, "/api/stories/lint", {"want": 3})[0] == 400


def test_lint_defaults_to_the_project_language(world, server):
    from lib import stories
    from lib.kanban import ops as board
    code, b = post(server, "/api/stories/lint", {"as": "usuario", "want": "un botón", "so": "x"})
    assert code == 200 and b == {"hints": stories.lint("usuario", "un botón", "x", board.docs_lang(), touches=[])}


def test_suggest_is_not_here_yet(world, server):
    assert post(server, "/api/stories/suggest", story(), token=PORTAL)[0] == 404
    assert post(server, "/api/stories/nope", story(), token=PORTAL)[0] == 404


# ── malformed tasks and a project without a board ────────────────────────────────────────────────────────────────

ROUTES = ["/api/stories/analyze", "/api/stories/save"]


def with_task(**kw):
    t = one_task()
    for k, v in kw.items():
        if v is KeyError:
            del t[k]
        else:
            t[k] = v
    return {**story(), "tasks": [t]}


@pytest.mark.parametrize("path", ROUTES)
@pytest.mark.parametrize("field", ["touches", "criteria", "deps", "added", "dropped"])
@pytest.mark.parametrize("bad", [5, "api:a.py", {"a": 1}, [1], [None], ["ok", 3]])
def test_a_task_list_field_that_is_not_a_list_of_text_is_a_400(world, server, path, field, bad):
    before = tree(world.root)
    code, b = post(server, path, with_task(**{field: bad}), token=PORTAL)
    assert code == 400 and field in b["error"], (field, bad, code, b)
    assert tree(world.root) == before


@pytest.mark.parametrize("path", ROUTES)
@pytest.mark.parametrize("field", ["key", "title", "group", "kind"])
@pytest.mark.parametrize("bad", [5, ["x"], {"a": 1}, True])
def test_a_task_text_field_that_is_not_text_is_a_400(world, server, path, field, bad):
    code, b = post(server, path, with_task(**{field: bad}), token=PORTAL)
    assert code == 400 and field in b["error"], (field, bad, code, b)


@pytest.mark.parametrize("path", ROUTES)
@pytest.mark.parametrize("bad", ["yes", 1, "false", []])
def test_edited_must_be_a_bool(world, server, path, bad):
    code, b = post(server, path, with_task(edited=bad), token=PORTAL)
    assert code == 400 and "edited" in b["error"]


@pytest.mark.parametrize("path", ROUTES)
@pytest.mark.parametrize("field", ["key", "title"])
def test_a_task_without_a_key_or_title_is_a_400_that_names_it(world, server, path, field):
    for blank in (KeyError, "", "  ", None):
        code, b = post(server, path, with_task(**{field: blank}), token=PORTAL)
        assert code == 400 and field in b["error"], (field, blank, code, b)


@pytest.mark.parametrize("path", ROUTES)
def test_a_well_formed_task_may_leave_the_optional_fields_out(world, server, path):
    t = {"key": K1, "title": "Orders: cobrar", "touches": [ORDERS]}
    code, _ = post(server, path, {**story(), "tasks": [t]}, token=PORTAL)
    assert code == 200


def test_reads_on_a_project_without_a_board(world, server):
    """Search still answers from the code map (a board only adds cards); an item is unknown (404)."""
    import shutil
    shutil.rmtree(world.root / "backlog")
    code, b = get(server, "/api/stories/files?q=zzz-no-such-file")
    assert code == 200 and b == []
    code, hits = get(server, "/api/stories/files?q=payment")
    assert code == 200 and isinstance(hits, list)
    code, b = get(server, "/api/stories/item?id=WI-1")
    assert code == 404 and "error" in b


@pytest.mark.parametrize("bad", ["api:a.py", 5, {"a": 1}, [1], ["ok", None]])
def test_lint_touches_must_be_a_list_of_text(world, server, bad):
    code, b = post(server, "/api/stories/lint", {"as": "a", "want": "b", "so": "c", "touches": bad})
    assert code == 400 and "touches" in b["error"]
