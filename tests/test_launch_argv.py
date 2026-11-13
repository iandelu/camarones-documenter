"""The commands the wizard and the wiki generator launch: interactive sessions (fresh, a plan unit's with its record and
conversation, Continue, the fallback with no terminal) and headless OpenWiki runs."""
from __future__ import annotations

import contextlib, os, subprocess, sys, time
from pathlib import Path

import pytest

from test_agent_sessions import assistant, inner, write_transcript
from test_agents import window_closed

UNIT, OTHER = "discovery:api", "discovery:web"


@pytest.fixture
def launched(kit, fake_wizard, monkeypatch):
    from lib import agents
    from lib.adapters.runners import base
    fake = lambda name: f"/bin/{name}"                                          # noqa: E731
    monkeypatch.setattr(kit.wizard, "which", fake)
    monkeypatch.setattr(agents, "which", fake)
    monkeypatch.setattr(base, "which", fake)
    box = {"cmds": [], "said": []}
    monkeypatch.setattr(kit.services.launcher, "open_new_terminal", lambda cmd, cwd: box["cmds"].append((cmd, cwd)) or True)
    monkeypatch.setattr(kit.wizard.W, "say", lambda self, msg, style="": box["said"].append(str(msg)))

    def make(answers=(), **prefs):
        w = fake_wizard(list(answers))
        w.prefs.update(prefs)
        box["short"] = (f"Follow the instructions in " if w.lang == "en" else "Sigue las instrucciones de ") + \
            kit.common.ws_rel("docs/.work/next-prompt.md")
        box["w"] = w
        return w
    box["make"] = make
    return box


def test_fresh_claude_session_uses_the_model_pref(kit, launched):
    w = launched["make"](["claude"], model="opus")
    assert w.launch_agent("prompt") == "bg"
    cmd, cwd = launched["cmds"][0]
    assert cmd == ["/bin/claude", "--model", "opus", launched["short"]] and cwd == kit.common.WORKSPACE


def test_the_wizard_opens_a_window_whatever_the_sessions_setting(launched):
    assert launched["make"](["claude"], sessions="canvas").launch_agent("prompt") == "bg"
    assert len(launched["cmds"]) == 1


def test_claude_model_defaults_to_sonnet(launched):
    launched["make"](["claude"]).launch_agent("prompt")
    assert launched["cmds"][0][0][:3] == ["/bin/claude", "--model", "sonnet"]


def test_the_next_unit_opens_with_the_model_routed_to_it(kit, launched):
    kit.plan.sync()
    kit.plan.set_status("setup", "done")
    w = launched["make"](["claude"], routing={"agentic-heavy": ["codex:o5", "claude:opus"]})
    w.run_unit(kit.plan.get(kit.plan.load(), UNIT))
    assert inner(launched["cmds"][0][0])[:3] == ["/bin/claude", "--model", "opus"]


def test_the_docs_update_opens_with_the_agentic_heavy_model(kit, launched):
    kit.plan.sync()
    launched["make"](["claude"], routing={"agentic-heavy": ["claude:opus"]}).do_update()
    assert launched["cmds"][0][0][:3] == ["/bin/claude", "--model", "opus"]


def test_fresh_codex_session_uses_its_model_pref(kit, launched):
    launched["make"](["codex"], codex_model="o5").launch_agent("prompt")
    assert launched["cmds"][0][0] == ["/bin/codex", "--model", "o5", launched["short"]]


def test_codex_model_has_a_default(kit, launched):
    launched["make"](["codex"]).launch_agent("prompt")
    assert launched["cmds"][0][0] == ["/bin/codex", "--model", kit.wizard.CODEX_MODEL_DEFAULT, launched["short"]]


# ---------- a plan unit's session: its record, its conversation, the rule the app follows too ----------
def plan_ready(kit):
    kit.plan.sync()
    kit.plan.set_status("setup", "done")


def open_it(kit, launched, uid=UNIT, agent="claude", **prefs):
    """Runs the unit from the wizard with that agent. Its window stays open: window_closed() ends it."""
    plan_ready(kit)
    launched["make"]([agent], **prefs).run_unit(kit.plan.get(kit.plan.load(), uid))


def opened_and_closed(kit, launched, uid=UNIT, agent="claude", **prefs):
    open_it(kit, launched, uid, agent, **prefs)
    window_closed(uid)


def saved(kit, session):
    write_transcript(kit, session, [assistant({"type": "text", "text": "hola"})])


