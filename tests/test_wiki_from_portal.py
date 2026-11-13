"""The Wikis tab can always start a wiki when an engine is there: a repo nobody chose yet is chosen by the click, and a
repo without its AI brief gets a starter brief written from the static scan (no AI), which repo-brief replaces later.
When no engine can run, the tab says exactly what is missing."""
from __future__ import annotations

import json, re, sys, time
from types import SimpleNamespace

import pytest

from test_plan_wiki import engine, unit  # noqa: F401 — the fake headless engine fixture


def row(kit, repo):
    return next(r for r in kit.services.wiki.wikis() if r["repo"] == repo)


def test_a_starter_brief_from_the_static_scan(wired):
    wiki = wired.services.wiki
    assert wiki.starter_brief("api") is True
    brief = (wired.root / "wikis" / "api" / "INSTRUCTIONS.md").read_text(encoding="utf-8")
    assert brief.startswith(wiki.STARTER_MARK) and "## Coverage" in brief and "Java" in brief
    assert wiki.wiki_brief_ready("api") and row(wired, "api")["brief"] == "starter"
    assert wiki.starter_brief("api") is False                                        # never over an existing brief
    (wired.root / "wikis" / "web" / "INSTRUCTIONS.md").parent.mkdir(parents=True, exist_ok=True)
    (wired.root / "wikis" / "web" / "INSTRUCTIONS.md").write_text("# web\n\n## Coverage\n", encoding="utf-8")
    assert wiki.starter_brief("web") is False and row(wired, "web")["brief"] == "ai"


def test_each_card_says_what_a_click_will_do(wired, monkeypatch):
    wiki = wired.services.wiki
    monkeypatch.setattr(wiki, "wiki_engines", lambda: ["claude"])
    r = row(wired, "api")
    assert r["chosen"] is False and r["brief"] is None and r["canGenerate"] is True
    wired.docs.set_wiki_repos(["api"])
    wiki.starter_brief("api")
    assert row(wired, "api")["canGenerate"] is True and row(wired, "api")["brief"] == "starter"
    monkeypatch.setattr(wiki, "wiki_engines", lambda: [])
    assert row(wired, "api")["canGenerate"] is False


@pytest.mark.parametrize("comps, installed, fix", [
    (["agents"], True, "off"),
    (["openwiki", "agents"], False, "missing"),
    (["openwiki", "agents"], True, "key"),
])
def test_without_an_engine_the_exact_fix(wired, monkeypatch, comps, installed, fix):
    wiki = wired.services.wiki
    ws = wired.docs.workspace(); ws["project"]["components"] = comps; wired.docs.save_workspace(ws)
    monkeypatch.setattr(wired.services.toolchain, "openwiki_installed", lambda: installed)
    monkeypatch.setattr(wired.services.wiki_engine, "openwiki_credentials", lambda: False)
    monkeypatch.setattr(wiki, "which", lambda name: None)
    assert wiki.wiki_engines() == [] and wiki.wiki_engine_help() == fix
    assert wired.serve.tree()["engineHelp"] == fix
    with pytest.raises(RuntimeError, match=re.escape(wiki.ENGINE_HELP[fix][:20])):
        wiki.openwiki_generate("api", log=lambda _: None)


# /api/tree asks on every page load and `npm ls -g` takes seconds: six of them when OpenWiki is missing, which is what
# timed the request out on Windows.
@pytest.fixture
def npm(wired, monkeypatch):
    """The `npm` commands run, answered `npm_rc`; the rest as they are."""
    calls, real = SimpleNamespace(cmds=[], rc=1), wired.services.toolchain.run

    def spy(cmd, *a, **k):
        if cmd[0] != "npm":
            return real(cmd, *a, **k)
        calls.cmds.append(cmd)
        return SimpleNamespace(returncode=calls.rc, stdout="", stderr="")
    monkeypatch.setattr(wired.services.toolchain, "run", spy)
    return calls


def package(folder, version, name="openwiki"):
    folder.mkdir(parents=True)
    (folder / "package.json").write_text(json.dumps({"name": name, "version": version}), encoding="utf-8")


def on_path(kit, monkeypatch, exe):
    monkeypatch.setattr(kit.services.toolchain, "which", lambda name: str(exe) if name == "openwiki" else None)


def test_a_page_load_without_openwiki_does_not_wait_for_npm(wired, monkeypatch, npm):
    monkeypatch.setattr(wired.services.wiki, "which", lambda name: None)
    monkeypatch.setattr(wired.services.toolchain, "which", lambda name: None)
    assert wired.serve.tree()["engines"] == []
    assert npm.cmds == []


@pytest.mark.parametrize("found, pinned", [(lambda v: v, True), (lambda v: "0.0.1", False)])
def test_on_windows_the_version_is_read_beside_the_command(wired, tmp_path, monkeypatch, npm, found, pinned):
    package(tmp_path / "npm" / "node_modules" / "openwiki", found(wired.common.VERSIONS["openwiki"]))
    (tmp_path / "npm" / "openwiki.cmd").write_text("@echo off\n", encoding="utf-8")
    on_path(wired, monkeypatch, tmp_path / "npm" / "openwiki.cmd")
    assert wired.services.toolchain.openwiki_installed() is pinned and npm.cmds == []


