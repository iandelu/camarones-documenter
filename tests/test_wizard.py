"""Wizard flows driven with queued answers (no terminal): menus must survive every state of the project."""
from __future__ import annotations

import re

import pytest
from questionary import Choice, Separator


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


# ---------- quick C4 draft (first look) ----------
@pytest.fixture
def first_look(kit, monkeypatch):
    page = kit.docs.DOCS / "architecture" / "first-look.md"
    page.parent.mkdir(parents=True)
    page.write_text("# First look\n", encoding="utf-8")
    calls = {"draft": 0, "portal": []}

    def draft(log=None, **kw):
        calls["draft"] += 1
        return None                                                              # scan failed → again / skip menu
    monkeypatch.setattr(kit.wizard.quickarch, "draft", draft)
    monkeypatch.setattr(kit.wizard.W, "open_portal", lambda self, h="": calls["portal"].append(h))
    return calls


def test_saved_first_look_is_kept_without_rescanning(first_look, fake_wizard):
    w = fake_wizard(["keep"])
    assert w.arch_flow() == "saved"
    assert first_look["draft"] == 0
    assert "first-look" not in w.answers.asked[0] and "ya está hecho" in w.answers.asked[0]


def test_saved_first_look_can_be_viewed_then_redone(first_look, fake_wizard):
    w = fake_wizard(["view", "redo", "skip"])
    assert w.arch_flow() == "skipped"
    assert first_look["portal"] == ["#/c4"] and first_look["draft"] == 1


def test_escape_on_a_saved_first_look_goes_back(kit, first_look, fake_wizard):
    assert fake_wizard([None]).arch_flow() == kit.wizard.BACK


# ---------- stack + tooling radar (first-run step and menu) ----------
def test_every_string_exists_in_both_languages(kit):
    T = kit.wizard.T
    assert set(T["es"]) == set(T["en"])


@pytest.mark.parametrize("state, step", [
    ({}, "name"), ({"step": 3, "done": False}, "setup"),
    ({"step": 4, "done": False}, "arch"), ({"step": 5, "done": False}, "intro"),   # firstrun.json from before 3.3
    ({"step": 4, "name": "stack", "done": False}, "stack"), ({"step": 0, "name": "arch"}, "arch"),
])
def test_first_run_resumes_on_the_same_step(kit, state, step):
    W = kit.wizard
    assert W.STEPS[W.resume_step(state)] == step


@pytest.fixture
def stack_screen(kit, monkeypatch):
    portal = []
    monkeypatch.setattr(kit.wizard.W, "open_portal", lambda self, h="": portal.append(h))
    return portal


def test_stack_step_accepts_the_detected_stack(kit, stack_screen, fake_wizard):
    w = fake_wizard(["view", "ok"])
    assert w.stack_flow() == "done"
    assert stack_screen == ["#/docs/overview/tooling.md"]
    assert (kit.docs.DOCS / "overview" / "tooling.md").exists()
    assert all("stack" not in r for r in kit.docs.workspace()["repos"])


def test_stack_step_fixes_a_repo_stack(kit, stack_screen, fake_wizard):
    w = fake_wizard(["fix", "api", "Java 21 · Spring Boot", "fix", "web", "Node.js · React", "ok"])
    assert w.stack_flow() == "done"
    rows = {r["name"]: r for r in kit.docs.workspace()["repos"]}
    assert rows["api"]["stack"] == "Java 21 · Spring Boot"
    assert "stack" not in rows["web"]                                     # same as detected: nothing to override
    assert "Java 21 · Spring Boot" in (kit.docs.DOCS / "overview" / "tooling.md").read_text(encoding="utf-8")


def test_stack_step_escape_goes_back(kit, stack_screen, fake_wizard):
    assert fake_wizard([None]).stack_flow() == kit.wizard.BACK
    w = fake_wizard(["fix", None, "ok"])                                  # Esc in the repo picker: back to the screen
    assert w.stack_flow() == "done"


# ---------- ⬆️ update Camarón ----------
@pytest.fixture
def said(kit, monkeypatch):
    out: list[str] = []
    monkeypatch.setattr(kit.wizard.W, "say", lambda self, m, style="": out.append(str(getattr(m, "renderable", m))))
    return out


def test_kit_update_on_a_local_kit_copy_explains_instead_of_running_git(kit, fake_wizard, monkeypatch, said):
    monkeypatch.setattr(kit.wizard.upgrade, "check", lambda *a, **kw: pytest.fail("must not touch git"))
    fake_wizard([]).do_kitupdate()
    assert "camaron unlink" in said[0]


def test_kit_update_offers_and_respects_no(kit, fake_wizard, monkeypatch):
    monkeypatch.setenv("CAMARONES_GLOBAL", "1")
    monkeypatch.setattr(kit.wizard.upgrade, "check", lambda *a, **kw: {"current": "3.8.0", "latest": "3.9.0", "behind": 4})
    monkeypatch.setattr(kit.wizard.upgrade, "self_update", lambda *a, **kw: pytest.fail("user said no"))
    w = fake_wizard([False])
    w.do_kitupdate()
    assert len(w.answers.asked) == 1


