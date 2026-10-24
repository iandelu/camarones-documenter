"""Actions from the Pipeline tab (R22): start a run, cancel it, retry a blocked unit. Every one needs the X-Camarones
header (a cross-site page cannot send it); one run at a time, whether it was started here or from the CLI."""
from __future__ import annotations

import json, sys, threading, time, urllib.error, urllib.request
from http.server import ThreadingHTTPServer

import pytest

from test_scheduler import FAKE


APP_TOKEN = "app-token"      # these actions run on the machine: the desktop app's server, not the browser portal


@pytest.fixture
def server(wired, monkeypatch):
    monkeypatch.setattr(wired.serve, "APP_TOKEN", APP_TOKEN)
    srv = ThreadingHTTPServer(("127.0.0.1", 0), wired.serve.Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


def post(url, body=None, header=True):
    req = urllib.request.Request(url, data=json.dumps(body or {}).encode(), method="POST",
                                 headers={"Content-Type": "application/json", **({"X-Camarones": "1", "X-Camaron-Token": APP_TOKEN} if header else {})})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


def get(url):
    with urllib.request.urlopen(url, timeout=10) as r:
        return json.loads(r.read())


@pytest.fixture
def fake_agent(wired, tmp_path, monkeypatch):
    script = tmp_path / "fake_agent.py"
    script.write_text(FAKE, encoding="utf-8")
    from lib.common import PREFS, save_json
    save_json(PREFS, {"runners": {"fake": {"argv": [sys.executable, str(script), "ok"]}},
                      "routing": {"agentic-heavy": ["fake"]}})
    log = tmp_path / "fake.log"
    for k, v in {"FAKE_LOG": str(log), "KIT_DIR": str(wired.kit_dir), "FAKE_SLEEP": "0.2", "FAKE_STATUS": "done"}.items():
        monkeypatch.setenv(k, v)
    wired.plan.sync()
    wired.plan.set_status("setup", "done")
    return log


def wait_for(cond, timeout=30):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if cond():
            return True
        time.sleep(0.2)
    return False


def status(wired, uid):
    return next(u for u in wired.plan.load()["units"] if u["id"] == uid)["status"]


@pytest.mark.parametrize("path", ["/api/runs", "/api/runs/r-1/cancel", "/api/units/retry"])
def test_actions_need_the_portal_header(server, path):
    assert post(server + path, {"unit": "x"}, header=False)[0] == 403


def test_a_run_started_from_the_portal_documents_units(wired, server, fake_agent):
    code, job = post(f"{server}/api/runs", {"parallel": 1, "max_units": 1})
    assert code == 200 and job["kind"] == "run"
    assert wait_for(lambda: get(f"{server}/api/jobs/{job['id']}")["status"] != "running")
    assert status(wired, "discovery:api") == "done"
    assert get(f"{server}/api/pipeline")["run"]["finished"]


def test_only_one_run_at_a_time(wired, server):
    from lib.harness import locks, scheduler
    holder = threading.Event()
    release = threading.Event()

    def hold():
        with locks.FileLock(scheduler.RUN_LOCK, info={"what": "run"}):
            holder.set()
            release.wait(10)
    threading.Thread(target=hold, daemon=True).start()
    holder.wait(5)
    try:
        code, body = post(f"{server}/api/runs", {"parallel": 1})
        assert code == 409 and "in progress" in body["error"]
    finally:
        release.set()


def test_cancel_stops_the_agents_and_puts_their_units_back(wired, server, fake_agent, monkeypatch):
    monkeypatch.setenv("FAKE_SLEEP", "30")
    code, job = post(f"{server}/api/runs", {"parallel": 2, "per_runner": "fake=2", "max_units": 2})
    assert code == 200
    assert wait_for(lambda: fake_agent.exists() and fake_agent.read_text(encoding="utf-8").count('"start"') == 2)
    run_id = get(f"{server}/api/pipeline")["run"]["run"]
    assert post(f"{server}/api/runs/{run_id}/cancel")[0] == 200
    assert wait_for(lambda: get(f"{server}/api/jobs/{job['id']}")["status"] != "running", timeout=20)
    assert {status(wired, u) for u in ("discovery:api", "discovery:web")} == {"todo"}
    assert '"end"' not in fake_agent.read_text(encoding="utf-8")                  # the agents were stopped
    d = get(f"{server}/api/runs/{run_id}")
    assert d["interrupted"] and {u["outcome"] for u in d["units"]} == {"cancelled"}


def test_retry_puts_a_blocked_unit_back_in_the_queue(wired, server):
    wired.plan.sync()
    wired.plan.set_status("discovery:api", "blocked", "integrate: conflicts")
    code, unit = post(f"{server}/api/units/retry", {"unit": "discovery:api"})
    assert code == 200 and unit["status"] == "todo" and status(wired, "discovery:api") == "todo"
    assert post(f"{server}/api/units/retry", {"unit": "setup"})[0] == 409          # only blocked units are retried


def test_the_cli_refuses_a_second_run(wired):
    from lib.harness import locks, scheduler
    with locks.FileLock(scheduler.RUN_LOCK):
        done = threading.Event()
        err = {}

        def other():
            try:
                scheduler.run_parallel(echo=lambda _: None, poll=0.01)
            except RuntimeError as e:
                err["e"] = str(e)
            done.set()
        threading.Thread(target=other).start()
        done.wait(10)
    assert "in progress" in err.get("e", "")


def test_autopilot_does_not_start_during_another_run(wired, monkeypatch):
    from lib.harness import locks, scheduler
    monkeypatch.setattr(wired.plan, "which", lambda n: f"/bin/{n}")
    out = []
    with locks.FileLock(scheduler.RUN_LOCK):
        result = {}
        t = threading.Thread(target=lambda: result.setdefault("n", wired.plan.run_autopilot(echo=out.append)))
        t.start()
        t.join(10)
    assert result["n"] == 0 and any("in progress" in l for l in out)
