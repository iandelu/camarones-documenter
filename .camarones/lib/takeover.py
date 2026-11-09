"""A unit passing between the autopilot and the person: the project server's side. The run may be another process, a CLI
in a terminal, so they talk through a file (lib/harness/handoff.py) and the run's log: `take` asks for the unit, waits
for the run to log how it ended and opens a terminal on the conversation of its headless agent; `hand_back` closes that
terminal and gives the conversation back; `stop` ends the agent and leaves the unit out of the run. A dead run has
nothing to ask: its unit opens on the last conversation its log names.

Only the autopilot's units, for now: the parallel scheduler does not watch for these files, so a parallel run is refused."""
from __future__ import annotations

import threading
import time

from . import agents, plan, sessions, terminals
from .common import CTX
from .harness import handoff, runs, scheduler
from .harness.events import EventLog

ANSWER = 10.0                   # seconds a run has to end its agent and say so
LOOK = 0.1                      # how often the run's log is read meanwhile

_taking = threading.Lock()      # one take at a time: a second click waits for the first, then finds its terminal open


class Refused(RuntimeError):
    """`code` for the app, which says it in its own language: no-run, parallel, no-answer, finished, no-terminal."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def _ask(run_id: str, uid: str) -> None:
    """Asks the run for the unit, if its agent is at work on it, and waits for the unit's end in the log. Refused when
    the run is alive and does not answer; a run that died meanwhile has left the unit behind."""
    log = EventLog(CTX.runs / run_id / "events.jsonl")
    offset = log.read()[1]                      # before the look at it: an end after that look is read below
    if not runs.running(run_id, uid):
        return
    handoff.request(run_id, uid, "you")
    deadline = time.monotonic() + ANSWER
    try:
        while time.monotonic() < deadline:
            events, offset = log.read(offset)
            if any(e["type"] == "unit.finished" and e.get("unit") == uid for e in events):
                return
            time.sleep(LOOK)
    finally:
        handoff.clear(run_id, uid)
    if scheduler.busy() is not None:
        raise Refused("no-answer", f"the run did not answer for {uid}: try again")


def take(uid: str, lang: str = "es", size: tuple[int, int] = (80, 24)) -> dict:
    """The unit's conversation on a terminal, `fresh` when its runner has none to resume (a new session on its prompt
    and checkpoints). AlreadyOpen and Limit before the run is asked anything; a machine with no PTY opens a window."""
    plan.get(plan.load(), uid)
    where, fallback = agents._place("canvas")
    with _taking:
        with agents._opening:
            agents._refuse_open(uid, where)
        run = runs.active()
        if run and run["kind"] == "parallel" and runs.running(run["run"], uid):
            raise Refused("parallel", "a parallel run keeps its units: only the autopilot's can be taken")
        if run:
            _ask(run["run"], uid)
        u = plan.get(plan.load(), uid)
        if u["status"] in ("done", "dropped"):
            raise Refused("finished", f"{uid} is {u['status']}: its agent finished it")
        last = runs.last_session(uid, run["run"] if run else None)
        if not last:
            raise Refused("no-run", f"no run has worked on {uid}")
        with agents._opening:
            agents._refuse_open(uid, where)     # a session opened by hand while the run answered
            if u["status"] == "todo":           # its agent had not marked it: a closed terminal still knows
                plan.set_status(uid, "doing")
            if last["id"]:
                res = agents._open(None, last["agent"], lang, resume=True, uid=uid, session=last["id"], where=where,
                                   size=size, fallback=fallback, since=time.time())
            else:
                res = agents._open(plan.prompt(uid, lang=lang), last["agent"], lang, resume=False, uid=uid, where=where,
                                   size=size, fallback=fallback)
    return {**res, "unit": uid, "fresh": not last["id"]}


def hand_back(uid: str) -> dict:
    """Closes the unit's terminal and gives its conversation to the run, which resumes it first. Without a run the
    terminal stays as it is."""
    plan.get(plan.load(), uid)
    run = runs.active()
    if not run:
        raise Refused("no-run", "no run is in progress")
    if run["kind"] == "parallel":
        raise Refused("parallel", "a parallel run does not take units back: only the autopilot does")
    term = terminals.find("unit", uid)
    if not term:
        raise Refused("no-terminal", f"{uid} has no terminal on the canvas")
    terminals.close_wait(term["id"], terminals.CLOSE_GRACE + 2)
    sessions.bound(uid)
    handoff.request(run["run"], uid, "pilot", session=term["session"], agent=term["agent"])
    return {"handed": uid, "terminal": term["id"]}


def stop(uid: str) -> dict:
    """Ends the unit's agent: the unit goes back to the queue and the run goes on without it."""
    plan.get(plan.load(), uid)
    run = runs.active()
    if not run or not runs.running(run["run"], uid):
        raise Refused("no-run", f"no run is working on {uid}")
    if run["kind"] == "parallel":
        raise Refused("parallel", "a parallel run keeps its units: only the autopilot's can be stopped")
    handoff.request(run["run"], uid, "stop")
    return {"stopping": uid}
