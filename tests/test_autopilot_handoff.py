"""The autopilot and the units the person takes (spec §4.2): a handed unit is no failure and no unit done, the run waits
while only those are left, a paused one is not picked up, and a unit handed back goes first, on its conversation."""
from __future__ import annotations

import json, os, subprocess, time

import pytest


class Stop(Exception):
    pass


def result(rc=0, output="", handoff=None, session=None):
    r = subprocess.CompletedProcess(["agent"], rc, output, "")
    r.handoff, r.session = handoff, session
    return r


@pytest.fixture
def pilot(kit, monkeypatch):
    plan = kit.plan
    plan.sync()
    plan.set_status("setup", "done")
    box = {"calls": [], "script": [], "echo": [], "naps": 0, "on_nap": None, "slept": []}
    real_sleep = time.sleep

    def run_agent(agent, text, lang, uid, echo, **kw):
        box["calls"].append({"agent": agent, "unit": uid, "text": text, **kw})
        step = box["script"].pop(0) if box["script"] else "done"
        if callable(step):
            step = step(uid)
        if step == "done":
            plan.set_status(uid, "done")
            return result()
        return step

    def sleep(s):
        if s < plan.WAIT_TAKEN:                                 # the time module's, shared: a lock or a retry elsewhere
            return real_sleep(s)
        box["naps"] += 1
        box["slept"].append(s)
        if box["on_nap"]:
            box["on_nap"](box["naps"])
        else:
            raise Stop
    monkeypatch.setattr(plan, "which", lambda name: f"/bin/{name}")
    monkeypatch.setattr(plan, "_run_agent", run_agent)
    monkeypatch.setattr(plan, "prompt", lambda uid, lang="es", unattended=False: f"prompt {uid}")
    monkeypatch.setattr(plan.time, "sleep", sleep)
    box["run"] = lambda **kw: plan.run_autopilot(echo=box["echo"].append, **kw)
    return box


def run_log(kit):
    from lib.harness.events import EventLog
    logs = sorted(kit.common.CTX.runs.glob("*/events.jsonl"))
    return EventLog(logs[-1]).read()[0]


def run_id(kit):
    return sorted(p.parent.name for p in kit.common.CTX.runs.glob("*/events.jsonl"))[-1]


def live_session(uid):
    """The unit is with the person: its record has a live pid."""
    from lib import sessions
    sessions.start(uid, "claude", "s-1")
    sessions.update(uid, pid=os.getpid())


def end_session(uid):
    from lib import sessions
    sessions.update(uid, ended=time.time())


def handed(uid, session="s-1"):
    return result(rc=-15, handoff="you", session=session)


def finish_of(events, uid):
    return [e for e in events if e["type"] == "unit.finished" and e["unit"] == uid]


def test_a_handed_unit_is_neither_a_failure_nor_a_unit_done(kit, pilot):
    taken = []

    def take(uid):
        taken.append(uid)
        kit.plan.set_status(uid, "doing")
        live_session(uid)
        return handed(uid)
    pilot["script"] = [take]
    assert pilot["run"](max_units=1) == 1                       # the limit is for the next one: handed does not use it
    assert [c["unit"] for c in pilot["calls"]][0] == taken[0] and len(pilot["calls"]) == 2
    ev = finish_of(run_log(kit), taken[0])
    assert [(e["outcome"], e["status"], e["session"]) for e in ev] == [("handed", "doing", "s-1")]
    assert not any("failed on" in line for line in pilot["echo"])


def test_a_handed_unit_is_not_run_again_while_it_is_with_the_person(kit, pilot):
    def take(uid):
        kit.plan.set_status(uid, "doing")
        live_session(uid)
        return handed(uid)
    pilot["script"] = [take]
    pilot["run"](max_units=2)
    ran = [c["unit"] for c in pilot["calls"]]
    assert len(ran) == len(set(ran))


def test_with_only_taken_units_left_it_waits_and_says_so_once_per_change(kit, pilot, monkeypatch):
    from lib import sessions
    units = [u["id"] for u in kit.plan.load()["units"] if u["runner"] == "agent"]
    monkeypatch.setattr(sessions, "taken", lambda queue: [u["id"] for u in queue][:2])

    def on_nap(n):
        if n == 3:
            monkeypatch.setattr(sessions, "taken", lambda queue: [u["id"] for u in queue][:1])
        if n == 5:
            raise Stop
    pilot["on_nap"] = on_nap
    monkeypatch.setattr(kit.plan, "available", lambda data=None: [u for u in kit.plan.load()["units"] if u["id"] in units[:2]])
    with pytest.raises(Stop):
        pilot["run"]()
    waits = [e["units"] for e in run_log(kit) if e["type"] == "unit.waiting"]
    assert waits == [units[:2], units[:1]]


