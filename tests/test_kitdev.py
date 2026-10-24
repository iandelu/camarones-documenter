"""Kit dev in the desktop app (lib/kitdev.py): the bench of a kit checkout — the sandbox, pytest, the portal's npm
test / build and the desktop helpers' tests — as jobs with their output live. Only in a checkout of the kit, only
behind the app's token, and only these commands, built as argument lists (never a shell)."""
from __future__ import annotations

import json, sys, threading, time, urllib.error, urllib.request
from http.server import ThreadingHTTPServer

import pytest

TOKEN = "dev-tok"


@pytest.fixture
def kd(kit, monkeypatch):
    from lib import kitdev
    monkeypatch.setattr(kitdev, "which", lambda name: f"/bin/{name}")
    monkeypatch.setattr(kitdev, "uv", lambda: "/bin/uv")
    return kitdev


def test_this_checkout_is_a_kit_checkout(kd):
    assert kd.available() is True
    assert kd.REPO == kd.KIT.parent


def test_each_task_and_where_it_runs(kd):
    sandbox = ["/bin/uv", "run", "--quiet", str(kd.REPO / "scripts" / "sandbox.py")]
    assert kd.command("sandbox-reset", {}) == (sandbox + ["reset"], kd.REPO)
    assert kd.command("sandbox-traces", {}) == (sandbox + ["traces"], kd.REPO)
    assert kd.command("sandbox-cli", {"line": "status --json"}) == (sandbox + ["cli", "status", "--json"], kd.REPO)
    assert kd.command("pytest", {}) == (["/bin/uv", "run", "pytest", "-q"], kd.REPO)
    assert kd.command("pytest", {"k": "catalog and not drift", "paths": ["tests/test_catalog.py"]}) == \
        (["/bin/uv", "run", "pytest", "-q", "-k", "catalog and not drift", "tests/test_catalog.py"], kd.REPO)
    app = kd.REPO / ".camarones" / "portal" / "app"
    assert kd.command("portal-ci", {}) == (["/bin/npm", "ci"], app)
    assert kd.command("portal-test", {}) == (["/bin/npm", "test"], app)
    assert kd.command("portal-build", {}) == (["/bin/npm", "run", "build"], app)
    assert kd.command("desktop-test", {}) == (["/bin/node", "--test"], kd.REPO / ".camarones" / "desktop")
    assert kd.command("build-diff", {}) == (["/bin/git", "status", "--porcelain", "--", ".camarones/portal/app-build"], kd.REPO)


@pytest.mark.parametrize("task,b", [
    ("rm", {}),
    ("sandbox-cli", {"line": "wizard"}),                       # interactive: `sandbox.py open` is the way
    ("sandbox-cli", {"line": "nonsense --x"}),
    ("sandbox-cli", {"line": ""}),
    ("pytest", {"paths": ["../secrets.py"]}),
    ("pytest", {"paths": [".camarones/lib/env.py"]}),          # tests only
    ("pytest", {"paths": ["tests/nope_test.py"]}),
    ("pytest", {"k": "-x"}),
])
def test_what_is_not_a_bench_task_is_refused(kd, task, b):
    with pytest.raises(ValueError):
        kd.command(task, b)


def test_the_global_install_is_not_a_dev_checkout(kd, monkeypatch):
    monkeypatch.setenv("CAMARONES_GLOBAL", "1")                         # also a full clone, but users run it
    assert kd.available() is False


def test_nothing_outside_a_kit_checkout(kd, monkeypatch, tmp_path):
    monkeypatch.setattr(kd, "REPO", tmp_path)
    assert kd.available() is False
    with pytest.raises(PermissionError):
        kd.command("pytest", {})


@pytest.fixture
def app(kit, monkeypatch):
    monkeypatch.setattr(kit.serve, "APP_TOKEN", TOKEN)
    srv = ThreadingHTTPServer(("127.0.0.1", 0), kit.serve.Handler)
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


def test_a_task_runs_as_a_job_through_the_app(kit, app, monkeypatch):
    from lib import kitdev
    monkeypatch.setattr(kitdev, "command", lambda task, b: ([sys.executable, "-c", "print('12 passed in 0.1s')"], kitdev.REPO))
    code, info = call(app + "/api/app/kitdev")
    assert code == 200 and info["available"] is True and "sandbox" in info
    code, job = call(app + "/api/app/kitdev", {"task": "pytest"})
    assert code == 200 and job["kind"].startswith("kitdev:")
    end = time.monotonic() + 30
    while call(f"{app}/api/jobs/{job['id']}")[1]["status"] == "running" and time.monotonic() < end:
        time.sleep(0.2)
    j = call(f"{app}/api/jobs/{job['id']}")[1]
    assert j["status"] == "done" and j["rc"] == 0 and "12 passed in 0.1s" in j["log"]
    assert call(app + "/api/app/kitdev", {"task": "pytest"}, token=None)[0] == 403
    monkeypatch.setattr(kitdev, "command", lambda task, b: (_ for _ in ()).throw(ValueError("unknown task rm")))
    assert call(app + "/api/app/kitdev", {"task": "rm"})[0] == 400
