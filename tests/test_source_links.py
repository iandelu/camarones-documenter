"""A page's sources as the portal shows them: where each one opens (the file and line here, the same lines on the
repo's forge), how fresh it is, and for code that changed since the page was written, the commits that touched it
with their pull request and ticket keys."""
from __future__ import annotations

import json
import subprocess

import pytest

API = "src/main/java/demo/Api.java"
ORIGINAL = "package demo;\n\npublic class Api {\n    // calls worker over HTTP\n}\n"


def page(kit, rel, sources):
    f = kit.root / "docs" / rel
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(f"---\ntitle: {rel}\nx-sources:\n" + "".join(f"  - {s}\n" for s in sources) + "---\n# Page\n",
                 encoding="utf-8")
    return f


def git(repo, *args):
    return subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True).stdout


def commit(kit, text, message):
    (kit.ws / "api" / API).write_text(text, encoding="utf-8")
    git(kit.ws / "api", "commit", "-qam", message)


def backdate(kit, logical):
    """The page was written a while ago: commits made in this test land after its stamp."""
    f = kit.root / "docs" / ".work" / "fresh.json"
    data = json.loads(f.read_text(encoding="utf-8"))
    data["pages"][logical]["at"] = "2000-01-01T00:00:00"
    f.write_text(json.dumps(data), encoding="utf-8")


@pytest.fixture
def links(kit):
    ws = kit.docs.workspace()
    for r in ws["repos"]:
        r["url"] = f"git@github.com:acme/{r['name']}.git"
    kit.docs.save_workspace(ws)
    import importlib
    return importlib.import_module("lib.sourcelinks")


@pytest.mark.parametrize("url, base", [
    ("https://github.com/acme/api.git", "https://github.com/acme/api"),
    ("git@github.com:acme/api.git", "https://github.com/acme/api"),
    ("ssh://git@gitlab.acme.io:2222/team/api.git", "https://gitlab.acme.io/team/api"),
    ("https://user:token@gitlab.com/team/api", "https://gitlab.com/team/api"),
    ("", ""),
    ("/srv/git/api", ""),
])
def test_a_clone_url_becomes_the_forge_web_address_without_credentials(links, url, base):
    assert links.web_base(url) == base


def test_the_lines_open_on_each_forge(links):
    assert links.blob_url("https://github.com/a/r", "main", "src/x.ts", (3, 9)) == "https://github.com/a/r/blob/main/src/x.ts#L3-L9"
    assert links.blob_url("https://gitlab.com/a/r", "dev", "src/x.ts", (3, 9)) == "https://gitlab.com/a/r/-/blob/dev/src/x.ts#L3-9"
    assert links.blob_url("https://bitbucket.org/a/r", "main", "x.ts", (3, 9)) == "https://bitbucket.org/a/r/src/main/x.ts#lines-3:9"
    assert links.blob_url("https://github.com/a/r", "main", "README.md") == "https://github.com/a/r/blob/main/README.md"
    assert links.blob_url("", "main", "README.md") == ""


@pytest.mark.parametrize("subject, body, n, url", [
    ("Merge pull request #12 from acme/feat", "", 12, "https://github.com/a/r/pull/12"),
    ("feat(queue): skip played songs (#34)", "", 34, "https://github.com/a/r/pull/34"),
    ("Merge branch 'feat' into 'main'", "Closes ABC-1\n\nSee merge request team/r!56", 56, "https://gitlab.com/team/r/-/merge_requests/56"),
    ("Merged in feat (pull request #7)", "", 7, "https://bitbucket.org/a/r/pull-requests/7"),
])
def test_a_commit_names_its_pull_request(links, subject, body, n, url):
    base = url.split("/pull")[0].split("/-/")[0]
    pr, _ = links.pr_and_tasks(subject, body, base)
    assert pr == {"n": n, "url": url}


def test_a_merge_commit_reads_as_its_pull_request_title(links):
    assert links.headline("Merge pull request #12 from acme/feat", "Skip played songs\n\nmore") == "Skip played songs"
    assert links.headline("Merge branch 'feat' into 'main'", "Skip played songs\n\nSee merge request t/r!5") == "Skip played songs"
    assert links.headline("Merge pull request #12 from acme/feat", "") == "Merge pull request #12 from acme/feat"
    assert links.headline("feat: skip played songs (#34)", "Body line") == "feat: skip played songs (#34)"


def test_a_commit_names_its_tickets_and_none_is_fine(links):
    pr, tasks = links.pr_and_tasks("fix: ENJ-42 queue order", "Refs ENJ-42, OPS-7", "")
    assert pr is None and tasks == ["ENJ-42", "OPS-7"]