def test_the_wait_ends_when_the_person_closes_the_unit_and_its_dependents_go_on(kit, pilot, monkeypatch):
    ready = next(u for u in kit.plan.available() if u["runner"] == "agent")
    for u in kit.plan.available():
        if u["id"] != ready["id"]:
            kit.plan.set_status(u["id"], "done")
    kit.plan.set_status(ready["id"], "doing")
    live_session(ready["id"])
    waiting_units = [u["id"] for u in kit.plan.load()["units"] if ready["id"] in (u.get("deps") or [])]

    def on_nap(_n):
        kit.plan.set_status(ready["id"], "done")
    pilot["on_nap"] = on_nap
    pilot["run"](max_units=1)
    assert pilot["naps"] == 1
    assert waiting_units and pilot["calls"][0]["unit"] in waiting_units
    assert any(e["type"] == "unit.waiting" and e["units"] == [ready["id"]] for e in run_log(kit))


def only_one_ready(kit):
    """Everything else out of the way: one unit is what the plan has left."""
    keep = next(u for u in kit.plan.available() if u["runner"] == "agent")["id"]
    for u in kit.plan.load()["units"]:
        if u["id"] != keep:
            kit.plan.set_status(u["id"], "done", record=False)
    return keep


def test_a_unit_closed_unfinished_is_paused_and_ends_the_wait(kit, pilot):
    uid = only_one_ready(kit)
    kit.plan.set_status(uid, "doing")
    live_session(uid)
    pilot["on_nap"] = lambda _n: end_session(uid)
    assert pilot["run"]() == 0
    assert pilot["calls"] == []                                 # the person's to continue: the run does not take it
    assert any("needs you" in line and f"{uid} paused" in line for line in pilot["echo"])


def test_a_handed_unit_whose_terminal_never_opens_does_not_hold_the_run_for_ever(kit, pilot, monkeypatch):
    from lib import sessions
    uid = only_one_ready(kit)
    kit.plan.set_status(uid, "doing")
    pilot["script"] = [lambda _u: handed(uid)]
    monkeypatch.setattr(sessions, "GRACE", 0)
    assert pilot["run"]() == 0
    assert any(f"{uid} paused" in line for line in pilot["echo"])
    assert len(pilot["calls"]) == 1


def test_a_handed_unit_is_waited_for_while_its_terminal_opens(kit, pilot):
    uid = only_one_ready(kit)
    kit.plan.set_status(uid, "doing")
    pilot["script"] = [lambda _u: handed(uid)]

    def on_nap(_n):                                             # the server opens it just after the event
        live_session(uid)
        kit.plan.set_status(uid, "done")
    pilot["on_nap"] = on_nap
    pilot["run"]()
    assert pilot["naps"] == 1 and len(pilot["calls"]) == 1
    assert not any("paused" in line for line in pilot["echo"])


def test_a_hand_back_goes_first_on_its_conversation_and_counts(kit, pilot):
    from lib.harness import handoff
    uid = only_one_ready(kit)
    kit.plan.set_status(uid, "doing")
    pilot["script"] = [lambda _u: handed(uid)]

    def on_nap(_n):
        handoff.request(run_id(kit), uid, "pilot", session="s-1", agent="claude")
    pilot["on_nap"] = on_nap
    assert pilot["run"]() == 1
    again = pilot["calls"][1]
    assert again["unit"] == uid and again["session"] == "s-1" and again["agent"] == "claude"
    assert uid in again["text"] and "prompt" not in again["text"]
    assert handoff.read(run_id(kit), uid) is None
    started = [e for e in run_log(kit) if e["type"] == "unit.started"]
    assert [e.get("resume") for e in started] == [None, "s-1"]


