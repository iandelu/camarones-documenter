"""What the portal reads: the tree (spaces, sections, C4 views), the wikis (navigation, backlinks) and the static export."""
from __future__ import annotations

import json

import pytest


def page(root, rel, text):
    f = root / rel
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(text, encoding="utf-8", newline="\n")
    return f


@pytest.fixture
def portal(kit, monkeypatch):
    docs = kit.root / "docs"
    page(docs, "index.md", "---\ntitle: Home\n---\n# Home\n")
    page(docs, "flows/checkout.md", "---\ntitle: Checkout\ntype: flow\n---\n# Checkout\n")
    page(docs, "repos/api/brief.md", "---\ntitle: api brief\n---\n# api brief\n")
    page(docs, "interview/discovery/api.md", "---\ntitle: Discovery api\ntype: interview\n---\n# Discovery\n")
    page(docs, "interview/open-questions.md", "# Open questions\n")
    wiki = kit.root / "wikis" / "api"
    page(wiki, "INSTRUCTIONS.md", "# brief for OpenWiki\n")
    page(wiki, "log.md", "# log\n")
    page(wiki, "index.md", '---\nokf_version: "0.2"\n---\n\n# Files\n\n- [Quickstart](quickstart.md)\n'
                           "- [HTTP API](http-api.md)\n")
    page(wiki, "http-api.md", "# HTTP resources\n\nStart with the [quickstart](./quickstart.md#run).\n")
    page(wiki, "quickstart.md", "# api quickstart\n\nSee [HTTP](http-api.md) and [caches](caches.md).\n")
    page(wiki, "caches.md", "# Caches\n\nNothing links back: [missing](nope.md).\n")
    monkeypatch.setattr(kit.env, "repo_changed_at", lambda _repo: 0.0)
    return kit


def rows(kit):
    return {r["path"]: r for r in kit.serve.tree()["docs"]}


@pytest.fixture
def serve_mod(portal):
    import importlib
    portal.serve = importlib.import_module("lib.serve")
    return portal


# ---------- characterization: what the tree already gives the portal ----------
def test_tree_lists_docs_and_wiki_pages_under_their_logical_paths(serve_mod):
    t = serve_mod.serve.tree()
    paths = [d["path"] for d in t["docs"]]
    assert {"index.md", "flows/checkout.md", "repos/api/brief.md", "repos/api/quickstart.md"} <= set(paths)
    assert "repos/api/INSTRUCTIONS.md" not in paths and "repos/api/log.md" not in paths
    assert t["project"] == "demo" and t["repos"] == ["api", "web", "worker"]


# ---------- spaces ----------
def test_pages_are_classified_into_docs_notes_and_wiki(serve_mod):
    r = rows(serve_mod)
    assert r["index.md"]["space"] == "docs"
    assert r["flows/checkout.md"]["space"] == "docs"
    assert r["repos/api/brief.md"]["space"] == "docs"          # shares the repos/api/ prefix with the wiki
    assert r["repos/api/quickstart.md"]["space"] == "wiki"
    assert r["interview/discovery/api.md"]["space"] == "notes"
    assert r["interview/open-questions.md"]["space"] == "notes"  # no frontmatter type, the folder decides


def test_sections_order_matches_llms(serve_mod):
    t = serve_mod.serve.tree()
    assert t["sections"] == serve_mod.docs.SECTIONS
    serve_mod.docs.llms()
    text = (serve_mod.root / "docs" / "llms.txt").read_text(encoding="utf-8")
    assert text.index("## flows") < text.index("## repos/api")


# ---------- C4 views ----------
VIEWS_C4 = """views {
  view index {
    title 'System context'
    include *
  }
  view containers of shop {
    include shop.*
  }
  dynamic view flow_checkout {
    title "Checkout"
    web -> api
  }
  deployment view deploy_prod {
    title 'Production'
  }
}
"""


def test_c4_views_are_read_from_the_model_without_likec4(serve_mod):
    arch = serve_mod.root / "docs" / "architecture"
    page(arch, "views.c4", VIEWS_C4)
    page(arch, "repos/api.c4", "views {\n  view api_components of shop.api {\n  }\n}\n")
    views = {v["id"]: v for v in serve_mod.env.c4_views()}
    assert views["index"] == {"id": "index", "title": "System context", "kind": "element", "file": "views.c4"}
    assert views["containers"]["title"] == "containers"
    assert views["flow_checkout"]["kind"] == "dynamic" and views["flow_checkout"]["title"] == "Checkout"
    assert views["deploy_prod"]["kind"] == "deployment"
    assert views["api_components"]["file"] == "repos/api.c4"
    assert [v["id"] for v in serve_mod.serve.tree()["views"]][:4] == ["index", "containers", "flow_checkout", "deploy_prod"]


