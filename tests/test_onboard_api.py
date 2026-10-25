"""The desktop app's onboarding endpoints (/api/app/onboard/*, token only) and GET /firstlook: a thin layer over
lib/onboard.py. Offline: setup's installs are faked, the C4 draft is a static scan."""
from __future__ import annotations

import inspect, json, os, re, subprocess, sys, threading, urllib.error, urllib.request

import pytest

from test_app_api import TOKEN, app_server, call, portal_server, wait_job   # noqa: F401 — fixtures reused

GET = ["state", "tools", "stack"]
POST = {"step": {"id": "tools"}, "repos": {"repos": []}, "setup": {}, "scan": {}, "stack": {"repo": "api", "text": "x"},
        "arch": {"action": "draft"}, "done": {}}


@pytest.fixture
def no_likec4(kit, monkeypatch):
    monkeypatch.setattr(kit.quickarch, "which", lambda *_a, **_k: None)       # the draft without LikeC4's validate/build


def fetch(url):
    """(status, text) of a plain GET: /firstlook is a page, not JSON."""
    try:
        with urllib.request.urlopen(url, timeout=30) as r:
            return r.status, r.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        return e.code, ""


def post(url, name, body, token=TOKEN):
    return call(f"{url}/api/app/onboard/{name}", body, token=token)


@pytest.mark.parametrize("name", GET)
def test_onboard_get_routes_need_the_token(app_server, name):
    code, body = call(f"{app_server}/api/app/onboard/{name}")
    assert code == 403 and body["app"] is True
    assert call(f"{app_server}/api/app/onboard/{name}", token="nope")[0] == 403


@pytest.mark.parametrize("name", POST)
def test_onboard_post_routes_need_the_token(app_server, name):
    code, body = post(app_server, name, POST[name], token=None)
    assert code == 403 and body["app"] is True
    assert post(app_server, name, POST[name], token="nope")[0] == 403


def test_the_browser_portal_cannot_reach_them(portal_server):
    assert call(f"{portal_server}/api/app/onboard/state")[0] == 403
    code, body = post(portal_server, "done", {}, token=None)
    assert code == 403 and body["app"] is True


def test_state_describes_a_first_run(app_server, kit):
    code, st = call(f"{app_server}/api/app/onboard/state", token=TOKEN)
    assert code == 200 and st["mode"] == "new" and st["kind"] == "legacy" and st["done"] is False
    assert st["steps"] == ["repos", "tools", "setup", "stack", "arch", "intro"]       # the start screen did "name"
    assert st["step"] == "repos"                                                      # nothing saved: the first listed
    assert {r["name"] for r in st["repos"]} == {"api", "web", "worker"}
    assert {r["name"] for r in st["found"]} == {"api", "web", "worker"}
    assert st["name"] == kit.onboard.docs.workspace()["project"]["name"] and st["name"]   # the wizard's header


def test_state_reads_old_position_files(app_server, kit):
    from lib.common import save_json
    f = kit.onboard.firstrun_file(kit.root)
    save_json(f, {"step": 2, "done": False})                  # before 3.3: an index into the old list (name, repos, tools…)
    assert call(f"{app_server}/api/app/onboard/state", token=TOKEN)[1]["step"] == "tools"
    save_json(f, {"step": 7, "done": True})
    st = call(f"{app_server}/api/app/onboard/state", token=TOKEN)[1]
    assert st["mode"] == "done" and st["done"] is True


def test_a_saved_join_resumes_in_the_join_steps(app_server, kit):
    from lib.common import save_json
    save_json(kit.onboard.firstrun_file(kit.root), {"mode": "join", "name": "setup", "step": 3, "done": False})
    st = call(f"{app_server}/api/app/onboard/state", token=TOKEN)[1]
    assert st["mode"] == "join" and st["steps"] == ["tools", "setup", "intro"] and st["step"] == "setup"


def test_one_function_decides_the_mode_for_the_cli_and_the_app(kit):
    assert kit.onboard.mode({"done": True}) == "done" and kit.onboard.mode({"step": 1}) == "new"
    assert kit.onboard.mode({"mode": "join"}) == "join"
    assert "onboard.mode(" in inspect.getsource(kit.wizard.W._run)          # the CLI does not keep its own copy


