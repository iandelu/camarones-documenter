"""Work plan units and the OpenWiki run lifecycle (choice of repos, brief requirement, open/close, one run at a time)."""
from __future__ import annotations

import os

import pytest


def unit(data, uid):
    return next(u for u in data["units"] if u["id"] == uid)


# ---------- plan ----------
def test_wiki_units_only_for_the_chosen_repos(kit):
    plan, docs = kit.plan, kit.docs
    data = plan.sync()
    assert unit(data, "repo-wiki:api")["status"] == "dropped"
    assert unit(data, "repo-wiki:api")["notes"] == plan.NO_WIKI
    docs.set_wiki_repos(["api"])
    data = plan.sync()
    assert unit(data, "repo-wiki:api")["status"] == "todo" and unit(data, "repo-wiki:api")["notes"] == ""
    assert unit(data, "repo-wiki:web")["status"] == "dropped"


def test_no_wiki_units_without_the_openwiki_component(kit):
    kit.docs.set_wiki_repos(["api"])
    kit.env.set_components(["likec4", "agents"])
    assert unit(kit.plan.sync(), "repo-wiki:api")["notes"] == "OpenWiki not selected"


def test_sync_keeps_progress_and_drops_removed_repos(kit):
    plan, docs = kit.plan, kit.docs
    plan.sync()
    plan.set_status("discovery:web", "done")
    ws = docs.workspace()
    ws["repos"] = [r for r in ws["repos"] if r["name"] != "worker"]
    docs.save_workspace(ws)
    data = plan.sync()
    assert unit(data, "discovery:web")["status"] == "done"
    assert unit(data, "discovery:worker")["status"] == "dropped"


def test_restoring_a_failed_run_is_not_a_transition(kit):
    plan = kit.plan
    plan.sync()
    stamp = plan.set_status("setup", "doing")["updated"]
    plan.set_status("setup", "todo", record=False)
    u = unit(plan.load(), "setup")
    assert u["status"] == "todo" and u["updated"] == stamp
    assert not plan.LOG.exists()
    plan.set_status("setup", "done")
    assert "**setup** → done" in plan.LOG.read_text(encoding="utf-8")


def test_available_follows_dependencies(kit):
    plan = kit.plan
    plan.sync()
    assert [u["id"] for u in plan.available()] == ["setup"]
    plan.set_status("setup", "done")
    ids = [u["id"] for u in plan.available()]
    assert {"discovery:api", "discovery:web", "discovery:worker"} <= set(ids)
    assert "discovery-cross" not in ids


# ---------- OpenWiki ----------
def test_close_without_open_is_a_no_op(wired):
    agents = wired.ws / "api" / "AGENTS.md"
    agents.write_text("the repo's own", encoding="utf-8")
    assert wired.env.wiki_close("api", log=lambda _: None) is False
    assert agents.read_text(encoding="utf-8") == "the repo's own"


def test_open_close_round_trip_restores_the_repo(wired):
    env, repo = wired.env, wired.ws / "api"
    claude_before = (repo / "CLAUDE.md").read_text(encoding="utf-8")
    env.wiki_open("api", log=lambda _: None)
    ow = repo / "openwiki"
    assert ow.is_dir() and not env._is_link(ow)
    (ow / "index.md").write_text("# api wiki\n", encoding="utf-8")        # what OpenWiki writes during the run
    (repo / "AGENTS.md").write_text("openwiki snippet", encoding="utf-8")
    (repo / "CLAUDE.md").write_text("openwiki snippet", encoding="utf-8")
    (repo / ".github" / "workflows").mkdir(parents=True)
    (repo / ".github" / "workflows" / "openwiki-update.yml").write_text("on: push", encoding="utf-8")
    assert env.wiki_close("api", log=lambda _: None) is True
    assert (wired.root / "wikis" / "api" / "index.md").is_file()
    assert env._is_link(ow)
    assert not (repo / "AGENTS.md").exists() and not (repo / ".github").exists()
    assert (repo / "CLAUDE.md").read_text(encoding="utf-8") == claude_before
    assert env.wiki_close("api", log=lambda _: None) is False               # a second close changes nothing


def test_brief_is_not_a_page(wired):
    wiki = wired.root / "wikis" / "web"
    (wiki / "INSTRUCTIONS.md").write_text("brief", encoding="utf-8")
    assert wired.env.wiki_pages("web") == [] and wired.env.wiki_brief_ready("web")
    (wiki / "overview.md").write_text("# overview", encoding="utf-8")
    assert [p.name for p in wired.env.wiki_pages("web")] == ["overview.md"]
    assert "repos/web/INSTRUCTIONS.md" not in [l for l, _ in wired.docs.iter_docs()]


def test_one_wiki_run_at_a_time(wired, monkeypatch):
    env = wired.env
    env.WIKI_LOCK.parent.mkdir(parents=True, exist_ok=True)
    env.WIKI_LOCK.write_text('{"pid": 999999, "repo": "web"}', encoding="utf-8")
    monkeypatch.setattr(env, "pid_alive", lambda pid: True)
    with pytest.raises(RuntimeError, match="another OpenWiki run"):
        with env.wiki_lock("api"):
            pass
    monkeypatch.setattr(env, "pid_alive", lambda pid: False)              # a dead holder does not block
    with env.wiki_lock("api"):
        assert f'"pid": {os.getpid()}' in env.WIKI_LOCK.read_text(encoding="utf-8")
    assert not env.WIKI_LOCK.exists()


@pytest.fixture
def engine(wired, monkeypatch):
    """A fake headless engine: `rc` is its exit code; with rc 0 it writes one page into the real openwiki/ folder."""
    env, box = wired.env, {"rc": 0, "calls": 0}

    def stream(cmd, cwd, log, env_=None):
        box["calls"] += 1
        if box["rc"] == 0:
            (wired.ws / "api" / "openwiki" / "index.md").write_text("# api\n", encoding="utf-8")
        log("session limit reached" if box["rc"] else "ok")
        return box["rc"]
    monkeypatch.setattr(env, "wiki_engines", lambda: ["claude"])
    monkeypatch.setattr(env, "stream", stream)
    monkeypatch.setattr(env, "wiki_graph", lambda *a, **kw: True)
    monkeypatch.setattr(env, "checkpoint_commit", lambda *a, **kw: True)
    wired.docs.set_wiki_repos(["api"])
    wired.plan.sync()
    return box


def test_first_wiki_needs_the_brief(wired, engine):
    with pytest.raises(RuntimeError, match="INSTRUCTIONS.md"):
        wired.env.openwiki_generate("api", log=lambda _: None)
    assert engine["calls"] == 0
    assert wired.env.openwiki_generate("api", log=lambda _: None, force=True) is True
    assert unit(wired.plan.load(), "repo-wiki:api")["status"] == "done"
    assert wired.env._is_link(wired.ws / "api" / "openwiki")


def test_engine_down_aborts_and_restores_the_unit(wired, engine):
    engine["rc"] = 1
    (wired.root / "wikis" / "api" / "INSTRUCTIONS.md").write_text("brief", encoding="utf-8")
    with pytest.raises(wired.env.WikiAbort):
        wired.env.openwiki_generate("api", log=lambda _: None)
    u = unit(wired.plan.load(), "repo-wiki:api")
    assert u["status"] == "todo"
    assert "repo-wiki:api" not in (wired.plan.LOG.read_text(encoding="utf-8") if wired.plan.LOG.exists() else "")
    assert not wired.env.WIKI_LOCK.exists()
    assert wired.env._is_link(wired.ws / "api" / "openwiki")             # the repo is put back even on failure
