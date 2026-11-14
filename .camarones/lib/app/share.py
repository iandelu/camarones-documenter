"""The team's docs repo: local checkpoint commits that keep docs progress safe in the umbrella repo, and sharing them
with the team (pull + push on demand, or after every checkpoint with auto-share)."""
from __future__ import annotations

import datetime as dt
import re
import sys

from lib.app import services
from lib.common import CACHE, CTX, ROOT, load_json, out, run, save_json
from lib.ports import Log
from lib.projects import git_failure


# ---------- progress safety: local checkpoint commits in the umbrella repo ----------
def _stderr(line: str) -> None:
    print(line, file=sys.stderr)


def board_repair(warn: Log = _stderr) -> list[str]:
    """The board's repair pass; what it changed. Its warnings go to `warn`; a failure is a warning, never a blocked
    commit. Only the main cam-docs has a board to repair: a unit's worktree leaves it to main."""
    from lib import kanban
    if not kanban.enabled() or CTX.root != CTX.state_root:
        return []
    try:
        from lib.kanban import repair
        res = repair.repair(log=lambda _: None)
    except Exception as e:                                   # noqa: BLE001 — the commit must go on
        warn(f"🦐⚠ board repair skipped: {e}")
        return []
    for w in res["warnings"]:
        warn(f"🦐⚠ board: {w}")
    return res["changed"]


def checkpoint_commit(message: str, warn: Log = _stderr) -> bool:
    """Commit docs progress locally. Keeps work safe if a session or the computer closes; pushes only with auto-share.
    The board repair's warnings go to `warn` (stderr unless a caller such as share() shows them in its own log)."""
    if not (ROOT / ".git").exists():
        return False
    board_repair(warn)
    paths = services.current().vcs.checkpoint_paths()
    if CTX.root != CTX.state_root:   # a unit's worktree: its pages only; derived files, plan state and the board belong to main
        paths = [p for p in paths if p not in ("backlog", ".gitattributes")]
        paths += [":(exclude)docs/.work", ":(exclude)docs/.status.json", ":(exclude)docs/llms.txt",
                  ":(exclude)docs/llms-full.txt"]
    if paths:                                    # (only exclusions would stage everything else)
        paths += [":(exclude,glob)backlog/**/*.tmp"]                   # a board write that died half way
        run(["git", "add", "--", *paths], cwd=ROOT, check=False, quiet=True)
    if run(["git", "diff", "--cached", "--quiet"], cwd=ROOT, check=False, quiet=True).returncode == 0:
        return False
    from lib import quality
    leaks = quality.staged_secrets()
    if leaks:        # left staged, not committed: fix the page, the next checkpoint picks it up
        print("🦐✖ checkpoint not committed — possible secrets staged:\n  " + "\n  ".join(leaks), file=sys.stderr)
        return False
    ident = [] if out(["git", "config", "user.email"], cwd=ROOT) else ["-c", "user.name=Camarón",
                                                                       "-c", "user.email=camarones@localhost"]
    r = run(["git", *ident, "commit", "-q", "-m", f"docs(camarones): {message}", "--no-verify"], cwd=ROOT, check=False, quiet=True)
    if r.returncode:
        return False
    if not _sharing and auto_share() and docs_remote():
        s = share(log=lambda _: None)
        if s["status"] not in ("pushed", "up-to-date", "nothing"):
            why = f" ({s['reason']})" if s.get("reason") else ""
            print(f"🦐 auto-share: {s['status']}{why}: {s['detail']}", file=sys.stderr)
    return True


# ---------- the team's docs repo: pull + push on demand, or after every checkpoint with auto-share ----------
AUTO_SHARE = CACHE / "share.json"                   # per machine: one teammate opting in never pushes for the others
SHARED = CACHE / "shared.json"                      # when this machine last shared (its own file: share.json is the opt-in)
_sharing = False


def auto_share() -> bool:
    return bool(load_json(AUTO_SHARE, {}).get("auto"))


def set_auto_share(on: bool) -> None:
    AUTO_SHARE.parent.mkdir(parents=True, exist_ok=True)
    save_json(AUTO_SHARE, {"auto": bool(on)})


def sync_status(fetch: bool = False) -> dict:
    """Where cam-docs stands against the team's repo, without the network unless `fetch`: the remote and branch, the
    commits ahead / behind the last fetched origin, the files not checkpointed yet, the last commit and last share."""
    git = lambda *a: out(["git", *a], cwd=ROOT)                       # noqa: E731
    url = docs_remote()
    branch = git("symbolic-ref", "--short", "HEAD") if (ROOT / ".git").exists() else ""
    fetched = None
    if url and fetch:
        from lib import creds
        r = run(["git", "fetch", "--quiet", "origin"], cwd=ROOT, check=False, quiet=True, env=creds.git_env(url))
        fetched = {"ok": True, "reason": ""} if r.returncode == 0 else \
            {"ok": False, "reason": git_failure(r.stderr or r.stdout or ""), "host": _remote_host(url), "detail": _git_said(r)}
    ahead = behind = None
    if url and branch and git("rev-parse", "--verify", "--quiet", f"origin/{branch}"):
        counts = git("rev-list", "--left-right", "--count", f"HEAD...origin/{branch}").split()
        if len(counts) == 2:
            ahead, behind = int(counts[0]), int(counts[1])
    paths = services.current().vcs.checkpoint_paths()
    pending = []
    if (ROOT / ".git").exists() and paths:
        status = run(["git", "status", "--porcelain", "-uall", "--", *paths], cwd=ROOT, check=False, capture=True).stdout or ""
        pending = sorted({ln[3:].strip().strip('"').split(" -> ")[-1] for ln in status.splitlines() if len(ln) > 3})
    head = git("log", "-1", "--format=%h%x00%s%x00%cI").split("\x00") if branch else []
    return {"remote": url, "branch": branch, "ahead": ahead, "behind": behind, "pending": pending,
            "head": dict(zip(("hash", "subject", "date"), head)) if len(head) == 3 else None,
            "auto": auto_share(), "last_share": load_json(SHARED, {}).get("last"), "fetched": fetched}