def test_greenfield_state_has_the_short_steps(app_server, kit):
    ws = kit.docs.workspace()
    ws["project"]["kind"] = "greenfield"
    kit.docs.save_workspace(ws)
    st = call(f"{app_server}/api/app/onboard/state", token=TOKEN)[1]
    assert st["kind"] == "greenfield" and st["steps"] == ["repos", "tools", "setup", "intro"]


def test_state_and_step_round_trip(app_server, kit):
    code, st = post(app_server, "step", {"id": "tools"})
    assert code == 200 and st["step"] == "tools"
    saved = json.loads(kit.onboard.firstrun_file(kit.root).read_text(encoding="utf-8"))
    assert saved["name"] == "tools" and saved["done"] is False
    assert call(f"{app_server}/api/app/onboard/state", token=TOKEN)[1]["step"] == "tools"
    assert post(app_server, "step", {"id": "nope"})[0] == 400
    assert post(app_server, "step", {})[0] == 400
    assert post(app_server, "step", {"id": "name"}) == (400, {"error": "step"})          # the start screen's, not listed


def test_step_only_accepts_the_modes_own_steps(app_server, kit):
    from lib.common import save_json
    save_json(kit.onboard.firstrun_file(kit.root), {"mode": "join", "name": "tools", "step": 2, "done": False})
    assert post(app_server, "step", {"id": "repos"}) == (400, {"error": "step"})
    code, st = post(app_server, "step", {"id": "setup"})
    assert code == 200 and st["step"] == "setup" and st["mode"] == "join"           # a join stays a join


def test_step_is_refused_once_the_first_run_is_done(app_server, kit):
    post(app_server, "done", {})
    assert post(app_server, "step", {"id": "tools"}) == (400, {"error": "done"})
    assert call(f"{app_server}/api/app/onboard/state", token=TOKEN)[1]["done"] is True


def test_repos_validation(app_server, kit):
    row = {"name": "api", "url": "https://git.example.com/a/api.git"}
    assert post(app_server, "repos", {"repos": [row, dict(row)]}) == (400, {"error": "duplicate"})
    assert post(app_server, "repos", {"repos": [{"url": "x"}]}) == (400, {"error": "name"})
    assert post(app_server, "repos", {"repos": []}) == (400, {"error": "repos"})            # legacy: at least one
    assert post(app_server, "repos", {})[0] == 400
    code, st = post(app_server, "repos", {"repos": [row]})
    assert code == 200 and st["repos"] == [{"name": "api", "url": row["url"], "branch": "main", "kind": "service"}]
    assert [r["name"] for r in kit.docs.workspace()["repos"]] == ["api"]
    ws = kit.docs.workspace()
    ws["project"]["kind"] = "greenfield"
    kit.docs.save_workspace(ws)
    code, st = post(app_server, "repos", {"repos": []})
    assert code == 200 and st["repos"] == []


@pytest.mark.parametrize("name", ["a/b", "a\\b", "..", "a..b", ".hidden", "-x", "cam-docs", "CAM-DOCS"])
def test_repo_names_are_folder_names(app_server, name):
    assert post(app_server, "repos", {"repos": [{"name": name}]}) == (400, {"error": "name"})


def test_a_repo_url_cannot_be_an_option(app_server):
    assert post(app_server, "repos", {"repos": [{"name": "api", "url": "--upload-pack=x"}]}) == (400, {"error": "url"})


def test_repos_keep_what_the_wizard_already_knows(app_server, kit):
    ws = kit.docs.workspace()
    ws["repos"][0]["stack"] = "Spring Boot"
    kit.docs.save_workspace(ws)
    name = ws["repos"][0]["name"]
    post(app_server, "repos", {"repos": [{"name": name, "branch": "dev", "kind": "webapp"}]})
    row = kit.docs.workspace()["repos"][0]
    assert (row["stack"], row["branch"], row["kind"]) == ("Spring Boot", "dev", "webapp")