def test_a_hand_back_jumps_the_queue(kit, pilot):
    from lib.harness import handoff
    ready = [u["id"] for u in kit.plan.available() if u["runner"] == "agent"]
    assert len(ready) >= 3

    def take(uid):
        kit.plan.set_status(uid, "doing")
        return handed(uid)

    def second(uid):
        handoff.request(run_id(kit), pilot["calls"][0]["unit"], "pilot", session="s-1", agent="claude")
        kit.plan.set_status(uid, "done")
        return result()
    pilot["script"] = [take, second]
    pilot["run"](max_units=2)
    assert pilot["calls"][2]["unit"] == pilot["calls"][0]["unit"] and pilot["calls"][2]["session"] == "s-1"


def test_a_hand_back_stays_on_its_agent_whatever_the_routing_prefers(kit, pilot):
    from lib.harness import handoff
    uid = only_one_ready(kit)
    kit.plan.set_status(uid, "doing")
    pilot["script"] = [lambda _u: handed(uid, "T")]
    pilot["on_nap"] = lambda _n: handoff.request(run_id(kit), uid, "pilot", session="T", agent="codex")
    pilot["run"]()
    assert pilot["calls"][0]["agent"] == "claude" and pilot["calls"][1]["agent"] == "codex"


def test_a_hand_back_with_no_conversation_runs_the_units_prompt(kit, pilot):
    from lib.harness import handoff
    uid = only_one_ready(kit)
    kit.plan.set_status(uid, "doing")
    pilot["script"] = [lambda _u: handed(uid, None)]
    pilot["on_nap"] = lambda _n: handoff.request(run_id(kit), uid, "pilot", session=None, agent="opencode")
    pilot["run"]()
    again = pilot["calls"][1]
    assert again["text"] == f"prompt {uid}" and "session" not in again


def test_a_hand_back_on_a_unit_already_done_is_dropped(kit, pilot):
    from lib.harness import handoff
    uid = only_one_ready(kit)
    kit.plan.set_status(uid, "doing")
    pilot["script"] = [lambda _u: handed(uid)]

    def on_nap(_n):
        kit.plan.set_status(uid, "done")
        handoff.request(run_id(kit), uid, "pilot", session="s-1", agent="claude")
    pilot["on_nap"] = on_nap
    assert pilot["run"]() == 0 and len(pilot["calls"]) == 1
    assert handoff.read(run_id(kit), uid) is None


def test_a_hand_back_waits_for_its_session_to_close(kit, pilot):
    from lib.harness import handoff
    uid = only_one_ready(kit)
    kit.plan.set_status(uid, "doing")
    live_session(uid)
    seen = []

    def on_nap(n):
        if n == 1:
            handoff.request(run_id(kit), uid, "pilot", session="s-1", agent="claude")
        if n == 2:
            seen.append(len(pilot["calls"]))
            end_session(uid)
    pilot["on_nap"] = on_nap
    pilot["run"]()
    assert seen == [0] and pilot["calls"][0]["session"] == "s-1"


def test_a_stopped_unit_goes_back_and_the_run_goes_on_without_it(kit, pilot):
    stopped = []

    def stop(uid):
        stopped.append(uid)
        kit.plan.set_status(uid, "doing")
        return result(rc=-15, handoff="stop", session="s-1")
    pilot["script"] = [stop]
    assert pilot["run"](max_units=1) == 1
    uid = stopped[0]
    assert kit.plan.get(kit.plan.load(), uid)["status"] == "todo"
    assert [(e["outcome"], e["status"]) for e in finish_of(run_log(kit), uid)] == [("cancelled", "todo")]
    assert [c["unit"] for c in pilot["calls"]].count(uid) == 1


def test_a_stopped_unit_stays_out_for_the_rest_of_the_run(kit, pilot):
    uid = only_one_ready(kit)
    pilot["script"] = [lambda _u: result(rc=-15, handoff="stop")]
    assert pilot["run"]() == 0
    assert len(pilot["calls"]) == 1
    assert any("needs you" in line and f"{uid} stopped" in line for line in pilot["echo"])


def test_a_cancelled_run_ends_while_its_agent_runs(kit, pilot):
    pilot["script"] = [lambda _u: result(rc=-15, handoff="cancel")]
    assert pilot["run"]() == 0
    assert len(pilot["calls"]) == 1
    ev = run_log(kit)
    uid = pilot["calls"][0]["unit"]
    assert [e["outcome"] for e in finish_of(ev, uid)] == ["cancelled"]
    assert ev[-1]["type"] == "run.finished"
    assert kit.plan.get(kit.plan.load(), uid)["status"] == "todo"


