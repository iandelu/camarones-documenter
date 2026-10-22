"""Freshness (R23, H14 L1 + H27): each page's x-sources are hashed when it is written; a page whose cited code changed
is suspect, one whose code is gone is stale. Agents never get suspect or stale pages (nor unreviewed pages without
sources): the MCP and llms.txt withhold them and point to the code. People still see them, with a banner."""
from __future__ import annotations

import json, os, subprocess, sys

import pytest

API = "src/main/java/demo/Api.java"          # 5 lines in the fixture repo


def page(kit, rel, sources=None, confirmed=False, body="# Page\n\nThe api calls worker over HTTP.\n"):
    f = kit.root / "docs" / rel
    f.parent.mkdir(parents=True, exist_ok=True)
    fm = f"---\ntitle: {rel}\n"
    if sources:
        fm += "x-sources:\n" + "".join(f"  - {s}\n" for s in sources)
    f.write_text(fm + "---\n" + body, encoding="utf-8")
    if confirmed:
        kit.docs.confirm([str(f)], by="ana")
    return f


def code(kit, text):
    (kit.ws / "api" / API).write_text(text, encoding="utf-8")


@pytest.fixture
def fresh(kit):
    from lib.harness import freshness
    kit.plan.sync()
    return freshness


ORIGINAL = "package demo;\n\npublic class Api {\n    // calls worker over HTTP\n}\n"


def test_a_page_is_fresh_until_its_cited_code_changes(kit, fresh):
    page(kit, "flows/a.md", [f"api:{API}#L3-L5"])
    fresh.stamp_all()
    assert fresh.status("flows/a.md")["state"] == "fresh"
    code(kit, ORIGINAL.replace("public class Api {", "public class Api implements Runnable {"))
    s = fresh.status("flows/a.md")
    assert s["state"] == "suspect" and s["changed"] == [f"api:{API}#L3-L5"]


def test_whitespace_comments_and_moved_code_do_not_count(kit, fresh):
    page(kit, "flows/a.md", [f"api:{API}#L3-L5"])
    fresh.stamp_all()
    code(kit, "package demo;\n\n\n// a new comment\n\npublic class   Api {\n        // calls worker over HTTP, reworded\n}\n")
    assert fresh.status("flows/a.md")["state"] == "fresh"                      # moved down, reformatted, comments


def test_a_missing_file_or_range_is_stale(kit, fresh):
    page(kit, "flows/a.md", [f"api:{API}#L3-L5"])
    page(kit, "flows/b.md", ["api:README.md"])
    fresh.stamp_all()
    (kit.ws / "api" / "README.md").unlink()
    code(kit, "package demo;\n")
    assert fresh.status("flows/b.md")["state"] == "stale" and fresh.status("flows/a.md")["state"] == "stale"


def test_rewriting_the_page_or_ack_takes_the_new_code_as_reference(kit, fresh):
    f = page(kit, "flows/a.md", [f"api:{API}#L3-L5"])
    fresh.stamp_all()
    code(kit, ORIGINAL.replace("Api {", "Api implements Runnable {"))
    assert fresh.status("flows/a.md")["state"] == "suspect"
    fresh.ack(["flows/a.md"], by="luis")
    assert fresh.status("flows/a.md")["state"] == "fresh"
    code(kit, ORIGINAL.replace("Api {", "Api implements Closeable {"))
    f.write_text(f.read_text(encoding="utf-8") + "\nNow it is closeable.\n", encoding="utf-8")
    fresh.stamp_all()                                          # the page was rewritten: it reflects the current code
    assert fresh.status("flows/a.md")["state"] == "fresh"


def test_plan_done_stamps_the_pages_written(kit, fresh):
    page(kit, "flows/a.md", [f"api:{API}#L3-L5"])
    kit.plan.set_status("discovery:api", "done")
    assert "flows/a.md" in json.loads(fresh.FILE.read_text(encoding="utf-8"))["pages"]


def test_an_upgraded_project_gets_its_baseline_on_first_look(kit, fresh):
    page(kit, "flows/a.md", [f"api:{API}#L3-L5"])
    assert not fresh.FILE.exists()
    assert fresh.status("flows/a.md")["state"] == "fresh" and fresh.FILE.exists()


def test_pages_without_sources_are_unverified(kit, fresh):
    page(kit, "overview/notes.md")
    assert fresh.status("overview/notes.md")["state"] == "unverified"


# ---------- the AI gate ----------
@pytest.fixture
def mcp(kit, fresh):
    import importlib
    return importlib.import_module("lib.mcp")


def test_agents_do_not_get_a_suspect_page_and_are_sent_to_the_code(kit, fresh, mcp):
    page(kit, "flows/a.md", [f"api:{API}#L3-L5"], body="# A\n\nThe api calls worker over HTTP.\n")
    fresh.stamp_all()
    code(kit, ORIGINAL.replace("Api {", "Api implements Runnable {"))
    text = mcp.read_doc("flows/a.md")
    assert "calls worker over HTTP" not in text and "withheld" in text and f"api/{API}" in text
    hits = mcp.search_docs("worker")
    assert "flows/a.md" not in hits.split("withheld")[0] and "1 page withheld" in hits


