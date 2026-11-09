"""A unit passing between the autopilot and the person (lib/takeover.py): the server's side of the handoff. The run here
is a thread that answers the file as the real one does; tests/test_autopilot_handoff.py has the run's side."""
from __future__ import annotations

import sys, threading, time
from types import SimpleNamespace

import pytest

from test_agents import ready_agent_unit, term  # noqa: F401  (fixture)
from test_terminals import ECHO, until


@pytest.fixture
def pair(wired, term, monkeypatch):                                      # noqa: F811
    from lib import takeover, terminals
    from lib.adapters.runners.claude import Claude
    from lib.adapters.runners.codex import Codex
    from lib.harness import handoff, scheduler
    from lib.harness.events import EventLog
    from lib.harness.ports import Invocation
    reqs = []

    def build(self, req):
        reqs.append(req)
        return Invocation([sys.executable, str(ECHO)], req.cwd, req.env)
    monkeypatch.setattr(Claude, "build", build)
    monkeypatch.setattr(Codex, "build", build)
    monkeypatch.setattr(scheduler, "busy", lambda: {"pid": 1})
    uid = ready_agent_unit(wired)["id"]
    wired.plan.set_status(uid, "doing")
    log = EventLog(wired.common.CTX.runs / "r-1" / "events.jsonl")
    yield SimpleNamespace(uid=uid, reqs=reqs, log=log, t=takeover, term=terminals, h=handoff, plan=wired.plan,
                          scheduler=scheduler, agents=term["agents"], box=term)
    terminals.shutdown()


def at_work(p, runner="claude", session="s-1", kind="agents"):
    """A run whose agent is at work on the unit."""
    p.log.emit("run.started", run="r-1", **({"agents": [runner]} if kind == "agents" else {"parallel": 2}))
    p.log.emit("unit.started", run="r-1", unit=p.uid, runner=runner)
    if session:
        p.log.emit("session", run="r-1", unit=p.uid, runner=runner, id=session)


def answers(p, outcome="handed", then=None):
    """The run's side: it sees the request, ends its agent and logs how the unit ended."""
    def go():
        until(lambda: p.h.read("r-1", p.uid))
        if then:
            then()
        p.h.clear("r-1", p.uid)
        p.log.emit("unit.finished", run="r-1", unit=p.uid, runner="claude", outcome=outcome, status="doing")
    threading.Thread(target=go, daemon=True).start()


def test_taking_a_unit_ends_the_runs_agent_and_opens_its_conversation(pair):
    from lib import sessions
    at_work(pair)
    answers(pair)
    before = time.time()
    r = pair.t.take(pair.uid, lang="en", size=(100, 30))
    t = r["terminal"]
    assert (t["kind"], t["unit"], t["agent"], t["session"], t["cols"], t["rows"]) == ("unit", pair.uid, "claude", "s-1", 100, 30)
    assert r["where"] == "canvas" and not r["fresh"]
    req = pair.reqs[-1]
    assert req.interactive and req.resume and req.session == "s-1" and req.prompt == ""
    rec = sessions.load(pair.uid)
    assert rec["session"] == "s-1" and rec["since"] >= before
    assert pair.plan.get(pair.plan.load(), pair.uid)["status"] == "doing"
    assert pair.h.read("r-1", pair.uid) is None


def test_the_terminal_has_the_project_the_agent_had(pair, wired, monkeypatch):
    from lib import terminals
    seen = {}
    real = terminals.spawn

    def spawn(argv, cwd, **kw):
        seen.update(cwd=cwd, env=kw.get("env"))
        return real(argv, cwd, **kw)
    monkeypatch.setattr(terminals, "spawn", spawn)
    at_work(pair)
    answers(pair)
    pair.t.take(pair.uid)
    assert seen["cwd"] == wired.common.WORKSPACE and seen["env"]["CAMARONES_ROOT"] == str(wired.common.ROOT)


def test_a_run_that_does_not_answer_keeps_the_unit(pair, monkeypatch):
    monkeypatch.setattr(pair.t, "ANSWER", 0.2)
    at_work(pair)
    with pytest.raises(pair.t.Refused) as e:
        pair.t.take(pair.uid)
    assert e.value.code == "no-answer"
    assert pair.h.read("r-1", pair.uid) is None and pair.term.listing() == []


