"""MCP read tools for the board: `board_next` and `board_waves`. Agents learn which tasks they may start without
colliding with work in progress; they never move cards."""
from __future__ import annotations

import importlib
import json
import subprocess

import pytest


@pytest.fixture
def mcp(kit):
    (kit.root / "docs").mkdir(exist_ok=True)           # `tools/call` needs a project: workspace.yaml and docs/
    return importlib.import_module("lib.mcp")


@pytest.fixture
def board(kit):
    subprocess.run(["git", "init", "-q", str(kit.root)], check=True)
    from lib.kanban import ops
    ops.init(log=lambda _: None)
    return ops


def call(mcp, name, **args):
    reply = mcp.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": name, "arguments": args}})
    result = reply["result"]
    return result["content"][0]["text"], result["isError"]


def ids(rows):
    return [r["id"] for r in rows]


def test_tools_are_listed_and_say_agents_cannot_move_cards(mcp):
    tools = {t["name"]: t for t in mcp.TOOLS}
    assert {"board_next", "board_waves"} <= set(tools) and {"board_next", "board_waves"} <= set(mcp.HANDLERS)
    for name in ("board_next", "board_waves"):
        text = tools[name]["description"].lower()
        assert "cannot move" in text and "person" in text and "gate" in text
        assert tools[name]["inputSchema"]["type"] == "object"
    assert "may start" in tools["board_next"]["description"]
    assert set(tools["board_next"]["inputSchema"]["properties"]) == {"n", "story", "epic"}
    assert set(tools["board_waves"]["inputSchema"]["properties"]) == {"story", "epic"}
    listed = mcp.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})["result"]["tools"]
    assert {"board_next", "board_waves"} <= {t["name"] for t in listed}


def test_board_next_omits_a_task_that_collides_with_work_in_progress(board, mcp):
    board.add("task", "Running", touches=["api:a.py"])
    board.add("task", "Clashes", touches=["api:a.py"])
    board.add("task", "Free", touches=["web:b.js"])
    board.move("WI-1", "In Progress")
    text, err = call(mcp, "board_next")
    got = json.loads(text)
    assert not err and ids(got["ready"]) == ["WI-3"]
    assert [w["id"] for w in got["waiting"]] == ["WI-2"]
    assert got["waiting"][0]["blocked_by"][0]["id"] == "WI-1"


def test_board_next_never_hands_out_two_tasks_on_the_same_file(board, mcp):
    board.add("task", "One", touches=["api:a.py"])
    board.add("task", "Two", touches=["api:a.py"])
    got = json.loads(call(mcp, "board_next")[0])
    assert ids(got["ready"]) == ["WI-1"]
    assert got["waiting"] == [{"id": "WI-2", "blocked_by": [{"kind": "wave", "wave": 1}]}]


def test_board_next_judges_an_item_without_touches_as_its_whole_repo(board, mcp):
    board.add("task", "Declared", touches=["api:a.py"])
    board.add("task", "Open", repos=["api"])
    board.move("WI-1", "In Progress")
    got = json.loads(call(mcp, "board_next")[0])
    assert got["ready"] == [] and ids([{"id": w["id"]} for w in got["waiting"]]) == ["WI-2"]


def test_board_next_n_defaults_to_3_and_is_clamped(board, mcp):
    for i in range(25):
        board.add("task", f"T{i}", touches=[f"api:f{i}.py"])
    assert len(json.loads(call(mcp, "board_next")[0])["ready"]) == 3
    assert len(json.loads(call(mcp, "board_next", n=0)[0])["ready"]) == 1
    assert len(json.loads(call(mcp, "board_next", n=-5)[0])["ready"]) == 1
    assert len(json.loads(call(mcp, "board_next", n=7)[0])["ready"]) == 7
    assert len(json.loads(call(mcp, "board_next", n=500)[0])["ready"]) == 20
    assert len(json.loads(call(mcp, "board_next", n="4")[0])["ready"]) == 4


@pytest.mark.parametrize("bad", ["many", None, 2.5, [1], True, "--5", "²", "4.0", ""])
def test_board_next_a_bad_n_is_a_plain_message(board, mcp, bad):
    text, err = call(mcp, "board_next", n=bad)
    assert not err and "n must be an integer" in text and "Traceback" not in text


def test_board_next_scoped_to_a_story_and_unknown_story(board, mcp):
    board.add("story", "Checkout")
    board.add("task", "In story", parent="WI-1", touches=["api:a.py"])
    board.add("task", "Elsewhere", touches=["web:b.js"])
    assert ids(json.loads(call(mcp, "board_next", story="WI-1")[0])["ready"]) == ["WI-2"]
    text, err = call(mcp, "board_next", story="WI-99")
    assert not err and "WI-99" in text and not text.startswith("{") and "Traceback" not in text


def test_board_next_scoped_to_an_epic(board, mcp):
    board.add("epic", "Epic")
    board.add("story", "Story", parent="WI-1")
    board.add("task", "In epic", parent="WI-2", touches=["api:a.py"])
    board.add("task", "Elsewhere", touches=["web:b.js"])
    assert ids(json.loads(call(mcp, "board_next", epic="WI-1")[0])["ready"]) == ["WI-3"]
    text, err = call(mcp, "board_next", story="WI-2", epic="WI-1")
    assert not err and "either a story or an epic" in text and not text.startswith("{")


def test_board_waves(board, mcp):
    board.add("task", "First", touches=["api:a.py"])
    board.add("task", "Second", touches=["api:a.py"])
    board.add("task", "Third", touches=["web:b.js"])
    text, err = call(mcp, "board_waves")
    got = json.loads(text)
    assert not err and [ids(w) for w in got["waves"]] == [["WI-1", "WI-3"], ["WI-2"]]


def test_board_waves_reports_a_cycle(board, mcp):
    board.add("task", "A")
    board.add("task", "B", dependencies=["WI-1"])
    item = board.load_state()[1]["WI-1"]
    item.fm["dependencies"] = ["WI-2"]
    board.save_item(item)
    assert json.loads(call(mcp, "board_waves")[0]) == {"cycle": ["WI-1", "WI-2"]}


def test_board_waves_story_and_epic_together_is_a_plain_message(board, mcp):
    board.add("task", "A")
    text, err = call(mcp, "board_waves", story="WI-1", epic="WI-1")
    assert not err and "either a story or an epic" in text and not text.startswith("{")


def test_no_board_is_a_plain_message_not_an_exception(kit, mcp):
    for name in ("board_next", "board_waves"):
        text, err = call(mcp, name)
        assert not err and text.startswith("No board here:") and "\n" not in text and "Traceback" not in text
        assert "camaron board init" in text
