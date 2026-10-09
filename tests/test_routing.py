"""Routing by tier (H10, H21): each kind of work names an ordered list of runners; the first installed one runs it.
Local models only through OpenCode, and never for agentic-heavy work unless a node allows it."""
from __future__ import annotations

import pytest


@pytest.fixture
def routing(kit):
    from lib.harness import routing
    return routing


def test_defaults_keep_todays_agents_for_every_tier(routing):
    assert routing.table({}, {}) == {t: ["claude", "codex"] for t in routing.TIERS}


def test_team_config_then_machine_prefs_override_per_tier(routing):
    ws = {"agents": {"routing": {"bounded": ["codex"], "judge": ["codex"]}}}
    prefs = {"routing": {"bounded": ["opencode:ollama/qwen3-coder:30b", "codex"]}}
    t = routing.table(ws, prefs)
    assert t["bounded"] == ["opencode:ollama/qwen3-coder:30b", "codex"]
    assert t["judge"] == ["codex"] and t["agentic-heavy"] == ["claude", "codex"]


def test_unknown_tier_is_an_error(routing):
    with pytest.raises(ValueError, match="bounded"):
        routing.table({"agents": {"routing": {"bonded": ["codex"]}}}, {})


def test_a_target_is_runner_plus_optional_model(routing):
    r = routing.parse("opencode:ollama/qwen3-coder:30b")
    assert (r.runner, r.model, r.local, str(r)) == ("opencode", "ollama/qwen3-coder:30b", True, "opencode:ollama/qwen3-coder:30b")
    assert routing.parse("claude").model is None and not routing.parse("claude:opus").local


def test_first_installed_runner_wins(routing):
    t = {"bounded": ["opencode:ollama/x", "codex", "claude"]}
    route, notes = routing.pick("bounded", t, available=lambda rid: rid == "claude")
    assert str(route) == "claude"
    assert any("opencode" in n and "not installed" in n for n in notes)       # a local model without OpenCode is reported


def test_local_models_are_refused_for_agentic_heavy_work(routing):
    t = {"agentic-heavy": ["opencode:ollama/x", "claude"]}
    route, notes = routing.pick("agentic-heavy", t, available=lambda rid: True)
    assert str(route) == "claude" and any("agentic-heavy" in n for n in notes)
    route, _ = routing.pick("agentic-heavy", t, available=lambda rid: True, allow_local=True)
    assert str(route) == "opencode:ollama/x"


def test_local_models_only_through_opencode(routing):
    route, notes = routing.pick("bounded", {"bounded": ["codex:ollama/x"]}, available=lambda rid: True)
    assert route is None and any("OpenCode" in n for n in notes)


def test_nothing_installed_gives_no_route(routing):
    route, notes = routing.pick("judge", {"judge": ["claude", "codex"]}, available=lambda rid: False)
    assert route is None and len(notes) == 2


def test_autopilot_follows_the_agentic_heavy_routing(kit, monkeypatch):
    plan = kit.plan
    plan.sync()
    plan.set_status("setup", "done")
    ws = kit.docs.workspace()
    ws["agents"] = {"routing": {"agentic-heavy": ["codex:o5", "claude"]}}
    kit.docs.save_workspace(ws)
    calls = []

    def run_agent(agent, text, lang, uid, echo):
        calls.append(agent)
        plan.set_status(uid, "done")
        import subprocess
        return subprocess.CompletedProcess([agent], 0, "", "")
    monkeypatch.setattr(plan, "which", lambda name: f"/bin/{name}")
    monkeypatch.setattr(plan, "_run_agent", run_agent)
    monkeypatch.setattr(plan, "prompt", lambda uid, lang="es", unattended=False: "p")
    assert plan.run_autopilot(max_units=1, echo=lambda _: None) == 1
    assert calls == ["codex:o5"]


def test_autopilot_hands_the_model_to_the_runner(kit, monkeypatch):
    import io
    from lib.adapters.runners import base
    seen = {}

    class FakeProc:
        def __init__(self, cmd, **kw):
            seen["cmd"] = cmd
            self.stdout = io.StringIO("")

        def wait(self):
            return 0

        def poll(self):
            return 0
    monkeypatch.setattr(base, "which", lambda name: f"/bin/{name}")
    monkeypatch.setattr(kit.plan.subprocess, "Popen", FakeProc)
    kit.plan._run_agent("codex:o5", "do it", "en", "discovery:api", echo=lambda _: None)
    assert seen["cmd"][0] == "/bin/codex" and seen["cmd"][-3:-1] == ["--model", "o5"]
