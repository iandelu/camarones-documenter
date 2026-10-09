"""Runner port: agent CLIs behind one interface. `build` pins today's argv; `parse` turns each agent's JSON stream into
normalised events (tool calls, messages, usage); `classify` tells a usage limit from a real failure."""
from __future__ import annotations

import io, json

import pytest

CLAUDE_TOOL = {"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "Read", "input": {"file_path": "a.py"}}]}}

# today's terminal view of each agent's stream: the refactor must not change a character
RENDERED = [
    ("claude", CLAUDE_TOOL, ["· Read a.py"], ""),
    ("claude", {"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "Read", "input": {}}]}}, ["· Read "], ""),
    ("claude", {"type": "assistant", "message": {"content": [{"type": "text", "text": "hello"}]}}, ["» hello"], ""),
    ("claude", {"type": "assistant", "message": {"content": [{"type": "text", "text": "  "}]}}, [], ""),
    ("claude", {"type": "result", "result": "Done", "is_error": False}, [], "Done"),
    ("claude", {"type": "result", "result": "boom", "is_error": True}, ["= error: boom"], "boom"),
    ("claude", {"type": "system", "subtype": "init"}, [], ""),
    ("codex", {"type": "item.started", "item": {"type": "command_execution", "command": "bash -lc 'ls'"}}, ["· $ bash -lc 'ls"], ""),
    ("codex", {"type": "item.completed", "item": {"type": "agent_message", "text": "hi"}}, ["» hi"], ""),
    ("codex", {"type": "item.completed", "item": {"type": "file_change", "changes": [{"path": "a.md"}, {"path": "b.md"}]}},
     ["· edit a.md", "· edit b.md"], ""),
    ("codex", {"type": "item.completed", "item": {"type": "mcp_tool_call", "server": "camarones", "tool": "search_docs"}},
     ["· camarones.search_docs"], ""),
    ("codex", {"type": "turn.failed", "error": {"message": "usage limit"}}, ["= error: usage limit"], "usage limit"),
    ("codex", {"type": "error", "message": "x"}, ["= error: x"], "x"),
    ("codex", {"type": "thread.started"}, [], ""),
]


@pytest.mark.parametrize("agent,event,shown,err", RENDERED)
def test_terminal_view_of_the_stream_is_unchanged(kit, agent, event, shown, err):
    assert kit.plan._render(agent, json.dumps(event)) == (shown, err)


@pytest.mark.parametrize("agent", ["claude", "codex"])
def test_plain_text_lines_pass_through(kit, agent):
    assert kit.plan._render(agent, "plain text") == (["plain text"], "plain text")
    assert kit.plan._render(agent, "") == ([], "")


@pytest.fixture
def runners(kit, monkeypatch):
    from lib.adapters import runners
    from lib.adapters.runners import base
    monkeypatch.setattr(base, "which", lambda name: f"/bin/{name}")
    return runners


def test_registry_knows_the_builtin_runners(runners):
    assert [r.id for r in runners.builtin()] == ["claude", "codex"]
    assert runners.get("codex").id == "codex"
    with pytest.raises(KeyError):
        runners.get("nope")


def test_claude_argv_is_todays(runners, kit):
    from lib.harness.ports import RunRequest
    inv = runners.get("claude").build(RunRequest(prompt="Follow the instructions in x.md", cwd=kit.ws, env={"A": "1"}))
    assert inv.argv == ["/bin/claude", "-p", "Follow the instructions in x.md", "--dangerously-skip-permissions",
                        "--output-format", "stream-json", "--verbose"]
    assert inv.cwd == kit.ws and inv.env == {"A": "1"}
    with_model = runners.get("claude").build(RunRequest(prompt="p", cwd=kit.ws, env={}, model="opus"))
    assert with_model.argv[-2:] == ["--model", "opus"]


def test_codex_argv_is_todays(runners, kit):
    from lib.harness.ports import RunRequest
    inv = runners.get("codex").build(RunRequest(prompt="Sigue las instrucciones de x.md", cwd=kit.ws, env={}))
    assert inv.argv == ["/bin/codex", "exec", "--approve-for-me", "--skip-git-repo-check", "--json",
                        "Sigue las instrucciones de x.md"]
    assert runners.get("codex").build(RunRequest(prompt="p", cwd=kit.ws, env={}, model="o5")).argv[-3:] == ["-m", "o5", "p"]


def test_autopilot_session_launches_the_runner_argv(kit, monkeypatch):
    seen = {}

    class FakeProc:
        def __init__(self, cmd, **kw):
            seen["cmd"], seen["kw"] = cmd, kw
            self.stdout = io.StringIO(json.dumps(CLAUDE_TOOL) + "\n")

        def wait(self):
            return 0

        def poll(self):
            return 0
    from lib.adapters.runners import base
    monkeypatch.setattr(base, "which", lambda name: f"/bin/{name}")
    monkeypatch.setattr(kit.plan.subprocess, "Popen", FakeProc)
    echo = []
    r = kit.plan._run_agent("claude", "do it", "en", "discovery:api", echo=echo.append)
    brief = kit.common.ws_rel(kit.common.rel_file(kit.plan.AUTOPILOT_PROMPT))
    assert seen["cmd"] == ["/bin/claude", "-p", f"Follow the instructions in {brief}", "--dangerously-skip-permissions",
                           "--output-format", "stream-json", "--verbose"]
    assert seen["kw"]["cwd"] == str(kit.common.WORKSPACE)
    assert seen["kw"]["env"]["CAMARONES_ROOT"] == str(kit.common.ROOT)
    assert r.returncode == 0 and "  · Read a.py" in echo


def test_claude_result_reports_usage_and_cost(runners):
    ev = {"type": "result", "subtype": "success", "is_error": False, "result": "ok", "total_cost_usd": 0.42,
          "usage": {"input_tokens": 1200, "output_tokens": 300, "cache_read_input_tokens": 5000,
                    "cache_creation_input_tokens": 700}}
    events = runners.get("claude").parse(json.dumps(ev))
    assert {"type": "usage", "in": 1200, "out": 300, "cache_read": 5000, "cache_write": 700, "cost_usd": 0.42} in events
    assert {"type": "result", "text": "ok"} in events


def test_codex_turn_reports_usage(runners):
    ev = {"type": "turn.completed", "usage": {"input_tokens": 900, "cached_input_tokens": 400, "output_tokens": 120}}
    assert runners.get("codex").parse(json.dumps(ev)) == [{"type": "usage", "in": 900, "out": 120, "cache_read": 400}]


def test_parse_normalises_tool_calls_and_file_changes(runners):
    assert runners.get("claude").parse(json.dumps(CLAUDE_TOOL)) == [{"type": "tool.call", "name": "Read", "arg": "a.py"}]
    ev = {"type": "item.completed", "item": {"type": "file_change", "changes": [{"path": "docs/a.md"}]}}
    assert runners.get("codex").parse(json.dumps(ev)) == [{"type": "file.changed", "path": "docs/a.md"}]


@pytest.mark.parametrize("agent", ["claude", "codex"])
def test_classify_tells_limits_from_failures(runners, agent):
    r = runners.get(agent)
    assert r.classify(0, "") == "ok"
    assert r.classify(1, "Claude usage limit reached, resets at 5pm") == "limited"
    assert r.classify(1, "segfault") == "failed"
    assert r.classify(1, "usage limit mentioned early\n" + "x" * 3000) == "failed"     # only the end of the output counts


def test_autopilot_keeps_its_limit_hints(kit):
    from lib.adapters.runners.base import LIMIT_HINTS
    assert kit.plan.LIMIT_HINTS == LIMIT_HINTS

