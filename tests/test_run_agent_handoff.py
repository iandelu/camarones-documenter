"""A headless agent the run can be asked to give up (plan._run_agent and lib/harness/handoff.py): a real process that
started one of its own, and the file that ends them."""
from __future__ import annotations

import datetime as dt, json, os, signal, subprocess, sys, threading
from pathlib import Path
from types import SimpleNamespace

import pytest

from test_terminals import until

FAKE = Path(__file__).parent / "fixtures" / "fake_agent.py"
UID = "discovery:api"


@pytest.fixture
def agent(kit, monkeypatch, tmp_path):
    from lib.adapters.runners import base
    from lib.adapters.runners.claude import Claude
    from lib.harness.ports import Invocation
    monkeypatch.setattr(base, "which", lambda name: f"/bin/{name}")
    box = SimpleNamespace(pids=tmp_path / "pids", seconds=60, child=True, req=None)

    def build(self, req):
        box.req = req
        return Invocation([sys.executable, str(FAKE), str(box.pids), str(box.seconds), *(["child"] if box.child else [])],
                          req.cwd, req.env)
    monkeypatch.setattr(Claude, "build", build)
    return box


def run(kit, target="claude", **kw):
    from lib.harness.events import EventLog
    log = EventLog(kit.common.CTX.runs / "r-1" / "events.jsonl")
    with kit.plan.recording(log, "r-1"):
        r = kit.plan._run_agent(target, "do it", "en", UID, echo=lambda _: None, **kw)
    return r, log.read()[0]


def once_up(box, then):
    """then(), from another thread, once the agent has started what it starts."""
    def go():
        until(box.pids.exists)
        then()
    threading.Thread(target=go, daemon=True).start()


def all_gone(box):
    from lib.harness.locks import pid_alive
    pids = [int(p) for p in box.pids.read_text(encoding="utf-8").split()]
    until(lambda: not any(pid_alive(p) for p in pids))


def test_asked_for_the_unit_the_agent_and_what_it_started_end(kit, agent):
    from lib.harness import handoff
    once_up(agent, lambda: handoff.request("r-1", UID, "you"))
    r, _ = run(kit)
    assert r.handoff == "you"
    assert handoff.read("r-1", UID) is None
    all_gone(agent)


def test_asked_to_stop_the_unit_the_agent_ends_too(kit, agent):
    from lib.harness import handoff
    once_up(agent, lambda: handoff.request("r-1", UID, "stop"))
    r, _ = run(kit)
    assert r.handoff == "stop"
    assert handoff.read("r-1", UID) is None
    all_gone(agent)


def test_a_cancelled_run_ends_its_agent(kit, agent):
    from lib.harness import scheduler
    once_up(agent, lambda: scheduler.request_cancel("r-1"))
    r, _ = run(kit)
    assert r.handoff == "cancel"
    all_gone(agent)


def test_an_agent_that_ignores_the_request_to_end_is_killed(kit, agent, monkeypatch, tmp_path):
    from lib.adapters.runners.claude import Claude
    from lib.harness import handoff
    from lib.harness.locks import pid_alive
    from lib.harness.ports import Invocation
    stubborn = tmp_path / "stubborn.py"
    stubborn.write_text(f"import os, signal, time\nsignal.signal(signal.SIGTERM, signal.SIG_IGN)\n"
                        f"open({str(agent.pids)!r}, 'w').write(str(os.getpid()))\ntime.sleep(60)\n", encoding="utf-8")
    monkeypatch.setattr(Claude, "build", lambda self, req: Invocation([sys.executable, str(stubborn)], req.cwd, req.env))
    monkeypatch.setattr(kit.plan, "END_GRACE", 0.2)
    once_up(agent, lambda: handoff.request("r-1", UID, "you"))
    r, _ = run(kit)
    assert r.handoff == "you"
    assert not pid_alive(int(agent.pids.read_text(encoding="utf-8")))


