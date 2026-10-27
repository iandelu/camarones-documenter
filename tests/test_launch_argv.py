"""The commands the wizard and the wiki generator launch, pinned so moving them behind the Runner port changes
nothing: interactive sessions (fresh, resumed, fallback) and headless OpenWiki runs."""
from __future__ import annotations

import contextlib, subprocess
from pathlib import Path

import pytest


@pytest.fixture
def launched(kit, fake_wizard, monkeypatch):
    from lib.adapters.runners import base
    fake = lambda name: f"/bin/{name}"                                          # noqa: E731
    monkeypatch.setattr(kit.wizard, "which", fake)
    monkeypatch.setattr(base, "which", fake)
    box = {"cmds": [], "history": True}
    monkeypatch.setattr(kit.wizard.env, "open_new_terminal", lambda cmd, cwd: box["cmds"].append((cmd, cwd)) or True)
    monkeypatch.setattr(kit.wizard, "claude_history", lambda cwd: box["history"])

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


def test_claude_model_defaults_to_sonnet(launched):
    launched["make"](["claude"]).launch_agent("prompt")
    assert launched["cmds"][0][0][:3] == ["/bin/claude", "--model", "sonnet"]


def test_resumed_claude_continues_the_conversation(launched):
    launched["make"]().launch_agent("prompt", resume_agent="claude")
    assert launched["cmds"][0][0] == ["/bin/claude", "--model", "sonnet", "--continue", launched["short"]]


def test_claude_without_history_starts_fresh(launched):
    launched["history"] = False
    launched["make"]().launch_agent("prompt", resume_agent="claude")
    assert launched["cmds"][0][0] == ["/bin/claude", "--model", "sonnet", launched["short"]]


def test_resumed_codex_reopens_the_last_session(launched):
    launched["make"]().launch_agent("prompt", resume_agent="codex")
    assert launched["cmds"][0][0] == ["/bin/codex", "resume", "--last"]


def test_fresh_codex_session_uses_its_model_pref(kit, launched):
    launched["make"](["codex"], codex_model="o5").launch_agent("prompt")
    assert launched["cmds"][0][0] == ["/bin/codex", "--model", "o5", launched["short"]]


def test_codex_model_has_a_default(kit, launched):
    launched["make"](["codex"]).launch_agent("prompt")
    assert launched["cmds"][0][0] == ["/bin/codex", "--model", kit.wizard.CODEX_MODEL_DEFAULT, launched["short"]]


def test_without_a_terminal_a_failed_resume_falls_back_to_a_fresh_session(kit, launched, monkeypatch):
    monkeypatch.setattr(kit.wizard.env, "open_new_terminal", lambda cmd, cwd: False)
    runs = []
    monkeypatch.setattr(kit.wizard.subprocess, "run",
                        lambda cmd, cwd=None: runs.append(cmd) or subprocess.CompletedProcess(cmd, 1 if len(runs) == 1 else 0))
    monkeypatch.setattr(kit.wizard.console, "set_alt_screen", lambda *_: None)
    assert launched["make"]().launch_agent("prompt", resume_agent="codex") is True
    assert runs == [["/bin/codex", "resume", "--last"], ["/bin/codex", "--model", kit.wizard.CODEX_MODEL_DEFAULT,
                                                         launched["short"]]]


@pytest.fixture
def wiki_cmd(kit, monkeypatch):
    from lib.adapters.runners import base
    env = kit.env
    seen = []
    monkeypatch.setattr(base, "which", lambda name: f"/bin/{name}")
    monkeypatch.setattr(env, "wiki_engines", lambda: ["openwiki", "claude", "codex"])
    monkeypatch.setattr(env, "link_repo_wiki", lambda repo, log=print: None)
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