def choose(kit, launched, answer, uid=UNIT, **prefs):
    """The half-done menu of a unit marked doing, answered; the argv of the session it opened."""
    before = len(launched["cmds"])
    launched["make"]([answer], **prefs).run_unit(kit.plan.get(kit.plan.load(), uid))
    return inner(launched["cmds"][-1][0]) if len(launched["cmds"]) > before else None


def said(launched, key, **kw):
    return launched["w"].t(key, **kw) in launched["said"]


def no_terminal(kit, monkeypatch, codes=(1, 0)):
    """No terminal emulator: the session blocks this one. The commands it ran, in order."""
    monkeypatch.setattr(kit.services.launcher, "open_new_terminal", lambda cmd, cwd: False)
    runs = []
    monkeypatch.setattr(kit.wizard.subprocess, "run",
                        lambda cmd, cwd=None: runs.append(cmd) or subprocess.CompletedProcess(cmd, codes[len(runs) - 1]))
    monkeypatch.setattr(kit.wizard.console, "set_alt_screen", lambda *_: None)
    return runs


def test_a_units_session_runs_in_the_wrapper_with_a_conversation_of_its_own(kit, launched):
    from lib import sessions
    open_it(kit, launched)
    cmd, rec = launched["cmds"][0][0], sessions.load(UNIT)
    assert cmd[0] == sys.executable and cmd[1].endswith("session_run.py") and cmd[2] == str(sessions.path(UNIT))
    assert rec["unit"] == UNIT and rec["agent"] == "claude" and rec["session"]
    assert inner(cmd) == ["/bin/claude", "--model", "sonnet", "--session-id", rec["session"], launched["short"]]


def test_a_session_on_no_unit_has_no_wrapper_and_no_record(kit, launched):
    from lib import sessions
    assert launched["make"](["claude"]).launch_agent("prompt") == "bg"
    assert launched["cmds"][0][0] == ["/bin/claude", "--model", "sonnet", launched["short"]]
    assert not sessions.DIR.exists()


def test_the_docs_update_keeps_no_record(kit, launched):
    from lib import sessions
    kit.plan.sync()
    launched["make"](["claude"]).do_update()
    assert launched["cmds"][0][0][:2] == ["/bin/claude", "--model"] and sessions.load("update") is None


def test_copying_the_prompt_opens_no_session_and_leaves_no_record(kit, launched):
    from lib import sessions
    plan_ready(kit)
    launched["make"](["copy"]).run_unit(kit.plan.get(kit.plan.load(), UNIT))
    assert not launched["cmds"] and sessions.load(UNIT) is None


def test_continue_reopens_the_units_conversation_not_the_newest_in_the_folder(kit, launched):
    """`claude --continue` took the newest transcript in the workspace folder, whichever unit or run wrote it."""
    from lib import sessions
    opened_and_closed(kit, launched)
    own = sessions.load(UNIT)["session"]
    saved(kit, own)
    saved(kit, "someone-elses-and-newer")
    assert choose(kit, launched, "continue") == ["/bin/claude", "--model", "sonnet", "--resume", own, launched["short"]]
    assert sessions.load(UNIT)["session"] == own and not said(launched, "res_fresh")


def assert_fresh(kit, launched, argv):
    """A new conversation of the unit's own, and the person told."""
    from lib import sessions
    assert "--continue" not in argv and "--resume" not in argv
    assert argv[3:5] == ["--session-id", sessions.load(UNIT)["session"]]
    assert said(launched, "res_fresh")


def test_continue_with_no_record_opens_a_new_session_and_says_so(kit, launched):
    plan_ready(kit)
    kit.plan.set_status(UNIT, "doing")                          # opened by an older kit: it left no record
    saved(kit, "someone-elses")
    assert_fresh(kit, launched, choose(kit, launched, "continue", last_agent="claude"))


def test_continue_whose_transcript_is_gone_opens_a_new_session_and_says_so(kit, launched):
    from lib import sessions
    opened_and_closed(kit, launched)
    lost = sessions.load(UNIT)["session"]                       # its agent saved no transcript
    saved(kit, "someone-elses")
    assert_fresh(kit, launched, choose(kit, launched, "continue"))
    rec = sessions.load(UNIT)
    assert rec["session"] != lost and rec["previous"] == [lost]


def test_continue_on_a_record_an_older_kit_left_with_no_conversation_opens_a_new_session(kit, launched):
    from lib import sessions
    plan_ready(kit)
    kit.plan.set_status(UNIT, "doing")
    sessions.start(UNIT, "claude", None)                        # what an earlier `--continue` from the app left behind
    window_closed(UNIT)
    saved(kit, "someone-elses")
    assert_fresh(kit, launched, choose(kit, launched, "continue"))