def test_no_model_means_no_views(serve_mod):
    assert serve_mod.env.c4_views() == []
    assert serve_mod.serve.tree()["views"] == []


# ---------- wikis ----------
def test_wiki_nav_follows_the_index_then_the_rest(serve_mod):
    nav = serve_mod.env.wiki_nav("api")
    assert [p["path"] for p in nav["pages"]] == ["repos/api/index.md", "repos/api/quickstart.md",
                                                 "repos/api/http-api.md", "repos/api/caches.md"]
    assert nav["pages"][1]["title"] == "api quickstart"
    assert nav["home"] == "repos/api/quickstart.md"


def test_wiki_backlinks_resolve_relative_links_inside_the_wiki(serve_mod):
    back = serve_mod.env.wiki_nav("api")["backlinks"]
    assert back["repos/api/quickstart.md"] == ["repos/api/http-api.md", "repos/api/index.md"]
    assert back["repos/api/caches.md"] == ["repos/api/quickstart.md"]
    assert "repos/api/nope.md" not in back


def test_wikis_rows_carry_the_navigation(serve_mod):
    rows_ = {w["repo"]: w for w in serve_mod.env.wikis()}
    assert rows_["api"]["pages"] == 4
    assert rows_["api"]["nav"]["home"] == "repos/api/quickstart.md"
    assert rows_["web"]["nav"] == {"home": None, "pages": [], "backlinks": {}}


# ---------- older workspaces ----------
def test_a_bare_workspace_still_builds_the_tree(kit):
    import importlib
    serve = importlib.import_module("lib.serve")
    t = serve.tree()
    assert t["docs"] == [] and t["views"] == [] and t["sections"]
    assert all(w["nav"]["pages"] == [] for w in kit.env.wikis())


# ---------- static export ----------
def test_static_export_carries_the_new_fields(serve_mod, monkeypatch):
    env, docs = serve_mod.env, serve_mod.docs
    env.set_components(["agents"])
    monkeypatch.setattr(docs, "vendor_file", lambda *_a: None)
    monkeypatch.setattr(docs, "vendor", lambda _site: (0, []))
    page(serve_mod.root / "docs" / "architecture", "views.c4", VIEWS_C4)
    site = env.export_site(log=lambda _: None)
    tree = json.loads((site / "api" / "tree.json").read_text(encoding="utf-8"))
    assert {d["path"]: d["space"] for d in tree["docs"]}["repos/api/http-api.md"] == "wiki"
    assert "flow_checkout" in [v["id"] for v in tree["views"]]
    wikis = json.loads((site / "api" / "wikis.json").read_text(encoding="utf-8"))
    assert next(w for w in wikis if w["repo"] == "api")["nav"]["pages"]
    assert (site / "doc.js").is_file() and (site / "index.html").is_file()


def test_wiki_graph_export_does_not_pass_flags_openwiki_rejects(serve_mod, monkeypatch):
    calls = []

    def fake_run(cmd, cwd=None, **_kw):
        calls.append(cmd)
        dest = cmd[cmd.index("--export") + 1]
        (serve_mod.env.Path(dest)).mkdir(parents=True, exist_ok=True)
        (serve_mod.env.Path(dest) / "index.html").write_text("ok", encoding="utf-8")
    monkeypatch.setattr(serve_mod.env, "run", fake_run)
    assert serve_mod.env.wiki_graph("api", log=lambda _: None)
    assert "--no-open" not in calls[0] and "--port" not in calls[0]   # openwiki: "--export cannot be combined with --port or --no-open"


def test_a_wiki_graph_older_than_its_pages_is_stale(serve_mod):
    import os
    graph = serve_mod.env.VIEWERS / "wiki-graph" / "api" / "index.html"
    graph.parent.mkdir(parents=True, exist_ok=True)
    graph.write_text("old", encoding="utf-8")
    os.utime(graph, (1_000_000, 1_000_000))
    rows = {w["repo"]: w for w in serve_mod.env.wikis()}
    assert rows["api"]["graph"] and rows["api"]["graphStale"]
    assert not rows["web"]["graph"] and not rows["web"]["graphStale"]
    os.utime(graph, None)
    assert not {w["repo"]: w for w in serve_mod.env.wikis()}["api"]["graphStale"]
