"""Autopilot: ready agent units back to back, switching agents on usage limits, stopping when a human is needed."""
from __future__ import annotations

import json, subprocess

import pytest


class Stop(Exception):
    pass


@pytest.fixture
def pilot(kit, monkeypatch):
    plan = kit.plan
    plan.sync()
    plan.set_status("setup", "done")
    box = {"calls": [], "script": [], "echo": []}

    def run_agent(agent, text, lang, uid, echo):
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
    monkeypatch.setattr(plan, "prompt", lambda uid, lang="es", unattended=False: f"prompt {uid}")
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
    assert pilot["run"]() == 0
    assert not pilot["calls"]
    assert any("interview" in l and "needs you" in l for l in pilot["echo"])


def test_stream_rendering_shows_tool_calls(kit):
    ev = {"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "Read", "input": {"file_path": "a.py"}}]}}
    shown, err = kit.plan._render("claude", json.dumps(ev))
    assert shown == ["· Read a.py"] and err == ""
    shown, err = kit.plan._render("codex", json.dumps({"type": "turn.failed", "error": {"message": "usage limit"}}))
    assert err == "usage limit"