def test_a_cancelled_run_stops_waiting_and_leaves_the_session_alone(kit, pilot):
    from lib import sessions
    from lib.harness import scheduler
    uid = only_one_ready(kit)
    kit.plan.set_status(uid, "doing")
    live_session(uid)
    pilot["on_nap"] = lambda _n: scheduler.request_cancel(run_id(kit))
    assert pilot["run"]() == 0
    assert pilot["calls"] == [] and sessions.live(sessions.load(uid))
    assert run_log(kit)[-1]["type"] == "run.finished"


def test_a_session_opened_by_hand_on_a_paused_unit_is_waited_for_again(kit, pilot):
    uid = only_one_ready(kit)
    kit.plan.set_status(uid, "doing")
    live_session(uid)

    def on_nap(n):
        if n == 1:                                              # closed, and opened again before the run looked
            end_session(uid)
            live_session(uid)
        if n == 2:
            kit.plan.set_status(uid, "done")
    pilot["on_nap"] = on_nap
    pilot["run"]()
    assert pilot["naps"] == 2 and pilot["calls"] == []


def test_a_unit_doing_from_before_the_run_is_still_picked_up(kit, pilot):
    uid = only_one_ready(kit)
    kit.plan.set_status(uid, "doing")                           # an earlier run or session that ended without closing it
    assert pilot["run"]() == 1
    assert [c["unit"] for c in pilot["calls"]] == [uid]


def test_a_handed_unit_ending_done_is_a_normal_end(kit, pilot):
    uid = only_one_ready(kit)

    def finish(_u):
        kit.plan.set_status(uid, "done")
        return result(rc=-15, handoff="you", session="s-1")     # it closed the unit as the request came
    pilot["script"] = [finish]
    assert pilot["run"]() == 1
    assert [e["outcome"] for e in finish_of(run_log(kit), uid)] == ["ok"]


def test_the_resume_prompt_is_in_the_runs_language_and_names_the_unit(kit):
    es, en = kit.plan._resume_prompt("discovery:api", "es"), kit.plan._resume_prompt("discovery:api", "en")
    assert "discovery:api" in es and "discovery:api" in en and es != en
    assert "plan done discovery:api" in es and "plan done discovery:api" in en
    assert "\n" not in json.dumps(es).replace("\\n", "")


def test_a_stopped_unit_left_to_the_pilot_goes_back_in(kit, pilot):
    from lib.harness import handoff
    uid = only_one_ready(kit)
    pilot["script"] = [lambda _u: result(rc=-15, handoff="stop", session="s-1")]
    real = kit.plan.sync
    asked = []

    def sync():                                                 # it stopped; then the person opened it and left it to the pilot
        if pilot["calls"] and not asked:
            asked.append(True)
            handoff.request(run_id(kit), uid, "pilot", session="s-1", agent="claude")
        return real()
    kit.plan.sync = sync
    try:
        assert pilot["run"]() == 1
    finally:
        kit.plan.sync = real
    assert [c.get("session") for c in pilot["calls"]] == [None, "s-1"]


def test_a_hand_back_on_its_way_is_no_pause(kit, pilot):
    """The terminal has ended and the request is not final yet: the run must not take that for a unit closed unfinished."""
    from lib.harness import handoff
    uid = only_one_ready(kit)
    kit.plan.set_status(uid, "doing")
    pilot["script"] = [lambda _u: handed(uid)]

    def on_nap(n):
        if n == 1:
            handoff.request(run_id(kit), uid, "pilot", session="s-1", agent="claude", closing=True)
            live_session(uid)
            end_session(uid)
        if n == 2:
            assert len(pilot["calls"]) == 1
            handoff.request(run_id(kit), uid, "pilot", session="s-1", agent="claude")
    pilot["on_nap"] = on_nap
    assert pilot["run"]() == 1
    assert pilot["naps"] == 2 and pilot["calls"][1]["session"] == "s-1"
    assert not any("paused" in line for line in pilot["echo"])


def test_a_hand_back_whose_server_died_closing_is_taken_all_the_same(kit, pilot):
    from lib.harness import handoff
    uid = only_one_ready(kit)
    kit.plan.set_status(uid, "doing")
    pilot["script"] = [lambda _u: handed(uid)]

    def on_nap(_n):
        handoff.request(run_id(kit), uid, "pilot", session="s-1", agent="claude", closing=True, at=time.time() - 3600)
    pilot["on_nap"] = on_nap
    assert pilot["run"]() == 1
    assert pilot["calls"][1]["session"] == "s-1"