def test_continue_with_no_unit_is_a_new_session_that_says_so(launched):
    launched["make"]().launch_agent("prompt", resume_agent="claude")
    assert launched["cmds"][0][0] == ["/bin/claude", "--model", "sonnet", launched["short"]]
    assert said(launched, "res_fresh")


def test_continue_reopens_the_conversation_a_run_left_and_the_bill_counts_it_from_now(kit, launched):
    from lib import sessions
    from lib.harness.events import EventLog
    plan_ready(kit)
    kit.plan.set_status(UNIT, "doing")
    log = EventLog(kit.common.CTX.runs / "r-1" / "events.jsonl")
    log.emit("run.started", run="r-1", agents=["claude"])
    log.emit("unit.started", run="r-1", unit=UNIT, runner="claude")
    log.emit("session", run="r-1", unit=UNIT, runner="claude", id="s-run")
    log.emit("unit.finished", run="r-1", unit=UNIT, runner="claude", outcome="handed", status="doing")
    log.emit("run.finished", run="r-1")
    saved(kit, "s-run")
    assert choose(kit, launched, "continue", last_agent="codex")[:5] == ["/bin/claude", "--model", "sonnet", "--resume", "s-run"]
    assert sessions.load(UNIT)["since"] > 0


def test_continue_goes_with_the_units_agent_not_the_last_one_used(kit, launched):
    """Another unit's session since then moved `last_agent`: this unit's conversation is still with its own agent."""
    from lib import sessions
    opened_and_closed(kit, launched)
    own = sessions.load(UNIT)["session"]
    saved(kit, own)
    assert choose(kit, launched, "continue", last_agent="codex")[3:5] == ["--resume", own]


def test_the_menu_names_the_units_agent(kit, launched, monkeypatch):
    opened_and_closed(kit, launched, agent="opencode")
    seen = []
    w = launched["make"]()
    monkeypatch.setattr(kit.wizard.W, "sel", lambda self, msg, opts, **kw: seen.extend(o.title for o in opts))
    w.run_unit(kit.plan.get(kit.plan.load(), UNIT))
    assert w.t("res_cont", agent="OpenCode") in seen


def test_with_the_units_agent_gone_the_menu_offers_no_continue(kit, launched, monkeypatch):
    opened_and_closed(kit, launched)
    monkeypatch.setattr(kit.wizard, "which", lambda name: f"/bin/{name}" if name != "claude" else None)
    seen = []
    w = launched["make"]()
    monkeypatch.setattr(kit.wizard.W, "sel", lambda self, msg, opts, **kw: seen.extend(o.value for o in opts))
    w.run_unit(kit.plan.get(kit.plan.load(), UNIT))
    assert seen == ["new", "done", "restart"]


def test_a_new_session_on_a_half_done_unit_is_a_new_conversation(kit, launched):
    from lib import sessions
    opened_and_closed(kit, launched)
    old = sessions.load(UNIT)["session"]
    saved(kit, old)
    w = launched["make"](["new", "claude"])
    w.run_unit(kit.plan.get(kit.plan.load(), UNIT))
    rec = sessions.load(UNIT)
    assert inner(launched["cmds"][-1][0])[3:5] == ["--session-id", rec["session"]] and rec["session"] != old
    assert not said(launched, "res_fresh")


def test_restart_starts_a_new_conversation_and_puts_the_notes_aside(kit, launched):
    from lib import sessions
    opened_and_closed(kit, launched)
    old = sessions.load(UNIT)["session"]
    saved(kit, old)
    note = kit.plan.note_file(UNIT)
    note.parent.mkdir(parents=True, exist_ok=True)
    note.write_text("half done", encoding="utf-8")
    w = launched["make"](["restart", "claude"])
    w.run_unit(kit.plan.get(kit.plan.load(), UNIT))
    assert inner(launched["cmds"][-1][0])[3:5] == ["--session-id", sessions.load(UNIT)["session"]]
    assert sessions.load(UNIT)["session"] != old and note.with_suffix(".old.md").exists()


def test_a_unit_the_app_opened_continues_from_the_wizard(kit, launched):
    from lib import agents, sessions
    plan_ready(kit)
    agents.launch_unit(UNIT, "claude")
    own = sessions.load(UNIT)["session"]
    saved(kit, own)
    window_closed(UNIT)
    assert choose(kit, launched, "continue")[3:5] == ["--resume", own]


def test_a_unit_the_wizard_opened_continues_from_the_app(kit, launched):
    from lib import agents, sessions
    opened_and_closed(kit, launched)
    own = sessions.load(UNIT)["session"]
    saved(kit, own)
    r = agents.launch_unit(UNIT, "claude", mode="continue")
    assert inner(launched["cmds"][-1][0])[3:5] == ["--resume", own] and "fresh" not in r


