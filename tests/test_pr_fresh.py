"""R27: what a pull request does to the docs, without AI. `camaron pr fresh <repo> --base <ref>` lists the pages whose
cited code the PR changes: left out of date by this PR, or already out of date before it. One comment per PR/MR,
updated in place; it warns and never blocks (H27)."""
from __future__ import annotations

import io, json, os, subprocess, sys
import urllib.error

import pytest

API = "src/main/java/demo/Api.java"
ORIGINAL = "package demo;\n\npublic class Api {\n    // calls worker over HTTP\n}\n"


def git(repo, *args):
    return subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True).stdout


def page(kit, rel, sources):
    f = kit.root / "docs" / rel
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(f"---\ntitle: {rel}\nx-sources:\n" + "".join(f"  - {s}\n" for s in sources) + "---\n# Page\n\nText.\n",
                 encoding="utf-8")


def commit(repo, files, msg):
    for rel, text in files.items():
        (repo / rel).parent.mkdir(parents=True, exist_ok=True)
        (repo / rel).write_text(text, encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", msg)


@pytest.fixture
def pr(kit):
    import importlib
    kit.plan.sync()
    page(kit, "flows/a.md", [f"api:{API}#L3-L5"])
    page(kit, "flows/b.md", ["api:README.md"])
    page(kit, "flows/c.md", ["web:package.json"])
    from lib.harness import freshness
    freshness.stamp_all()
    repo = kit.ws / "api"
    commit(repo, {"README.md": "# api\n\nREST backend, now with gRPC.\n"}, "main moves on")     # b out of date already
    git(repo, "checkout", "-q", "-b", "feature")
    return importlib.import_module("lib.pr")


def test_pages_the_pr_leaves_out_of_date(kit, pr):
    commit(kit.ws / "api", {API: ORIGINAL.replace("Api {", "Api implements Runnable {")}, "change the api")
    r = pr.impact("api", base="main")
    assert r["files"] == [API]
    assert [(p["path"], p["state"], p["since"]) for p in r["pages"]] == [("flows/a.md", "suspect", "pr")]
    assert r["pages"][0]["code"] == [f"api/{API}#L3-L5"]


def test_a_page_already_out_of_date_is_told_apart(kit, pr):
    commit(kit.ws / "api", {"README.md": "# api\n\nREST backend, gRPC and events.\n"}, "readme again")
    r = pr.impact("api", base="main")
    assert [(p["path"], p["since"]) for p in r["pages"]] == [("flows/b.md", "before")]


def test_cosmetic_changes_and_other_repos_are_not_reported(kit, pr):
    commit(kit.ws / "api", {API: ORIGINAL.replace("public class   Api", "public class Api").replace("    //", "  //")},
           "reformat")
    assert pr.impact("api", base="main")["pages"] == []


def test_deleted_code_is_stale(kit, pr):
    git(kit.ws / "api", "rm", "-q", API)
    git(kit.ws / "api", "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "drop api")
    r = pr.impact("api", base="main")
    assert [(p["path"], p["state"]) for p in r["pages"]] == [("flows/a.md", "stale")]


def test_files_can_be_given_instead_of_a_base(kit, pr):
    (kit.ws / "api" / API).write_text(ORIGINAL.replace("Api {", "Api implements Runnable {"), encoding="utf-8")
    r = pr.impact("api", files=[API])
    assert [(p["path"], p["since"]) for p in r["pages"]] == [("flows/a.md", "pr")]


def test_the_comment(kit, pr):
    commit(kit.ws / "api", {API: ORIGINAL.replace("Api {", "Api implements Runnable {"),
                            "README.md": "# api\n\nChanged in the PR too.\n"}, "both")
    body = pr.comment(pr.impact("api", base="main"))
    assert body.startswith(pr.MARKER)
    assert "| `flows/a.md` | suspect | `api/src/main/java/demo/Api.java#L3-L5` |" in body
    assert "Already out of date before this PR" in body and "`flows/b.md`" in body
    assert "camaron fresh --plan" in body and "camaron fresh --ack" in body
    es = pr.comment(pr.impact("api", base="main"), lang="es")
    assert "Ya estaban desactualizadas" in es


def test_the_comment_when_nothing_is_affected(kit, pr):
    body = pr.comment(pr.impact("api", files=["src/other.txt"]))
    assert pr.MARKER in body and "No documented code changed" in body


# ---------- posting: one comment per PR, updated in place ----------
class Forge:
    """Records requests; answers the list call with `existing`."""

    def __init__(self, existing=None, fail=False):
        self.calls, self.existing, self.fail = [], existing or [], fail

    def __call__(self, req, timeout=None):
        if self.fail:
            raise urllib.error.URLError("down")
        self.calls.append((req.get_method(), req.full_url, json.loads(req.data) if req.data else None,
                           dict(req.header_items())))
        return io.BytesIO(json.dumps(self.existing if req.get_method() == "GET" else {}).encode())


GH = {"GITHUB_ACTIONS": "true", "GITHUB_TOKEN": "t0k", "GITHUB_REPOSITORY": "acme/api", "PR_NUMBER": "7",
      "GITHUB_API_URL": "https://api.github.com"}
GL = {"GITLAB_CI": "true", "DOCS_BOT_TOKEN": "t0k", "CI_API_V4_URL": "https://gl.acme/api/v4", "CI_PROJECT_ID": "12",
      "CI_MERGE_REQUEST_IID": "3"}


def test_github_creates_then_updates_the_same_comment(pr):
    f = Forge()
    assert pr.post(f"{pr.MARKER}\nbody", env=GH, opener=f, affected=True) == "created"
    assert f.calls[-1][:2] == ("POST", "https://api.github.com/repos/acme/api/issues/7/comments")
    assert f.calls[-1][3]["Authorization"] == "Bearer t0k"
    f = Forge(existing=[{"id": 1, "body": "unrelated"}, {"id": 99, "body": f"{pr.MARKER}\nold"}])
    assert pr.post(f"{pr.MARKER}\nnew", env=GH, opener=f, affected=True) == "updated"
    assert f.calls[-1][:2] == ("PATCH", "https://api.github.com/repos/acme/api/issues/comments/99")


def test_gitlab_notes(pr):
    f = Forge(existing=[{"id": 5, "body": f"{pr.MARKER}\nold"}])
    assert pr.post(f"{pr.MARKER}\nnew", env=GL, opener=f, affected=True) == "updated"
    assert f.calls[-1][:2] == ("PUT", "https://gl.acme/api/v4/projects/12/merge_requests/3/notes/5")
    assert f.calls[-1][3]["Private-token"] == "t0k"


def test_nothing_to_say_and_no_comment_yet_posts_nothing(pr):
    f = Forge()
    assert pr.post(f"{pr.MARKER}\nnone", env=GH, opener=f, affected=False) == "skipped"
    assert [c[0] for c in f.calls] == ["GET"]


def test_an_earlier_comment_is_updated_when_the_pr_no_longer_affects_docs(pr):
    f = Forge(existing=[{"id": 99, "body": f"{pr.MARKER}\nold"}])
    assert pr.post(f"{pr.MARKER}\nnone", env=GH, opener=f, affected=False) == "updated"


def test_posting_problems_never_fail(pr):
    assert pr.post("x", env=GH, opener=Forge(fail=True), affected=True).startswith("failed")
    assert pr.post("x", env={}, opener=Forge(), affected=True).startswith("not in a PR")


def test_the_pr_number_comes_from_the_github_event(pr, tmp_path):
    ev = tmp_path / "event.json"
    ev.write_text(json.dumps({"pull_request": {"number": 42}}), encoding="utf-8")
    env = {**GH, "GITHUB_EVENT_PATH": str(ev)}
    env.pop("PR_NUMBER")
    f = Forge()
    pr.post(f"{pr.MARKER}\nx", env=env, opener=f, affected=True)
    assert "/issues/42/comments" in f.calls[-1][1]


def test_the_command(kit, pr):
    commit(kit.ws / "api", {API: ORIGINAL.replace("Api {", "Api implements Runnable {")}, "change")
    env = {k: v for k, v in os.environ.items() if k not in ("GITHUB_ACTIONS", "GITLAB_CI")}
    env["CAMARONES_ROOT"] = str(kit.root)
    run = lambda *a: subprocess.run([sys.executable, str(kit.kit_dir / "camarones.py"), "pr", "fresh", *a],  # noqa: E731
                                    env=env, capture_output=True, text=True, encoding="utf-8")
    out = json.loads(run("api", "--base", "main", "--json").stdout)
    assert out["pages"][0]["path"] == "flows/a.md"
    r = run("api", "--base", "main", "--post")
    assert r.returncode == 0 and "flows/a.md" in r.stdout and "not in a PR" in r.stdout
    assert run("nope", "--base", "main").returncode == 2


def test_generated_pages_point_to_blocks(kit, pr):
    f = kit.root / "docs" / "flows" / "a.md"
    f.write_text(f.read_text(encoding="utf-8").replace("---\n# Page", "x-generated: true\n---\n# Page"), encoding="utf-8")
    from lib.harness import freshness
    freshness.stamp_all()
    commit(kit.ws / "api", {API: ORIGINAL.replace("Api {", "Api implements Runnable {")}, "change")
    body = pr.comment(pr.impact("api", base="main"))
    assert "| `flows/a.md` ⚙ |" in body and "camaron blocks" in body
