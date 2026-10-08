"""Autopilot: ready agent units back to back, switching agents on usage limits, stopping when a human is needed."""
from __future__ import annotations

import json, subprocess, threading, time

import pytest


class Stop(Exception):
    pass


@pytest.fixture
def pilot(kit, monkeypatch):
    plan = kit.plan
    plan.sync()
    plan.set_status("setup", "done")
    box = {"calls": [], "script": [], "echo": []}

    def run_agent(agent, text, lang, uid, echo, **kw):
        box["calls"].append((agent, uid))
        step = box["script"].pop(0) if box["script"] else ("done", 0, "")
        status, rc, output = step
        if status:
            plan.set_status(uid, status)
        return subprocess.CompletedProcess([agent], rc, output, "")

    def sleep(_s):
        raise Stop
    monkeypatch.setattr(plan, "which", lambda name: f"/bin/{name}")
    monkeypatch.setattr(plan, "_run_agent", run_agent)
    monkeypatch.setattr(plan, "prompt", lambda uid, lang="es", unattended=False, **kw: f"prompt {uid}")
    monkeypatch.setattr(plan.time, "sleep", sleep)
    box["run"] = lambda **kw: plan.run_autopilot(echo=box["echo"].append, **kw)
    return box


def test_nothing_to_run_without_agents(kit, monkeypatch):
    monkeypatch.setattr(kit.plan, "which", lambda name: None)
    assert kit.plan.run_autopilot(echo=lambda _: None) == 0


def test_runs_ready_units_back_to_back(pilot):
    assert pilot["run"](max_units=2) == 2
    assert [a for a, _ in pilot["calls"]] == ["claude", "claude"]
    assert all(uid.startswith("discovery:") for _, uid in pilot["calls"])


def test_stops_when_a_unit_ends_without_done_or_block(pilot):
    pilot["script"] = [("doing", 0, "")]
    assert pilot["run"]() == 0
    assert len(pilot["calls"]) == 1
    assert any("ended without" in l for l in pilot["echo"])


def test_switches_agent_on_usage_limit(pilot):
    pilot["script"] = [(None, 1, "Claude usage limit reached, resets at 5pm"), ("done", 0, "")]
    assert pilot["run"](max_units=1) == 1
    assert [a for a, _ in pilot["calls"]] == ["claude", "codex"]
    assert pilot["calls"][0][1] == pilot["calls"][1][1]                   # same unit retried on the other agent


def test_waits_when_every_agent_is_limited(pilot):
    pilot["script"] = [(None, 1, "usage limit"), (None, 1, "rate limit")]
    with pytest.raises(Stop):
        pilot["run"]()
    assert any("All agents are at their usage limit" in l for l in pilot["echo"])


def test_any_other_failure_stops(pilot):
    pilot["script"] = [(None, 2, "segfault")]
    assert pilot["run"]() == 0
    assert any("failed on" in l and "segfault" in l for l in pilot["echo"])


def test_interviews_are_left_to_a_human(kit, pilot):
    for u in kit.plan.load()["units"]:
        if u["id"].startswith("discovery"):
            kit.plan.set_status(u["id"], "done")
    pilot["run"]()
    ran = [uid for _, uid in pilot["calls"]]
    assert ran and not any(uid.startswith("interview-") for uid in ran)          # drafts go on without them
    assert any("interview" in l and "needs you" in l for l in pilot["echo"])


# ---------- parallel workers ----------
@pytest.fixture
def workers(kit, monkeypatch):
    """A fake agent that takes a little while and records how many units run at once."""
    plan = kit.plan
    plan.sync()
    plan.set_status("setup", "done")
    box = {"calls": [], "active": set(), "peak": 0, "overlaps": [], "owners": [], "fail": set(), "echo": []}
    guard = threading.Lock()

    def run_agent(agent, text, lang, uid, echo, session=None, **kw):
        with guard:
            box["calls"].append(uid)
            if box["active"] and (uid in plan.GLOBAL_TYPES or any(a in plan.GLOBAL_TYPES for a in box["active"])
                                  or plan.get(plan.load(), uid)["type"] in plan.GLOBAL_TYPES):
                box["overlaps"].append((uid, sorted(box["active"])))
            box["active"].add(uid)
            box["peak"] = max(box["peak"], len(box["active"]))
            box["owners"].append((plan.get(plan.load(), uid).get("owner") or {}).get("session"))
        echo("working")
        time.sleep(0.3)
        with guard:
            box["active"].discard(uid)
        if uid in box["fail"]:
            return subprocess.CompletedProcess([agent], 2, "boom", "")
        plan.set_status(uid, "done")
        return subprocess.CompletedProcess([agent], 0, "", "")
    monkeypatch.setattr(plan, "which", lambda name: f"/bin/{name}" if name == "claude" else None)
    monkeypatch.setattr(plan, "_run_agent", run_agent)
    monkeypatch.setattr(plan, "prompt", lambda uid, lang="es", unattended=False, **kw: f"prompt {uid}")
    box["run"] = lambda **kw: plan.run_autopilot(echo=box["echo"].append, **kw)
    return box


def test_jobs_run_units_side_by_side(workers):
    assert workers["run"](jobs=3, max_units=3) == 3
    assert workers["peak"] == 3
    assert sorted(workers["calls"]) == ["discovery:api", "discovery:web", "discovery:worker"]
    assert all(s and s.startswith("autopilot-w") for s in workers["owners"])          # claimed per worker
    assert any(l.startswith("[w") and "working" in l for l in workers["echo"])        # prefixed output


def test_one_job_runs_one_unit_at_a_time(workers):
    workers["run"](max_units=3)
    assert workers["peak"] == 1


def test_global_units_run_alone(kit, workers):
    for u in kit.plan.load()["units"]:
        if u["id"].startswith(("discovery", "repo-brief", "repo-wiki")):
            kit.plan.set_status(u["id"], "done")
    workers["run"](jobs=3, max_units=6)
    assert "arch-system" in workers["calls"]
    assert workers["overlaps"] == []


def test_a_failure_stops_new_units_and_waits_for_running_ones(workers):
    workers["fail"].add("discovery:api")
    done = workers["run"](jobs=2)
    assert done == 1                                                                  # the unit running next to it
    assert len(workers["calls"]) == 2
    assert any("failed on discovery:api" in l for l in workers["echo"])
    assert "owner" not in kit_unit(workers, "discovery:api")                            # released for a later run


def kit_unit(workers, uid):
    import lib.plan as plan
    return plan.get(plan.load(), uid)


def test_units_held_by_another_window_are_left_alone(kit, workers):
    kit.plan.claim("discovery:api", "window-1")
    workers["run"](jobs=2, max_units=2)
    assert "discovery:api" not in workers["calls"]
    assert kit.plan.get(kit.plan.load(), "discovery:api")["owner"]["session"] == "window-1"


def test_stream_rendering_shows_tool_calls(kit):
    ev = {"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "Read", "input": {"file_path": "a.py"}}]}}
    shown, err = kit.plan._render("claude", json.dumps(ev))
    assert shown == ["· Read a.py"] and err == ""
    shown, err = kit.plan._render("codex", json.dumps({"type": "turn.failed", "error": {"message": "usage limit"}}))
    assert err == "usage limit"
