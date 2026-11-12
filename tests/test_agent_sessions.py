"""The board's view of interactive agent sessions (lib/sessions.py, lib/session_run.py): whether a unit marked doing
still has its terminal window open, what the agent did last, and the conversation Continue reopens."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time

import pytest

from test_agents import ready_agent_unit, term, window_closed  # noqa: F401  (fixture)


def inner(cmd):
    """The agent's own argv inside the wrapper the terminal runs."""
    return cmd[cmd.index("--") + 1:]


def write_transcript(wired, session, entries):
    from lib import sessions
    d = sessions.claude_dir(wired.common.WORKSPACE)
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{session}.jsonl").write_text("".join(json.dumps(e) + "\n" for e in entries), encoding="utf-8")


def assistant(*content, ts="2026-10-26T10:00:00.000Z"):
    return {"type": "assistant", "timestamp": ts, "message": {"role": "assistant", "content": list(content)}}


# ---------- launching ----------
def test_the_terminal_runs_the_agent_inside_the_session_wrapper(wired, term):
    from lib import sessions
    u = ready_agent_unit(wired)
    term["agents"].launch_unit(u["id"], "claude", lang="en")
    cmd = term["cmds"][0][0]
    assert cmd[0] == sys.executable and cmd[1].endswith("session_run.py")
    assert cmd[2] == str(sessions.path(u["id"]))
    rec = sessions.load(u["id"])
    assert rec["unit"] == u["id"] and rec["agent"] == "claude" and rec["session"]
    assert inner(cmd)[:5] == ["/bin/claude", "--model", "sonnet", "--session-id", rec["session"]]


def test_continue_reopens_the_units_own_conversation(wired, term):
    from lib import sessions
    u = ready_agent_unit(wired)
    term["agents"].launch_unit(u["id"], "claude")
    first = sessions.load(u["id"])["session"]
    write_transcript(wired, first, [assistant({"type": "text", "text": "hola"})])
    window_closed(u["id"])
    r = term["agents"].launch_unit(u["id"], "claude", mode="continue")
    assert inner(term["cmds"][1][0])[3:5] == ["--resume", first]
    assert sessions.load(u["id"])["session"] == first
    assert "fresh" not in r


def assert_fresh(cmd, rec, result):
    """A new conversation of the unit's own, and the person told: never `--continue`, which takes the newest
    conversation in the folder, whichever unit or run it was."""
    argv = inner(cmd)
    assert "--continue" not in argv and "--resume" not in argv
    assert argv[3:5] == ["--session-id", rec["session"]]
    assert result["fresh"] is True


def test_continue_whose_transcript_is_gone_opens_a_fresh_session_and_says_so(wired, term):
    from lib import sessions
    u = ready_agent_unit(wired)
    term["agents"].launch_unit(u["id"], "claude")
    lost = sessions.load(u["id"])["session"]                    # its agent saved no transcript
    write_transcript(wired, "an-old-run", [assistant({"type": "text", "text": "someone else's"})])
    window_closed(u["id"])
    r = term["agents"].launch_unit(u["id"], "claude", mode="continue")
    rec = sessions.load(u["id"])
    assert_fresh(term["cmds"][1][0], rec, r)
    assert rec["session"] != lost and rec["previous"] == [lost]


def test_continue_with_no_record_opens_a_fresh_session_and_says_so(wired, term):
    from lib import sessions
    u = ready_agent_unit(wired)
    wired.plan.set_status(u["id"], "doing")                     # opened by an older kit: no record
    write_transcript(wired, "an-old-run", [assistant({"type": "text", "text": "someone else's"})])
    r = term["agents"].launch_unit(u["id"], "claude", mode="continue")
    assert_fresh(term["cmds"][0][0], sessions.load(u["id"]), r)


def test_continue_on_a_record_with_no_conversation_opens_a_fresh_session_and_says_so(wired, term):
    from lib import sessions
    u = ready_agent_unit(wired)
    wired.plan.set_status(u["id"], "doing")
    sessions.start(u["id"], "claude", None)                     # what an earlier `--continue` left behind
    window_closed(u["id"])
    write_transcript(wired, "an-old-run", [assistant({"type": "text", "text": "someone else's"})])
    r = term["agents"].launch_unit(u["id"], "claude", mode="continue")
    assert_fresh(term["cmds"][0][0], sessions.load(u["id"]), r)