def test_a_take_that_comes_as_the_agent_hits_a_limit_keeps_the_unit_for_the_person(kit, pilot):
    from lib.harness import handoff
    uid = only_one_ready(kit)
    kit.plan.set_status(uid, "doing")

    def limited(_u):
        handoff.request(run_id(kit), uid, "you")
        return result(rc=1, output="usage limit reached", session="s-1")
    pilot["script"] = [limited]

    def on_nap(_n):                                             # the server opens its terminal, then lets the request go
        live_session(uid)
        handoff.clear(run_id(kit), uid)
        kit.plan.set_status(uid, "done")
    pilot["on_nap"] = on_nap
    pilot["run"]()
    assert len(pilot["calls"]) == 1 and pilot["naps"] == 1


def test_a_take_whose_server_died_does_not_hold_the_unit(kit, pilot):
    from lib.harness import handoff
    uid = only_one_ready(kit)
    kit.plan.set_status(uid, "doing")
    pilot["script"] = [lambda _u: (handoff.request(run_id(kit), uid, "you", at=time.time() - 3600),
                                   result(rc=1, output="usage limit reached", session="s-1"))[1]]
    assert pilot["run"]() == 1
    assert len(pilot["calls"]) == 2 and handoff.read(run_id(kit), uid) is None


def test_a_stop_that_comes_as_the_agent_ends_is_honoured(kit, pilot):
    from lib.harness import handoff
    uid = only_one_ready(kit)
    pilot["script"] = [lambda _u: (handoff.request(run_id(kit), uid, "stop"), result(rc=1, output="usage limit reached"))[1]]
    assert pilot["run"]() == 0
    assert len(pilot["calls"]) == 1 and handoff.read(run_id(kit), uid) is None
    assert any(f"{uid} stopped" in line for line in pilot["echo"])


def test_a_cancel_cuts_a_usage_limits_wait_short(kit, pilot):
    from lib.harness import scheduler
    pilot["script"] = [result(rc=1, output="usage limit"), result(rc=1, output="rate limit")]
    pilot["on_nap"] = lambda _n: scheduler.request_cancel(run_id(kit))
    assert pilot["run"]() == 0
    assert pilot["naps"] == 1 and pilot["slept"] == [kit.plan.WAIT_TAKEN]
    assert any("cancelled" in line for line in pilot["echo"])


def test_a_hand_back_cuts_a_usage_limits_wait_short(kit, pilot):
    from lib.harness import handoff
    handoff.request("r-1", "a", "pilot", session="s-1", agent="claude")
    pilot["on_nap"] = lambda _n: None
    kit.plan._limit_wait(3600, "r-1")
    assert pilot["naps"] == 1


def test_a_usage_limits_wait_runs_its_course_otherwise(kit, pilot):
    from lib.harness import handoff
    handoff.request("r-1", "a", "pilot", session="s-1", agent="claude", closing=True)    # not the run's yet
    pilot["on_nap"] = lambda _n: None
    kit.plan._limit_wait(3 * kit.plan.WAIT_TAKEN, "r-1")
    assert pilot["naps"] == 3


def test_the_run_says_it_waits_again_after_running_something_else(kit, pilot):
    ready = [u["id"] for u in kit.plan.available() if u["runner"] == "agent"]
    a, b = ready[0], ready[1]
    for u in kit.plan.load()["units"]:
        if u["id"] not in (a, b):
            kit.plan.set_status(u["id"], "done", record=False)
    kit.plan.set_status(a, "doing")
    kit.plan.set_status(b, "blocked", "waits for something")
    live_session(a)

    def on_nap(n):
        if n == 1:
            kit.plan.set_status(b, "todo")                      # another unit comes up, runs and ends: then a is all that is left
        if n == 2:
            kit.plan.set_status(a, "done")
    pilot["on_nap"] = on_nap
    pilot["run"]()
    assert [e["units"] for e in run_log(kit) if e["type"] == "unit.waiting"] == [[a], [a]]


def test_a_unit_the_person_stopped_says_so_in_the_log(kit, pilot):
    uid = only_one_ready(kit)
    pilot["script"] = [lambda _u: result(rc=-15, handoff="stop")]
    pilot["run"]()
    assert finish_of(run_log(kit), uid)[0]["stopped"] is True