def test_unreviewed_pages_without_sources_are_withheld_confirmed_ones_served(kit, fresh, mcp):
    page(kit, "overview/draft.md", body="# Draft\n\nGuessing things.\n")
    page(kit, "overview/reviewed.md", confirmed=True, body="# Reviewed\n\nA person checked this.\n")
    assert "Guessing" not in mcp.read_doc("overview/draft.md") and "awaits review" in mcp.read_doc("overview/draft.md")
    assert "A person checked this" in mcp.read_doc("overview/reviewed.md")


def test_fresh_pages_are_served_as_before(kit, fresh, mcp):
    page(kit, "flows/a.md", [f"api:{API}#L3-L5"], body="# A\n\nThe api calls worker over HTTP.\n")
    fresh.stamp_all()
    assert "calls worker over HTTP" in mcp.read_doc("flows/a.md")
    assert "flows/a.md" in mcp.search_docs("worker")


def test_the_warn_policy_serves_with_a_notice(kit, fresh, mcp):
    ws = kit.docs.workspace()
    ws["freshness"] = {"ai_policy": "warn"}
    kit.docs.save_workspace(ws)
    page(kit, "flows/a.md", [f"api:{API}#L3-L5"], body="# A\n\nThe api calls worker over HTTP.\n")
    fresh.stamp_all()
    code(kit, ORIGINAL.replace("Api {", "Api implements Runnable {"))
    text = mcp.read_doc("flows/a.md")
    assert "calls worker over HTTP" in text and "may be out of date" in text


def test_llms_txt_lists_withheld_pages_apart(kit, fresh):
    page(kit, "flows/a.md", [f"api:{API}#L3-L5"])
    page(kit, "flows/b.md", ["api:README.md"])
    fresh.stamp_all()
    code(kit, ORIGINAL.replace("Api {", "Api implements Runnable {"))
    kit.docs.llms()
    text = (kit.root / "docs" / "llms.txt").read_text(encoding="utf-8")
    head, _, tail = text.partition("## Out of date")
    assert "flows/b.md" in head and "flows/a.md" not in head and "flows/a.md" in tail


def test_people_see_the_state_in_the_portal_rows(kit, fresh):
    page(kit, "flows/a.md", [f"api:{API}#L3-L5"])
    fresh.stamp_all()
    code(kit, ORIGINAL.replace("Api {", "Api implements Runnable {"))
    row = next(r for r in kit.docs.collect() if r["path"] == "flows/a.md")
    assert row["fresh"] == "suspect"


def test_check_warns_about_out_of_date_pages(kit, fresh):
    page(kit, "flows/a.md", [f"api:{API}#L3-L5"])
    fresh.stamp_all()
    code(kit, ORIGINAL.replace("Api {", "Api implements Runnable {"))
    _, warns = kit.docs.check()
    assert any("flows/a.md" in w and "changed since" in w for w in warns)


def test_fresh_plan_adds_a_unit_to_refresh_out_of_date_pages(kit, fresh):
    page(kit, "flows/a.md", [f"api:{API}#L3-L5"])
    fresh.stamp_all()
    code(kit, ORIGINAL.replace("Api {", "Api implements Runnable {"))
    u = fresh.refresh_unit()
    assert u["id"] == "refresh-docs" and "flows/a.md" in u["notes"]
    assert "## refresh-docs" in (kit.kit_dir / "PLAYBOOK.md").read_text(encoding="utf-8")


def test_the_fresh_command(kit, fresh):
    page(kit, "flows/a.md", [f"api:{API}#L3-L5"])
    fresh.stamp_all()
    code(kit, ORIGINAL.replace("Api {", "Api implements Runnable {"))
    env = {**os.environ, "CAMARONES_ROOT": str(kit.root)}
    cli = lambda *a: subprocess.run([sys.executable, str(kit.kit_dir / "camarones.py"), "fresh", *a], env=env,  # noqa: E731
                                    capture_output=True, text=True, encoding="utf-8")
    rows = json.loads(cli("--json").stdout)
    assert next(r for r in rows if r["path"] == "flows/a.md")["state"] == "suspect"
    assert "suspect" in cli().stdout
    assert cli("--ack", "flows/a.md", "--by", "luis").returncode == 0
    assert next(r for r in json.loads(cli("--json").stdout) if r["path"] == "flows/a.md")["state"] == "fresh"


def test_the_portal_page_says_its_code_changed(kit, fresh):
    page(kit, "flows/a.md", [f"api:{API}#L3-L5"])
    fresh.stamp_all()
    code(kit, ORIGINAL.replace("Api {", "Api implements Runnable {"))
    import importlib
    serve = importlib.import_module("lib.serve")
    d = serve.read("flows/a.md")
    assert d["fresh"] == "suspect" and d["freshness"]["changed"] == [f"api:{API}#L3-L5"]
    core = (kit.kit_dir / "portal" / "app" / "public" / "legacy" / "core.js").read_text(encoding="utf-8")
    assert core.count("'banner.suspect'") == 2 and core.count("'banner.stale'") == 2          # en + es