def docs_remote() -> str:
    return out(["git", "remote", "get-url", "origin"], cwd=ROOT) if (ROOT / ".git").exists() else ""


def set_remote(url: str) -> None:
    """Point cam-docs at the team's repo (origin). The first share publishes it."""
    if not (ROOT / ".git").exists():
        run(["git", "init", "-q", str(ROOT)], quiet=True)
    run(["git", "remote", "remove", "origin"], cwd=ROOT, check=False, quiet=True)
    from lib.projects import clean_remote
    run(["git", "remote", "add", "origin", clean_remote(url)], cwd=ROOT, quiet=True)


def _remote_host(url: str) -> str:
    from lib import creds
    return (creds.host_of(url) or "") if re.match(r"^[a-z][a-z0-9+.-]*://|^[\w.+-]+@", url, re.I) else ""


def _git_said(r) -> str:
    """git's own words for a failed fetch or push, from its fatal/error line on (its last line alone is often a fragment)."""
    lines = [ln.strip() for ln in (r.stderr or r.stdout or "").strip().splitlines() if ln.strip()]
    start = next((i for i, ln in enumerate(lines) if ln.lower().startswith(("fatal:", "error:"))), len(lines) - 1)
    return " · ".join(lines[max(start, 0):])[:400]


def _ident() -> list[str]:
    return [] if out(["git", "config", "user.email"], cwd=ROOT) else ["-c", "user.name=Camarón",
                                                                      "-c", "user.email=camarones@localhost"]


def share(log: Log = print) -> dict:
    """Checkpoint, bring in the team's work (rebase onto origin) and push. Returns {"status", "detail"}:
    pushed · up-to-date · no-remote · nothing · blocked (secrets staged) · conflict (rebase undone) · error."""
    url = docs_remote()
    if not url:
        return {"status": "no-remote", "detail": ""}
    from lib import creds
    from lib.projects import clean_remote
    if clean_remote(url) != url:                                      # stored as typed by an older kit
        url = clean_remote(url)
        run(["git", "remote", "set-url", "origin", url], cwd=ROOT, check=False, quiet=True)
    auth = creds.git_env(url)
    host = _remote_host(url)

    def git(*args: str, env: dict | None = None):
        return run(["git", *args], cwd=ROOT, check=False, quiet=True, env=env)

    def last(r) -> str:
        lines = (r.stderr or r.stdout or "").strip().splitlines()
        return lines[-1] if lines else ""

    def failed(r) -> dict:
        reason = git_failure(r.stderr or r.stdout or "")
        if reason == "auth" and host and not creds.get(host):
            reason = "no-token"
        return {"status": "error", "reason": reason, "host": host, "detail": _git_said(r)}

    said: set[str] = set()

    def warn(line: str) -> None:                                      # the board's warnings, once each, in this log
        if line not in said:
            said.add(line)
            log(line)

    global _sharing
    _sharing = True
    try:
        checkpoint_commit("share", warn=warn)
    finally:
        _sharing = False
    if git("diff", "--cached", "--quiet").returncode != 0:
        return {"status": "blocked", "detail": "staged changes were not committed (possible secrets): run check --secrets"}
    if git("rev-parse", "--verify", "--quiet", "HEAD").returncode != 0:
        return {"status": "nothing", "detail": ""}
    branch = out(["git", "symbolic-ref", "--short", "HEAD"], cwd=ROOT)
    if not branch:
        return {"status": "error", "detail": "detached HEAD: check out a branch first"}
    log(f"fetching {url}…")
    r = git("fetch", "--quiet", "origin", env=auth)
    if r.returncode:
        return failed(r)
    theirs = f"origin/{branch}"
    if git("rev-parse", "--verify", "--quiet", theirs).returncode == 0:
        log(f"rebasing onto {theirs}…")
        if git(*_ident(), "rebase", "--quiet", "--autostash", theirs).returncode:
            git("rebase", "--abort")
            return {"status": "conflict", "detail": theirs}
        if board_repair(warn):                                        # a merge can leave duplicate ids or stale mirrors
            _sharing = True
            try:
                checkpoint_commit("board repaired after sync", warn=warn)
            finally:
                _sharing = False
            if git("diff", "--cached", "--quiet").returncode != 0:
                return {"status": "blocked", "detail": "the board repair was not committed (possible secrets): run check --secrets"}
        if out(["git", "rev-list", "--count", f"{theirs}..HEAD"], cwd=ROOT) == "0":
            _shared()
            return {"status": "up-to-date", "detail": branch}
    log(f"pushing {branch}…")
    r = git("push", "--quiet", "-u", "origin", branch, env=auth)
    if r.returncode:
        return failed(r)
    _shared()
    return {"status": "pushed", "detail": branch}


def _shared() -> None:
    """Remember when this machine last shared (the portal's Sync view shows it)."""
    SHARED.parent.mkdir(parents=True, exist_ok=True)
    save_json(SHARED, {"last": dt.datetime.now().astimezone().isoformat(timespec="seconds")})
