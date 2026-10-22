"""AI proposal for a pull request (R31, H15/H23). `camaron pr propose <PR url>`: the PR's code is fetched into a ref of
the service repo (the checkout is never touched), the pages it leaves out of date are listed without AI (lib/pr.py), and
an agent updates them in a cam-docs worktree on branch `docs/pr-<repo>-<n>`. The kit commits, pushes and opens the
docs PR/MR, and can comment its link on the service PR. It runs on this machine first; the generated `docs-propose` CI
job runs the same command on a self-hosted runner, for PRs a member labels, never for forks."""
from __future__ import annotations

import json, os, re, urllib.error, urllib.parse, urllib.request
from pathlib import Path

from .common import CTX, KIT, ROOT, WORKSPACE, out, repo_dir, run, uv, which
from . import docs

MARKER = "<!-- camaron:docs-propose -->"
GH = re.compile(r"https?://(?P<host>[^/]+)/(?P<slug>[^/]+/(?P<repo>[^/]+))/pull/(?P<n>\d+)")
GL = re.compile(r"https?://(?P<host>[^/]+)/(?P<slug>.+/(?P<repo>[^/]+))/-/merge_requests/(?P<n>\d+)")


class ProposeError(RuntimeError):
    """The proposal cannot start; nothing was changed."""


def parse_url(url: str) -> dict:
    for forge, pat, spec in (("github", GH, "pull/{n}/head"), ("gitlab", GL, "merge-requests/{n}/head")):
        m = pat.match(url.strip())
        if m:
            n = int(m["n"])
            return {"forge": forge, "host": m["host"], "slug": m["slug"], "repo": m["repo"], "number": n,
                    "refspec": spec.format(n=n), "url": url.strip()}
    raise ProposeError(f"not a GitHub pull request or GitLab merge request URL: {url}")


def _default_base(repo: str) -> str:
    head = out(["git", "-C", str(repo_dir(repo)), "symbolic-ref", "--short", "refs/remotes/origin/HEAD"])
    return head or "origin/main"


def _cli_in_tree() -> str:
    return f'"{uv()}" run --quiet --script "{KIT / "camarones.py"}"'


def prompt(info: dict, repo: str, ref: str, base: str, branch: str, tree: Path, pages: list[dict]) -> str:
    cli = _cli_in_tree()
    rel = os.path.relpath(tree, WORKSPACE).replace("\\", "/")
    listed = "\n".join(f"- `docs/{p['path']}` ({p['state']}; code: {', '.join(p['code'])})" for p in pages) or \
        f"- (run `{cli} pr fresh {repo} --base {base} --head {ref}` to list them)"
    return f"""Camarón PR proposal — {info['url']} changes `{repo}`.
You work in the workspace folder. Your copy of the docs is `{rel}/` (cam-docs on branch `{branch}`); every `docs/…`
path below is relative to it. The service repo is `{repo}/`: never modify it, never check anything out there.
The PR's code is at `{ref}`: see what changed with `git -C {repo} diff {base}...{ref}`, read a file as the PR leaves it
with `git -C {repo} show {ref}:<path>`.

Pages whose cited code this PR changes:
{listed}

1. Update only those pages (and their `docs/i18n/es/` translations, then `{cli} translated <files>`) so they describe
   the code at `{ref}`. Keep `x-sources` on the same code (prefer symbols: `repo:path#Class.method`). Follow
   `{rel}/.camarones/CONVENTIONS.md`. A confirmed page you change needs re-confirmation by a person: say so below.
2. Run `{cli} check` and fix what it reports on these pages.
3. Write two to five lines for the docs PR description to `{rel}/.camarones/.cache/pr-proposal.md`: what changed and
   which pages need a person's review.
Do not commit or push: the kit does it when you finish. Never write `x-confirmed`.
"""


