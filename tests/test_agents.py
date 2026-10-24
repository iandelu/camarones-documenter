"""Interactive agent sessions on the plan (lib/agents.py): what the wizard's "next unit" launches, without the wizard,
so the desktop app opens the same session in its own terminal window. And the app's Run with its options."""
from __future__ import annotations

import json, threading, urllib.error, urllib.request
from http.server import ThreadingHTTPServer

import pytest


@pytest.fixture
def term(wired, monkeypatch):
    from lib import agents
    from lib.adapters.runners import base
    fake = lambda name: f"/bin/{name}" if name in ("claude", "codex") else None      # noqa: E731
    monkeypatch.setattr(agents, "which", fake)
    monkeypatch.setattr(base, "which", fake)
    box = {"cmds": [], "ok": True, "history": True}
    monkeypatch.setattr(agents.env, "open_new_terminal", lambda cmd, cwd: box["cmds"].append((cmd, cwd)) or box["ok"])
    monkeypatch.setattr(agents, "claude_history", lambda cwd: box["history"])
    wired.plan.sync()
    wired.plan.set_status("setup", "done")
    box["agents"] = agents
    return box


def ready_agent_unit(wired):
    return next(u for u in wired.plan.available() if u["runner"] == "agent")


def test_installed_agents_are_the_runners_found_on_this_machine(term):
    ids = [a["id"] for a in term["agents"].installed()]
    assert ids == ["claude", "codex"]


def test_a_ready_unit_opens_in_its_own_terminal_in_the_workspace(wired, term):
    u = ready_agent_unit(wired)
    r = term["agents"].launch_unit(u["id"], "claude", lang="en")
    cmd, cwd = term["cmds"][0]
    assert cmd[:3] == ["/bin/claude", "--model", "sonnet"] and cmd[-1].startswith("Follow the instructions in ")
    assert cwd == wired.common.WORKSPACE
    assert wired.plan.get(wired.plan.load(), u["id"])["status"] == "doing"
    prompt = (wired.common.WORK / "next-prompt.md").read_text(encoding="utf-8")
    assert u["id"] in prompt and r["agent"] == "claude"
    assert json.loads(wired.common.PREFS.read_text(encoding="utf-8"))["last_agent"] == "claude"


def test_continue_resumes_the_agents_last_conversation(wired, term):
    u = ready_agent_unit(wired)
    wired.plan.set_status(u["id"], "doing")
    term["agents"].launch_unit(u["id"], "claude", mode="continue")
    assert "--continue" in term["cmds"][0][0]
    term["history"] = False                                     # nothing to continue: a fresh session
    term["agents"].launch_unit(u["id"], "claude", mode="continue")
    assert "--continue" not in term["cmds"][1][0]


def test_restart_puts_the_old_notes_aside(wired, term):
    u = ready_agent_unit(wired)
    wired.plan.set_status(u["id"], "doing")
    note = wired.plan.note_file(u["id"])
    note.parent.mkdir(parents=True, exist_ok=True)
    note.write_text("half done", encoding="utf-8")
    term["agents"].launch_unit(u["id"], "codex", mode="restart")
    assert not note.exists() and note.with_suffix(".old.md").exists()


@pytest.mark.parametrize("case", ["waiting", "not-agent", "unknown-agent", "unknown-unit"])
def test_what_cannot_be_launched_says_why(wired, term, case):
    data = wired.plan.load()
    ready = {u["id"] for u in wired.plan.available(data)}
    waiting = next(u["id"] for u in data["units"] if u["runner"] == "agent" and u["status"] == "todo" and u["id"] not in ready)
    uid, agent, err = {"waiting": (waiting, "claude", ValueError),
                       "not-agent": ("setup", "claude", ValueError),
                       "unknown-agent": (ready_agent_unit(wired)["id"], "gemini", ValueError),
                       "unknown-unit": ("nope", "claude", KeyError)}[case]
    with pytest.raises(err):
        term["agents"].launch_unit(uid, agent)
    assert not term["cmds"]


def test_without_a_terminal_it_points_at_the_prompt(wired, term):
    term["ok"] = False
    with pytest.raises(RuntimeError, match="next-prompt.md"):
        term["agents"].launch_unit(ready_agent_unit(wired)["id"], "claude")


def test_update_session(wired, term):
    term["agents"].launch_update("codex", lang="es")
    assert term["cmds"][0][0][0] == "/bin/codex"
    assert term["cmds"][0][0][-1].startswith("Sigue las instrucciones de ")


# ---------- through the app's server ----------

TOKEN = "t0k"


@pytest.fixture
def app(wired, term, monkeypatch):
    monkeypatch.setattr(wired.serve, "APP_TOKEN", TOKEN)
    srv = ThreadingHTTPServer(("127.0.0.1", 0), wired.serve.Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


def call(url, body=None, token=TOKEN):
    req = urllib.request.Request(url, data=None if body is None else json.dumps(body).encode(),
                                 method="GET" if body is None else "POST",
                                 headers={"Content-Type": "application/json", "X-Camarones": "1",
                                          **({"X-Camaron-Token": token} if token else {})})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


def test_the_app_lists_agents_and_opens_a_unit(wired, app, term):
    code, a = call(app + "/api/app/agents")
    assert code == 200 and [x["id"] for x in a["agents"]] == ["claude", "codex"]
    u = ready_agent_unit(wired)
    code, r = call(app + "/api/app/agent", {"unit": u["id"], "agent": "codex", "lang": "en"})
    assert code == 200 and r["launched"] is True and term["cmds"]
    code, r = call(app + "/api/app/agent", {"unit": "setup", "agent": "codex"})
    assert code == 400 and r["error"]
    assert call(app + "/api/app/agent", {"unit": u["id"], "agent": "codex"}, token=None)[0] == 403


def test_run_takes_its_options(wired, monkeypatch):
    from lib.harness import scheduler
    seen = {}
    monkeypatch.setattr(scheduler, "busy", lambda: None)
    monkeypatch.setattr(scheduler, "run_parallel", lambda **kw: seen.update(kw) or 0)
    job, code = wired.serve.start_run({"parallel": 3, "per_runner": "claude=2", "max_units": 4, "lang": "es",
                                       "include_interviews": True, "policy": "never"})
    for _ in range(100):
        if seen:
            break
        threading.Event().wait(0.05)
    assert code == 200
    assert seen["max_parallel"] == 3 and seen["per_runner"] == {"claude": 2} and seen["max_units"] == 4
    assert seen["include_interviews"] is True and seen["policy"] == "never" and seen["lang"] == "es"
    assert wired.serve.start_run({"policy": "always"})[1] == 400