def test_tools_lists_rows_and_whether_the_required_are_there(app_server):
    code, body = call(f"{app_server}/api/app/onboard/tools", token=TOKEN)
    assert code == 200 and {"git", "node", "graphify"} <= {r["id"] for r in body["rows"]}
    assert body["required_ok"] == all(r["ok"] for r in body["rows"] if r["kind"] == "t_required")


def test_setup_job_logs_progress(app_server, kit, monkeypatch):
    def fake_setup(ci=False, log=print, comps=None):
        for i in range(3):
            log(f"✔ step {i}")
        return True
    monkeypatch.setattr(kit.env, "setup", fake_setup)
    monkeypatch.setattr(kit.env, "install_prereq", lambda k, log=print: True)
    monkeypatch.setattr(kit.env, "set_components", lambda c: None)
    code, job = post(app_server, "setup", {"system": ["docker"], "components": ["likec4", "bogus"]})
    assert code == 200 and job["kind"] == "onboard:setup"
    j = wait_job(app_server, job["id"])
    assert j["status"] == "done", j["log"]
    lines = [l for l in j["log"] if re.match(r"^\[\d+/\d+\]", l)]
    assert len(lines) == 4 and lines[0].startswith("[1/") and lines[-1].startswith("[4/")     # docker + three steps
    assert j["result"]["ok"] is True and j["result"]["failed"] == [] and j["result"]["missing"] == []
    assert kit.plan.get(kit.plan.load(), "setup")["status"] == "done"


def test_a_failed_setup_ends_failed_with_its_result(app_server, kit, monkeypatch):
    monkeypatch.setattr(kit.env, "setup", lambda ci=False, log=print, comps=None: (_ for _ in ()).throw(RuntimeError("boom")))
    monkeypatch.setattr(kit.env, "install_prereq", lambda k, log=print: False)
    monkeypatch.setattr(kit.env, "set_components", lambda c: None)
    j = wait_job(app_server, post(app_server, "setup", {"system": ["docker"], "components": []})[1]["id"])
    assert j["status"] == "failed" and any("boom" in l for l in j["log"])
    assert j["result"]["ok"] is False and j["result"]["failed"] == ["docker"]


def test_cancelling_setup_stops_between_steps(app_server, kit, monkeypatch):
    installed, ran_setup = [], []
    first, release = threading.Event(), threading.Event()

    def install(k, log=print):
        installed.append(k)
        first.set()
        release.wait(20)                                  # the first tool is "installing" while the user cancels
        return True
    monkeypatch.setattr(kit.env, "install_prereq", install)
    monkeypatch.setattr(kit.env, "setup", lambda ci=False, log=print, comps=None: ran_setup.append(1) or True)
    monkeypatch.setattr(kit.env, "set_components", lambda c: None)
    code, job = post(app_server, "setup", {"system": ["git", "docker", "java"], "components": []})
    assert code == 200 and first.wait(20)
    assert call(f"{app_server}/api/app/jobs/{job['id']}/cancel", {}, token=TOKEN) == (200, {"cancelling": job["id"]})
    release.set()
    j = wait_job(app_server, job["id"])
    assert j["status"] == "failed" and "cancelled" in j["log"]
    assert installed == ["git"] and ran_setup == []                  # nothing after the step it was in
    assert j["result"]["cancelled"] is True and j["result"]["ok"] is False
    assert call(f"{app_server}/api/app/jobs/{job['id']}/cancel", {}, token=TOKEN)[0] >= 400    # finished: as before


def test_cancelling_after_env_setup_does_not_mark_it_done(kit, monkeypatch):
    flag = {"stop": False}
    monkeypatch.setattr(kit.env, "setup", lambda ci=False, log=print, comps=None: flag.update(stop=True) or True)
    assert kit.onboard.run_setup(lambda _: None, cancelled=lambda: flag["stop"]) is False
    assert kit.plan.get(kit.plan.load(), "setup")["status"] != "done"


def test_a_setup_that_was_not_cancelled_says_so(app_server, kit, monkeypatch):
    monkeypatch.setattr(kit.env, "setup", lambda ci=False, log=print, comps=None: True)
    monkeypatch.setattr(kit.env, "set_components", lambda c: None)
    j = wait_job(app_server, post(app_server, "setup", {"system": [], "components": []})[1]["id"])
    assert j["status"] == "done" and j["result"]["cancelled"] is False


