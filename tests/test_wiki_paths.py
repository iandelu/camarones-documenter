"""A repo's OpenWiki page (cam-docs/wikis/<repo>/<page>) has the logical path wikis/<repo>/<page>, so it can never
collide with a docs page (docs/repos/<repo>/index.md vs OpenWiki's own index.md). Kits up to 4.80.1 called it
repos/<repo>/<page>: that path still finds the wiki page wherever no docs page has it (links, read_doc, freshness
stamps, translations). A wiki page links a docs page the way its file sits on disk, `../../docs/<page>`; the
`../../<page>` form older wikis used to get past `check` keeps working."""
from __future__ import annotations

import json


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def page(title, body=""):
    return f"---\ntitle: {title}\nx-sources:\n  - api:pom.xml\n---\n# {title}\n\n{body}\n"


def setup_wiki(kit):
    root = kit.root
    write(root / "docs" / "repos" / "api" / "index.md", page("api", "The repo page."))
    write(root / "docs" / "flows" / "orders.md", page("Orders"))
    write(root / "wikis" / "api" / "index.md", page("api wiki", "OpenWiki's index."))
    write(root / "wikis" / "api" / "quickstart.md", page("Quickstart"))
    return root


def rows_by_file(kit):
    return {r["file"]: r for r in kit.docs.collect()}


def test_a_wiki_index_and_the_repo_page_have_different_paths(kit):
    setup_wiki(kit)
    rows = kit.docs.collect()
    paths = [r["path"] for r in rows]
    assert len(paths) == len(set(paths))
    by_file = {r["file"]: r for r in rows}
    assert by_file["docs/repos/api/index.md"]["path"] == "repos/api/index.md"
    assert by_file["docs/repos/api/index.md"]["space"] == "docs"
    assert by_file["wikis/api/index.md"]["path"] == "wikis/api/index.md"
    assert by_file["wikis/api/index.md"]["space"] == "wiki"


def broken(kit):
    errors, _ = kit.quality.check_links(kit.docs.collect())
    return [e for e in errors if "broken link" in e]


def test_a_wiki_links_docs_pages_as_its_file_sits_on_disk(kit):
    root = setup_wiki(kit)
    write(root / "wikis" / "api" / "flows.md", page("Flows", "[orders](../../docs/flows/orders.md#orders) · "
                                                    "[repo page](../../docs/repos/api/index.md) · [qs](quickstart.md)"))
    write(root / "wikis" / "api" / "deep" / "page.md", page("Deep", "[orders](../../../docs/flows/orders.md) · "
                                                            "[up](../index.md)"))
    write(root / "wikis" / "api" / "gone.md", page("Gone", "[missing](../../docs/flows/missing.md)"))
    errs = broken(kit)
    assert [e for e in errs if "flows.md" in e or "deep/page.md" in e] == []
    assert any("wikis/api/gone.md" in e and "missing.md" in e for e in errs)


def test_links_written_for_the_old_wiki_paths_keep_resolving(kit):
    """`../../<page>` from a wiki page (the workaround), and a docs page linking the wiki by its old path."""
    root = setup_wiki(kit)
    write(root / "wikis" / "api" / "old.md", page("Old", "[orders](../../flows/orders.md) · [qs](../../repos/api/quickstart.md)"))
    write(root / "docs" / "guides" / "api.md", page("Guide", "[the wiki's quickstart](../repos/api/quickstart.md) · "
                                                    "[on disk](../../wikis/api/quickstart.md)"))
    assert broken(kit) == []


def test_link_target_maps_a_resolved_link_to_a_page(kit):
    known = {"repos/api/index.md", "flows/orders.md", "wikis/api/index.md", "wikis/api/quickstart.md"}
    t = kit.docs.link_target
    assert t("docs/flows/orders.md", known) == "flows/orders.md"
    assert t("flows/orders.md", known) == "flows/orders.md"
    assert t("repos/api/quickstart.md", known) == "wikis/api/quickstart.md"   # old wiki path, no docs page there
    assert t("repos/api/index.md", known) == "repos/api/index.md"             # a docs page keeps its path
    assert t("wikis/api/index.md", known) == "wikis/api/index.md"
    assert t("flows/nope.md", known) == "flows/nope.md"                       # unknown stays as written


