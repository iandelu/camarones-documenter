"""Component tests of the wizard: the real questionary menus driven with keystrokes through a prompt_toolkit pipe
(no terminal, no monkeypatched prompts). Every key is queued up front and the pipe is closed, so a prompt the test
did not expect fails at once with EOFError instead of hanging. Only the agent launch and the file manager are faked."""
from __future__ import annotations

import json

import pytest
from prompt_toolkit.application import create_app_session
from prompt_toolkit.input import create_pipe_input
from prompt_toolkit.output import DummyOutput

DOWN, ENTER, ESC, CLEAR = "\x1b[B", "\r", "\x1b", "\x15"     # ↓ · Enter · Esc · Ctrl+U (clear the line)
YES = "y"                                                     # a confirm answers on the key, no Enter
# A trailing Esc stays in the parser (it may start a sequence like ↓) until a timeout that a closed pipe never
# reaches; an unbound key after the last one flushes it. F12 is bound by no prompt, so it never answers anything.
FLUSH = "[24~"

QUESTIONNAIRE = """\
questions:
  - id: ctx-envs
    topic: context
    text: Is there a staging environment?
    kind: confirm
  - id: lang-owner
    topic: language
    text: Who is the owner?
    kind: single
    options: [The pet's owner, The clinic]
"""


@pytest.fixture
def ui(kit, monkeypatch):
    """ui.play(*keys, fn=callable) runs fn with the keys queued; ui.launched / ui.revealed record the side effects."""
    wz = kit.wizard
    box = {"launched": [], "revealed": []}
    monkeypatch.setattr(wz.time, "sleep", lambda _s: None)
    monkeypatch.setattr(wz.console, "clear", lambda *a, **kw: None)
    monkeypatch.setattr(wz.W, "launch_agent",
                        lambda self, prompt, resume_agent=None: box["launched"].append(prompt.splitlines()[0]) or "bg")
    monkeypatch.setattr(wz.W, "reveal", lambda self, folder: box["revealed"].append(folder))
    monkeypatch.setattr(wz.env, "open_url", lambda url: pytest.fail(f"opened {url}"))

    def play(*keys, fn):
        with create_pipe_input() as inp, create_app_session(input=inp, output=DummyOutput()):
            inp.send_text("".join(keys) + FLUSH)
            inp.close()
            return fn()
    box["play"] = play
    return type("UI", (), box)


def unit(kit, uid):
    return next(u for u in kit.plan.load()["units"] if u["id"] == uid)


def started_interview(kit):
    """The state a real project was in: discovery done, a live interview session opened and closed half-way."""
    kit.common.save_json(kit.wizard.FIRSTRUN, {"step": 6, "done": True})
    kit.wizard.usage.set_enabled(True)                 # stats already decided: no one-off notice before the menu
    kit.plan.sync()
    for u in kit.plan.load()["units"]:
        if u["id"].startswith(("setup", "discovery")):
            kit.plan.set_status(u["id"], "done")
    kit.plan.set_status("interview-context", "doing")


def team_waiting_for_answers(kit):
    kit.plan.set_interview_mode("team")
    for uid in ("setup", "discovery:api", "discovery:web", "discovery:worker", "discovery-cross", "questionnaire"):
        kit.plan.set_status(uid, "done")
    kit.questionnaire.SOURCE.parent.mkdir(parents=True, exist_ok=True)
    kit.questionnaire.SOURCE.write_text(QUESTIONNAIRE, encoding="utf-8")


# ---------- main menu → the interview already started ----------
def test_resuming_a_started_interview_offers_the_team_questionnaire(kit, ui):
    started_interview(kit)
    # main menu: "▶ continue interview-context" is first → mode question, team is the default → agent writes the
    # questionnaire → back on the main menu: Esc, and "yes" to leave
    ui.play(ENTER, ENTER, ESC, YES, fn=kit.wizard.W()._run)
    assert ui.launched == ["Camarón session — unit `questionnaire`: " + unit(kit, "questionnaire")["title"]]
    assert kit.docs.interview_mode() == "team"
    assert unit(kit, "interview-context")["status"] == "todo"


