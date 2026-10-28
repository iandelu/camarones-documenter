"""What the portal reads: the tree (spaces, sections, C4 views), the wikis (navigation, backlinks) and the static export."""
from __future__ import annotations

import json
import re

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
    d = serve_mod.root / "docs"                         # pages without sources reach agents once confirmed (H27)
    serve_mod.docs.confirm([str(d / "flows/checkout.md"), str(d / "repos/api/brief.md")], by="ana")
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


# ---------- decisions ----------
def test_a_decision_row_carries_the_status_of_its_adr_and_no_other_row_does(serve_mod):
    docs = serve_mod.root / "docs"
    page(docs, "decisions/0001-redis.md", "---\ntitle: 0001 — Redis\ntype: decision\n---\n# 0001 — Redis\n\n## Status\n\nAccepted (2026-10-01)\n")
    page(docs, "decisions/0002-orm.md", "---\ntitle: 0002 — ORM\ntype: decision\n---\n# 0002 — ORM\n\n## Status\n\nProposed\n")
    page(docs, "decisions/0003-jpa.md", "# 0003 — JPA\n\n## Estado\n\nSustituida por [0004](0004-orm.md)\n")
    page(docs, "decisions/0005-odd.md", "---\ntype: decision\n---\n# 0005 — Odd\n\nNo status section.\n")
    page(docs, "decisions/index.md", "# Decisions\n\nThe list.\n")
    r = rows(serve_mod)
    assert [r[f"decisions/{n}.md"].get("adr_status") for n in ("0001-redis", "0002-orm", "0003-jpa", "0005-odd")] \
        == ["accepted", "proposed", "superseded", "unknown"]
    assert "adr_status" not in r["decisions/index.md"] and "adr_status" not in r["flows/checkout.md"]


def test_the_tree_marks_as_decisions_the_pages_the_app_lists(serve_mod):
    docs = serve_mod.root / "docs"
    page(docs, "decisions/old/0006-nested.md", "# 0006 — Nested\n\n## Status\n\nAccepted\n")
    page(docs, "guides/why-redis.md", "---\ntype: decision\n---\n# Why Redis\n\n## Status\n\nProposed\n")
    r = rows(serve_mod)
    assert "adr_status" not in r["decisions/old/0006-nested.md"] and r["guides/why-redis.md"]["adr_status"] == "proposed"


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
    assert (site / "favicon.svg").is_file() and (site / "index.html").is_file()
    assert 'content="static"' in (site / "index.html").read_text(encoding="utf-8")
    assert (site / "theme" / "tokens.css").is_file() and (site / "theme" / "fonts" / "Inter.woff2").is_file()
    viewers = ("wiki-graph", "architecture", "code-graph")          # pages other tools generate (openwiki, likec4…)
    texts = [f.read_text(encoding="utf-8", errors="ignore") for f in site.rglob("*")
             if f.suffix in (".html", ".css", ".js") and f.relative_to(site).parts[0] not in viewers]
    assert not any(re.search(r"fonts\.(googleapis|gstatic)\.com", t) for t in texts)   # the portal asks no font CDN


def test_static_export_carries_the_decisions_that_cover_each_page(serve_mod, monkeypatch):
    env, docs = serve_mod.env, serve_mod.docs
    env.set_components(["agents"])
    monkeypatch.setattr(docs, "vendor_file", lambda *_a: None)
    monkeypatch.setattr(docs, "vendor", lambda _site: (0, []))
    root = serve_mod.root / "docs"
    page(root, "orders.md", "---\ntitle: Orders\nx-sources:\n  - api:src/S.java\n---\n# Orders\n")
    page(root / "i18n" / "es", "orders.md", "---\ntitle: Pedidos\n---\n# Pedidos\n")
    page(root, "decisions/0003-jpa.md", "---\nx-sources:\n  - api:src/S.java\n---\n# 0003 — JPA\n\n## Estado\n\nAceptada\n")
    site = env.export_site(log=lambda _: None)
    read = lambda lang, rel: json.loads((site / "api" / "doc" / lang / f"{rel}.json").read_text(encoding="utf-8"))  # noqa: E731
    covering = [{"id": "0003", "title": "JPA", "path": "decisions/0003-jpa.md", "kind": "retro", "implementation": "n/a"}]
    assert read("_", "orders.md")["decisions"] == covering and read("es", "orders.md")["decisions"] == covering
    assert read("_", "flows/checkout.md")["decisions"] == []
    tree = json.loads((site / "api" / "tree.json").read_text(encoding="utf-8"))
    assert {d["path"]: d.get("adr_status") for d in tree["docs"]}["decisions/0003-jpa.md"] == "accepted"


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


def test_code_maps_are_listed_served_and_exported(serve_mod, monkeypatch):
    import importlib
    from test_codemap import write_graph
    serve_mod.codemap = importlib.import_module("lib.codemap")
    write_graph(serve_mod)
    assert serve_mod.serve.tree()["codeMaps"] == ["api"]
    env, docs = serve_mod.env, serve_mod.docs
    env.set_components(["agents"])
    monkeypatch.setattr(docs, "vendor_file", lambda *_a: None)
    monkeypatch.setattr(docs, "vendor", lambda _site: (0, []))
    site = env.export_site(log=lambda _: None)
    m = json.loads((site / "api" / "codemap" / "api.json").read_text(encoding="utf-8"))
    assert m["stats"]["files"] == 5