def test_resumed_codex_reopens_its_last_session_only_while_that_is_this_units(kit, launched):
    from lib import sessions
    opened_and_closed(kit, launched, agent="codex")
    assert choose(kit, launched, "continue") == ["/bin/codex", "resume", "--last"]
    assert not said(launched, "res_fresh")
    window_closed(UNIT)
    opened_and_closed(kit, launched, OTHER, agent="codex")
    sessions.update(OTHER, launched=time.time() + 60)           # it opened after: its conversation is now the last
    argv = choose(kit, launched, "continue")
    assert argv == ["/bin/codex", "--model", kit.wizard.CODEX_MODEL_DEFAULT, launched["short"]]
    assert said(launched, "res_fresh")


def test_a_runner_with_no_way_back_is_not_offered_continue(kit, launched, monkeypatch):
    """Gemini's template takes no resume: its Continue could only be the new session the menu already offers."""
    opened_and_closed(kit, launched, agent="gemini")
    seen = []
    w = launched["make"]()
    monkeypatch.setattr(kit.wizard.W, "sel", lambda self, msg, opts, **kw: seen.extend(o.value for o in opts))
    w.run_unit(kit.plan.get(kit.plan.load(), UNIT))
    assert seen == ["new", "done", "restart"]


# ---------- a session open, or a run at work: a second one would fight over its conversation ----------
def test_a_unit_with_its_session_open_is_not_opened_again(kit, launched):
    from lib import sessions
    open_it(kit, launched)
    sessions.update(UNIT, pid=os.getpid())
    rec = sessions.load(UNIT)
    assert choose(kit, launched, "continue") is None
    assert said(launched, "unit_open", u=UNIT) and sessions.load(UNIT) == rec


def test_a_todo_unit_with_its_session_open_is_not_opened_again(kit, launched):
    from lib import sessions
    open_it(kit, launched)
    sessions.update(UNIT, pid=os.getpid())
    kit.plan.set_status(UNIT, "todo")
    launched["make"]().run_unit(kit.plan.get(kit.plan.load(), UNIT))
    assert len(launched["cmds"]) == 1 and said(launched, "unit_open", u=UNIT)


def test_restart_with_the_session_open_changes_nothing(kit, launched):
    from lib import sessions
    open_it(kit, launched)
    sessions.update(UNIT, pid=os.getpid())
    note = kit.plan.note_file(UNIT)
    note.parent.mkdir(parents=True, exist_ok=True)
    note.write_text("half done", encoding="utf-8")
    launched["make"](["restart"]).run_unit(kit.plan.get(kit.plan.load(), UNIT))
    assert note.exists() and kit.plan.get(kit.plan.load(), UNIT)["status"] == "doing"
    assert len(launched["cmds"]) == 1


def test_a_unit_can_be_marked_done_with_its_session_open(kit, launched):
    from lib import sessions
    open_it(kit, launched)
    sessions.update(UNIT, pid=os.getpid())
    launched["make"](["done"]).run_unit(kit.plan.get(kit.plan.load(), UNIT))
    assert kit.plan.get(kit.plan.load(), UNIT)["status"] == "done"


def test_a_unit_a_runs_agent_is_working_on_is_not_opened(kit, launched, monkeypatch):
    from lib.harness import scheduler
    from lib.harness.events import EventLog
    plan_ready(kit)
    kit.plan.set_status(UNIT, "doing")
    monkeypatch.setattr(scheduler, "busy", lambda: {"pid": 1})
    log = EventLog(kit.common.CTX.runs / "r-1" / "events.jsonl")
    log.emit("run.started", run="r-1", agents=["claude"])
    log.emit("unit.started", run="r-1", unit=UNIT, runner="claude")
    launched["make"](["continue"], last_agent="claude").run_unit(kit.plan.get(kit.plan.load(), UNIT))
    assert not launched["cmds"] and said(launched, "unit_at_work", u=UNIT)


# ---------- no terminal emulator: the session blocks this terminal, and a failed resume falls back to a fresh one ----------
def test_without_a_terminal_a_failed_resume_falls_back_to_a_fresh_session(kit, launched, monkeypatch):
    opened_and_closed(kit, launched, agent="codex")
    runs = no_terminal(kit, monkeypatch)
    assert launched["make"]().launch_agent("prompt", resume_agent="codex", uid=UNIT) is True
    assert [inner(c) for c in runs] == [["/bin/codex", "resume", "--last"],
                                        ["/bin/codex", "--model", kit.wizard.CODEX_MODEL_DEFAULT, launched["short"]]]
    assert said(launched, "res_fresh")