def test_choosing_live_resumes_the_interview_session(kit, ui):
    started_interview(kit)
    # live → the usual resume menu of a started unit: "new session" is first
    ui.play(ENTER, DOWN, ENTER, ENTER, ESC, YES, fn=kit.wizard.W()._run)
    assert ui.launched[0].startswith("Camarón session — unit `interview-context`")
    assert kit.docs.workspace()["project"]["interviews"] == "live"


def test_escape_on_the_mode_question_changes_nothing(kit, ui):
    started_interview(kit)
    ui.play(ENTER, ESC, ESC, YES, fn=kit.wizard.W()._run)
    assert ui.launched == []
    assert "interviews" not in kit.docs.workspace()["project"]
    assert unit(kit, "interview-context")["status"] == "doing"


def test_the_question_is_asked_once(kit, ui):
    started_interview(kit)
    ui.play(ENTER, DOWN, ENTER, ENTER, ESC, YES, fn=kit.wizard.W()._run)      # live · new session
    # next time "continue" goes to the resume menu (new session / continue / done / restart), not the mode question
    ui.play(ENTER, ENTER, ESC, YES, fn=kit.wizard.W()._run)
    assert len(ui.launched) == 2 and ui.launched[1].startswith("Camarón session — unit `interview-context`")


# ---------- the team questionnaire menu entry ----------
def test_menu_entry_switches_a_started_interview_to_the_team(kit, ui):
    started_interview(kit)
    ui.play(ENTER, ENTER, fn=kit.wizard.W().do_team)                          # switch? yes · start it now? yes
    assert kit.docs.interview_mode() == "team"
    assert ui.launched[0].startswith("Camarón session — unit `questionnaire`")


def test_menu_entry_can_be_declined(kit, ui):
    started_interview(kit)
    ui.play("n", fn=kit.wizard.W().do_team)
    assert kit.docs.interview_mode() == "live" and ui.launched == []


# ---------- the answers step ----------
def test_answers_step_export_import_close(kit, ui, tmp_path):
    team_waiting_for_answers(kit)
    answers = tmp_path / "respuestas-ana.json"
    answers.write_text(json.dumps({"respondent": "Ana", "answers": {"ctx-envs": {"choice": "no"}}}), encoding="utf-8")
    ui.play(ENTER, ENTER,                                                    # export · ↩
            DOWN, ENTER, CLEAR, str(tmp_path), ENTER, ENTER,                 # import a folder · ↩
            DOWN, DOWN, ENTER,                                               # close: enough answers
            fn=lambda: kit.wizard.W().run_unit(unit(kit, "answers")))
    assert (kit.questionnaire.QDIR / "questionnaire.html").exists()
    assert ui.revealed == [kit.questionnaire.QDIR]
    assert list(kit.questionnaire.responses()) == ["Ana"]
    assert unit(kit, "answers")["status"] == "done"
    assert "interview-context" in [u["id"] for u in kit.plan.available()]


def test_close_is_disabled_until_someone_answers(kit, ui):
    team_waiting_for_answers(kit)
    # ↓ import, ↓ skips the disabled "close" and lands on "↩ back"
    ui.play(DOWN, DOWN, ENTER, fn=lambda: kit.wizard.W().run_unit(unit(kit, "answers")))
    assert unit(kit, "answers")["status"] == "todo"


def test_escape_in_the_import_path_goes_back_to_the_menu(kit, ui):
    team_waiting_for_answers(kit)
    ui.play(DOWN, ENTER, ESC, ESC, fn=lambda: kit.wizard.W().run_unit(unit(kit, "answers")))
    assert kit.questionnaire.responses() == {}
    assert unit(kit, "answers")["status"] == "todo"


def test_a_wrong_path_is_reported_and_the_menu_stays(kit, ui, tmp_path):
    team_waiting_for_answers(kit)
    ui.play(DOWN, ENTER, CLEAR, str(tmp_path / "nope.json"), ENTER, ENTER, ESC,
            fn=lambda: kit.wizard.W().run_unit(unit(kit, "answers")))
    assert kit.questionnaire.responses() == {}
    assert unit(kit, "answers")["status"] == "todo"