@pytest.mark.skipif(sys.platform == "win32", reason="npm links a command on POSIX; on Windows it writes a shim")
@pytest.mark.parametrize("found, pinned", [(lambda v: v, True), (lambda v: "0.0.1", False)])
def test_on_posix_the_version_is_read_through_the_commands_link(wired, tmp_path, monkeypatch, npm, found, pinned):
    pkg = tmp_path / "prefix" / "lib" / "node_modules" / "openwiki"
    package(pkg, found(wired.common.VERSIONS["openwiki"]))
    (pkg / "dist").mkdir()
    (pkg / "dist" / "cli.js").write_text("#!/usr/bin/env node\n", encoding="utf-8")
    (tmp_path / "prefix" / "bin").mkdir()
    (tmp_path / "prefix" / "bin" / "openwiki").symlink_to(pkg / "dist" / "cli.js")
    on_path(wired, monkeypatch, tmp_path / "prefix" / "bin" / "openwiki")
    assert wired.services.toolchain.openwiki_installed() is pinned and npm.cmds == []


@pytest.mark.parametrize("rc, installed", [(0, True), (1, False)])
def test_a_shim_with_no_package_beside_it_still_asks_npm(wired, tmp_path, monkeypatch, npm, rc, installed):
    (tmp_path / "openwiki").mkdir()                                   # a folder that happens to share the name
    package(tmp_path / "openwiki" / "shims", "9.9.9", name="something-else")
    (tmp_path / "openwiki" / "shims" / "openwiki").write_text("#!/bin/sh\n", encoding="utf-8")
    on_path(wired, monkeypatch, tmp_path / "openwiki" / "shims" / "openwiki")
    npm.rc = rc
    assert wired.services.toolchain.openwiki_installed() is installed and npm.cmds and npm.cmds[0][:2] == ["npm", "ls"]


def test_the_portal_chooses_the_repo_writes_the_starter_brief_and_generates(wired, engine):  # noqa: F811
    wired.docs.set_wiki_repos([])
    wired.plan.sync()
    assert unit(wired.plan.load(), "repo-wiki:api")["status"] == "dropped"
    job = wired.serve.wiki({"repo": "api", "choose": True, "starter": True})
    for _ in range(100):
        if wired.serve.JOBS[job["id"]]["status"] != "running":
            break
        time.sleep(0.05)
    assert wired.serve.JOBS[job["id"]]["status"] == "done", wired.serve.JOBS[job["id"]]["log"]
    assert "api" in wired.docs.wiki_repos() and engine["calls"] == 1
    assert unit(wired.plan.load(), "repo-wiki:api")["status"] == "done"
    assert row(wired, "api")["brief"] == "starter"


def test_without_the_flags_the_portal_changes_nothing(wired, engine):  # noqa: F811
    wired.docs.set_wiki_repos([])
    with pytest.raises(ValueError, match="not chosen"):
        wired.serve.wiki({"repo": "api"})
    assert not (wired.root / "wikis" / "api" / "INSTRUCTIONS.md").exists() and engine["calls"] == 0



@pytest.fixture
def installer(wired, engine, monkeypatch):  # noqa: F811
    """No OpenWiki MCP in the project yet; `openwiki integrations install <host> --project .` (as setup runs it)
    writes it, unless `fail` is set."""
    import importlib, json
    mcp = wired.root / ".mcp.json"
    cfg = json.loads(mcp.read_text(encoding="utf-8"))
    cfg["mcpServers"].pop("openwiki", None)
    mcp.write_text(json.dumps(cfg), encoding="utf-8")
    box = {"calls": [], "fail": False}

    def run(cmd, cwd=None, **kw):
        box["calls"].append(cmd)
        if cmd[:3] == ["openwiki", "integrations", "install"] and not box["fail"]:
            data = json.loads(mcp.read_text(encoding="utf-8"))
            data["mcpServers"]["openwiki"] = {"command": "openwiki", "args": ["mcp", "--host", cmd[3]]}
            mcp.write_text(json.dumps(data), encoding="utf-8")
        return type("Done", (), {"returncode": 1 if box["fail"] else 0})()
    monkeypatch.setattr(wired.services.wiki, "run", run)
    monkeypatch.setattr(importlib.import_module("lib.install_state"), "learn", lambda cmds, **kw: None)
    (wired.root / "wikis" / "api" / "INSTRUCTIONS.md").write_text("brief", encoding="utf-8")
    return box


def test_a_run_connects_openwiki_to_the_agent_first(wired, engine, installer):  # noqa: F811
    import json
    assert not wired.services.wiki_engine.openwiki_wired("claude")
    assert wired.services.wiki.openwiki_generate("api", log=lambda _: None) is True
    assert ["openwiki", "integrations", "install", "claude", "--project", "."] in installer["calls"]
    settings = json.loads((wired.root / ".claude" / "settings.json").read_text(encoding="utf-8"))
    assert "openwiki" in settings["enabledMcpjsonServers"]                       # a headless run loads it unasked
    installer["calls"].clear()
    wired.services.wiki.openwiki_generate("api", log=lambda _: None)
    assert not any(c[:3] == ["openwiki", "integrations", "install"] for c in installer["calls"])


