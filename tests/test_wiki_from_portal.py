"""The Wikis tab can always start a wiki when an engine is there: a repo nobody chose yet is chosen by the click, and a
repo without its AI brief gets a starter brief written from the static scan (no AI), which repo-brief replaces later.
When no engine can run, the tab says exactly what is missing."""
from __future__ import annotations

import re, time

import pytest

from test_plan_wiki import engine, unit  # noqa: F401 — the fake headless engine fixture


def row(kit, repo):
    return next(r for r in kit.env.wikis() if r["repo"] == repo)


def test_a_starter_brief_from_the_static_scan(wired):
    env = wired.env
    assert env.starter_brief("api") is True
    brief = (wired.root / "wikis" / "api" / "INSTRUCTIONS.md").read_text(encoding="utf-8")
    assert brief.startswith(env.STARTER_MARK) and "## Coverage" in brief and "Java" in brief
    assert env.wiki_brief_ready("api") and row(wired, "api")["brief"] == "starter"
    assert env.starter_brief("api") is False                                         # never over an existing brief
    (wired.root / "wikis" / "web" / "INSTRUCTIONS.md").parent.mkdir(parents=True, exist_ok=True)
    (wired.root / "wikis" / "web" / "INSTRUCTIONS.md").write_text("# web\n\n## Coverage\n", encoding="utf-8")
    assert env.starter_brief("web") is False and row(wired, "web")["brief"] == "ai"


def test_each_card_says_what_a_click_will_do(wired, monkeypatch):
    env = wired.env
    monkeypatch.setattr(env, "wiki_engines", lambda: ["claude"])
    r = row(wired, "api")
    assert r["chosen"] is False and r["brief"] is None and r["canGenerate"] is True
    wired.docs.set_wiki_repos(["api"])
    env.starter_brief("api")
    assert row(wired, "api")["canGenerate"] is True and row(wired, "api")["brief"] == "starter"
    monkeypatch.setattr(env, "wiki_engines", lambda: [])
    assert row(wired, "api")["canGenerate"] is False


@pytest.mark.parametrize("comps, installed, fix", [
    (["agents"], True, "off"),
    (["openwiki", "agents"], False, "missing"),
    (["openwiki", "agents"], True, "key"),
])
def test_without_an_engine_the_exact_fix(wired, monkeypatch, comps, installed, fix):
    env = wired.env
    ws = wired.docs.workspace(); ws["project"]["components"] = comps; wired.docs.save_workspace(ws)
    monkeypatch.setattr(env, "openwiki_installed", lambda: installed)
    monkeypatch.setattr(env, "openwiki_credentials", lambda: False)
    monkeypatch.setattr(env, "which", lambda name: None)
    assert env.wiki_engines() == [] and env.wiki_engine_help() == fix
    assert wired.serve.tree()["engineHelp"] == fix
    with pytest.raises(RuntimeError, match=re.escape(env.ENGINE_HELP[fix][:20])):
        env.openwiki_generate("api", log=lambda _: None)


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