def test_stack_lists_and_edits(app_server, kit):
    code, rows = call(f"{app_server}/api/app/onboard/stack", token=TOKEN)
    assert code == 200 and set(rows["api"]) == {"stack", "detected_stack"}
    code, rows = post(app_server, "stack", {"repo": "api", "text": "Kotlin + Ktor"})
    assert code == 200 and rows["api"]["stack"] == "Kotlin + Ktor"
    assert post(app_server, "stack", {"repo": "ghost", "text": "x"})[0] == 400
    assert post(app_server, "stack", {"repo": "api", "text": 5})[0] == 400
    assert post(app_server, "stack", {"repo": "api", "text": ["x"]})[0] == 400
    assert post(app_server, "stack", {"repo": "api", "text": None})[0] == 200                  # back to the detected one


def test_scan_runs_as_a_job(app_server, kit, monkeypatch):
    import lib.wizard
    seen = []
    monkeypatch.setattr(lib.wizard, "scan_repos", lambda log=print: (log("scanned"), seen.append(1)))
    code, job = post(app_server, "scan", {})
    assert code == 200 and job["kind"] == "onboard:scan"
    assert wait_job(app_server, job["id"])["status"] == "done" and seen


def test_arch_draft_save_and_firstlook(app_server, kit, no_likec4):
    assert fetch(f"{app_server}/firstlook")[0] == 404                      # no draft yet; and no token needed to ask
    code, job = post(app_server, "arch", {"action": "draft"})
    assert code == 200 and job["kind"] == "onboard:arch"
    res = wait_job(app_server, job["id"])["result"]
    assert {r["name"] for r in res["repos"]} == {"api", "web", "worker"} and res["html"] is False
    assert {"datastores", "brokers", "relations", "valid"} <= set(res)
    code, saved = post(app_server, "arch", {"action": "save"})
    assert code == 200 and saved["exists"] is False
    assert "docs/architecture/model.c4" in saved["written"]
    assert (kit.root / "docs" / "architecture" / "model.c4").is_file()


def test_firstlook_serves_the_drafts_page_without_a_token(app_server, kit, tmp_path):
    page = tmp_path / "index.html"
    page.write_text("<html><body>draft</body></html>", encoding="utf-8")
    kit.onboard.LAST_DRAFT["html"] = page
    code, text = fetch(f"{app_server}/firstlook")
    assert code == 200 and "draft" in text
    page.unlink()
    assert fetch(f"{app_server}/firstlook")[0] == 404                      # a page that is gone is a 404, not a crash


def test_arch_save_asks_before_overwriting(app_server, kit, no_likec4):
    wait_job(app_server, post(app_server, "arch", {"action": "draft"})[1]["id"])
    model = kit.root / "docs" / "architecture" / "model.c4"
    model.parent.mkdir(parents=True, exist_ok=True)
    model.write_text("// mine\n", encoding="utf-8")
    assert post(app_server, "arch", {"action": "save"}) == (200, {"exists": True})
    assert post(app_server, "arch", {"action": "save", "overwrite": False}) == (200, {"exists": True})
    assert model.read_text(encoding="utf-8") == "// mine\n"
    code, saved = post(app_server, "arch", {"action": "save", "overwrite": True})
    assert code == 200 and saved["exists"] is False and model.read_text(encoding="utf-8") != "// mine\n"


def test_arch_save_waits_for_a_running_draft(app_server, kit, no_likec4, monkeypatch):
    real, started, release = kit.quickarch.draft, threading.Event(), threading.Event()

    def slow(log=print):
        started.set()
        release.wait(20)
        return real(log=log)
    monkeypatch.setattr(kit.quickarch, "draft", slow)
    code, job = post(app_server, "arch", {"action": "draft"})
    assert code == 200 and started.wait(20)
    assert post(app_server, "arch", {"action": "save"}) == (409, {"error": "busy"})
    assert post(app_server, "arch", {"action": "save-ai", "agent": "claude"}) == (409, {"error": "busy"})
    release.set()
    assert wait_job(app_server, job["id"])["status"] == "done"
    assert post(app_server, "arch", {"action": "save"})[0] == 200