def test_a_changed_source_says_which_commits_and_pull_requests_touched_it(kit, links):
    from lib.harness import freshness
    ref = f"api:{API}#L3-L5"
    page(kit, "flows/a.md", [ref, "api:README.md"])
    freshness.stamp_all()
    backdate(kit, "flows/a.md")
    commit(kit, ORIGINAL.replace("Api {", "Api implements Runnable {"), "feat(api): run as a task (#42)\n\nENJ-9")
    info = {e["ref"]: e for e in links.describe("flows/a.md", [ref, "api:README.md"], freshness.status("flows/a.md"))}
    e = info[ref]
    assert e["state"] == "changed" and e["repo"] == "api" and e["path"] == API and e["lines"] == [3, 5]
    assert e["url"] == f"https://github.com/acme/api/blob/main/{API}#L3-L5" and e["line"] == 3
    c, initial = e["commits"]                                   # newest first; the fixture's own commit is older
    assert initial["subject"] == "initial" and initial["pr"] is None
    assert c["subject"] == "feat(api): run as a task (#42)" and c["pr"] == {"n": 42, "url": "https://github.com/acme/api/pull/42"}
    assert c["tasks"] == ["ENJ-9"] and c["author"] == "Test" and len(c["short"]) >= 7
    assert info["api:README.md"]["state"] == "fresh" and info["api:README.md"]["commits"] == []
    assert "file" not in e                                      # an absolute path is only for this machine's portal


def test_a_gone_source_is_missing_and_an_uncommitted_change_says_so(kit, links):
    from lib.harness import freshness
    page(kit, "flows/a.md", [f"api:{API}#L3-L5", "api:README.md"])
    freshness.stamp_all()
    (kit.ws / "api" / "README.md").unlink()
    (kit.ws / "api" / API).write_text(ORIGINAL.replace("Api {", "Api implements Runnable {"), encoding="utf-8")
    info = {e["ref"]: e for e in links.describe("flows/a.md", [f"api:{API}#L3-L5", "api:README.md"], freshness.status("flows/a.md"))}
    assert info["api:README.md"]["state"] == "missing" and info["api:README.md"]["dirty"]
    assert info[f"api:{API}#L3-L5"]["state"] == "changed" and info[f"api:{API}#L3-L5"]["dirty"]


def test_a_symbol_opens_where_it_is_now_and_pages_and_c4_elements_are_described(kit, links):
    from lib.harness import freshness
    (kit.ws / "api" / API).write_text("package demo;\n\n\npublic class Api {\n    void call() {\n    }\n}\n", encoding="utf-8")
    refs = [f"api:{API}#Api.call", "docs/flows/b.md", "c4:enjoy.api"]
    page(kit, "flows/b.md", ["api:README.md"])
    page(kit, "flows/a.md", refs)
    info = {e["ref"]: e for e in links.describe("flows/a.md", refs, freshness.status("flows/a.md"))}
    sym = info[f"api:{API}#Api.call"]
    assert sym["kind"] == "symbol" and sym["symbol"] == "Api.call" and sym["line"] == 5 and sym["lines"] == [5, 6]
    assert sym["url"].endswith(f"{API}#L5-L6")
    assert info["docs/flows/b.md"] == {"ref": "docs/flows/b.md", "kind": "doc", "page": "flows/b.md", "state": "fresh"}
    assert info["c4:enjoy.api"]["kind"] == "c4" and info["c4:enjoy.api"]["name"] == "enjoy.api"


def test_a_repo_that_is_not_here_leaves_links_and_commits_empty(kit, links):
    e, = links.describe("flows/a.md", ["nowhere:src/x.py#L1-L2"], {"state": "stale", "changed": [], "missing": ["nowhere:src/x.py#L1-L2"]})
    assert e["state"] == "missing" and e["url"] == "" and e["commits"] == [] and e["repo"] == "nowhere"


def test_the_portal_page_carries_its_sources_and_only_the_live_one_gets_local_files(kit, links):
    from lib.harness import freshness
    ref = f"api:{API}#L3-L5"
    page(kit, "flows/a.md", [ref])
    freshness.stamp_all()
    import importlib
    serve = importlib.import_module("lib.serve")
    d = serve.read("flows/a.md")
    assert d["sources"] == [ref] and d["sourceInfo"][0]["state"] == "fresh" and "file" not in d["sourceInfo"][0]
    live = serve.api_doc({"path": "flows/a.md"})
    f = live["sourceInfo"][0]["file"]
    assert f.endswith(API) and "\\" not in f and (kit.ws / "api" / API).samefile(f)