def test_without_a_terminal_a_failed_claude_resume_gets_a_conversation_of_its_own(kit, launched, monkeypatch):
    """--session-id refuses an id already used, so the retry cannot be the conversation that just failed."""
    from lib import sessions
    opened_and_closed(kit, launched)
    own = sessions.load(UNIT)["session"]
    saved(kit, own)
    runs = no_terminal(kit, monkeypatch)
    assert launched["make"]().launch_agent("prompt", resume_agent="claude", uid=UNIT) is True
    rec = sessions.load(UNIT)
    assert inner(runs[0])[3:5] == ["--resume", own]
    assert inner(runs[1])[3:5] == ["--session-id", rec["session"]] and rec["session"] != own
    assert rec["previous"] == [own] and said(launched, "res_fresh")


def test_without_a_terminal_a_resume_that_worked_is_not_run_again(kit, launched, monkeypatch):
    from lib import sessions
    opened_and_closed(kit, launched)
    own = sessions.load(UNIT)["session"]
    saved(kit, own)
    runs = no_terminal(kit, monkeypatch, codes=(0,))
    assert launched["make"]().launch_agent("prompt", resume_agent="claude", uid=UNIT) is True
    assert len(runs) == 1 and not said(launched, "res_fresh") and sessions.load(UNIT)["session"] == own


def test_without_a_terminal_a_new_session_that_fails_is_not_run_again(kit, launched, monkeypatch):
    runs = no_terminal(kit, monkeypatch)
    plan_ready(kit)
    assert launched["make"](["claude"]).launch_agent("prompt", uid=UNIT) is True
    assert len(runs) == 1


@pytest.fixture
def wiki_cmd(kit, monkeypatch):
    from lib.adapters.runners import base
    env = kit.env
    seen = []
    monkeypatch.setattr(base, "which", lambda name: f"/bin/{name}")
    monkeypatch.setattr(env, "wiki_engines", lambda: ["openwiki", "claude", "codex"])
    monkeypatch.setattr(kit.services.links, "link_repo_wiki", lambda repo, log=print: None)
    monkeypatch.setattr(env, "wire_openwiki", lambda host, log=print: None)      # argv only: wiring has its own tests
    monkeypatch.setattr(env, "wiki_pages", lambda repo: [])
    monkeypatch.setattr(env, "wiki_prompt", lambda repo, mode: "PROMPT")
    monkeypatch.setattr(env, "wiki_workdir", lambda repo, log=print: contextlib.nullcontext())
    monkeypatch.setattr(env, "stream", lambda cmd, cwd, log, env=None: seen.append((cmd, cwd)) or 1)

    def run(engine):
        env.openwiki_generate("api", mode="init", log=lambda _: None, engine=engine, force=True)
        cmd, cwd = seen.pop()
        return [Path(cmd[0]).name, *cmd[1:]], cwd
    return run


def test_openwiki_engine_runs_openwiki_itself(kit, wiki_cmd):
    assert wiki_cmd("openwiki") == (["openwiki", "code", "--init", "--print"], kit.common.repo_dir("api"))


def test_wiki_by_claude_is_scoped_to_edits_and_wiki_tools(kit, wiki_cmd):
    cmd, cwd = wiki_cmd("claude")
    assert cmd == ["claude", "-p", "PROMPT", "--permission-mode", "acceptEdits", "--allowedTools",
                   "mcp__openwiki Skill Read Write Edit Glob Grep Bash(git:*) Bash(ls:*) Bash(graphify:*) "
                   f"Bash({kit.common.cli_cmd()} plan note:*)", "--output-format", "stream-json", "--verbose"]
    assert cwd == kit.common.WORKSPACE


def test_wiki_by_codex_runs_full_auto_in_the_workspace(kit, wiki_cmd):
    assert wiki_cmd("codex") == (["codex", "exec", "--full-auto", "-C", str(kit.common.WORKSPACE), "--json", "PROMPT"],
                                 kit.common.WORKSPACE)


def test_other_runners_take_their_own_model_pref(launched):
    launched["make"](["opencode"]).launch_agent("prompt")
    assert launched["cmds"][0][0] == ["/bin/opencode", "--prompt", launched["short"]]
    launched["make"](["opencode"], opencode_model="ollama/qwen3-coder:30b").launch_agent("prompt")
    assert launched["cmds"][1][0] == ["/bin/opencode", "--model", "ollama/qwen3-coder:30b", "--prompt", launched["short"]]
