"""The start gate (`ops.move` to In Progress) and `board next` / `board waves`."""
from __future__ import annotations

import json
import subprocess

import pytest


@pytest.fixture
def board(kit):
    subprocess.run(["git", "init", "-q", str(kit.root)], check=True)
    from lib.kanban import ops
    ops.init(log=lambda _: None)
    return ops


def two_on_one_file(ops):
    ops.add("task", "First", touches=["api:a.py"])
    ops.add("task", "Second", touches=["api:a.py"])
    ops.move("WI-1", "In Progress")


def test_person_is_warned_then_can_force(board):
    two_on_one_file(board)
    with pytest.raises(board.GateError) as err:
        board.move("WI-2", "In Progress")
    assert err.value.blocked_by == [{"id": "WI-1", "kind": "conflict", "files": ["api:a.py"]}]
    assert isinstance(err.value, board.BoardError)
    assert "WI-1" in str(err.value) and "api:a.py" in str(err.value)
    assert board.show("WI-2")["status"] == "Backlog"                  # a refusal changes nothing
    for surface in ("cli", "portal", "app"):
        assert surface in board.HUMAN
    assert board.move("WI-2", "In Progress", force=True)["status"] == "In Progress"


def test_a_forced_move_is_counted(board, kit):
    kit.usage.set_enabled(True)
    two_on_one_file(board)
    board.move("WI-2", "In Progress", force=True, surface="portal")
    data = json.loads((kit.usage.DIR / f"{kit.usage.me()}.json").read_text(encoding="utf-8"))
    events = {k: v for m in data["months"].values() for k, v in m["events"].items()}
    assert events["board:move-forced:portal"] == 1
    assert "board:move-forced:cli" not in events                      # WI-1's clean move is not a forced one


def test_agents_are_always_refused(board):
    two_on_one_file(board)
    for surface in ("mcp", "harness"):
        assert surface in board.AGENT
        with pytest.raises(board.GateError) as err:
            board.move("WI-2", "In Progress", surface=surface, force=True)
        assert err.value.blocked_by[0]["id"] == "WI-1"
    assert board.show("WI-2")["status"] == "Backlog"


def test_an_agent_counts_a_card_without_touches_as_its_whole_repo(board):
    board.add("task", "Declared", touches=["api:a.py"])
    board.add("task", "Open", repos=["api"])
    board.move("WI-1", "In Progress")
    with pytest.raises(board.GateError):
        board.move("WI-2", "In Progress", surface="mcp")
    assert board.move("WI-2", "In Progress")["status"] == "In Progress"       # a person: no declared overlap


def test_dependency_not_done_blocks(board):
    board.add("task", "First")
    board.add("task", "Second", dependencies=["WI-1"])
    with pytest.raises(board.GateError) as err:
        board.move("WI-2", "In Progress")
    assert err.value.blocked_by == [{"id": "WI-1", "kind": "dependency"}]
    board.move("WI-1", "Done")
    assert board.move("WI-2", "In Progress")["status"] == "In Progress"


def test_archived_dependency_does_not_block(board):
    board.add("task", "Old")
    board.add("task", "New", dependencies=["WI-1"])
    board.archive("WI-1")
    assert board.move("WI-2", "In Progress")["status"] == "In Progress"


def test_a_card_edited_a_moment_ago_is_judged_on_its_file(board):
    two_on_one_file(board)
    board.update_item("WI-2", touches=["api:other.py"])
    assert board.move("WI-2", "In Progress")["status"] == "In Progress"


def test_the_gate_runs_only_when_entering_in_progress(board):
    two_on_one_file(board)
    board.move("WI-2", "In Progress", force=True)
    assert board.move("WI-2", "In Progress")["status"] == "In Progress"       # already there: nothing to judge
    assert board.move("WI-2", "Blocked")["status"] == "Blocked"
    assert board.move("WI-2", "In Review")["status"] == "In Review"


