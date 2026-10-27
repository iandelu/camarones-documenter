"""Sessions opened by hand on the canvas (lib/agents.py with where="canvas"): the same agent inside session_run.py,
now in a terminal the project server holds instead of a window."""
from __future__ import annotations

import os, sys, threading

import pytest

from test_agents import ready_agent_unit, term  # noqa: F401  (fixture)
from test_terminals import ECHO, until


@pytest.fixture
def canvas(wired, term, monkeypatch):                                    # noqa: F811
    from lib import terminals
    from lib.adapters.runners.claude import Claude
    from lib.harness.ports import Invocation
    monkeypatch.setattr(Claude, "build", lambda self, req: Invocation([sys.executable, str(ECHO)], req.cwd, req.env))
    yield term
    terminals.shutdown()


def test_a_unit_opens_as_a_terminal_on_the_canvas(wired, canvas):
    from lib import sessions
    u = ready_agent_unit(wired)
    r = canvas["agents"].launch_unit(u["id"], "claude", lang="en", where="canvas", size=(100, 30))
    assert r["where"] == "canvas" and canvas["cmds"] == []
    t = r["terminal"]
    assert (t["kind"], t["unit"], t["agent"], t["cols"], t["rows"]) == ("unit", u["id"], "claude", 100, 30)
    assert wired.plan.get(wired.plan.load(), u["id"])["status"] == "doing"
    until(lambda: sessions.running(sessions.load(u["id"])))


def test_the_docs_update_opens_as_a_loose_terminal_with_no_record(wired, canvas):
    from lib import sessions
    r = canvas["agents"].launch_update("claude", where="canvas")
    assert (r["terminal"]["kind"], r["terminal"]["unit"]) == ("update", None)
    assert sessions.load("update") is None
    with pytest.raises(canvas["agents"].AlreadyOpen) as e:
        canvas["agents"].launch_update("claude", where="canvas")
    assert e.value.terminal == r["terminal"]["id"]


def test_a_unit_open_on_the_canvas_is_not_opened_again(wired, canvas):
    u = ready_agent_unit(wired)
    first = canvas["agents"].launch_unit(u["id"], "claude", where="canvas")["terminal"]["id"]
    with pytest.raises(canvas["agents"].AlreadyOpen) as e:
        canvas["agents"].launch_unit(u["id"], "claude", mode="continue", where="canvas")
    assert e.value.terminal == first


def test_the_ninth_terminal_is_refused_before_the_unit_moves(wired, canvas, monkeypatch):
    from lib import sessions, terminals
    monkeypatch.setattr(terminals, "MAX_LIVE", 1)
    canvas["agents"].launch_update("claude", where="canvas")
    u = ready_agent_unit(wired)
    with pytest.raises(terminals.Limit):
        canvas["agents"].launch_unit(u["id"], "claude", where="canvas")
    assert wired.plan.get(wired.plan.load(), u["id"])["status"] == "todo" and sessions.load(u["id"]) is None


def test_without_a_terminal_here_the_canvas_falls_back_to_a_window(wired, canvas, monkeypatch):
    from lib import terminals
    monkeypatch.setattr(terminals, "available", lambda: False)
    r = canvas["agents"].launch_unit(ready_agent_unit(wired)["id"], "claude", where="canvas")
    assert (r["where"], r["fallback"]) == ("window", "no-pty") and len(canvas["cmds"]) == 1


def test_a_window_is_still_a_window(wired, canvas):
    from lib import terminals
    r = canvas["agents"].launch_unit(ready_agent_unit(wired)["id"], "claude")
    assert r["where"] == "window" and len(canvas["cmds"]) == 1 and terminals.listing() == []


def test_a_terminal_that_cannot_start_falls_back_to_a_window_with_its_record(wired, canvas, monkeypatch):
    from lib import sessions, terminals

    def no_pty(*a, **kw):
        raise terminals.Unavailable("no PTY")
    monkeypatch.setattr(terminals, "_start", no_pty)
    u = ready_agent_unit(wired)
    r = canvas["agents"].launch_unit(u["id"], "claude", where="canvas")
    assert (r["where"], r["fallback"], "terminal" in r) == ("window", "no-pty", False)
    assert "session_run.py" in canvas["cmds"][0][0][1] and sessions.load(u["id"])["session"]


def test_a_session_open_in_a_window_is_not_opened_on_the_canvas(wired, canvas):
    from lib import sessions
    u = ready_agent_unit(wired)
    canvas["agents"].launch_unit(u["id"], "claude")
    sessions.update(u["id"], pid=os.getpid())
    with pytest.raises(canvas["agents"].AlreadyOpen) as e:
        canvas["agents"].launch_unit(u["id"], "claude", mode="continue", where="canvas")
    assert e.value.terminal is None


def test_two_quick_opens_of_one_unit_open_it_once(wired, canvas, monkeypatch):
    import time
    from lib import terminals
    uid = ready_agent_unit(wired)["id"]
    plan, prompt = canvas["agents"].plan, canvas["agents"].plan.prompt
    monkeypatch.setattr(plan, "prompt", lambda *a, **kw: time.sleep(0.3) or prompt(*a, **kw))   # between check and open
    gate, outcomes = threading.Barrier(2), []

    def click():
        gate.wait()
        try:
            outcomes.append(canvas["agents"].launch_unit(uid, "claude", where="canvas")["terminal"]["id"])
        except canvas["agents"].AlreadyOpen as e:
            outcomes.append(e)
    clicks = [threading.Thread(target=click) for _ in range(2)]
    [c.start() for c in clicks]
    [c.join() for c in clicks]
    assert sorted(type(o).__name__ for o in outcomes) == ["AlreadyOpen", "str"] and len(terminals.listing()) == 1
