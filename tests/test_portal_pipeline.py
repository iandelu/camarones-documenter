"""The Pipeline tab's data (R21): the plan as a graph, run details, and a run's events streamed live over SSE.
Each SSE message's id is the byte offset after it, so a browser that reconnects with Last-Event-ID misses nothing and
sees nothing twice."""
from __future__ import annotations

import json, threading, urllib.request
from http.server import ThreadingHTTPServer

import pytest


@pytest.fixture
def server(kit):
    srv = ThreadingHTTPServer(("127.0.0.1", 0), kit.serve.Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


def get_json(url):
    with urllib.request.urlopen(url, timeout=10) as r:
        return json.loads(r.read())


def sse(url, last_id=None):
    req = urllib.request.Request(url, headers={"Last-Event-ID": str(last_id)} if last_id is not None else {})
    out = []
    with urllib.request.urlopen(req, timeout=10) as r:
        assert r.headers.get("Content-Type", "").startswith("text/event-stream")
        msg = {}
        for raw in r:
            line = raw.decode("utf-8").rstrip("\n")
            if not line:
                if "data" in msg:
                    out.append((int(msg["id"]), json.loads(msg["data"])))
                msg = {}
            elif not line.startswith(":"):
                k, _, v = line.partition(": ")
                msg[k] = v
    return out


@pytest.fixture
def run_log(kit):
    from lib.harness.events import EventLog
    log = EventLog(kit.common.CTX.runs / "r-20261016-100000-1" / "events.jsonl")
    log.emit("run.started", run="r-20261016-100000-1")
    log.emit("unit.started", run="r-20261016-100000-1", unit="discovery:api", runner="claude", isolation="worktree")
    log.emit("tool.call", run="r-20261016-100000-1", unit="discovery:api", runner="claude", name="Read", arg="pom.xml")
    log.emit("unit.finished", run="r-20261016-100000-1", unit="discovery:api", runner="claude", outcome="ok",
             status="done", seconds=12.0)
    log.emit("run.finished", run="r-20261016-100000-1", done=1)
    return log


def test_the_stream_sends_every_event_and_ends_with_the_run(server, run_log):
    got = sse(f"{server}/api/runs/r-20261016-100000-1/events")
    assert [e["type"] for _, e in got] == ["run.started", "unit.started", "tool.call", "unit.finished", "run.finished"]
    assert [i for i, _ in got] == sorted(i for i, _ in got)


def test_a_reconnect_resumes_after_the_last_event_seen(server, run_log):
    first = sse(f"{server}/api/runs/r-20261016-100000-1/events")
    resumed = sse(f"{server}/api/runs/r-20261016-100000-1/events", last_id=first[2][0])
    assert [e["type"] for _, e in resumed] == ["unit.finished", "run.finished"]


def test_a_live_run_streams_events_as_they_are_written(kit, server):
    from lib.harness.events import EventLog
    log = EventLog(kit.common.CTX.runs / "r-live" / "events.jsonl")
    log.emit("run.started", run="r-live")

    def later():
        import time
        time.sleep(0.6)
        log.emit("unit.started", run="r-live", unit="a", runner="claude")
        log.emit("run.finished", run="r-live", done=0)
    threading.Thread(target=later).start()
    assert [e["type"] for _, e in sse(f"{server}/api/runs/r-live/events")] == ["run.started", "unit.started",
                                                                             "run.finished"]


def test_an_unknown_run_is_a_404(server):
    with pytest.raises(urllib.error.HTTPError) as e:
        urllib.request.urlopen(f"{server}/api/runs/nope/events", timeout=5)
    assert e.value.code == 404


def test_pipeline_api_has_units_with_status_dependencies_and_how_they_run(kit, server, run_log):
    kit.plan.sync()
    kit.plan.set_status("setup", "done")
    data = get_json(f"{server}/api/pipeline")
    u = next(x for x in data["units"] if x["id"] == "discovery:api")
    assert {k: u[k] for k in ("status", "deps", "isolation", "tier", "phase")} == {
        "status": "todo", "deps": ["setup"], "isolation": "worktree", "tier": "agentic-heavy", "phase": 1}
    assert data["run"]["run"] == "r-20261016-100000-1"


def test_run_detail_api(server, run_log):
    d = get_json(f"{server}/api/runs/r-20261016-100000-1")
    assert d["units"][0]["unit"] == "discovery:api" and d["units"][0]["seconds"] == 12.0


def test_each_unit_says_whether_it_is_ready(kit, server):
    """The app's Plan groups the units by what they ask for: `ready` is plan.available's own rule (redo chains, soft
    links), not a guess from deps on the page."""
    kit.plan.sync()
    kit.plan.set_status("setup", "done")
    units = get_json(server + "/api/pipeline")["units"]
    ready = {u["id"] for u in kit.plan.available()}
    assert ready and {u["id"] for u in units if u["ready"]} == ready
    assert next(u for u in units if u["id"] == "setup")["ready"] is False


def test_the_pipeline_says_how_interviews_run_once_chosen(kit, server):
    """The app's Plan asks for the interview mode on an interview unit instead of failing when it starts."""
    kit.plan.sync()
    assert get_json(server + "/api/pipeline")["interviews"] is None
    kit.docs.set_interview_mode("team")
    assert get_json(server + "/api/pipeline")["interviews"] == "team"
