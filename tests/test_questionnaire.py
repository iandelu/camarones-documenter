"""Deferred team interviews: a questionnaire the team answers offline, then agent units that consolidate the answers."""
from __future__ import annotations

import subprocess

import pytest


def unit(data, uid):
    return next(u for u in data["units"] if u["id"] == uid)


def ids(data):
    return [u["id"] for u in data["units"]]


def set_mode(kit, mode):
    ws = kit.docs.workspace()
    ws["project"]["interviews"] = mode
    kit.docs.save_workspace(ws)


# ---------- plan ----------
def test_projects_without_the_key_keep_live_interviews(kit):
    """3.x projects have no `interviews` key: same plan as before, no questionnaire units."""
    assert kit.docs.interview_mode() == "live"
    data = kit.plan.sync()
    assert "questionnaire" not in ids(data) and "answers" not in ids(data)
    assert unit(data, "interview-context")["deps"] == ["discovery-cross"]


def test_team_mode_adds_questionnaire_then_answers_before_the_interviews(kit):
    set_mode(kit, "team")
    data = kit.plan.sync()
    q, a = unit(data, "questionnaire"), unit(data, "answers")
    assert (q["runner"], q["deps"]) == ("agent", ["discovery-cross"])
    assert (a["runner"], a["deps"]) == ("wizard", ["questionnaire"])
    assert unit(data, "interview-context")["deps"] == ["answers"]
    assert ids(data).index("questionnaire") < ids(data).index("answers") < ids(data).index("interview-context")


def test_unknown_mode_falls_back_to_live(kit):
    set_mode(kit, "carrier-pigeon")
    assert kit.docs.interview_mode() == "live"


def test_switching_back_to_live_drops_the_pending_questionnaire(kit):
    set_mode(kit, "team")
    kit.plan.sync()
    set_mode(kit, "live")
    data = kit.plan.sync()
    assert unit(data, "questionnaire")["status"] == "dropped"
    assert unit(data, "answers")["status"] == "dropped"
    assert unit(data, "interview-context")["deps"] == ["discovery-cross"]
    set_mode(kit, "team")                                                 # and it comes back when chosen again
    data = kit.plan.sync()
    assert unit(data, "questionnaire")["status"] == "todo" and unit(data, "questionnaire")["notes"] == ""


def test_a_finished_questionnaire_is_kept_when_switching_to_live(kit):
    set_mode(kit, "team")
    kit.plan.sync()
    kit.plan.set_status("questionnaire", "done")
    set_mode(kit, "live")
    assert unit(kit.plan.sync(), "questionnaire")["status"] == "done"


def test_team_mode_after_live_interviews_does_not_ask_again(kit):
    kit.plan.sync()
    kit.plan.set_status("interview-context", "done")
    set_mode(kit, "team")
    data = kit.plan.sync()
    assert unit(data, "questionnaire")["status"] == "dropped"
    assert unit(data, "answers")["status"] == "dropped"
    assert unit(data, "interview-context")["status"] == "done"


# ---------- autopilot ----------
@pytest.fixture
def pilot(kit, monkeypatch):
    plan = kit.plan
    calls = []

    def run_agent(agent, text, lang, uid, echo):
        calls.append(uid)
        plan.set_status(uid, "done")
        return subprocess.CompletedProcess([agent], 0, "", "")
    monkeypatch.setattr(plan, "which", lambda name: f"/bin/{name}")
    monkeypatch.setattr(plan, "_run_agent", run_agent)
    monkeypatch.setattr(plan, "prompt", lambda uid, lang="es", unattended=False: f"prompt {uid}")
    return calls


def finish(kit, *prefixes):
    for u in kit.plan.load()["units"]:
        if u["id"].startswith(prefixes):
            kit.plan.set_status(u["id"], "done")


def test_autopilot_writes_the_questionnaire_and_waits_for_answers(kit, pilot):
    set_mode(kit, "team")
    kit.plan.sync()
    finish(kit, "setup", "discovery")
    echo = []
    kit.plan.run_autopilot(echo=echo.append)
    assert "questionnaire" in pilot
    assert not any(uid.startswith("interview-") for uid in pilot)
    assert any("answers" in l and "wizard step" in l for l in echo)


def test_autopilot_consolidates_team_answers(kit, pilot):
    set_mode(kit, "team")
    kit.plan.sync()
    finish(kit, "setup", "discovery", "questionnaire", "answers")
    kit.plan.run_autopilot(echo=lambda _: None, max_units=3)
    assert pilot[0] == "interview-context"


def test_autopilot_still_leaves_live_interviews_to_a_human(kit, pilot):
    kit.plan.sync()
    finish(kit, "setup", "discovery")
    kit.plan.run_autopilot(echo=lambda _: None)
    assert pilot == []
