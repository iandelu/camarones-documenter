"""A headless agent the run can be asked to give up (plan._run_agent and lib/harness/handoff.py): a real process that
started one of its own, and the file that ends them."""
from __future__ import annotations

import json, os, signal, subprocess, sys, threading
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


def test_a_request_left_when_the_agent_ends_on_its_own_goes_with_it(kit, agent, monkeypatch):
    from lib.harness import handoff
    agent.seconds, agent.child = 0, False
    monkeypatch.setattr(kit.plan, "WATCH", 60)
    handoff.request("r-1", UID, "stop")
    r, _ = run(kit)
    assert getattr(r, "handoff", None) is None and r.returncode == 0
    assert handoff.read("r-1", UID) is None


def test_the_parallel_scheduler_keeps_its_agents(kit, agent, monkeypatch):
    from lib.harness import handoff
    agent.seconds, agent.child = 1, False
    monkeypatch.setattr(kit.plan, "WATCH", 0.05)
    handoff.request("r-1", UID, "you")
    r = kit.plan._run_agent("claude", "do it", "en", UID, echo=lambda _: None, emit=lambda *a, **k: None)
    assert getattr(r, "handoff", None) is None and r.returncode == 0
    assert handoff.read("r-1", UID)["to"] == "you"


@pytest.mark.skipif(sys.platform == "win32", reason="a stopped job is taskkill /T there, which walks the tree itself")
def test_a_stopped_job_ends_its_agent_and_the_log_says_the_run_ended(kit, tmp_path):
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
        os.killpg(job.pid, signal.SIGTERM)                       # how a job of the server is stopped (appapi.cancel)
        job.wait(30)
    finally:
        if job.poll() is None:
            job.kill()
    alive = [p for p in map(int, pids.read_text(encoding="utf-8").split()) if pid_alive(p)]
    until(lambda: not any(pid_alive(p) for p in alive))
    log = next(kit.common.CTX.runs.glob("*/events.jsonl"))
    last = EventLog(log).read()[0][-1]
    assert last["type"] == "run.finished" and last["interrupted"] is True