def test_a_new_conversation_gets_its_id_and_the_log_says_so(kit, agent):
    agent.seconds, agent.child = 0, False
    r, ev = run(kit)
    assert not agent.req.resume and agent.req.session and r.session == agent.req.session
    said = [e for e in ev if e["type"] == "session"]
    assert [(e["unit"], e["runner"], e["id"]) for e in said] == [(UID, "claude", r.session)]
    assert getattr(r, "handoff", None) is None


def test_each_attempt_has_its_own_conversation(kit, agent):
    agent.seconds, agent.child = 0, False
    first, _ = run(kit)
    second, _ = run(kit)
    assert first.session != second.session


def test_a_conversation_it_is_given_is_resumed(kit, agent):
    agent.seconds, agent.child = 0, False
    r, ev = run(kit, session="s-1")
    assert agent.req.resume and agent.req.session == "s-1" and r.session == "s-1"
    assert [e["id"] for e in ev if e["type"] == "session"] == ["s-1"]


def test_a_conversation_the_agent_names_is_kept(kit, agent, monkeypatch):
    from lib.adapters.runners.codex import Codex
    from lib.harness.ports import Invocation
    seen = {}
    line = json.dumps({"type": "thread.started", "thread_id": "T"})

    def build(self, req):
        seen["req"] = req
        return Invocation([sys.executable, "-c", f"print({line!r})"], req.cwd, req.env)
    monkeypatch.setattr(Codex, "build", build)
    r, ev = run(kit, target="codex")
    assert seen["req"].session is None and r.session == "T"
    assert [e["id"] for e in ev if e["type"] == "session"] == ["T"]


def test_a_request_the_agent_ended_before_is_left_for_the_run(kit, agent, monkeypatch):
    from lib.harness import handoff
    agent.seconds, agent.child = 0, False
    monkeypatch.setattr(kit.plan, "WATCH", 60)
    handoff.request("r-1", UID, "stop")
    r, _ = run(kit)
    assert getattr(r, "handoff", None) is None and r.returncode == 0
    assert handoff.read("r-1", UID)["to"] == "stop"


def spent(kit, sid, when=None, tokens=7):
    """A line of the conversation's transcript, as Claude Code writes it while it works."""
    from lib import sessions
    ts = (when or dt.datetime.now(dt.timezone.utc)).isoformat().replace("+00:00", "Z")
    f = sessions.claude_dir(kit.common.WORKSPACE) / f"{sid}.jsonl"
    f.parent.mkdir(parents=True, exist_ok=True)
    with f.open("a", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps({"type": "assistant", "timestamp": ts, "message": {
            "id": f"m-{ts}", "model": "claude-x",
            "usage": {"input_tokens": 3, "output_tokens": tokens, "cache_read_input_tokens": 11,
                      "cache_creation_input_tokens": 13}}}) + "\n")


def test_what_an_ended_agent_spent_is_on_the_runs_bill(kit, agent):
    from lib.harness import handoff

    def take():
        spent(kit, agent.req.session)
        handoff.request("r-1", UID, "you")
    once_up(agent, take)
    r, ev = run(kit)
    usage = [e for e in ev if e["type"] == "usage"]                # it never got to its result, where Claude says it
    assert r.handoff == "you" and len(usage) == 1
    u = usage[0]
    assert (u["unit"], u["runner"], u["model"], u["in"], u["out"], u["cache_read"], u["cache_write"]) == \
        (UID, "claude", "claude-x", 3, 7, 11, 13)


def test_a_resumed_attempt_only_bills_what_it_spent(kit, agent):
    from lib.harness import handoff
    spent(kit, "s-1", dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=1), tokens=500)

    def take():
        spent(kit, "s-1", tokens=7)
        handoff.request("r-1", UID, "you")
    once_up(agent, take)
    _, ev = run(kit, session="s-1")
    assert [e["out"] for e in ev if e["type"] == "usage"] == [7]


