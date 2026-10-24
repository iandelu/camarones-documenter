"""The CI tab (S15): what the kit's pipelines look like in this project — installed or not, out of date against the
definition, the per-repo files to copy — with the last `check` and freshness, the last pipeline run when `gh` or
`glab` is installed and logged in (hidden otherwise), and a button that writes the pipeline like `camaron ci`."""
from __future__ import annotations

import json, threading, urllib.error, urllib.request
from http.server import ThreadingHTTPServer

import pytest


@pytest.fixture
def ci(kit, monkeypatch):
    from lib import ci
    monkeypatch.setattr(ci, "_probe", lambda cmd: None)                                  # no network in tests
    return ci


def test_nothing_installed_yet(kit, ci):
    s = ci.status()
    assert s["forge"] in ("github", "gitlab") and s["target"] == "local"
    assert all(v["path"] is None for v in s["installed"].values())
    assert s["pipeline"] is None and "check" in s and set(s["freshness"]) >= {"fresh", "suspect", "stale"}
    assert "openwiki" in s["snippets"]["repo"] and "camaron" in s["snippets"]["fresh"]
    assert s["snippets"]["propose"] is None                                              # only for self-hosted runners


def test_after_camaron_ci_it_is_installed_and_current(kit, ci):
    kit.env.install_ci("github", log=lambda _: None)
    s = ci.status("github")
    inst = s["installed"]
    assert inst["umbrella"]["path"] == ".github/workflows/docs.yml" and inst["fresh"]["path"] == ".camarones/ci/docs-fresh.github.yml"
    assert inst["snippet"]["path"] == ".camarones/ci/repo.github.yml" and not inst["fresh"]["outdated"]
    f = kit.root / ".camarones" / "ci" / "docs-fresh.github.yml"
    f.write_text(f.read_text(encoding="utf-8") + "# edited by hand\n", encoding="utf-8")
    assert ci.status("github")["installed"]["fresh"]["outdated"] is True


def test_self_hosted_projects_also_get_the_proposal_job(kit, ci):
    ws = kit.docs.workspace(); ws["ci"] = {"target": "self-hosted"}; kit.docs.save_workspace(ws)
    s = ci.status("gitlab")
    assert s["target"] == "self-hosted" and "pr propose" in s["snippets"]["propose"]
    assert "propose" in s["installed"]


@pytest.mark.parametrize("forge, tool, reply, want", [
    ("github", "gh", [{"status": "completed", "conclusion": "failure", "displayTitle": "docs: brief",
                       "url": "https://github.com/o/r/actions/runs/1", "createdAt": "2026-10-22T10:00:00Z",
                       "workflowName": "docs"}],
     {"status": "failure", "title": "docs: brief", "url": "https://github.com/o/r/actions/runs/1", "at": "2026-10-22T10:00:00Z"}),
    ("gitlab", "glab", [{"status": "success", "ref": "main", "web_url": "https://gitlab.com/o/r/-/pipelines/9",
                         "created_at": "2026-10-22T10:00:00Z"}],
     {"status": "success", "title": "main", "url": "https://gitlab.com/o/r/-/pipelines/9", "at": "2026-10-22T10:00:00Z"}),
])
def test_the_last_pipeline_comes_from_the_forge_cli(kit, monkeypatch, forge, tool, reply, want):
    from lib import ci
    seen = []
    monkeypatch.setattr(ci, "_probe", lambda cmd: seen.append(cmd) or json.dumps(reply))
    assert ci.last_pipeline(forge) == want and seen[0][0] == tool
    monkeypatch.setattr(ci, "_probe", lambda cmd: None)                                  # not installed / not logged in
    assert ci.last_pipeline(forge) is None
    monkeypatch.setattr(ci, "_probe", lambda cmd: "not json")
    assert ci.last_pipeline(forge) is None


@pytest.fixture
def portal(kit, ci, monkeypatch):
    monkeypatch.setattr(kit.serve, "APP_TOKEN", "app-token")       # installing CI files is the desktop app's work
    srv = ThreadingHTTPServer(("127.0.0.1", 0), kit.serve.Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


def call(url, body=None, header=True):
    req = urllib.request.Request(url, data=json.dumps(body).encode() if body is not None else None,
                                 method="POST" if body is not None else "GET",
                                 headers={"Content-Type": "application/json", **({"X-Camarones": "1", "X-Camaron-Token": "app-token"} if header else {})})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


def test_the_portal_shows_and_writes_the_pipeline(kit, portal):
    code, s = call(f"{portal}/api/ci")
    assert code == 200 and s["installed"]["umbrella"]["path"] is None
    assert call(f"{portal}/api/ci", {"forge": "gitlab"}, header=False)[0] == 403
    assert call(f"{portal}/api/ci", {"forge": "jenkins"})[0] == 400
    code, s = call(f"{portal}/api/ci", {"forge": "gitlab"})
    assert code == 200 and s["forge"] == "gitlab" and s["installed"]["umbrella"]["path"] == ".gitlab-ci.yml"
    assert (kit.root / ".camarones" / "ci" / "docs-fresh.gitlab-ci.yml").is_file()
