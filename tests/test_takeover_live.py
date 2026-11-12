"""The slice's "done when" with real processes and nothing between them but the files: an autopilot in its own process,
holding the real run lock, with agents that are real processes, and the project server's side here, on a real terminal.
The person takes a unit, corrects it and hands it back; the pilot carries on with it and the other unit never stopped."""
from __future__ import annotations

import os, signal, subprocess, sys, time
from pathlib import Path
from types import SimpleNamespace

import pytest

from test_agents import term  # noqa: F401  (fixture)
from test_terminals import ECHO, screen, until

AGENT = """
import os, sys, time
from pathlib import Path
pids, prompt, first, kit = sys.argv[1:5]
sys.path.insert(0, kit)
text = Path(prompt).read_text(encoding="utf-8")
if "prompt " + first in text:                 # the first unit, the first time: it works until it is ended
    Path(pids).write_text(str(os.getpid()), encoding="utf-8")
    print('{"type": "assistant", "message": {"content": [{"type": "text", "text": "working"}]}}', flush=True)
    time.sleep(120)
from lib import plan
plan.set_status(first if first in text else text.split()[1], "done")
"""

DRIVER = """
import faulthandler, signal, sys
if hasattr(signal, "SIGUSR1"):                # a pilot that outlives its Stop dumps its threads into its log
    faulthandler.register(signal.SIGUSR1, all_threads=True)
sys.path.insert(0, {kit!r})
from lib import plan
from lib.adapters.runners import base
from lib.adapters.runners.claude import Claude
from lib.harness.ports import Invocation
base.which = plan.which = lambda name: "/bin/" + name
Claude.build = lambda self, req: Invocation([sys.executable, {agent!r}, {pids!r}, str(plan.AUTOPILOT_PROMPT), {first!r}, {kit!r}],
                                            req.cwd, req.env)
plan.prompt = lambda uid, lang="es", unattended=False: "prompt " + uid
{extra}
plan.run_autopilot(lang="en", echo=print)
"""

STOP_AS_IT_STARTS = """
import time
emit = plan._emit
def emit_then_wait(kind, **fields):           # the Stop lands between the agent's start and the watch on it
    emit(kind, **fields)
    if kind == "session":
        time.sleep(60)
plan._emit = emit_then_wait
"""


@pytest.fixture
def live(wired, term, tmp_path, monkeypatch, request):                   # noqa: F811
    from lib import takeover, terminals
    from lib.adapters.runners.claude import Claude
    from lib.common import kill_tree
    from lib.harness import runs
    from lib.harness.ports import Invocation
    monkeypatch.setattr(Claude, "build", lambda self, req: Invocation([sys.executable, str(ECHO)], req.cwd, req.env))
    ready = [u["id"] for u in wired.plan.available() if u["runner"] == "agent"][:2]
    for u in wired.plan.load()["units"]:
        if u["id"] not in ready:
            wired.plan.set_status(u["id"], "done", record=False)
    first, other = ready
    agent, pids = tmp_path / "agent.py", tmp_path / "pids"
    agent.write_text(AGENT, encoding="utf-8")
    driver = DRIVER.format(kit=str(wired.kit_dir), agent=str(agent), pids=str(pids), first=first,
                           extra=getattr(request, "param", ""))
    out = (tmp_path / "pilot.log").open("wb")
    job = subprocess.Popen([sys.executable, "-c", driver], env=dict(os.environ), stdout=out, stderr=subprocess.STDOUT,
                           start_new_session=sys.platform != "win32")
    box = SimpleNamespace(first=first, other=other, pids=pids, job=job, t=takeover, term=terminals, plan=wired.plan, runs=runs,
                          log=tmp_path / "pilot.log")
    box.events = lambda: runs.events(runs.ids(wiki=False)[0]) if runs.ids(wiki=False) else []
    yield box
    if job.poll() is None:
        kill_tree(job.pid)
    job.wait(30)
    out.close()
    terminals.shutdown()


def stop_pilot(box, timeout: float = 30) -> int:
    """The app's Stop the autopilot (appapi.cancel: SIGTERM to its group). One that outlives it dumps its threads into
    its log, and the test fails with that log, so a slow CI run says where the pilot was."""
    from lib.common import kill_tree
    kill_tree(box.job.pid)
    try:
        return box.job.wait(timeout)
    except subprocess.TimeoutExpired:
        if hasattr(signal, "SIGUSR1"):
            os.kill(box.job.pid, signal.SIGUSR1)
            time.sleep(1)
        pytest.fail(f"the autopilot outlived its Stop by {timeout} s; its log:\n"
                    + box.log.read_text(encoding="utf-8", errors="replace")[-8000:])


