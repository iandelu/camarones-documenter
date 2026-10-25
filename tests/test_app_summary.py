"""The desktop app's Summary (4.52): one next step from the plan and the review queue (plan.next_step), the same rule
as the wizard's default — finish the agent unit left half done, else the next ready unit, else review, else nothing
left — read by the app at GET /api/app/summary. And the jobs its panel lists, with which of them can be stopped."""
from __future__ import annotations

import json, os, sys, threading, time, urllib.error, urllib.request
from http.server import ThreadingHTTPServer

import pytest

TOKEN = "sum-tok"
BRIEF = ("id", "title", "runner", "type")


def brief(u):
    return {k: u[k] for k in BRIEF}


def test_a_fresh_plan_starts_with_the_machine(wired):
    data = wired.plan.sync()
    s = wired.plan.next_step(data)
    assert s["kind"] == "next" and s["unit"]["id"] == "setup" and s["unit"]["runner"] == "wizard"


def test_then_the_next_ready_unit(wired):
    wired.plan.sync()
    wired.plan.set_status("setup", "done")
    ready = [u for u in wired.plan.available() if u["status"] != "doing"]
    assert wired.plan.next_step() == {"kind": "next", "unit": brief(ready[0])}


def test_a_unit_left_half_done_comes_first(wired):
    wired.plan.sync()
    wired.plan.set_status("setup", "done")
    u = next(u for u in wired.plan.available() if u["runner"] == "agent")
    wired.plan.set_status(u["id"], "doing")
    s = wired.plan.next_step()
    assert s == {"kind": "resume", "unit": brief(wired.plan.get(wired.plan.load(), u["id"]))}


def test_with_nothing_ready_the_review_then_nothing_left(wired):
    data = wired.plan.sync()
    for u in data["units"]:
        u["status"] = "done"
    assert wired.plan.next_step(data, review=3) == {"kind": "review", "count": 3}
    assert wired.plan.next_step(data) == {"kind": "done"}


def test_the_wizard_defaults_to_the_same_step(kit):
    from lib import wizard
    assert wizard.MENU_DEFAULT == {"resume": "resume", "next": "next", "review": "review", "done": "portal"}


@pytest.fixture
def app(kit, monkeypatch):
    monkeypatch.setattr(kit.serve, "APP_TOKEN", TOKEN)
    srv = ThreadingHTTPServer(("127.0.0.1", 0), kit.serve.Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


def get(url, token=TOKEN):
    req = urllib.request.Request(url, headers={"X-Camarones": "1", **({"X-Camaron-Token": token} if token else {})})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


def test_the_app_reads_the_summary_with_its_token(wired, app):
    wired.plan.sync()
    code, body = get(app + "/api/app/summary")
    assert code == 200
    assert body["step"] == wired.plan.next_step(lang="es")              # nothing picked on this machine: Spanish
    done, total = wired.plan.progress()
    assert body["plan"] == {"done": done, "total": total} and isinstance(body["review"], int)
    assert get(app + "/api/app/summary", token=None)[0] == 403


def wait_end(job, timeout=30):
    end = time.monotonic() + timeout
    while job["status"] == "running" and time.monotonic() < end:
        time.sleep(0.1)
    return job


def test_a_stopped_job_says_it_was_stopped(kit):
    from lib import appapi
    sleeper = appapi.stream_job(kit.serve.start_job, "test:sleep", [sys.executable, "-c", "import time; time.sleep(30)"],
                                kit.kit_dir, dict(os.environ))
    end = time.monotonic() + 10
    while not appapi.stoppable(sleeper["id"]) and time.monotonic() < end:     # its thread starts the process
        time.sleep(0.05)
    appapi.cancel(sleeper["id"])
    j = wait_end(sleeper)
    assert j["status"] == "failed" and j["stopped"] is True               # failed, as it always was; and why
    quick = wait_end(appapi.stream_job(kit.serve.start_job, "test:quick", [sys.executable, "-c", "print(1)"],
                                       kit.kit_dir, dict(os.environ)))
    assert quick["status"] == "done" and quick["stopped"] is False


def test_the_jobs_say_which_can_be_stopped(kit, app, monkeypatch):
    from lib import appapi
    gate = threading.Event()
    job = kit.serve.start_job("test:wait", "wait", lambda log: gate.wait(10))

    class Running:
        def poll(self):
            return None
    try:
        row = next(j for j in get(app + "/api/jobs")[1] if j["id"] == job["id"])
        assert row["stoppable"] is False and "log" not in row              # a build: it runs to the end
        monkeypatch.setitem(appapi.PROCS, job["id"], {"proc": Running()})
        row = next(j for j in get(app + "/api/jobs")[1] if j["id"] == job["id"])
        assert row["stoppable"] is True                                     # a process the app started: Stop
    finally:
        gate.set()


def post(url, body, token=TOKEN):
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST",
                                 headers={"Content-Type": "application/json", "X-Camarones": "1", "X-Camaron-Token": token})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def test_a_panel_reading_in_the_background_keeps_its_job_out_of_the_panel(wired, app):
    """A section reads `trust --json` and the like each time it opens: those jobs say quiet, and the jobs panel skips
    them. The first caller decides: a read attaching to a job someone started stays visible."""
    quiet = post(app + "/api/app/cmd", {"cmd": "version", "args": {}, "quiet": True})
    rows = {j["id"]: j for j in get(app + "/api/jobs")[1]}
    assert rows[quiet["id"]]["quiet"] is True
    wait_end(kit_job(wired, quiet["id"]))
    loud = post(app + "/api/app/cmd", {"cmd": "version", "args": {}})
    assert {j["id"]: j for j in get(app + "/api/jobs")[1]}[loud["id"]]["quiet"] is False


def kit_job(wired, job_id):
    return wired.serve.JOBS[job_id]


DOCTOR = {"prerequisites": [{"name": "node", "ok": False, "need": True}], "tools": [], "drift": [],
          "fix_drift": {"cmd": "repair", "args": {}}}


def test_the_app_reads_the_last_doctor_check_and_asks_for_a_new_one(wired, app, monkeypatch):
    from lib import doctor
    monkeypatch.setattr(doctor, "report", lambda: DOCTOR)
    assert get(app + "/api/app/doctor")[1] == {"checked": None}
    assert get(app + "/api/app/summary")[1]["doctor"] is None             # never checked: the Summary says nothing
    job = post(app + "/api/app/doctor", {})
    wait_end(kit_job(wired, job["id"]))
    body = get(app + "/api/app/doctor")[1]
    assert body["checked"]["result"] == DOCTOR
    assert get(app + "/api/app/summary")[1]["doctor"] == doctor.problems(DOCTOR)
    assert get(app + "/api/app/doctor", token=None)[0] == 403
