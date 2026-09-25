"""Wizard flows driven with queued answers (no terminal): menus must survive every state of the project."""
from __future__ import annotations

import pytest
from questionary import Choice


@pytest.fixture(autouse=True)
def no_waits(kit, monkeypatch):
    monkeypatch.setattr(kit.wizard.time, "sleep", lambda _s: None)
    monkeypatch.setattr(kit.wizard.console, "clear", lambda *a, **kw: None)


def test_checkbox_with_nothing_selectable_goes_back(kit):
    w = kit.wizard.W()
    assert w.chk("pick", [Choice("api", "api", disabled="no brief")]) is None     # questionary would crash here


def test_wikis_menu_with_no_ready_repo_does_not_crash(wired, fake_wizard, monkeypatch):
    wired.docs.set_wiki_repos(["api"])                                           # chosen, but no INSTRUCTIONS.md yet
    wired.plan.sync()
    monkeypatch.setattr(wired.env, "openwiki_generate", lambda *a, **kw: pytest.fail("must not start a run"))
    w = fake_wizard(["gen", None])
    w.do_wikis()
    assert len(w.answers.asked) == 2                                             # no repo picker in between


def test_choosing_wiki_repos_updates_the_plan(wired, fake_wizard):
    wired.plan.sync()
    w = fake_wizard(["choose", ["web"], None])
    w.do_wikis()
    assert wired.docs.wiki_repos() == ["web"]
    units = {u["id"]: u["status"] for u in wired.plan.load()["units"]}
    assert units["repo-wiki:web"] == "todo" and units["repo-wiki:api"] == "dropped"


def test_main_menu_exit_and_escape(kit, fake_wizard):
    kit.common.save_json(kit.wizard.FIRSTRUN, {"step": 6, "done": True})
    kit.plan.sync()
    fake_wizard(["exit"])._run()
    w = fake_wizard([None, False, None, True])                                   # Esc → "stay", Esc → "leave"
    w._run()
    assert len(w.answers.asked) == 4


def test_menu_errors_are_shown_not_raised(kit, fake_wizard, monkeypatch):
    kit.common.save_json(kit.wizard.FIRSTRUN, {"step": 6, "done": True})
    kit.plan.sync()
    monkeypatch.setattr(kit.wizard.W, "do_status", lambda self: 1 / 0)
    fake_wizard(["status", "exit"])._run()