def at_work(box):
    until(lambda: box.pids.exists() and box.pids.read_text(encoding="utf-8"), timeout=60)
    until(lambda: box.runs.active() is not None and box.runs.running(box.runs.ids(wiki=False)[0], box.first), timeout=30)
    until(lambda: any(e["type"] == "session" and e["unit"] == box.first for e in box.events()))  # the agent may come first
    return int(box.pids.read_text(encoding="utf-8"))


def status(box, uid):
    return box.plan.get(box.plan.load(), uid)["status"]


def test_take_a_unit_correct_it_hand_it_back_and_the_pilot_carries_on(live):
    from lib import sessions
    from lib.harness.locks import pid_alive
    agent_pid = at_work(live)
    sid = next(e["id"] for e in live.events() if e["type"] == "session" and e["unit"] == live.first)

    r = live.t.take(live.first, lang="en")                       # the run's own process answers, through the files
    tid = r["terminal"]["id"]
    assert r["terminal"]["session"] == sid and not r["fresh"]
    until(lambda: not pid_alive(agent_pid))
    assert sessions.load(live.first)["since"] > 0

    until(lambda: status(live, live.other) == "done", timeout=60)   # the other unit never stopped
    until(lambda: any(e["type"] == "unit.waiting" and e["units"] == [live.first] for e in live.events()), timeout=30)
    assert status(live, live.first) == "doing" and live.job.poll() is None

    until(lambda: sessions.running(sessions.load(live.first)))
    until(lambda: b"ready" in screen(live.term, tid))
    live.term.write(tid, "leave the gateway out\n")
    until(lambda: b"leave the gateway out" in screen(live.term, tid))

    live.t.hand_back(live.first)
    assert live.job.wait(60) == 0, live.log.read_text(encoding="utf-8")
    assert live.term.get(tid)["ended"] is not None
    assert status(live, live.first) == "done"
    ev = live.events()
    assert [e["outcome"] for e in ev if e["type"] == "unit.finished" and e["unit"] == live.first] == ["handed", "ok"]
    assert [e.get("resume") for e in ev if e["type"] == "unit.started" and e["unit"] == live.first] == [None, sid]
    end = ev[-1]
    assert end["type"] == "run.finished" and end["done"] == 2 and not end.get("interrupted")


def test_stopping_a_unit_leaves_the_run_going_with_the_other(live):
    from lib.harness.locks import pid_alive
    agent_pid = at_work(live)
    assert live.t.stop(live.first) == {"stopping": live.first}
    until(lambda: not pid_alive(agent_pid))
    until(lambda: status(live, live.other) == "done", timeout=60)
    assert live.job.wait(60) == 0, live.log.read_text(encoding="utf-8")
    ev = live.events()
    assert [e["outcome"] for e in ev if e["type"] == "unit.finished" and e["unit"] == live.first] == ["cancelled"]
    assert status(live, live.first) == "todo"


def test_stopping_the_run_leaves_the_terminal_open(live):
    at_work(live)
    tid = live.t.take(live.first)["terminal"]["id"]
    until(lambda: status(live, live.other) == "done", timeout=60)
    stop_pilot(live)
    until(lambda: live.runs.active() is None)
    assert live.term.get(tid)["ended"] is None
    live.term.write(tid, "still here\n")
    until(lambda: b"still here" in screen(live.term, tid))


def test_a_dead_run_leaves_its_unit_to_be_taken(live):
    from lib.harness.locks import pid_alive
    agent_pid = at_work(live)
    sid = next(e["id"] for e in live.events() if e["type"] == "session" and e["unit"] == live.first)
    stop_pilot(live)
    until(lambda: not pid_alive(agent_pid))                      # no agent outlives its run
    until(lambda: live.runs.active() is None)
    r = live.t.take(live.first)
    assert r["terminal"]["session"] == sid


@pytest.mark.parametrize("live", [STOP_AS_IT_STARTS], indirect=True, ids=["stop-as-it-starts"])
def test_a_run_stopped_as_its_agent_starts_ends_that_agent(live):
    from lib.harness.locks import pid_alive
    agent_pid = at_work(live)
    stop_pilot(live)
    until(lambda: not pid_alive(agent_pid))
