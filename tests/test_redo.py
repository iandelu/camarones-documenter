"""Redoing a finished unit later (e.g. an interview): review-and-update session, optional reopening of what built on it."""
from __future__ import annotations

import os, subprocess, sys

import pytest

from conftest import KIT_DIR


def unit(data, uid):
    return next(u for u in data["units"] if u["id"] == uid)


def finish(plan, *uids):
    for uid in uids:
        plan.set_status(uid, "done", record=False)


@pytest.fixture
def interviewed(kit):
    """setup → discovery → cross → interview-context done; its dependents half done."""
    plan = kit.plan
    plan.sync()
    finish(plan, "setup", "discovery:api", "discovery:web", "discovery:worker", "discovery-cross")
    plan.set_status("interview-context", "done", "context agreed")
    finish(plan, "interview-language", "repo-brief:api", "domain")          # domain ← interview-language ← context
    return kit


# ---------- plan ----------
def test_dependents_are_the_finished_units_built_on_it(interviewed):
    plan = interviewed.plan
    ids = [u["id"] for u in plan.dependents(plan.load(), "interview-context")]
    assert ids == ["interview-language", "repo-brief:api", "domain"]                    # plan order, transitive
    assert "repo-brief:web" not in ids                                                  # not done: nothing to redo


def test_redo_reopens_the_unit_and_remembers_when_it_was_done(interviewed):
    plan = interviewed.plan
    was = unit(plan.load(), "interview-context")["updated"]
    plan.redo("interview-context")
    u = unit(plan.load(), "interview-context")
    assert u["status"] == "todo" and u["redo"] == was
    assert unit(plan.load(), "domain")["status"] == "done"                              # dependents untouched
    assert "**interview-context** → redo" in plan.LOG.read_text(encoding="utf-8")
    assert "interview-context" in [x["id"] for x in plan.available()]


def test_redo_can_reopen_chosen_dependents(interviewed):
    plan = interviewed.plan
    plan.redo("interview-context", also=["domain"])
    data = plan.load()
    assert unit(data, "domain")["status"] == "todo" and "redo" in unit(data, "domain")
    assert unit(data, "repo-brief:api")["status"] == "done"
    assert "domain" not in [x["id"] for x in plan.available()]                          # still waits for its deps


def test_only_finished_units_can_be_redone(interviewed):
    with pytest.raises(ValueError):
        interviewed.plan.redo("repo-brief:web")


def test_sync_keeps_the_redo_mark_and_done_clears_it(interviewed):
    plan = interviewed.plan
    plan.redo("interview-context")
    assert "redo" in unit(plan.sync(), "interview-context")
    plan.set_status("interview-context", "done")
    assert "redo" not in unit(plan.load(), "interview-context")


def test_redo_prompt_reviews_instead_of_resuming(interviewed):
    plan = interviewed.plan
    plan.note("interview-context", "asked about environments")
    plan.redo("interview-context")
    assert not plan.note_file("interview-context").exists()                            # old checkpoints archived
    text = plan.prompt("interview-context")
    assert "REDO" in text and "RESUME" not in text
    assert "before-redo" in text                                                        # points at the old checkpoints
    assert "`domain`" in text                                                           # pages that may now be outdated
    plan.set_status("interview-context", "doing")
    plan.note("interview-context", "half way through the new round")
    text = plan.prompt("interview-context")
    assert "REDO" in text and "RESUME" in text                                          # an interrupted redo resumes


# ---------- CLI ----------
def cli(kit, *args):
    env = {**os.environ, "CAMARONES_ROOT": str(kit.root), "PYTHONUTF8": "1"}
    return subprocess.run([sys.executable, str(KIT_DIR / "camarones.py"), "plan", *args], env=env,
                          capture_output=True, text=True, encoding="utf-8", cwd=kit.ws)


def test_cli_plan_redo(interviewed):
    r = cli(interviewed, "redo", "interview-context", "--also", "domain")
    assert r.returncode == 0, r.stdout + r.stderr
    data = interviewed.plan.load()
    assert unit(data, "interview-context")["status"] == "todo" and unit(data, "domain")["status"] == "todo"
    assert "repo-brief:api" in r.stdout                                                 # hint: still done, may be outdated
    r = cli(interviewed, "redo", "repo-brief:web")
    assert r.returncode != 0


# ---------- wizard ----------
@pytest.fixture(autouse=True)
def no_waits(kit, monkeypatch):
    monkeypatch.setattr(kit.wizard.time, "sleep", lambda _s: None)
    monkeypatch.setattr(kit.wizard.console, "clear", lambda *a, **kw: None)


def test_wizard_redo_asks_about_dependents_then_offers_to_start(interviewed, fake_wizard, monkeypatch):
    started = []
    monkeypatch.setattr(interviewed.wizard.W, "run_unit", lambda self, u: started.append(u["id"]))
    target = unit(interviewed.plan.load(), "interview-context")
    w = fake_wizard([target, ["domain"], True])
    w.do_redo()
    data = interviewed.plan.load()
    assert unit(data, "interview-context")["status"] == "todo" and unit(data, "domain")["status"] == "todo"
    assert started == ["interview-context"]


def test_wizard_redo_back_changes_nothing(interviewed, fake_wizard):
    target = unit(interviewed.plan.load(), "interview-context")
    fake_wizard([target, None]).do_redo()                                               # Esc on the dependents list
    assert unit(interviewed.plan.load(), "interview-context")["status"] == "done"


def test_wizard_redo_with_nothing_done(kit, fake_wizard):
    kit.plan.sync()
    w = fake_wizard([])
    w.do_redo()
    assert w.answers.asked == []