def test_the_gate_still_judges_when_the_index_cannot_be_opened(board, monkeypatch):
    two_on_one_file(board)
    from lib.kanban import index

    def broken():
        raise OSError("disk gone")
    monkeypatch.setattr(index, "connect", broken)
    with pytest.raises(board.GateError) as err:
        board.move("WI-2", "In Progress")
    assert err.value.blocked_by == [{"id": "WI-1", "kind": "conflict", "files": ["api:a.py"]}]


def test_move_without_collision_is_unchanged(board):
    board.add("task", "One")
    board.add("task", "Two")
    row = board.move("WI-2", "In Progress")
    assert row["status"] == "In Progress" and row["ordinal"] == 1000
    item = board.load_state()[1]["WI-2"]
    assert item.fm["status"] == "In Progress" and item.fm["ordinal"] == 1000 and item.fm["assignee"] == []
    cards = board.load_state()[0]
    assert cards["WI-2"]["status"] == "In Progress" and cards["WI-2"]["ordinal"] == 1000
    assert board.move("WI-1", "In Progress")["ordinal"] == 2000       # a 4.x board (no touches) still moves freely


def test_next_respects_waves_and_in_progress(board):
    board.add("task", "Running", touches=["api:a.py"])
    board.add("task", "Collides", touches=["api:a.py"], priority="P0")
    board.add("task", "Free first", touches=["api:b.py"], priority="P1")
    board.add("task", "Free second", touches=["api:b.py"], priority="P2")
    board.add("task", "After", touches=["web:c.js"], dependencies=["WI-1"])
    board.move("WI-1", "In Progress")
    got = board.next_items(10)
    assert [(r["id"], r["wave"]) for r in got["ready"]] == [("WI-3", 0), ("WI-4", 1)]
    assert got["ready"][0]["title"] == "Free first" and got["ready"][0]["status"] == "Backlog"
    assert got["waiting"] == [
        {"id": "WI-2", "blocked_by": [{"id": "WI-1", "kind": "conflict", "files": ["api:a.py"]}]},
        {"id": "WI-5", "blocked_by": [{"id": "WI-1", "kind": "dependency"}]}]
    assert [r["id"] for r in board.next_items(1)["ready"]] == ["WI-3"]


def test_next_is_scoped_to_a_story_or_epic(board):
    board.add("epic", "Epic")
    board.add("story", "Story", parent="WI-1")
    board.add("task", "In story", parent="WI-2", touches=["api:a.py"])
    board.add("task", "Elsewhere", touches=["api:z.py"])
    ids = lambda **kw: {r["id"] for r in board.next_items(10, **kw)["ready"]}      # noqa: E731
    assert ids(story="WI-2") == {"WI-2", "WI-3"}
    assert "WI-4" not in ids(story="WI-2") and "WI-4" not in ids(epic="WI-1")
    assert "WI-3" in ids(epic="WI-1") and "WI-3" not in ids(story="WI-4")
    with pytest.raises(board.BoardError):
        board.next_items(story="WI-99")


def test_waves_groups_what_can_run_together(board):
    board.add("task", "A", touches=["api:a.py"])
    board.add("task", "B", touches=["api:a.py"])
    board.add("task", "C", touches=["web:c.js"])
    board.add("task", "Done one", touches=["web:c.js"])
    board.move("WI-4", "Done")
    got = board.waves()
    assert [[r["id"] for r in w] for w in got["waves"]] == [["WI-1", "WI-3"], ["WI-2"]]
    assert got["waves"][0][0]["title"] == "A"


def test_waves_reports_cycles(board):
    board.add("task", "A")
    board.add("task", "B", dependencies=["WI-1"])
    item = board.load_state()[1]["WI-1"]
    item.fm["dependencies"] = ["WI-2"]
    board.save_item(item)
    assert board.waves() == {"cycle": ["WI-1", "WI-2"]}