def test_a_page_is_found_by_its_old_wiki_path(kit):
    setup_wiki(kit)
    find = kit.docs.find_page
    assert find("repos/api/quickstart.md").as_posix().endswith("wikis/api/quickstart.md")
    assert find("wikis/api/quickstart.md").as_posix().endswith("wikis/api/quickstart.md")
    assert find("docs/repos/api/index.md").as_posix().endswith("docs/repos/api/index.md")
    assert find("repos/api/index.md").as_posix().endswith("docs/repos/api/index.md")
    assert find("repos/api/nope.md") is None


def test_the_mcp_reads_a_wiki_page_by_its_old_path(kit):
    setup_wiki(kit)
    import importlib
    mcp = importlib.import_module("lib.mcp")
    assert "Quickstart" in mcp.read_doc("repos/api/quickstart.md")
    assert "OpenWiki's index" in mcp.read_doc("wikis/api/index.md")
    assert "The repo page" in mcp.read_doc("repos/api/index.md")


def test_freshness_stamps_under_the_old_wiki_path_carry_over(kit):
    root = setup_wiki(kit)
    text = "---\ntitle: Quickstart\nx-sources:\n  - api:pom.xml\n---\n# Quickstart\n\nRun it.\n"
    write(root / "wikis" / "api" / "quickstart.md", text)
    from lib.harness import freshness
    work = freshness.FILE
    work.parent.mkdir(parents=True, exist_ok=True)
    sha = kit.docs.body_sha(kit.docs.split_fm(text)[1])                     # unchanged since its stamp
    old = {"body_sha": sha, "at": "2026-01-01T00:00:00Z", "sources": {"api:pom.xml": freshness.fingerprint("api:pom.xml")},
           "flag": {"reason": "wrong port", "by": "agent", "at": "2026-01-02T00:00:00Z"}}
    work.write_text(json.dumps({"v": 1, "pages": {"repos/api/quickstart.md": old}}), encoding="utf-8")
    freshness.stamp_all()
    pages = json.loads(work.read_text(encoding="utf-8"))["pages"]
    assert "repos/api/quickstart.md" not in pages
    assert pages["wikis/api/quickstart.md"]["flag"]["reason"] == "wrong port"
    assert freshness.states()["wikis/api/quickstart.md"]["state"] == "suspect"


def test_a_wiki_translation_at_its_old_path_is_still_read(kit):
    root = setup_wiki(kit)
    tr = "---\ntitle: Inicio rápido\nx-translation-of: wikis/api/quickstart.md\n---\n# Inicio rápido\n"
    write(root / "docs" / "i18n" / "es" / "repos" / "api" / "quickstart.md", tr)
    write(root / "docs" / "i18n" / "es" / "repos" / "api" / "index.md", tr.replace("Inicio rápido", "api (es)"))
    by_file = rows_by_file(kit)
    assert by_file["wikis/api/quickstart.md"]["i18n"]["es"] == "outdated"      # found, not "missing"
    assert by_file["wikis/api/index.md"]["i18n"]["es"] == "missing"            # that one is the repo page's
    assert by_file["docs/repos/api/index.md"]["i18n"]["es"] == "outdated"
    tf = kit.docs.translation_file("wikis/api/quickstart.md", "es")
    assert tf.as_posix().endswith("docs/i18n/es/repos/api/quickstart.md")
    assert kit.docs.translation_file("wikis/api/index.md", "es").as_posix().endswith("docs/i18n/es/wikis/api/index.md")


def test_an_ai_draft_copy_under_the_old_wiki_path_is_kept(kit):
    """harness/drafts keeps the AI's copy of each page to measure how much a person edits it before confirming."""
    root = setup_wiki(kit)
    from lib.harness import drafts
    drafts.FILE.parent.mkdir(parents=True, exist_ok=True)
    ai = "# Quickstart\n\nThe AI's words.\n"
    text = (root / "wikis" / "api" / "quickstart.md").read_text(encoding="utf-8")
    now = kit.docs.body_sha(kit.docs.split_fm(text)[1])                      # the page has not changed since
    drafts.FILE.write_text(json.dumps({"pages": {"repos/api/quickstart.md": {
        "sha": now, "body": ai, "unit": "repo-wiki:api", "at": "2026-01-01T00:00:00Z", "confirmations": []}}}),
        encoding="utf-8")
    drafts.snapshot("later")
    pages = json.loads(drafts.FILE.read_text(encoding="utf-8"))["pages"]
    assert "repos/api/quickstart.md" not in pages and pages["wikis/api/quickstart.md"]["body"] == ai
    assert drafts.record_confirmation("wikis/api/quickstart.md", ai, "ana") == 0.0