def test_a_run_that_dies_while_it_is_asked_leaves_the_unit_to_the_person(pair, monkeypatch):
    monkeypatch.setattr(pair.t, "ANSWER", 0.2)
    at_work(pair)
    until_asked = threading.Event()

    def died():
        until(lambda: pair.h.read("r-1", pair.uid))
        monkeypatch.setattr(pair.scheduler, "busy", lambda: None)
        until_asked.set()
    threading.Thread(target=died, daemon=True).start()
    r = pair.t.take(pair.uid)
    assert until_asked.is_set() and r["terminal"]["session"] == "s-1"


def test_with_the_run_dead_it_opens_on_its_last_conversation_without_asking(pair, monkeypatch):
    monkeypatch.setattr(pair.scheduler, "busy", lambda: None)
    at_work(pair)
    r = pair.t.take(pair.uid)
    assert r["terminal"]["session"] == "s-1" and pair.h.read("r-1", pair.uid) is None


def test_an_agent_that_ended_on_its_own_and_closed_the_unit_has_nothing_to_take(pair):
    at_work(pair)
    answers(pair, "ok", then=lambda: pair.plan.set_status(pair.uid, "done"))
    with pytest.raises(pair.t.Refused) as e:
        pair.t.take(pair.uid)
    assert e.value.code == "finished" and pair.term.listing() == []


def test_an_agent_that_ended_on_its_own_with_the_unit_open_is_taken_all_the_same(pair):
    at_work(pair)
    answers(pair, "ok")
    assert pair.t.take(pair.uid)["terminal"]["session"] == "s-1"


def test_a_unit_with_its_session_open_says_which_terminal(pair):
    at_work(pair)
    answers(pair)
    first = pair.t.take(pair.uid)["terminal"]["id"]
    with pytest.raises(pair.agents.AlreadyOpen) as e:
        pair.t.take(pair.uid)
    assert e.value.terminal == first


def test_at_the_limit_nothing_is_asked_of_the_run(pair, monkeypatch):
    monkeypatch.setattr(pair.term, "MAX_LIVE", 0)
    at_work(pair)
    with pytest.raises(pair.term.Limit):
        pair.t.take(pair.uid)
    assert pair.h.read("r-1", pair.uid) is None


def test_a_runner_with_no_conversation_opens_a_new_session_on_the_units_prompt(pair):
    from lib import sessions
    at_work(pair, session=None)
    answers(pair)
    r = pair.t.take(pair.uid, lang="en")
    assert r["fresh"] and r["terminal"]["session"] is None
    assert pair.reqs[-1].prompt and not pair.reqs[-1].resume
    assert sessions.load(pair.uid).get("since") is None


def test_a_codex_unit_stays_on_codex(pair):
    at_work(pair, runner="codex:o5", session="T")
    answers(pair)
    r = pair.t.take(pair.uid)
    assert r["terminal"]["agent"] == "codex" and pair.reqs[-1].session == "T"


def test_a_parallel_run_keeps_its_units_for_now(pair):
    at_work(pair, kind="parallel")
    with pytest.raises(pair.t.Refused) as e:
        pair.t.take(pair.uid)
    assert e.value.code == "parallel" and pair.h.read("r-1", pair.uid) is None
    with pytest.raises(pair.t.Refused) as e:
        pair.t.stop(pair.uid)
    assert e.value.code == "parallel"


def test_two_clicks_open_one_terminal(pair):
    at_work(pair)
    answers(pair)
    out = []

    def click():
        try:
            out.append(pair.t.take(pair.uid)["terminal"]["id"])
        except pair.agents.AlreadyOpen as e:
            out.append(("open", e.terminal))
    threads = [threading.Thread(target=click) for _ in range(2)]
    [th.start() for th in threads]
    [th.join(20) for th in threads]
    opened = [x for x in out if isinstance(x, str)]
    assert len(opened) == 1 and ("open", opened[0]) in out
    assert len(pair.term.listing()) == 1


def test_a_unit_never_run_has_nothing_to_take(pair):
    pair.log.emit("run.started", run="r-1", agents=["claude"])
    with pytest.raises(pair.t.Refused) as e:
        pair.t.take(pair.uid)
    assert e.value.code == "no-run"


def test_an_unknown_unit_is_a_key_error(pair):
    with pytest.raises(KeyError):
        pair.t.take("nope")


def test_a_unit_whose_agent_had_not_marked_it_reads_in_progress(pair):
    pair.plan.set_status(pair.uid, "todo")
    at_work(pair)
    answers(pair)
    pair.t.take(pair.uid)
    assert pair.plan.get(pair.plan.load(), pair.uid)["status"] == "doing"