def test_an_agent_with_no_ids_only_reopens_its_last_conversation_when_that_is_this_units(wired, term):
    from lib import sessions
    first, other = [u["id"] for u in wired.plan.available() if u["runner"] == "agent"][:2]
    term["agents"].launch_unit(first, "codex")
    window_closed(first)
    r = term["agents"].launch_unit(first, "codex", mode="continue")
    assert inner(term["cmds"][1][0]) == ["/bin/codex", "resume", "--last"] and "fresh" not in r
    window_closed(first)
    term["agents"].launch_unit(other, "codex")
    window_closed(other)
    sessions.update(other, launched=time.time() + 60)           # it opened after: its conversation is now the last
    r = term["agents"].launch_unit(first, "codex", mode="continue")
    assert "resume" not in inner(term["cmds"][3][0]) and r["fresh"] is True


def test_a_runner_with_no_way_back_never_reopens(wired, term):
    from lib import sessions
    u = ready_agent_unit(wired)
    sessions.start(u["id"], "gemini", None)
    assert sessions.last_opened("gemini") == u["id"]
    assert term["agents"].conversation(u["id"], "gemini", True) == (None, None, False)


def test_restart_starts_a_new_conversation(wired, term):
    from lib import sessions
    u = ready_agent_unit(wired)
    term["agents"].launch_unit(u["id"], "claude")
    first = sessions.load(u["id"])["session"]
    window_closed(u["id"])
    term["agents"].launch_unit(u["id"], "claude", mode="restart")
    assert sessions.load(u["id"])["session"] != first


def test_an_open_session_is_not_opened_twice(wired, term):
    from lib import sessions
    u = ready_agent_unit(wired)
    term["agents"].launch_unit(u["id"], "claude")
    sessions.update(u["id"], pid=os.getpid())
    with pytest.raises(ValueError, match="already open"):
        term["agents"].launch_unit(u["id"], "claude", mode="continue")


# ---------- live or paused ----------
def test_no_record_means_no_session(wired):
    from lib import sessions
    assert sessions.state("nope") is None


def test_a_session_is_live_while_its_wrapper_runs(wired):
    from lib import sessions
    sessions.start("u1", "claude", "s-1")
    assert sessions.state("u1")["live"] is True                 # just launched: the window is still opening
    sessions.update("u1", launched=time.time() - sessions.GRACE - 1)
    assert sessions.state("u1")["live"] is False                # it never started
    sessions.update("u1", pid=os.getpid())
    assert sessions.state("u1")["live"] is True
    sessions.update("u1", ended=time.time())
    assert sessions.state("u1")["live"] is False


def test_a_closed_window_leaves_a_dead_pid(wired):
    from lib import sessions
    p = subprocess.Popen([sys.executable, "-c", "pass"])
    p.wait()
    sessions.start("u1", "claude", "s-1")
    sessions.update("u1", pid=p.pid, launched=time.time() - sessions.GRACE - 1)
    assert sessions.state("u1")["live"] is False


def test_the_wrapper_records_its_pid_and_when_the_agent_ended(wired):
    from lib import sessions
    rec = sessions.start("u1", "claude", "s-1")
    seen = wired.root / "seen.json"
    child = [sys.executable, "-c", f"import shutil; shutil.copy(r'{rec}', r'{seen}')"]
    code = subprocess.call(sessions.wrap(rec, child))
    assert code == 0
    during = json.loads(seen.read_text(encoding="utf-8"))
    after = sessions.load("u1")
    assert during["pid"] and "ended" not in during and during["session"] == "s-1"
    assert after["ended"] and after["code"] == 0


def test_the_wrapper_passes_the_agents_exit_code_through(wired):
    from lib import sessions
    rec = sessions.start("u1", "claude", "s-1")
    assert subprocess.call(sessions.wrap(rec, [sys.executable, "-c", "raise SystemExit(3)"])) == 3