def test_when_openwiki_cannot_be_connected_the_run_says_so(wired, engine, installer):  # noqa: F811
    installer["fail"] = True
    with pytest.raises(RuntimeError, match="camaron setup"):
        wired.services.wiki.openwiki_generate("api", log=lambda _: None)
    assert engine["calls"] == 0


@pytest.fixture
def held(wired, monkeypatch):
    """Wiki generation that runs until the test lets it go."""
    import threading
    gate = threading.Event()
    monkeypatch.setattr(wired.services.wiki, "openwiki_generate", lambda repo, mode, log, engine="": gate.wait(10))
    yield gate
    gate.set()


def test_while_one_repos_wiki_runs_another_repo_is_busy_and_nothing_is_chosen(wired, held):
    wired.docs.set_wiki_repos([])
    wired.plan.sync()
    first = wired.serve.wiki({"repo": "api", "choose": True})
    assert first["status"] == "running" and first["repo"] == "api"
    ws_file, plan_file = wired.docs.ws_file(), wired.plan.PLAN
    ws_before, plan_before = ws_file.read_bytes(), plan_file.read_bytes()
    assert wired.serve.wiki({"repo": "web", "choose": True, "starter": True}) == {"error": "busy", "repo": "api"}
    assert ws_file.read_bytes() == ws_before and plan_file.read_bytes() == plan_before
    assert "web" not in wired.docs.wiki_repos()
    assert not (wired.root / "wikis" / "web" / "INSTRUCTIONS.md").exists()
    assert wired.serve.wiki({"repo": "api"})["id"] == first["id"]                 # the same repo attaches
    held.set()


def test_a_second_repo_during_the_first_ones_preparation_is_busy(wired, held, monkeypatch):
    """The first repo's run is claimed before choosing it and writing its starter brief (seconds on real repos): a
    second repo clicked meanwhile is busy and nothing of it is chosen or written."""
    import threading
    wired.docs.set_wiki_repos([])
    wired.plan.sync()
    preparing, release = threading.Event(), threading.Event()
    real = wired.services.wiki.starter_brief

    def slow(repo):
        if repo == "api":
            preparing.set()
            release.wait(10)
        return real(repo)
    monkeypatch.setattr(wired.services.wiki, "starter_brief", slow)
    first: dict = {}
    t = threading.Thread(target=lambda: first.update(wired.serve.wiki({"repo": "api", "choose": True, "starter": True})))
    t.start()
    try:
        assert preparing.wait(10)
        second = wired.serve.wiki({"repo": "web", "choose": True, "starter": True})
    finally:
        release.set()
        t.join(10)
    assert second == {"error": "busy", "repo": "api"}
    assert "web" not in wired.docs.wiki_repos()
    assert not (wired.root / "wikis" / "web" / "INSTRUCTIONS.md").exists()
    assert first["repo"] == "api" and first["status"] == "running"
    held.set()


def test_a_preparation_that_fails_leaves_no_running_wiki(wired, held, monkeypatch):
    wired.docs.set_wiki_repos(["api", "web"])

    def boom(repo):
        raise OSError("disk full")
    monkeypatch.setattr(wired.services.wiki, "starter_brief", boom)
    with pytest.raises(OSError, match="disk full"):
        wired.serve.wiki({"repo": "api", "starter": True})
    failed = [j for j in wired.serve.JOBS.values() if j["kind"] == "wiki" and j.get("repo") == "api"]
    assert failed and failed[-1]["status"] == "failed" and any("disk full" in line for line in failed[-1]["log"])
    monkeypatch.undo()
    monkeypatch.setattr(wired.services.wiki, "openwiki_generate", lambda repo, mode, log, engine="": held.wait(10))
    assert wired.serve.wiki({"repo": "web"})["status"] == "running"                # not blocked by the failed one
    held.set()


def test_the_busy_answer_is_a_409(wired, held, monkeypatch):
    import json, threading, urllib.error, urllib.request
    from http.server import ThreadingHTTPServer
    monkeypatch.setattr("lib.interfaces.http.server.APP_TOKEN", "tok")
    wired.docs.set_wiki_repos(["api", "web"])
    wired.serve.wiki({"repo": "api"})
    srv = ThreadingHTTPServer(("127.0.0.1", 0), wired.serve.Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        req = urllib.request.Request(f"http://127.0.0.1:{srv.server_address[1]}/api/wiki", method="POST",
                                     data=json.dumps({"repo": "web"}).encode(),
                                     headers={"Content-Type": "application/json", "X-Camarones": "1", "X-Camaron-Token": "tok"})
        with pytest.raises(urllib.error.HTTPError) as e:
            urllib.request.urlopen(req, timeout=10)
        assert e.value.code == 409 and json.loads(e.value.read())["error"] == "busy"
    finally:
        srv.shutdown()
