"""The handoff between a run and the project server: a file per request (lib/harness/handoff.py), and what a run's log
says of a unit (lib/harness/runs.py)."""
from __future__ import annotations

import pytest


@pytest.fixture
def log(kit):
    from lib.harness.events import EventLog

    def write(run_id, *events):
        out = EventLog(kit.common.CTX.runs / run_id / "events.jsonl")
        for kind, fields in events:
            out.emit(kind, run=run_id, **fields)
        return run_id
    return write


def test_a_request_is_read_back_and_cleared(kit):
    from lib.harness import handoff
    assert handoff.read("r-1", "discovery:api") is None
    handoff.request("r-1", "discovery:api", "pilot", session="s-1", agent="claude")
    got = handoff.read("r-1", "discovery:api")
    assert (got["to"], got["unit"], got["session"], got["agent"]) == ("pilot", "discovery:api", "s-1", "claude")
    assert got["at"] > 0
    handoff.clear("r-1", "discovery:api")
    assert handoff.read("r-1", "discovery:api") is None
    handoff.clear("r-1", "discovery:api")                       # nothing to clear: not an error


def test_a_unit_id_is_a_file_name_on_every_os(kit):
    from lib.harness import handoff
    assert ":" not in handoff.file("r-1", "discovery:api").name
    handoff.request("r-1", "discovery:api", "you")
    assert handoff.file("r-1", "discovery:api").is_file()


def test_pending_lists_the_run_requests_by_unit_and_skips_a_damaged_file(kit):
    from lib.harness import handoff
    assert handoff.pending("r-1") == {}
    handoff.request("r-1", "discovery:api", "pilot")
    handoff.request("r-1", "discovery:web", "stop")
    handoff.file("r-1", "broken").write_text("{not json", encoding="utf-8")
    assert {u: r["to"] for u, r in handoff.pending("r-1").items()} == {"discovery:api": "pilot", "discovery:web": "stop"}


def test_a_unit_runs_when_its_last_start_has_no_finish(kit, log):
    from lib.harness import runs
    rid = log("r-1", ("unit.started", {"unit": "a"}), ("unit.finished", {"unit": "a", "outcome": "handed"}),
              ("unit.started", {"unit": "a", "resume": "s"}), ("unit.started", {"unit": "b"}),
              ("unit.finished", {"unit": "b", "outcome": "ok"}))
    assert runs.running(rid, "a") and not runs.running(rid, "b") and not runs.running(rid, "c")


def test_the_last_session_is_of_the_last_attempt_with_its_agent(kit, log):
    from lib.harness import runs
    log("r-1", ("unit.started", {"unit": "a", "runner": "claude"}), ("session", {"unit": "a", "runner": "claude", "id": "s-1"}),
        ("unit.finished", {"unit": "a", "outcome": "limited"}), ("unit.started", {"unit": "a", "runner": "codex:o5"}),
        ("session", {"unit": "a", "runner": "codex:o5", "id": "T"}), ("session", {"unit": "z", "runner": "claude", "id": "other"}))
    assert runs.last_session("a") == {"id": "T", "agent": "codex"}
    assert runs.last_session("never") is None


def test_an_attempt_with_no_conversation_has_no_id_but_says_its_agent(kit, log):
    from lib.harness import runs
    log("r-1", ("unit.started", {"unit": "a", "runner": "claude"}), ("session", {"unit": "a", "runner": "claude", "id": "s-1"}),
        ("unit.finished", {"unit": "a", "outcome": "limited"}), ("unit.started", {"unit": "a", "runner": "opencode"}))
    assert runs.last_session("a") == {"id": None, "agent": "opencode"}


def test_a_resumed_attempt_keeps_its_conversation(kit, log):
    from lib.harness import runs
    log("r-1", ("unit.started", {"unit": "a", "runner": "codex", "resume": "T"}))
    assert runs.last_session("a") == {"id": "T", "agent": "codex"}


def test_the_last_session_reads_the_newest_run_unless_told(kit, log):
    from lib.harness import runs
    log("r-1", ("unit.started", {"unit": "a", "runner": "claude"}), ("session", {"unit": "a", "runner": "claude", "id": "old"}))
    log("r-2", ("unit.started", {"unit": "b", "runner": "claude"}))
    assert runs.last_session("a") is None
    assert runs.last_session("a", "r-1") == {"id": "old", "agent": "claude"}


def test_there_is_no_active_run_without_a_lock(kit, log):
    from lib.harness import runs
    assert runs.active() is None
    rid = log("r-1", ("run.started", {"agents": ["claude"]}))
    assert runs.active() is None                                # its process is gone: nobody holds the lock
    assert rid


def test_a_run_a_lock_holder_keeps_is_active_with_its_kind(kit, log, monkeypatch):
    from lib.harness import runs, scheduler
    monkeypatch.setattr(scheduler, "busy", lambda: {"pid": 1})
    log("r-1", ("run.started", {"agents": ["claude"]}))
    assert runs.active() == {"run": "r-1", "kind": "autopilot"}
    log("r-2", ("run.started", {"parallel": 2}))
    assert runs.active() == {"run": "r-2", "kind": "parallel"}
    log("r-2", ("run.finished", {"done": 0}))
    assert runs.active() is None


def test_a_handoff_is_not_a_failure_in_a_run_summary(kit, log):
    from lib.harness import runs
    rid = log("r-1", ("run.started", {"agents": ["claude"]}), ("unit.started", {"unit": "a", "runner": "claude"}),
              ("unit.finished", {"unit": "a", "outcome": "handed", "status": "doing"}),
              ("unit.started", {"unit": "b", "runner": "claude"}),
              ("unit.finished", {"unit": "b", "outcome": "cancelled", "status": "todo"}))
    s = runs.summary(rid)
    assert s["failed"] == 0 and s["kind"] == "autopilot"


def test_an_old_run_log_has_no_kind(kit, log):
    from lib.harness import runs
    assert runs.summary(log("r-1", ("unit.started", {"unit": "a"})))["kind"] is None


def test_a_unit_started_again_after_a_handoff_is_the_runs(kit, log):
    from lib import sessions
    log("r-1", ("run.started", {"agents": ["claude"]}), ("unit.started", {"unit": "a"}),
        ("unit.finished", {"unit": "a", "outcome": "handed"}), ("unit.started", {"unit": "a", "resume": "s"}),
        ("unit.started", {"unit": "b"}), ("unit.finished", {"unit": "b", "outcome": "handed"}))
    assert sessions.headless(True) == {"a"}


def test_a_request_that_cannot_be_cleared_does_not_stop_the_run(kit, monkeypatch):
    from lib.harness import handoff

    def held(_fn):
        raise PermissionError("Windows: someone is reading it")
    handoff.request("r-1", "discovery:api", "you")
    monkeypatch.setattr(handoff, "retry_busy", held)
    handoff.clear("r-1", "discovery:api")                       # the next look finds it, or the next attempt clears it