def plan_for(url: str, ref: str | None = None, base: str | None = None, runner: str | None = None,
             lang: str = "en") -> dict:
    """Everything the proposal would do, without doing any of it (`--dry-run`)."""
    from . import plan as plan_mod
    from .adapters import runners
    from .harness.ports import RunRequest
    info = parse_url(url)
    repo = os.environ.get("DOCS_REPO_NAME") or info["repo"]
    if repo not in docs.repo_names():
        raise ProposeError(f"repo '{repo}' is not in workspace.yaml (set DOCS_REPO_NAME if it has another name)")
    local_ref = ref or f"refs/camaron/pr/{info['number']}"
    base = base or _default_base(repo)
    branch = f"docs/pr-{repo}-{info['number']}"
    tree = WORKSPACE / ".cw" / f"pr-{repo}-{info['number']}"
    targets = [runner] if runner else plan_mod._agents(lambda _: None)
    if not targets:
        raise ProposeError("no agent installed for documentation work (claude, codex or opencode)")
    r, model = plan_mod._runner(targets[0])
    text = prompt(info, repo, local_ref, base, branch, tree, [])
    short = "Follow the instructions in " + plan_mod._at(CTX.cache / "prompts" / f"pr-{repo}-{info['number']}.md")
    inv = r.build(RunRequest(prompt=short, cwd=WORKSPACE, env={"CAMARONES_ROOT": str(tree)}, model=model))
    return {**info, "repo": repo, "ref": local_ref, "base": base, "branch": branch, "worktree": str(tree),
            "uid": f"pr:{repo}-{info['number']}", "target": targets[0], "argv": inv.argv, "prompt": text,
            "fetch": None if ref else ["git", "-C", str(repo_dir(repo)), "fetch", "origin",
                                       f"{info['refspec']}:{local_ref}"]}


def _git(*args: str, cwd: Path) -> tuple[int, str]:
    r = run(["git", *args], cwd=cwd, check=False, capture=True)
    return r.returncode, ((r.stdout or "") + (r.stderr or "")).strip()


def _api(url: str, method: str, payload: dict, headers: dict) -> dict:
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), method=method,
                                 headers={**headers, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read() or b"{}")


def open_docs_pr(remote: str, branch: str, title: str, body: str, env: dict | None = None) -> str:
    """Open the cam-docs PR/MR: the API with DOCS_WRITE_TOKEN, else `gh`/`glab`, else say how."""
    env = dict(os.environ) if env is None else env
    token = env.get("DOCS_WRITE_TOKEN")
    m = re.match(r"(?:https?://|git@)(?P<host>[^/:]+)[/:](?P<slug>.+?)(?:\.git)?$", remote)
    if token and m and "github" in m["host"]:
        api = env.get("GITHUB_API_URL", "https://api.github.com").rstrip("/")
        base = out(["git", "-C", str(ROOT), "symbolic-ref", "--short", "refs/remotes/origin/HEAD"]).split("/")[-1] or "main"
        try:
            pr = _api(f"{api}/repos/{m['slug']}/pulls", "POST", {"head": branch, "base": base, "title": title,
                                                                  "body": body}, {"Authorization": f"Bearer {token}"})
            return pr.get("html_url", "opened")
        except (urllib.error.URLError, OSError, ValueError) as e:
            return f"could not open the PR: {e}"
    if token and m:
        api = env.get("CI_API_V4_URL", f"https://{m['host']}/api/v4").rstrip("/")
        try:
            mr = _api(f"{api}/projects/{urllib.parse.quote(m['slug'], safe='')}/merge_requests", "POST",
                      {"source_branch": branch, "target_branch": env.get("CI_DEFAULT_BRANCH", "main"), "title": title,
                       "description": body, "remove_source_branch": True}, {"PRIVATE-TOKEN": token})
            return mr.get("web_url", "opened")
        except (urllib.error.URLError, OSError, ValueError) as e:
            return f"could not open the MR: {e}"
    for tool, args in (("gh", ["pr", "create", "--head", branch, "--title", title, "--body", body]),
                       ("glab", ["mr", "create", "--source-branch", branch, "--title", title, "--description", body,
                                 "--yes"])):
        if which(tool):
            code, text = _git_tool(tool, args)
            return text.splitlines()[-1] if code == 0 and text else f"`{tool}` could not open it: {text[-200:]}"
    return f"branch {branch} pushed: open the PR/MR from it on your forge"


def _git_tool(tool: str, args: list[str]) -> tuple[int, str]:
    r = run([tool, *args], cwd=ROOT, check=False, capture=True)
    return r.returncode, ((r.stdout or "") + (r.stderr or "")).strip()


PREVIEWS = CTX.cache / "previews"


def preview(tree: Path, name: str) -> Path | None:
    """The docs branch as a static portal (the `artifact` publisher): what reviewers open before merging."""
    import shutil
    r = run([uv(), "run", "--quiet", "--script", str(KIT / "camarones.py"), "portal"], cwd=tree, check=False,
            capture=True, env={"CAMARONES_ROOT": str(tree)})
    site = tree / ".camarones" / ".cache" / "site"
    if r.returncode or not site.is_dir():
        return None
    dest = PREVIEWS / name
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(site, dest)
    return dest


