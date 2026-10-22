"""Autopilot writes a run event log: what ran, on which agent, how it ended and what it cost (feeds the KPIs and the
portal's live view)."""
from __future__ import annotations

import io, json, subprocess

import pytest


def run_events(kit) -> list[dict]:
    from lib.harness.events import EventLog
    logs = sorted(kit.common.CTX.runs.glob("*/events.jsonl"))
    assert len(logs) == 1
    return EventLog(logs[0]).read()[0]


@pytest.fixture
def pilot(kit, monkeypatch):
    plan = kit.plan
    plan.sync()
    plan.set_status("setup", "done")
    script = []

    def run_agent(agent, text, lang, uid, echo):
        status, rc, output = script.pop(0) if script else ("done", 0, "")
        if status:
            plan.set_status(uid, status)
        return subprocess.CompletedProcess([agent], rc, output, "")
    monkeypatch.setattr(plan, "which", lambda name: f"/bin/{name}")
    monkeypatch.setattr(plan, "_run_agent", run_agent)
    monkeypatch.setattr(plan, "prompt", lambda uid, lang="es", unattended=False: f"prompt {uid}")
    return script


def test_a_run_records_each_unit_and_how_it_ended(kit, pilot):
    assert kit.plan.run_autopilot(max_units=1, echo=lambda _: None) == 1
    ev = run_events(kit)
    assert [e["type"] for e in ev] == ["run.started", "unit.started", "unit.finished", "run.finished"]
    assert len({e["run"] for e in ev}) == 1
    started, finished = ev[1], ev[2]
    assert started["unit"].startswith("discovery:") and started["runner"] == "claude"
    assert finished["unit"] == started["unit"] and finished["outcome"] == "ok" and finished["status"] == "done"
    assert ev[3]["done"] == 1


def test_a_usage_limit_is_recorded_before_switching_agent(kit, pilot):
    pilot += [(None, 1, "usage limit reached"), ("done", 0, "")]
    kit.plan.run_autopilot(max_units=1, echo=lambda _: None)
    ev = run_events(kit)
    limited = [e for e in ev if e["type"] == "unit.finished" and e["outcome"] == "limited"]
    assert len(limited) == 1 and limited[0]["runner"] == "claude"
    assert [e["runner"] for e in ev if e["type"] == "unit.started"] == ["claude", "codex"]


def test_the_agent_stream_lands_in_the_run_log(kit, monkeypatch):
    from lib.adapters.runners import base
    from lib.harness.events import EventLog
    lines = [{"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "Read", "input": {"file_path": "a.py"}}]}},
             {"type": "result", "result": "ok", "total_cost_usd": 0.5, "usage": {"input_tokens": 10, "output_tokens": 2}}]

    class FakeProc:
        def __init__(self, cmd, **kw):
            self.stdout = io.StringIO("".join(json.dumps(l) + "\n" for l in lines))

        def wait(self):
            return 0

        def poll(self):
            return 0
    monkeypatch.setattr(base, "which", lambda name: f"/bin/{name}")
    monkeypatch.setattr(kit.plan.subprocess, "Popen", FakeProc)
    log = EventLog(kit.root / "events.jsonl")
    with kit.plan.recording(log, "r-test"):
        kit.plan._run_agent("claude", "do it", "en", "discovery:api", echo=lambda _: None)
    ev = log.read()[0]
    assert {"type": "tool.call", "name": "Read", "arg": "a.py"}.items() <= ev[0].items()
    usage = next(e for e in ev if e["type"] == "usage")
    assert (usage["run"], usage["unit"], usage["runner"], usage["cost_usd"]) == ("r-test", "discovery:api", "claude", 0.5)


def test_outside_a_run_nothing_is_recorded(kit, monkeypatch):
    class FakeProc:
        def __init__(self, cmd, **kw):
            self.stdout = io.StringIO("")

        def wait(self):
            return 0

        def poll(self):
            return 0
    from lib.adapters.runners import base
    monkeypatch.setattr(base, "which", lambda name: f"/bin/{name}")
    monkeypatch.setattr(kit.plan.subprocess, "Popen", FakeProc)
    kit.plan._run_agent("claude", "do it", "en", "discovery:api", echo=lambda _: None)
    assert not list(kit.common.CTX.runs.glob("*/events.jsonl"))
