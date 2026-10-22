"""R31: `camaron pr propose <PR url>` — an agent updates the docs a pull request leaves out of date, on its own cam-docs
branch (`docs/pr-<repo>-<n>`), and the kit commits it and opens the docs PR. It runs locally first; a CI job does the
same only on self-hosted runners, for PRs a member labels `docs:update`, never for PRs from forks."""
from __future__ import annotations

import json, subprocess, sys

import pytest
import yaml

API = "src/main/java/demo/Api.java"
ORIGINAL = "package demo;\n\npublic class Api {\n    // calls worker over HTTP\n}\n"

AGENT = r'''
import os, sys
root = os.environ["CAMARONES_ROOT"]
page = os.path.join(root, "docs", "flows", "a.md")
with open(page, "a", encoding="utf-8") as fh:
    fh.write("\nNow it implements Runnable.\n")
open(os.environ["FAKE_LOG"], "a", encoding="utf-8").write(root + "\n")
'''


def git(repo, *args):
    return subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True).stdout


@pytest.fixture
def pr(wired, tmp_path, monkeypatch):
    import importlib
    f = wired.root / "docs" / "flows" / "a.md"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(f"---\ntitle: A\nx-sources:\n  - api:{API}#L3-L5\n---\n# A\n\nThe api calls worker.\n", encoding="utf-8")
    wired.env.checkpoint_commit("page a")
    from lib.harness import freshness
    freshness.stamp_all()
    repo = wired.ws / "api"
    git(repo, "checkout", "-q", "-b", "feature")
    (repo / API).write_text(ORIGINAL.replace("Api {", "Api implements Runnable {"), encoding="utf-8")
    git(repo, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qam", "runnable")
    git(repo, "checkout", "-q", "main")
    script = tmp_path / "agent.py"
    script.write_text(AGENT, encoding="utf-8")
    monkeypatch.setenv("FAKE_LOG", str(tmp_path / "agent.log"))
    from lib.common import PREFS, save_json
    save_json(PREFS, {"runners": {"fake": {"argv": [sys.executable, str(script)]}}, "routing": {"agentic-heavy": ["fake"]}})
    return importlib.import_module("lib.propose")


URL = "https://github.com/acme/api/pull/7"


@pytest.mark.parametrize("url, forge, number, refspec", [
    ("https://github.com/acme/api/pull/7", "github", 7, "pull/7/head"),
    ("https://gitlab.acme.io/team/backend/api/-/merge_requests/3", "gitlab", 3, "merge-requests/3/head"),
])
def test_urls(pr, url, forge, number, refspec):
    info = pr.parse_url(url)
    assert (info["forge"], info["repo"], info["number"], info["refspec"]) == (forge, "api", number, refspec)


def test_an_unknown_url_or_repo_is_refused(pr):
    with pytest.raises(pr.ProposeError):
        pr.parse_url("https://example.com/whatever")
    with pytest.raises(pr.ProposeError, match="not in workspace.yaml"):
        pr.plan_for("https://github.com/acme/billing/pull/1")


def test_the_dry_run_shows_the_branch_the_fetch_and_the_agent(wired, pr):
    p = pr.plan_for(URL, base="main")
    assert p["branch"] == "docs/pr-api-7"
    assert p["fetch"] == ["git", "-C", str(wired.ws / "api"), "fetch", "origin", "pull/7/head:refs/camaron/pr/7"]
    assert p["target"] == "fake" and p["argv"][1].endswith("agent.py")
    assert URL in p["prompt"] and "git -C api diff main...refs/camaron/pr/7" in p["prompt"]
    assert not (wired.ws / ".cw").exists() or not any((wired.ws / ".cw").iterdir())          # nothing created


def test_a_proposal_lands_on_its_own_branch_and_main_is_untouched(wired, pr):
    before = (wired.root / "docs" / "flows" / "a.md").read_text(encoding="utf-8")
    r = pr.propose(URL, ref="feature", base="main", echo=lambda _: None)
    assert r["pages"] == ["flows/a.md"] and r["committed"] and r["branch"] == "docs/pr-api-7"
    assert (wired.root / "docs" / "flows" / "a.md").read_text(encoding="utf-8") == before
    shown = git(wired.root, "show", "docs/pr-api-7:docs/flows/a.md")
    assert "Now it implements Runnable." in shown
    assert git(wired.root, "worktree", "list").count("\n") == 1                               # its worktree is gone
    assert "no remote" in r["pushed"]


def test_nothing_to_do_when_the_pr_touches_no_documented_code(wired, pr):
    repo = wired.ws / "api"
    git(repo, "checkout", "-q", "-b", "readme-only")
    (repo / "notes.txt").write_text("x\n", encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "notes")
    git(repo, "checkout", "-q", "main")
    r = pr.propose(URL, ref="readme-only", base="main", echo=lambda _: None)
    assert r["pages"] == [] and not r["committed"]


# ---------- CI: self-hosted only, labelled, never forks ----------
SELF = {"target": "self-hosted", "runner_labels": ["self-hosted", "docs"], "runner_tags": ["docs-ai"],
        "kit_repo": "https://example.test/kit.git", "kit_ref": "v9.9.9", "uv": "0.12.18"}


@pytest.fixture
def ci(kit):
    import importlib
    return importlib.import_module("lib.ci")


def test_the_propose_job_exists_only_for_self_hosted_runners(ci):
    assert ci.render_propose("github", {**SELF, "target": "local"}) is None
    gh = yaml.safe_load(ci.render_propose("github", SELF))
    job = gh["jobs"]["docs-propose"]
    assert gh[True] == {"pull_request": {"types": ["labeled"]}}
    assert "github.event.label.name == 'docs:update'" in job["if"]
    assert "github.event.pull_request.head.repo.full_name == github.repository" in job["if"]      # no forks
    assert job["runs-on"] == ["self-hosted", "docs"]


def test_the_gitlab_propose_job_rules(ci):
    gl = yaml.safe_load(ci.render_propose("gitlab", SELF))
    rule = gl["docs:propose"]["rules"][0]["if"]
    assert "docs:update" in rule and "$CI_MERGE_REQUEST_SOURCE_PROJECT_ID == $CI_PROJECT_ID" in rule
    assert gl["docs:propose"]["tags"] == ["docs-ai"]


@pytest.mark.parametrize("forge", ["github", "gitlab"])
def test_propose_golden(ci, forge):
    import os
    from pathlib import Path
    golden = Path(__file__).parent / "golden" / "ci" / f"docs-propose.{forge}.self-hosted.yml"
    text = ci.render_propose(forge, SELF)
    if os.environ.get("UPDATE_GOLDEN"):
        golden.write_text(text, encoding="utf-8", newline="\n")
    assert text == golden.read_text(encoding="utf-8")


def test_the_command_dry_run(wired, pr):
    import os
    env = {**os.environ, "CAMARONES_ROOT": str(wired.root)}
    out = subprocess.run([sys.executable, str(wired.kit_dir / "camarones.py"), "pr", "propose", URL, "--base", "main",
                          "--dry-run", "--json"], env=env, capture_output=True, text=True, encoding="utf-8")
    assert out.returncode == 0, out.stderr
    assert json.loads(out.stdout)["branch"] == "docs/pr-api-7"


@pytest.mark.parametrize("forge", ["github", "gitlab"])
def test_the_token_never_lands_in_the_runners_git_config(ci, forge):
    text = ci.render_propose(forge, SELF)
    assert "git config --global" not in text and "GIT_CONFIG_VALUE_0" in text


def test_the_preview_is_the_docs_branch_as_a_static_portal(wired, pr, monkeypatch):
    calls = []

    def fake_run(cmd, cwd=None, check=True, quiet=False, capture=False, env=None):
        import subprocess as sp
        if cmd[-1] == "portal":
            calls.append(cwd)
            site = cwd / ".camarones" / ".cache" / "site"
            site.mkdir(parents=True, exist_ok=True)
            (site / "index.html").write_text("<html>preview</html>", encoding="utf-8")
            return sp.CompletedProcess(cmd, 0, "", "")
        return real(cmd, cwd=cwd, check=check, quiet=quiet, capture=capture, env=env)
    real = pr.run
    monkeypatch.setattr(pr, "run", fake_run)
    r = pr.propose(URL, ref="feature", base="main", echo=lambda _: None, with_preview=True)
    assert calls and (wired.root / ".camarones" / ".cache" / "previews" / "pr-api-7" / "index.html").exists()
    assert r["preview"].endswith("pr-api-7")


def test_the_label_is_configurable(kit, ci):
    ws = kit.docs.workspace()
    ws["ci"] = {"target": "self-hosted", "propose_label": "docs-please"}
    kit.docs.save_workspace(ws)
    gh = yaml.safe_load(ci.render_propose("github"))
    assert "github.event.label.name == 'docs-please'" in gh["jobs"]["docs-propose"]["if"]
    assert "docs-please" in yaml.safe_load(ci.render_propose("gitlab"))["docs:propose"]["rules"][0]["if"]