def propose(url: str, ref: str | None = None, base: str | None = None, runner: str | None = None, lang: str = "en",
            comment: bool = False, echo=print, with_preview: bool = False) -> dict:
    from . import plan as plan_mod, pr as pr_mod
    p = plan_for(url, ref, base, runner, lang)
    repo, branch, tree = p["repo"], p["branch"], Path(p["worktree"])
    if p["fetch"]:
        code, text = _git(*p["fetch"][3:], cwd=repo_dir(repo))
        if code:
            raise ProposeError(f"cannot fetch the PR into {repo}: {text[-300:]}")
    impact = pr_mod.impact(repo, base=p["base"], head=p["ref"])
    pages = [x for x in impact["pages"]]
    result = {"url": url, "branch": branch, "pages": [x["path"] for x in pages], "committed": False, "pushed": "",
              "docs_pr": "", "comment": ""}
    if not pages:
        echo("This PR changes no documented code: nothing to propose.")
        return result
    if tree.exists():
        _git("worktree", "remove", "--force", str(tree), cwd=ROOT)
    _git("worktree", "prune", cwd=ROOT)
    tree.parent.mkdir(parents=True, exist_ok=True)
    exists = _git("rev-parse", "--verify", "--quiet", f"refs/heads/{branch}", cwd=ROOT)[0] == 0
    code, text = _git("worktree", "add", *([str(tree), branch] if exists else ["-b", branch, str(tree), "HEAD"]), cwd=ROOT)
    if code:
        raise ProposeError(f"cannot create the docs worktree: {text[-300:]}")
    try:
        text = prompt(parse_url(url), repo, p["ref"], p["base"], branch, tree, pages)
        echo(f"{p['target']} updates {len(pages)} page(s) for {url} on {branch}…")
        env = {"CAMARONES_ROOT": str(tree), "CAMARONES_STATE_ROOT": str(CTX.state_root),
               "CAMARONES_WORKSPACE": str(WORKSPACE), "CAMARONES_UNIT": p["uid"]}
        res = plan_mod._run_agent(p["target"], text, lang, p["uid"], echo=echo,
                                  prompt_file=CTX.cache / "prompts" / f"pr-{repo}-{p['number']}.md", env=env)
        if res.returncode:
            raise ProposeError(f"the agent stopped: {(res.stdout or '')[-300:]}")
        _git("add", "--", *[d for d in ("docs", "wikis") if (tree / d).exists()],
             ":(exclude)docs/.work", ":(exclude)docs/llms.txt", ":(exclude)docs/llms-full.txt",
             ":(exclude)docs/.status.json", cwd=tree)
        if _git("diff", "--cached", "--quiet", cwd=tree)[0] == 0:
            echo("The agent changed nothing.")
            return result
        _git("-c", "user.name=camaron", "-c", "user.email=camaron@localhost", "commit", "-q", "-m",
             f"docs: update for {repo} {'!' if p['forge'] == 'gitlab' else '#'}{p['number']}", cwd=tree)
        result["committed"] = True
        if with_preview:
            site = preview(tree, f"pr-{repo}-{p['number']}")
            result["preview"] = str(site) if site else "could not build the preview (run `camaron portal` there)"
        summary_file = tree / ".camarones" / ".cache" / "pr-proposal.md"
        summary = summary_file.read_text(encoding="utf-8").strip() if summary_file.is_file() else ""
        remote = out(["git", "-C", str(ROOT), "remote", "get-url", "origin"])
        if not remote:
            result["pushed"] = f"committed on {branch}; no remote to push to"
        else:
            code, text = _git("push", "-q", "origin", f"HEAD:refs/heads/{branch}", "--force-with-lease", cwd=tree)
            result["pushed"] = f"pushed {branch}" if code == 0 else f"push failed: {text[-200:]}"
            if code == 0:
                body = f"Docs for {url}\n\n{summary or 'Pages updated by an agent; review the drafts.'}"
                sign = "!" if p["forge"] == "gitlab" else "#"
                result["docs_pr"] = open_docs_pr(remote, branch, f"docs: {repo} {sign}{p['number']}", body)
                if comment:
                    note = f"{MARKER}\n### Docs proposal\n\nAn agent updated the affected pages: {result['docs_pr']}\n"
                    result["comment"] = pr_mod.post(note, affected=True, marker=MARKER)
        return result
    finally:
        _git("worktree", "remove", "--force", str(tree), cwd=ROOT)
        _git("worktree", "prune", cwd=ROOT)