def test_handing_back_closes_the_terminal_then_asks_the_run(pair):
    from lib import sessions
    at_work(pair)
    answers(pair)
    tid = pair.t.take(pair.uid)["terminal"]["id"]
    until(lambda: sessions.running(sessions.load(pair.uid)))
    r = pair.t.hand_back(pair.uid)
    assert r == {"handed": pair.uid, "terminal": tid}
    assert pair.term.get(tid)["ended"] is not None and pair.term.get(tid)["closed"]
    req = pair.h.read("r-1", pair.uid)
    assert (req["to"], req["session"], req["agent"]) == ("pilot", "s-1", "claude")
    assert not sessions.live(sessions.load(pair.uid))


def test_with_no_run_the_terminal_stays_and_nothing_is_written(pair, monkeypatch):
    at_work(pair)
    answers(pair)
    tid = pair.t.take(pair.uid)["terminal"]["id"]
    monkeypatch.setattr(pair.scheduler, "busy", lambda: None)
    with pytest.raises(pair.t.Refused) as e:
        pair.t.hand_back(pair.uid)
    assert e.value.code == "no-run"
    assert pair.term.get(tid)["ended"] is None and pair.h.read("r-1", pair.uid) is None


def test_a_session_in_a_window_cannot_be_handed_back_from_here(pair):
    pair.log.emit("run.started", run="r-1", agents=["claude"])
    with pytest.raises(pair.t.Refused) as e:
        pair.t.hand_back(pair.uid)
    assert e.value.code == "no-terminal"


def test_a_session_opened_by_hand_can_be_left_to_the_pilot(pair):
    from lib import sessions
    pair.log.emit("run.started", run="r-1", agents=["claude"])
    pair.box["history"] = True
    pair.plan.set_status(pair.uid, "todo")
    r = pair.agents.launch_unit(pair.uid, "claude", where="canvas")
    until(lambda: sessions.running(sessions.load(pair.uid)))
    pair.t.hand_back(pair.uid)
    req = pair.h.read("r-1", pair.uid)
    assert req["session"] == r["terminal"]["session"] and req["agent"] == "claude"
    assert sessions.load(pair.uid)["since"] == 0.0              # the bill: what the run writes next is the run's


def test_stopping_a_unit_asks_the_run(pair):
    at_work(pair)
    assert pair.t.stop(pair.uid) == {"stopping": pair.uid}
    assert pair.h.read("r-1", pair.uid)["to"] == "stop"


def test_a_unit_the_run_is_not_on_cannot_be_stopped(pair):
    pair.log.emit("run.started", run="r-1", agents=["claude"])
    with pytest.raises(pair.t.Refused) as e:
        pair.t.stop(pair.uid)
    assert e.value.code == "no-run" and pair.h.read("r-1", pair.uid) is None


def test_continue_finds_the_conversation_a_dead_run_left(pair, monkeypatch):
    from lib import sessions
    monkeypatch.setattr(pair.scheduler, "busy", lambda: None)
    at_work(pair)
    transcript = sessions.claude_dir(pair.plan.WORKSPACE) / "s-1.jsonl"
    transcript.parent.mkdir(parents=True, exist_ok=True)
    transcript.write_text("{}\n", encoding="utf-8")
    before = time.time()
    r = pair.agents.launch_unit(pair.uid, "claude", mode="continue", where="canvas")
    assert r["terminal"]["session"] == "s-1" and pair.reqs[-1].resume and pair.reqs[-1].session == "s-1"
    assert sessions.load(pair.uid)["since"] >= before


def test_continue_on_codex_reopens_its_own_conversation(pair, monkeypatch):
    monkeypatch.setattr(pair.scheduler, "busy", lambda: None)
    at_work(pair, runner="codex", session="T")
    pair.agents.launch_unit(pair.uid, "codex", mode="continue", where="canvas")
    assert pair.reqs[-1].session == "T" and pair.reqs[-1].resume


def test_continue_with_no_conversation_known_stays_the_agents_own_last(pair, monkeypatch):
    monkeypatch.setattr(pair.scheduler, "busy", lambda: None)
    pair.agents.launch_unit(pair.uid, "codex", mode="continue", where="canvas")
    assert pair.reqs[-1].session is None and pair.reqs[-1].resume
