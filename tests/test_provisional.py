"""The interviews no longer gate the drafting: units start from code and discovery (provisional), and are reopened to
refine once the interview they were missing is done. The pipeline declares those links as `soft`."""
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
    for uid in ("i18n", "confirm"):                                             # translating/confirming still waits
        assert {"interview-context", "interview-language", "interview-history"} <= set(unit(data, uid)["deps"])


def test_team_interviews_still_wait_for_the_answers_but_drafts_do_not(kit):
    ws = kit.docs.workspace()
    ws["project"]["interviews"] = "team"
    kit.docs.save_workspace(ws)
    kit.plan.sync()
    finish(kit.plan, "setup", "discovery:api", "discovery:web", "discovery:worker", "discovery-cross")
    ready = ready_ids(kit.plan)
    assert "interview-context" not in ready and "questionnaire" in ready and "repo-brief:api" in ready


def test_a_4x_plan_with_interview_gates_is_migrated(discovered):
    """An older kit stored hard interview deps and no `soft`: sync converts it, keeps progress, and is idempotent."""
    plan = discovered.plan
    data = plan.load()
    for u in data["units"]:
        u.pop("soft", None)
    unit(data, "repo-brief:api")["deps"] = ["interview-context"]
    unit(data, "domain")["deps"] = ["interview-language"]
    unit(data, "repo-brief:web").update(status="doing", notes="half way")
    plan.save(data)
    first = plan.sync()
    assert unit(first, "repo-brief:api")["deps"] == ["discovery-cross"]
    assert unit(first, "repo-brief:api")["soft"] == ["interview-context"]
    assert unit(first, "repo-brief:web")["status"] == "doing" and unit(first, "repo-brief:web")["notes"] == "half way"
    assert plan.sync() == first


def test_sync_keeps_the_provisional_marks(discovered):
    plan = discovered.plan
    plan.set_status("repo-brief:api", "doing")
    plan.sync()
    assert unit(plan.load(), "repo-brief:api")["provisional"] == ["interview-context"]


def test_dependents_follow_the_soft_links(discovered):
    plan = discovered.plan
    plan.set_status("repo-brief:api", "done")
    assert "repo-brief:api" in [u["id"] for u in plan.dependents(plan.load(), "interview-context")]


def test_starting_before_the_interview_makes_the_unit_provisional(discovered):
    plan = discovered.plan
    text = plan.prompt("repo-brief:api", unattended=True)
    assert "PROVISIONAL" in text and "interview-context" in text and "open-questions.md" in text
    assert "context · repo-brief:api" in text                                  # how to tag the question
    u = plan.set_status("repo-brief:api", "doing")
    assert u["provisional"] == ["interview-context"]


def test_starting_after_the_interview_is_not_provisional(discovered):
    plan = discovered.plan
    plan.set_status("interview-context", "done")
    u = plan.set_status("repo-brief:api", "doing")
    assert "provisional" not in u
    assert "PROVISIONAL" not in plan.prompt("repo-brief:api", unattended=True)


def test_finishing_the_interview_reopens_provisional_drafts_to_refine(discovered):
    plan = discovered.plan
    plan.set_status("repo-brief:api", "doing")
    plan.set_status("repo-brief:api", "done", "drafted from code")
    plan.set_status("repo-brief:web", "doing")                              # still being written
    plan.set_status("domain", "doing")
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
    plan.set_status("repo-brief:api", "doing")
    plan.set_status("repo-brief:api", "done")
    plan.set_status("interview-context", "done")
    u = plan.set_status("repo-brief:api", "doing")
    assert "provisional" not in u                                           # the interview is there now
    plan.set_status("repo-brief:api", "done")
    u = unit(plan.load(), "repo-brief:api")
    assert "refine" not in u and "redo" not in u and u["status"] == "done"


def test_interview_prompt_starts_from_the_drafts_questions(discovered):
    text = discovered.plan.prompt("interview-context")
    assert "DRAFT QUESTIONS" in text and "`context ·`" in text


def test_plan_show_marks_early_drafts(discovered):
    plan = discovered.plan
    lines = plan.render().splitlines()
    assert any("repo-brief:api" in l and "draft" in l for l in lines)
    assert not any("discovery-cross" in l and "draft" in l for l in lines)


def test_wizard_labels_early_drafts_in_both_languages(discovered):
    data = discovered.plan.load()
    for lang in ("es", "en"):
        w = discovered.wizard.W()
        w.lang = lang
        assert w.t("draft_lbl") in w.unit_label(discovered.plan.get(data, "domain"), data)
        assert w.t("draft_lbl") not in w.unit_label(discovered.plan.get(data, "discovery-cross"), data)
    assert discovered.wizard.T["es"]["draft_lbl"] != discovered.wizard.T["en"]["draft_lbl"]


def test_cli_done_on_an_interview_lists_the_units_to_refine(discovered):
    plan = discovered.plan
    plan.set_status("repo-brief:api", "doing")
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


# ---------- the pipeline declares the soft links ----------
@pytest.fixture
def pipeline(kit):
    from lib.harness import pipeline
    return pipeline


def test_expand_resolves_soft_links_like_needs(pipeline):
    spec = {"name": "t", "nodes": [
        {"id": "setup", "type": "setup"},
        {"id": "interview-context", "type": "interview-context", "needs": ["setup"]},
        {"for_each": "repos", "nodes": [{"id": "repo-brief:{repo}", "type": "repo-brief", "needs": ["setup"],
                                         "soft": ["interview-context"]}]},
        {"id": "domain", "type": "domain", "needs": ["setup"], "soft": ["repo-brief:*"]}]}
    got = {n["id"]: n for n in pipeline.expand(spec, repos=["a", "b"], predicates={})}
    assert got["repo-brief:a"]["soft"] == ["interview-context"]
    assert got["domain"]["soft"] == ["repo-brief:a", "repo-brief:b"]
    assert got["setup"]["soft"] == []


def test_validation_checks_soft_links(pipeline):
    spec = {"name": "t", "nodes": [{"id": "setup", "type": "setup"},
                                   {"id": "domain", "type": "domain", "needs": ["setup"], "soft": ["ghost"]}]}
    assert "nodes[1].soft: unknown node 'ghost'" in pipeline.validate(spec)


def test_schema_documents_soft(pipeline):
    import json
    schema = json.loads((pipeline.DIR / "schema.json").read_text(encoding="utf-8"))
    assert "soft" in schema["$defs"]["node"]["properties"]