def test_an_agent_that_said_what_it_spent_is_not_counted_again(kit, agent, monkeypatch):
    from lib.adapters.runners.claude import Claude
    from lib.harness.ports import Invocation
    line = json.dumps({"type": "result", "result": "ok", "total_cost_usd": 0.5, "usage": {"input_tokens": 1, "output_tokens": 2}})

    def build(self, req):
        agent.req = req
        spent(kit, req.session, dt.datetime.now(dt.timezone.utc) + dt.timedelta(seconds=30))
        return Invocation([sys.executable, "-c", f"print({line!r})"], req.cwd, req.env)
    monkeypatch.setattr(Claude, "build", build)
    _, ev = run(kit)
    assert [e["out"] for e in ev if e["type"] == "usage"] == [2]


def test_a_transcript_that_cannot_be_read_does_not_stop_the_run(kit, agent, monkeypatch):
    from lib.harness import handoff, transcripts

    def boom(*_):
        raise ValueError("not a transcript")
    monkeypatch.setattr(transcripts, "read", boom)
    once_up(agent, lambda: handoff.request("r-1", UID, "you"))
    r, ev = run(kit)
    assert r.handoff == "you" and not [e for e in ev if e["type"] == "usage"]


def test_the_parallel_scheduler_keeps_its_agents(kit, agent, monkeypatch):
    from lib.harness import handoff
    agent.seconds, agent.child = 1, False
    monkeypatch.setattr(kit.plan, "WATCH", 0.05)
    handoff.request("r-1", UID, "you")
    r = kit.plan._run_agent("claude", "do it", "en", UID, echo=lambda _: None, emit=lambda *a, **k: None)
    assert getattr(r, "handoff", None) is None and r.returncode == 0
    assert handoff.read("r-1", UID)["to"] == "you"


@pytest.mark.skipif(sys.platform == "win32", reason="no SIGHUP on Windows")
def test_a_run_started_with_nohup_stays_that_way(kit):
    if threading.current_thread() is not threading.main_thread():
        pytest.skip("signal handlers are the main thread's")
    old = signal.signal(signal.SIGHUP, signal.SIG_IGN)
    try:
        with kit.plan._term_unwinds():
            assert signal.getsignal(signal.SIGHUP) == signal.SIG_IGN
            assert callable(signal.getsignal(signal.SIGTERM))
        assert signal.getsignal(signal.SIGHUP) == signal.SIG_IGN
    finally:
        signal.signal(signal.SIGHUP, old)


@pytest.mark.skipif(sys.platform == "win32", reason="a stopped job is taskkill /T there, which walks the tree itself")
@pytest.mark.parametrize("sig", ["SIGTERM", "SIGHUP"])       # a stopped job; the terminal a CLI run is in, closed
def test_a_stopped_run_ends_its_agent_and_the_log_says_so(kit, tmp_path, sig):
    from lib.harness.events import EventLog
    from lib.harness.locks import pid_alive
    kit.plan.sync()
    kit.plan.set_status("setup", "done")
    pids = tmp_path / "pids"
    driver = f"""
import sys
sys.path.insert(0, {str(kit.kit_dir)!r})
from lib import plan
from lib.adapters.runners import base
from lib.adapters.runners.claude import Claude
from lib.harness.ports import Invocation
base.which = plan.which = lambda name: "/bin/" + name
Claude.build = lambda self, req: Invocation([sys.executable, {str(FAKE)!r}, {str(pids)!r}, "60", "child"], req.cwd, req.env)
plan.prompt = lambda uid, lang="es", unattended=False: "p"
plan.run_autopilot(lang="en", max_units=1, echo=lambda _: None)
"""
    job = subprocess.Popen([sys.executable, "-c", driver], env=dict(os.environ), start_new_session=True)
    try:
        until(pids.exists, timeout=60)
        os.killpg(job.pid, getattr(signal, sig))
        job.wait(30)
    finally:
        if job.poll() is None:
            job.kill()
    alive = [p for p in map(int, pids.read_text(encoding="utf-8").split()) if pid_alive(p)]
    until(lambda: not any(pid_alive(p) for p in alive))
    log = next(kit.common.CTX.runs.glob("*/events.jsonl"))
    last = EventLog(log).read()[0][-1]
    assert last["type"] == "run.finished" and last["interrupted"] is True