def test_arch_save_needs_a_draft_and_a_known_action(app_server, kit):
    assert post(app_server, "arch", {"action": "save"})[0] == 400
    assert post(app_server, "arch", {"action": "nope"})[0] == 400


def test_arch_save_ai_saves_then_opens_the_agent(app_server, kit, no_likec4, monkeypatch):
    import lib.agents
    launched = []
    monkeypatch.setattr(lib.agents, "launch_prompt", lambda prompt, agent, lang="es": launched.append((prompt, agent, lang)) or {"ok": True})
    wait_job(app_server, post(app_server, "arch", {"action": "draft"})[1]["id"])
    code, res = post(app_server, "arch", {"action": "save-ai", "agent": "claude", "lang": "en"})
    assert code == 200 and (kit.root / "docs" / "architecture" / "model.c4").is_file()
    assert launched == [(kit.onboard.arch_prompt("en"), "claude", "en")]


@pytest.mark.parametrize("raised, code", [(RuntimeError("no terminal window"), "terminal"), (ValueError("x is not installed"), "agent")])
def test_arch_save_ai_keeps_the_save_when_the_agent_cannot_open(app_server, kit, no_likec4, monkeypatch, raised, code):
    """The model is already written when the agent fails to open: the save stands and the app is told why."""
    import lib.agents

    def boom(*_a, **_k):
        raise raised
    monkeypatch.setattr(lib.agents, "launch_prompt", boom)
    wait_job(app_server, post(app_server, "arch", {"action": "draft"})[1]["id"])
    status, res = post(app_server, "arch", {"action": "save-ai", "agent": "claude", "lang": "es"})
    assert status == 200 and (kit.root / "docs" / "architecture" / "model.c4").is_file()
    assert res["written"] and res["launched"] is False and res["error"] == code


def test_done_finishes_the_first_run_and_commits(app_server, kit):
    from fixtures.builder import git
    git(kit.root, "init", "-q", "-b", "main")             # the fixture's cam-docs is a plain folder
    (kit.root / "docs").mkdir(exist_ok=True)
    (kit.root / "docs" / "first.md").write_text("---\ntitle: First\n---\n# First\n", encoding="utf-8")
    code, res = post(app_server, "done", {})
    assert code == 200 and res == {"committed": True}
    saved = json.loads(kit.onboard.firstrun_file(kit.root).read_text(encoding="utf-8"))
    assert saved["done"] is True
    assert call(f"{app_server}/api/app/onboard/state", token=TOKEN)[1]["mode"] == "done"
    assert kit.common.out(["git", "log", "-1", "--format=%s"], cwd=kit.root) == "docs(camarones): first setup"


def test_done_counts_the_steps_of_the_computed_mode(app_server, kit, monkeypatch):
    kit.plan.sync()                                        # the team's plan + workspace came with the repo, this machine is not set up
    monkeypatch.setattr(kit.onboard, "local_ready", lambda: False)
    assert call(f"{app_server}/api/app/onboard/state", token=TOKEN)[1]["mode"] == "join"
    post(app_server, "done", {})
    assert json.loads(kit.onboard.firstrun_file(kit.root).read_text(encoding="utf-8"))["step"] == len(kit.onboard.JOIN_STEPS)


def test_server_starts_on_a_fresh_docs_root(kit, tmp_path):
    folder = tmp_path / "idea"
    folder.mkdir()
    root = kit.onboard.start(folder)
    e = {**os.environ, "CAMARONES_ROOT": str(root), "CAMARONES_APP_TOKEN": TOKEN}
    pr = subprocess.Popen([sys.executable, str(kit.kit_dir / "camarones.py"), "up", "--foreground", "--port", "0"],
                          env=e, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8")
    try:
        ready = json.loads(pr.stdout.readline())
        assert ready["ready"] is True and ready["port"] > 0
        code, st = call(f"http://127.0.0.1:{ready['port']}/api/app/onboard/state", token=TOKEN)
        assert code == 200 and st["kind"] == "greenfield" and st["step"] == "repos" and st["repos"] == []
    finally:
        pr.terminate()
        pr.wait(timeout=10)