# ---------- one writer at a time ----------
def meanwhile(fn):
    """`fn` on another thread, given a moment to finish: a writer holding the record makes it wait instead."""
    t = threading.Thread(target=fn, daemon=True)
    t.start()
    t.join(0.5)
    return t


def test_the_wrappers_end_keeps_a_mark_written_meanwhile(wired, monkeypatch):
    """hand_back marks the record (`since`) while the agent exits and the wrapper writes its end: neither write drops
    the other's. Here the mark comes between the wrapper's read of the record and its write."""
    from lib import session_run, sessions
    rec = sessions.start("u1", "claude", "s-1")
    real, reads, marks = session_run._read, [], []

    def read(p):
        r = real(p)
        reads.append(r)
        if len(reads) == 2:                                     # the end's read
            marks.append(meanwhile(lambda: sessions.bound("u1")))
        return r
    monkeypatch.setattr(session_run, "_read", read)
    assert session_run.main([str(rec), "--", sys.executable, "-c", "pass"]) == 0
    marks[0].join(15)
    after = sessions.load("u1")
    assert after["since"] == 0.0 and after["code"] == 0 and after["pid"] and after["session"] == "s-1"


def test_closing_the_record_keeps_a_mark_written_meanwhile(wired, monkeypatch):
    """The terminal closing the record from its reader thread (`update`) and hand_back's mark meet the same way."""
    from lib import sessions
    sessions.start("u1", "claude", "s-1")
    real, marks = sessions.load, []

    def load(uid):
        r = real(uid)
        if not marks:
            marks.append(None)
            marks[0] = meanwhile(lambda: sessions.bound(uid))
        return r
    monkeypatch.setattr(sessions, "load", load)
    sessions.update("u1", ended=time.time(), code=-1)
    marks[0].join(15)
    assert real("u1")["since"] == 0.0 and real("u1")["code"] == -1


def test_the_wrapper_waits_while_the_server_writes_the_record(wired):
    """The wrapper, a process of its own, takes the record's lock as lib/sessions.py does: while the server holds it,
    the wrapper writes nothing and the agent does not start."""
    from lib import sessions
    rec = sessions.start("u1", "claude", "s-1")
    seen = wired.root / "seen.json"
    child = [sys.executable, "-c", f"import shutil; shutil.copy(r'{rec}', r'{seen}')"]
    with sessions.lock("u1"):
        p = subprocess.Popen(sessions.wrap(rec, child))
        time.sleep(1)
        assert p.poll() is None and not seen.exists() and "pid" not in sessions.load("u1")
    assert p.wait(30) == 0 and json.loads(seen.read_text(encoding="utf-8"))["pid"]