def test_kit_update_when_already_current_asks_nothing(kit, fake_wizard, monkeypatch, said):
    monkeypatch.setenv("CAMARONES_GLOBAL", "1")
    monkeypatch.setattr(kit.wizard.upgrade, "check", lambda *a, **kw: {"current": "3.8.0", "latest": "3.8.0", "behind": 0})
    fake_wizard([]).do_kitupdate()
    assert "3.8.0" in said[0]


def test_kit_update_yes_updates_then_restarts(kit, fake_wizard, monkeypatch):
    monkeypatch.setenv("CAMARONES_GLOBAL", "1")
    calls = []
    monkeypatch.setattr(kit.wizard.upgrade, "check", lambda *a, **kw: {"current": "3.8.0", "latest": "3.8.0", "behind": 1})
    monkeypatch.setattr(kit.wizard.upgrade, "self_update", lambda log=print, **kw: calls.append("update") or "3.8.0")
    monkeypatch.setattr(kit.wizard.upgrade, "relaunch_global", lambda: calls.append("relaunch"))
    fake_wizard([True]).do_kitupdate()
    assert calls == ["update", "relaunch"]


def test_kit_update_failure_is_reported_not_raised(kit, fake_wizard, monkeypatch, said):
    monkeypatch.setenv("CAMARONES_GLOBAL", "1")

    def offline(*a, **kw):
        raise RuntimeError("could not reach the kit")
    monkeypatch.setattr(kit.wizard.upgrade, "check", offline)
    fake_wizard([]).do_kitupdate()
    assert "could not reach the kit" in said[0]


# ---------- main menu: daily actions on top, the rest in sections ----------
@pytest.fixture
def menu(kit, monkeypatch):
    """Drives _run with queued answers and records every list it showed: [(msg, values, default)]."""
    kit.common.save_json(kit.wizard.FIRSTRUN, {"step": 6, "done": True})
    kit.plan.sync()
    shown, ran = [], []
    W = kit.wizard.W
    monkeypatch.setattr(W, "banner", lambda self, *a, **kw: None)
    monkeypatch.setattr(W, "pause", lambda self: None)
    for name in ("plan", "status", "uninstall", "next"):
        monkeypatch.setattr(W, f"do_{name}", lambda self, n=name: ran.append(n))

    def drive(answers):
        q = list(answers)

        def sel(self, msg, choices, back=True, default=None):
            shown.append((msg, [c.value for c in choices if not isinstance(c, Separator)], default))
            return q.pop(0)
        monkeypatch.setattr(W, "sel", sel)
        monkeypatch.setattr(W, "yes", lambda self, *a, **kw: q.pop(0))
        W()._run()
        return shown, ran
    return drive


def test_main_menu_is_short_and_reaches_every_action(kit, menu):
    shown, _ = menu(["exit"])
    main = shown[0][1]
    assert len(main) <= 12
    w = kit.wizard.W()
    reachable = set(main) | {a for acts in w.menu_sections().values() for a in acts}
    handlers = {n[3:] for n in dir(w) if n.startswith("do_")} - {"confirm", "answers", "autopilot", "extra", "team"}   # sub-flows or conditional
    assert handlers <= reachable


def test_section_opens_a_submenu_and_runs_the_action(menu):
    shown, ran = menu(["s_docs", "status", "exit"])
    assert ran == ["status"]
    assert "status" in shown[1][1] and "status" not in shown[0][1]


def test_escape_in_a_submenu_goes_back_to_the_main_menu(menu):
    shown, ran = menu(["s_settings", None, "exit"])
    assert ran == [] and len(shown) == 3


def test_destructive_actions_live_in_settings_last(kit, menu):
    shown, _ = menu(["s_settings", None, "exit"])
    assert "uninstall" not in shown[0][1]
    assert shown[1][1][-1] == "uninstall"


def test_main_menu_points_at_the_next_step(menu):
    shown, _ = menu(["exit"])
    assert shown[0][2] == "next"


# ---------- tutorial ----------
def test_tutorial_md_is_generated_from_the_wizard_pages(kit):
    md = (kit.kit_dir / "TUTORIAL.md").read_text(encoding="utf-8")
    assert md == kit.wizard.tutorial.markdown()


def test_tutorial_has_the_same_pages_in_both_languages(kit):
    P = kit.wizard.tutorial.PAGES
    assert [p["icon"] for p in P["es"]] == [p["icon"] for p in P["en"]]


@pytest.mark.parametrize("lang", ["es", "en"])
def test_tutorial_names_the_menu_sections(kit, lang):
    T, P = kit.wizard.T[lang], kit.wizard.tutorial.PAGES[lang]
    text = "\n".join(p["art"] + p["text"] for p in P)
    for key in ("s_docs", "s_team", "s_settings"):
        assert re.sub(r"^\W+", "", T[key]) in text
