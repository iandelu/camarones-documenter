"""A page's sources as a reader sees them (the portal's Sources card): where each one opens — the same lines on the
repo's forge, and on this machine the file and line (added by the live server only, see `with_files`) — how fresh it
is, and for code that changed or went away since the page was written, the commits that touched it with their pull
request and ticket keys. Never fails a page: a repo that is not cloned, not a git repo or has no remote just leaves
those fields empty."""
from __future__ import annotations

import re
from pathlib import Path

from . import docs
from .common import CAM_DIR, ROOT, out
from .harness import freshness
from .history import TICKET

PULL = re.compile(r"Merge pull request #(\d+)"            # GitHub merge commit
                  r"|\(pull request #(\d+)\)"              # Bitbucket merge commit
                  r"|\(#(\d+)\)\s*$")                      # GitHub squash: "subject (#12)"
MERGE_REQUEST = re.compile(r"See merge request \S*!(\d+)")  # GitLab, in the merge commit's body
MAX_COMMITS = 5
SEP, END = "\x1f", "\x1e"
UMBRELLA = (None, "", "umbrella", ".", CAM_DIR)


def web_base(url: str) -> str:
    """A clone URL as the forge's web address: https, no credentials, no .git; '' for a local path."""
    url = (url or "").strip()
    url = re.sub(r"^ssh://(?:[^@/]+@)?([^/:]+)(?::\d+)?/", r"https://\1/", url)
    url = re.sub(r"^[^@/:]+@([^:/]+):", r"https://\1/", url)
    url = re.sub(r"^(https?://)[^@/]+@", r"\1", url)
    url = url.rstrip("/").removesuffix(".git")
    return url if re.match(r"https?://[^/]+/.+", url) else ""


def forge(base: str) -> str:
    host = re.sub(r"^https?://", "", base).split("/")[0].lower()
    return "github" if "github" in host else "bitbucket" if "bitbucket" in host else "gitlab"


def blob_url(base: str, branch: str, path: str, span: tuple[int, int] | None = None) -> str:
    if not base:
        return ""
    f, branch = forge(base), branch or "main"
    if f == "github":
        return f"{base}/blob/{branch}/{path}" + (f"#L{span[0]}-L{span[1]}" if span else "")
    if f == "bitbucket":
        return f"{base}/src/{branch}/{path}" + (f"#lines-{span[0]}:{span[1]}" if span else "")
    return f"{base}/-/blob/{branch}/{path}" + (f"#L{span[0]}-{span[1]}" if span else "")


def pr_url(base: str, n: int) -> str:
    if not base:
        return ""
    return {"github": f"{base}/pull/{n}", "bitbucket": f"{base}/pull-requests/{n}"}.get(
        forge(base), f"{base}/-/merge_requests/{n}")


def commit_url(base: str, sha: str) -> str:
    if not base:
        return ""
    return {"github": f"{base}/commit/{sha}", "bitbucket": f"{base}/commits/{sha}"}.get(
        forge(base), f"{base}/-/commit/{sha}")


def headline(subject: str, body: str) -> str:
    """What a commit did, in a line: a merge commit's subject only names the branch, its body starts with the PR title."""
    first = next((line.strip() for line in body.splitlines() if line.strip()), "")
    merge = re.match(r"Merge (?:pull request|branch)|Merged in ", subject)
    return first if merge and first and not first.startswith("See merge request") else subject


def pr_and_tasks(subject: str, body: str, base: str = "") -> tuple[dict | None, list[str]]:
    """The pull request a commit came from ({n, url}, or None) and the ticket keys it mentions, in order."""
    m = PULL.search(subject) or MERGE_REQUEST.search(body)
    n = int(next(g for g in m.groups() if g)) if m else 0
    pr = {"n": n, "url": pr_url(base, n)} if m else None
    tasks = list(dict.fromkeys(TICKET.findall(f"{subject}\n{body}")))
    return pr, tasks


def _repo(name: str | None) -> tuple[Path, str, str]:
    """(clone directory, forge web address, branch) of a source's repo; the umbrella is cam-docs itself."""
    if name in UMBRELLA:
        where, entry = ROOT, {}
    else:
        entry = next((r for r in docs.workspace().get("repos", []) if r.get("name") == name), {})
        where = freshness._file(name, "")
    here = where.is_dir()
    url = entry.get("url") or (out(["git", "remote", "get-url", "origin"], cwd=where) if here else "")
    branch = entry.get("branch") or (out(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=where) if here else "")
    return where, web_base(url), branch if branch and branch != "HEAD" else "main"


def _commits(where: Path, path: str, since: str, base: str) -> list[dict]:
    raw = out(["git", "log", f"--since={since}", "-n", str(MAX_COMMITS),
               f"--format=%H{SEP}%h{SEP}%an{SEP}%aI{SEP}%s{SEP}%b{END}", "--", path], cwd=where)
    rows = []
    for rec in filter(None, (r.strip() for r in raw.split(END))):
        sha, short, author, at, subject, body = (rec.split(SEP) + [""] * 6)[:6]
        pr, tasks = pr_and_tasks(subject, body, base)
        rows.append({"sha": sha, "short": short, "author": author, "at": at, "subject": subject,
                     "title": headline(subject, body), "pr": pr,
                     "tasks": tasks, "url": commit_url(base, sha)})
    return rows


def describe(logical: str, refs: list, state: dict | None) -> list[dict]:
    """One entry per source: {ref, kind, state: fresh|changed|missing|unchecked, …what opens it}."""
    st = state or {}
    changed, missing = set(st.get("changed", [])), set(st.get("missing", []))
    known = st.get("state") not in (None, "unverified")
    stamp = freshness.stamped(logical) or {}
    repos: dict = {}
    rows = []
    for raw in refs:
        ref = str(raw).strip()
        k = freshness.kind(ref)
        e = {"ref": ref, "kind": k,
             "state": "missing" if ref in missing else "changed" if ref in changed else "fresh" if known else "unchecked"}
        if k == "doc":
            e["page"] = freshness.parse(ref)[1].removeprefix("docs/")
        elif k == "c4":
            e["name"] = ref[3:]
        else:
            rows.append(_code(e, ref, k, stamp, repos))
            continue
        rows.append(e)
    return rows


def _code(e: dict, ref: str, k: str, stamp: dict, repos: dict) -> dict:
    repo, path, span = freshness.parse(ref)
    if repo not in repos:
        repos[repo] = _repo(repo)
    where, base, branch = repos[repo]
    symbol = ref.partition("#")[2].strip() if k == "symbol" else ""
    if symbol:
        from .harness.symbols import locate
        lines = freshness._lines(repo, path)
        found = locate(lines, symbol, Path(path).suffix) if lines else None
        span = (found[0] + 1, found[1] + 1) if found else None
    e.update(repo=repo or "", path=path, symbol=symbol, lines=list(span) if span else None,
             line=span[0] if span else 1, url=blob_url(base, branch, path, span), since=stamp.get("at", ""),
             commits=[], dirty=False)
    if e["state"] in ("changed", "missing") and where.is_dir():
        if stamp.get("at"):
            e["commits"] = _commits(where, path, stamp["at"], base)
        e["dirty"] = bool(out(["git", "status", "--porcelain", "--", path], cwd=where))
    return e


def with_files(rows: list[dict]) -> list[dict]:
    """The live portal's extra: each code source's absolute path on this machine, for the reader's editor."""
    for e in rows:
        if e["kind"] in ("code", "symbol"):
            e["file"] = freshness._file(e["repo"] or None, e["path"]).resolve().as_posix()
    return rows
