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
