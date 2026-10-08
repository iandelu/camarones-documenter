"""The interviews no longer gate the drafting: units start from code and discovery (provisional), and are reopened to
refine once the interview they were missing is done."""
from __future__ import annotations

import os, subprocess, sys

import pytest

from conftest import KIT_DIR


def unit(data, uid):
    return next(u for u in data["units"] if u["id"] == uid)


def finish(plan, *uids):
    for uid in uids:
        plan.set_status(uid, "done", record=False)


def ready_ids(plan):
    return [u["id"] for u in plan.available()]


@pytest.fixture
def discovered(kit):
    plan = kit.plan
    plan.sync()
    finish(plan, "setup", "discovery:api", "discovery:web", "discovery:worker", "discovery-cross")
    return kit


def test_drafting_units_do_not_wait_for_the_interviews(discovered):
    plan = discovered.plan
    ready = ready_ids(plan)
    for uid in ("interview-context", "repo-brief:api", "repo-brief:web", "domain", "data", "decisions-quality"):
        assert uid in ready, uid
    data = plan.load()
    assert unit(data, "repo-brief:api")["soft"] == ["interview-context"]
    assert unit(data, "domain")["soft"] == ["interview-language"]
    assert unit(data, "flows-catalog")["deps"] == ["arch-system"]
    assert "interview-history" in unit(data, "flows-catalog")["soft"]
    assert unit(data, "interview-language")["deps"] == ["interview-context"]   # interviews keep their order


def test_team_interviews_still_wait_for_the_answers_but_drafts_do_not(kit):
    ws = kit.docs.workspace()
    ws["project"]["interviews"] = "team"
    kit.docs.save_workspace(ws)
    kit.plan.sync()
    finish(kit.plan, "setup", "discovery:api", "discovery:web", "discovery:worker", "discovery-cross")
    ready = ready_ids(kit.plan)
    assert "interview-context" not in ready and "questionnaire" in ready and "repo-brief:api" in ready


def test_a_3x_plan_with_interview_gates_is_migrated(discovered):
    """An older kit stored hard interview deps and no `soft`: sync converts it, keeps progress, and is idempotent."""
    plan = discovered.plan

    def old_form(data):
        for u in data["units"]:
            u.pop("soft", None)
        unit(data, "repo-brief:api")["deps"] = ["interview-context"]
        unit(data, "domain")["deps"] = ["interview-language"]
        unit(data, "repo-brief:web").update(status="doing", notes="half way")
    plan.mutate(old_form)
    first = plan.sync()
    assert unit(first, "repo-brief:api")["deps"] == ["discovery-cross"]
    assert unit(first, "repo-brief:api")["soft"] == ["interview-context"]
    assert unit(first, "repo-brief:web")["status"] == "doing" and unit(first, "repo-brief:web")["notes"] == "half way"
    assert plan.sync() == first
    plan.claim("repo-brief:web", "A")                                       # the old in-progress unit can be resumed


def test_dependents_follow_the_soft_links(discovered):
    plan = discovered.plan
    plan.set_status("repo-brief:api", "done")
    assert "repo-brief:api" in [u["id"] for u in plan.dependents(plan.load(), "interview-context")]


def test_starting_before_the_interview_makes_the_unit_provisional(discovered):
    plan = discovered.plan
    u = plan.claim("repo-brief:api", "A")
    assert u["provisional"] == ["interview-context"]
    text = plan.prompt("repo-brief:api", unattended=True)
    assert "PROVISIONAL" in text and "interview-context" in text and "plan ask" in text


def test_starting_after_the_interview_is_not_provisional(discovered):
    plan = discovered.plan
    plan.set_status("interview-context", "done")
    u = plan.claim("repo-brief:api", "A")
    assert "provisional" not in u
    assert "PROVISIONAL" not in plan.prompt("repo-brief:api", unattended=True)


def test_finishing_the_interview_reopens_provisional_drafts_to_refine(discovered):
    plan = discovered.plan
    plan.claim("repo-brief:api", "A")
    plan.set_status("repo-brief:api", "done", "drafted from code")
    plan.claim("repo-brief:web", "B")                                       # still being written
    plan.claim("domain", "C")
    plan.set_status("domain", "done")                                       # provisional on interview-language only
    reopened = plan.set_status("interview-context", "done", "context agreed")
    data = plan.load()
    api = unit(data, "repo-brief:api")
    assert api["status"] == "todo" and api["refine"] == ["interview-context"] and api.get("redo")
    web = unit(data, "repo-brief:web")
    assert web["status"] == "doing" and web["refine"] == ["interview-context"] and not web.get("provisional")
    assert unit(data, "domain")["status"] == "done"
    assert "refine" in plan.LOG.read_text(encoding="utf-8")
    assert reopened["reopened"] == ["repo-brief:api"]                       # what the CLI reports
    text = plan.prompt("repo-brief:api", unattended=True)
    assert "REFINE" in text and "interview-context" in text and "the user asked to go over it again" not in text
    assert "repo-brief:api" in ready_ids(plan)


def test_closing_a_refine_clears_it(discovered):
    plan = discovered.plan
    plan.claim("repo-brief:api", "A")
    plan.set_status("repo-brief:api", "done")
    plan.set_status("interview-context", "done")
    u = plan.claim("repo-brief:api", "A")
    assert "provisional" not in u                                           # the interview is there now
    plan.set_status("repo-brief:api", "done")
    u = unit(plan.load(), "repo-brief:api")
    assert "refine" not in u and "redo" not in u and u["status"] == "done"


def test_cli_done_on_an_interview_lists_the_units_to_refine(discovered):
    plan = discovered.plan
    plan.claim("repo-brief:api", "A")
    plan.set_status("repo-brief:api", "done")
    env = {**os.environ, "CAMARONES_ROOT": str(discovered.root), "PYTHONUTF8": "1"}
    r = subprocess.run([sys.executable, str(KIT_DIR / "camarones.py"), "plan", "done", "interview-context", "--note", "ok"],
                       env=env, capture_output=True, text=True, encoding="utf-8", cwd=discovered.ws)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "refine" in r.stdout and "repo-brief:api" in r.stdout


def test_quick_profile_is_unchanged(kit):
    ws = kit.docs.workspace()
    ws["project"]["profile"] = "quick"
    kit.docs.save_workspace(ws)
    data = kit.plan.sync()
    assert all(not u.get("soft") for u in data["units"])
