"""The desktop app's side of the portal server (lib/appapi.py): work that starts a process or calls a model needs the
token the app passes to the server it launches; the browser portal is the team's viewer. With a token, the server
also refuses requests whose Host is not itself (DNS rebinding) and runs catalog commands as jobs."""
from __future__ import annotations

import json, os, subprocess, sys, threading, time, urllib.error, urllib.request
from http.server import ThreadingHTTPServer

import pytest

TOKEN = "s3cret-token"
PROCESS = ["/api/runs", "/api/runs/r-1/cancel", "/api/wiki", "/api/build", "/api/inventory", "/api/schemas",
           "/api/ci", "/api/ask/answer"]


@pytest.fixture
def app_server(kit, monkeypatch):
    monkeypatch.setattr(kit.serve, "APP_TOKEN", TOKEN)
    srv = ThreadingHTTPServer(("127.0.0.1", 0), kit.serve.Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


@pytest.fixture
def portal_server(kit):
    srv = ThreadingHTTPServer(("127.0.0.1", 0), kit.serve.Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


def call(url, body=None, token=None, host=None):
    headers = {"Content-Type": "application/json", "X-Camarones": "1"}
    if token:
        headers["X-Camaron-Token"] = token
    if host:
        headers["Host"] = host
    req = urllib.request.Request(url, data=None if body is None else json.dumps(body).encode(),
                                 method="GET" if body is None else "POST", headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


@pytest.mark.parametrize("path", PROCESS)
def test_the_browser_portal_sends_machine_work_to_the_app(portal_server, path):
    code, body = call(portal_server + path, {"what": "c4", "q": "x", "forge": "gitlab", "repo": "api"})
    assert code == 403 and body["app"] is True and "camaron app" in body["error"]


@pytest.mark.parametrize("path", PROCESS)
def test_a_wrong_token_is_refused(app_server, path):
    assert call(app_server + path, {}, token="nope")[0] == 403


def test_the_right_token_reaches_the_endpoint(app_server):
    code, body = call(app_server + "/api/build", {"what": "nonsense"}, token=TOKEN)
    assert code == 400 and "unknown build" in body["error"]                    # past the gate, into the handler


def test_portal_work_needs_no_token(portal_server, kit):
    code, _ = call(portal_server + "/api/tree")
    assert code == 200
    (kit.root / "docs" / "overview.md").write_text("---\ntitle: Overview\n---\n# Overview\n", encoding="utf-8")
    assert call(portal_server + "/api/feedback", {"path": "overview.md", "text": "typo", "by": "Ana"})[0] == 200


def test_with_a_token_a_foreign_host_is_refused(app_server):
    assert call(app_server + "/api/tree", host="evil.example")[0] == 403
    assert call(app_server + "/api/tree", host="evil.example:80", token=TOKEN)[0] == 403
    assert call(app_server + "/api/tree")[0] == 200


def test_info_says_what_the_app_can_show(app_server):
    code, info = call(app_server + "/api/app/info", token=TOKEN)
    assert code == 200 and info["kitdev"] is True and info["kit"] and info["user"] == "Test"
    assert call(app_server + "/api/app/info")[0] == 403


def test_the_catalog_reaches_the_app(app_server):
    code, cat = call(app_server + "/api/app/catalog", token=TOKEN)
    assert code == 200 and any(c["name"] == "run" and c["verdict"] == "app" for c in cat["commands"])


# ---------- commands as jobs ----------

@pytest.fixture
def entries(kit):
    from lib import appapi
    return {c["name"]: c for c in appapi.catalog()["commands"]}


def test_argv_follows_the_catalog(kit, entries):
    from lib import appapi
    assert appapi.argv(entries["run"], {"parallel": 3, "include_interviews": True, "only": ["a", "b"]}) == \
        ["run", "--parallel", "3", "--include-interviews", "--only", "a", "b"]
    assert appapi.argv(entries["interview"], {"action": "status", "json": True}) == ["interview", "status", "--json"]
    assert appapi.argv(entries["wiki"], {"repos": ["api"], "mode": "update"}) == ["wiki", "api", "--update"]
    assert appapi.argv(entries["run"], {"parallel": 2, "include_interviews": False}) == ["run", "--parallel", "2"]


@pytest.mark.parametrize("cmd,args,msg", [
    ("run", {"parallel": "many"}, "parallel"),
    ("run", {"policy": "always"}, "policy"),
    ("run", {"nope": 1}, "nope"),
    ("interview", {}, "action"),
    ("wiki", {"repos": ["--evil"]}, "repos"),
])
def test_argv_refuses_what_the_parser_would_not_take(kit, entries, cmd, args, msg):
    from lib import appapi
    with pytest.raises(ValueError, match=msg):
        appapi.argv(entries[cmd], args)


def test_a_yes_flag_is_only_sent_after_the_app_asked(kit, entries):
    from lib import appapi
    with pytest.raises(PermissionError):
        appapi.argv(entries["uninstall"], {"no_backup": True})
    assert appapi.argv(entries["uninstall"], {"no_backup": True}, confirmed=True) == ["uninstall", "--no-backup", "--yes"]
    assert appapi.argv(entries["uninstall"], {"dry_run": True}) == ["uninstall", "--dry-run"]   # a preview: no asking
    with pytest.raises(ValueError, match="yes"):
        appapi.argv(entries["uninstall"], {"yes": True}, confirmed=True)        # never set by the caller itself


@pytest.mark.parametrize("cmd", ["confirm", "mcp", "wizard", "new", "join", "switch", "nonsense"])
def test_commands_the_app_does_not_run(app_server, cmd):
    code, body = call(app_server + "/api/app/cmd", {"cmd": cmd, "args": {}}, token=TOKEN)
    assert code in (400, 404) and body["error"]


def wait_job(url, jid, timeout=60):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        code, j = call(f"{url}/api/jobs/{jid}")
        if j["status"] != "running":
            return j
        time.sleep(0.2)
    raise AssertionError("job did not finish")


def test_a_command_runs_as_a_job_with_its_output(app_server):
    code, job = call(app_server + "/api/app/cmd", {"cmd": "version", "args": {}}, token=TOKEN)
    assert code == 200 and job["kind"] == "cmd:version"
    code, other = call(app_server + "/api/app/cmd", {"cmd": "status", "args": {"json": True}}, token=TOKEN)
    assert other["id"] != job["id"] and other["kind"] == "cmd:status --json"
    j = wait_job(app_server, job["id"])
    assert j["status"] == "done" and j["rc"] == 0 and any("Camarón" in line for line in j["log"])


def test_a_json_command_returns_its_result(app_server):
    code, job = call(app_server + "/api/app/cmd", {"cmd": "status", "args": {"json": True}}, token=TOKEN)
    j = wait_job(app_server, job["id"])
    assert j["status"] == "done" and isinstance(j["result"], list)


def test_a_failing_command_is_a_failed_job(app_server):
    code, job = call(app_server + "/api/app/cmd", {"cmd": "stack", "args": {"repo": "no-such-repo"}}, token=TOKEN)
    j = wait_job(app_server, job["id"])
    assert j["status"] == "failed" and j["rc"] != 0


def test_job_events_stream_the_log(app_server):
    code, job = call(app_server + "/api/app/cmd", {"cmd": "version", "args": {}}, token=TOKEN)
    req = urllib.request.Request(f"{app_server}/api/app/jobs/{job['id']}/events", headers={"X-Camaron-Token": TOKEN})
    with urllib.request.urlopen(req, timeout=60) as r:
        body = r.read().decode("utf-8")
    events = [json.loads(line[6:]) for line in body.splitlines() if line.startswith("data: ")]
    assert events[-1]["type"] == "end" and events[-1]["status"] == "done"
    assert any(e["type"] == "line" for e in events)


# ---------- the CLI side ----------

def cli(kit, *args):
    e = {**os.environ, "CAMARONES_ROOT": str(kit.root)}
    return subprocess.run([sys.executable, str(kit.kit_dir / "camarones.py"), *args], env=e, capture_output=True,
                          text=True, encoding="utf-8")


def test_projects_lists_the_registry(kit):
    kit.projects.register(kit.root, "demo")
    r = cli(kit, "projects", "--json")
    assert r.returncode == 0, r.stderr
    rows = json.loads(r.stdout)
    assert [p["name"] for p in rows] == ["demo"] and rows[0]["exists"] is True
    kit.projects.register(kit.root)                                     # named after its folder: cam-docs
    assert json.loads(cli(kit, "projects", "--json").stdout)[0]["name"] == kit.ws.name


def test_up_with_an_app_token_says_its_port(kit):
    e = {**os.environ, "CAMARONES_ROOT": str(kit.root), "CAMARONES_APP_TOKEN": TOKEN}
    pr = subprocess.Popen([sys.executable, str(kit.kit_dir / "camarones.py"), "up", "--foreground", "--port", "0"],
                          env=e, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8")
    try:
        ready = json.loads(pr.stdout.readline())
        assert ready["ready"] is True and ready["port"] > 0
        code, info = call(f"http://127.0.0.1:{ready['port']}/api/app/info", token=TOKEN)
        assert code == 200
    finally:
        pr.terminate()
        pr.wait(timeout=10)


def test_stopping_a_job_stops_the_command_and_its_agent(app_server, kit, tmp_path, monkeypatch):
    code, job = call(app_server + "/api/app/cmd", {"cmd": "review", "args": {}}, token=TOKEN)
    assert code == 400                                                   # CLI-only commands are not run
    # a run on a fake agent that takes long (never a real agent CLI of this machine)
    from test_scheduler import FAKE
    from conftest import wire_project
    wire_project(kit)
    script = tmp_path / "fake_agent.py"
    script.write_text(FAKE, encoding="utf-8")
    from lib.common import PREFS, save_json
    save_json(PREFS, {"runners": {"fake": {"argv": [sys.executable, str(script), "ok"]}},
                      "routing": {"agentic-heavy": ["fake"], "bounded": ["fake"]}})
    log = tmp_path / "fake.log"
    for k, v in {"FAKE_LOG": str(log), "KIT_DIR": str(kit.kit_dir), "FAKE_SLEEP": "60"}.items():
        monkeypatch.setenv(k, v)
    kit.plan.sync()
    kit.plan.set_status("setup", "done")
    code, job = call(app_server + "/api/app/cmd", {"cmd": "run", "args": {"max_units": 1, "per_runner": "fake=1"}},
                     token=TOKEN)
    assert code == 200
    end = time.monotonic() + 60
    while not (log.exists() and '"start"' in log.read_text(encoding="utf-8")) and time.monotonic() < end:
        time.sleep(0.2)
    assert log.exists(), call(f"{app_server}/api/jobs/{job['id']}")[1]["log"]
    code, _ = call(f"{app_server}/api/app/jobs/{job['id']}/cancel", {}, token=TOKEN)
    assert code == 200
    j = wait_job(app_server, job["id"], timeout=30)
    assert j["status"] == "failed"
    time.sleep(1)
    assert '"end"' not in log.read_text(encoding="utf-8")                 # the agent went with it


def test_a_read_only_form_of_a_confirmed_command_needs_no_confirmation(kit, entries):
    from lib import appapi
    assert appapi.argv(entries["trust"], {"json": True}) == ["trust", "--json"]          # lists, approves nothing
    with pytest.raises(PermissionError):
        appapi.argv(entries["trust"], {})
    assert appapi.argv(entries["trust"], {}, confirmed=True) == ["trust", "--yes"]