def test_a_write_cut_short_leaves_the_record_as_it_was(wired, monkeypatch):
    """A record is replaced whole or not at all: a reader (the board, the bill, another writer) never meets it half
    written, and a process killed while writing it does not leave it so."""
    from pathlib import Path
    from lib import sessions
    sessions.start("u1", "claude", "s-1")
    real, folder = Path.write_text, sessions.DIR.resolve()

    def cut(self, data, *a, **kw):
        if self.parent.resolve() == folder:
            real(self, data[:len(data) // 2], *a, **kw)
            raise OSError("disk full")
        return real(self, data, *a, **kw)
    with monkeypatch.context() as m:
        m.setattr(Path, "write_text", cut)
        with pytest.raises(OSError):
            sessions.update("u1", pid=1)
    assert sessions.load("u1")["session"] == "s-1"
    assert [f.name for f in sessions.DIR.iterdir()] == ["u1.json"]


# ---------- what the agent is doing ----------
def test_activity_is_the_last_tool_the_agent_called(wired):
    from lib import sessions
    sessions.start("u1", "claude", "s-1")
    write_transcript(wired, "s-1", [
        {"type": "user", "timestamp": "2026-10-26T09:59:00.000Z", "message": {"role": "user", "content": "go"}},
        assistant({"type": "text", "text": "Voy a leer el repo"}, ts="2026-10-26T09:59:30.000Z"),
        assistant({"type": "tool_use", "name": "Edit", "input": {"file_path": "cam-docs/docs/x.md", "old_string": "a"}}),
        {"type": "file-history-snapshot"},
    ])
    act = sessions.state("u1")["activity"]
    assert act == {"state": "working", "tool": "Edit", "arg": "cam-docs/docs/x.md", "text": "Voy a leer el repo",
                   "ts": "2026-10-26T10:00:00.000Z"}


def test_a_finished_turn_waits_for_you(wired):
    from lib import sessions
    sessions.start("u1", "claude", "s-1")
    write_transcript(wired, "s-1", [
        assistant({"type": "tool_use", "name": "Read", "input": {"file_path": "a.md"}}),
        {"type": "user", "timestamp": "2026-10-26T10:00:01.000Z",
         "message": {"role": "user", "content": [{"type": "tool_result", "content": "..."}]}},
        assistant({"type": "text", "text": "¿Confirmas el glosario?"}, ts="2026-10-26T10:01:00.000Z"),
    ])
    act = sessions.state("u1")["activity"]
    assert act["state"] == "waiting" and act["text"] == "¿Confirmas el glosario?" and act["tool"] == "Read"


def test_no_transcript_no_activity(wired):
    from lib import sessions
    sessions.start("u1", "codex", None)
    assert sessions.state("u1")["activity"] is None


# ---------- on the board ----------
def test_the_pipeline_says_which_doing_units_are_paused(wired, term):
    from lib import sessions
    u = ready_agent_unit(wired)
    term["agents"].launch_unit(u["id"], "claude")
    sessions.update(u["id"], pid=os.getpid())
    row = next(x for x in wired.serve.api_pipeline("es")["units"] if x["id"] == u["id"])
    assert row["status"] == "doing" and row["paused"] is False and row["session"]["live"] is True
    sessions.update(u["id"], ended=time.time())
    row = next(x for x in wired.serve.api_pipeline("es")["units"] if x["id"] == u["id"])
    assert row["paused"] is True and row["session"]["live"] is False
    other = next(x for x in wired.serve.api_pipeline("es")["units"] if x["status"] == "todo")
    assert other["paused"] is False and other["session"] is None


def test_a_run_that_died_does_not_keep_its_units_busy(wired, monkeypatch):
    """A parallel run killed before writing run.finished leaves units started and never finished in its log: only a
    run that holds the run lock right now is working on them."""
    from lib import sessions
    from lib.harness import scheduler
    from lib.harness.events import EventLog
    log = wired.common.CTX.runs / "2026-10-26-run" / "events.jsonl"
    log.parent.mkdir(parents=True, exist_ok=True)
    EventLog(log).emit("unit.started", unit="u1")
    monkeypatch.setattr(scheduler, "busy", lambda: {"pid": 1})
    assert sessions.headless() == {"u1"}
    monkeypatch.setattr(scheduler, "busy", lambda: None)
    assert sessions.headless() == set()


def test_headless_uses_the_lock_answer_it_is_given(wired, monkeypatch):
    from lib import sessions
    from lib.harness import scheduler
    from lib.harness.events import EventLog
    log = wired.common.CTX.runs / "2026-10-26-run" / "events.jsonl"
    log.parent.mkdir(parents=True, exist_ok=True)
    EventLog(log).emit("unit.started", unit="u1")
    monkeypatch.setattr(scheduler, "busy", lambda: pytest.fail("probed again"))
    assert sessions.headless(busy=True) == {"u1"}
    assert sessions.headless(busy=False) == set()


def test_the_wrapper_can_run_without_a_record(monkeypatch, tmp_path):
    from lib import session_run, sessions
    monkeypatch.chdir(tmp_path)
    assert sessions.wrap(None, ["agent", "x"])[-4:] == ["-", "--", "agent", "x"]
    assert session_run.main(["-", "--", sys.executable, "-c", "raise SystemExit(4)"]) == 4
    assert list(tmp_path.iterdir()) == []
