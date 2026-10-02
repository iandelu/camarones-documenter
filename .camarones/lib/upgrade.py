"""Kit upgrades: find a newer Camarón next to the project (unzipped folder or zip) and install it in place.

Looked up when the wizard opens:
  * <project>/camarones-documenter*/ or camarones-kit*/ (the zip unzipped into its own folder)
  * camarones-documenter*.zip / camarones-kit*.zip in the project folder, its parent folder or ~/Downloads
The project's config (.camarones/workspace.yaml) and caches (.camarones/.cache/) are kept; docs/ is never touched.
"""
from __future__ import annotations

import os, re, shutil, subprocess, sys, tempfile, zipfile
from pathlib import Path

from .common import ROOT, HOME, KIT, CACHE, VERSIONS, IS_WIN

VER_RE = re.compile(r'"kit":\s*"([\d.]+)"')


OFFICIAL_URL = "https://github.com/iandelu/camarones-documenter.git"
FETCH_TIMEOUT = 20


def kit_url() -> str:
    """Where the central kit comes from; CAMARONES_KIT_URL points it at a fork or a local checkout (kit development)."""
    return os.environ.get("CAMARONES_KIT_URL") or OFFICIAL_URL


def _git(repo: Path, *args: str, timeout: float | None = None) -> subprocess.CompletedProcess:
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}          # a credential prompt would freeze the wizard
    try:
        return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, encoding="utf-8",
                              errors="replace", env=env, timeout=timeout)
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(args, 124, "", f"timed out after {timeout}s")


def _is_local_path(url: str) -> bool:
    return "://" not in url and not re.match(r"^[\w.-]+@[\w.-]+:", url)


def central_repo(repo: Path | None = None) -> Path:
    """The central kit clone. Only the global launcher (install-global.cmd/.sh) sets CAMARONES_GLOBAL — that, not
    ROOT (which falls back to KIT.parent with no project context either way), tells legacy and global installs apart."""
    repo = repo or KIT.parent
    if not os.environ.get("CAMARONES_GLOBAL"):
        raise RuntimeError("this project has its own local kit copy (not a global install) — "
                           "use `upgrade <newer-kit-folder>` instead, or `unlink` to switch to a global install.")
    if not (repo / ".git").exists():
        raise RuntimeError(f"self-update needs the central kit ({repo}) to be a git clone — see install-global.cmd/.sh")
    return repo


def ensure_origin(repo: Path) -> bool:
    """Installs made before 3.8 cloned from the installer's own checkout, so `origin` was a folder that only moved
    when its owner pulled it. Point those at kit_url(); a remote URL (a fork) is the user's choice and stays."""
    url = _git(repo, "remote", "get-url", "origin").stdout.strip()
    if not url or not _is_local_path(url) or url == kit_url():
        return False
    _git(repo, "remote", "set-url", "origin", kit_url())
    return True


def _version_in(text: str) -> str | None:
    m = VER_RE.search(text)
    return m.group(1) if m else None


def check(repo: Path | None = None, timeout: float = FETCH_TIMEOUT) -> dict:
    """What the central kit's upstream has that this clone does not, without changing the working tree."""
    repo = repo or KIT.parent
    ensure_origin(repo)
    r = _git(repo, "fetch", "--quiet", timeout=timeout)
    if r.returncode != 0:
        url = _git(repo, "remote", "get-url", "origin").stdout.strip() or kit_url()
        raise RuntimeError(f"could not reach {url}: {(r.stderr or r.stdout).strip() or 'no answer'}")
    behind = _git(repo, "rev-list", "--count", "HEAD..@{u}").stdout.strip()
    latest = _version_in(_git(repo, "show", "@{u}:.camarones/lib/common.py").stdout)
    return {"current": current(), "latest": latest or current(), "behind": int(behind or 0)}


def _uv_kit(repo: Path, *args: str) -> list[str]:
    """Run the (possibly just updated) kit through uv, not sys.executable: a newer kit may declare new inline deps."""
    from .common import uv
    return [uv(), "run", "--quiet", "--script", str(repo / ".camarones" / "camarones.py"), *args]


def self_update(log=print, repo: Path | None = None) -> str:
    """Global install only: `git pull` the central kit clone in place. Every project resolves ROOT
    against this same KIT, so this is the only step needed to bring all of them up to date at once."""
    repo = central_repo(repo)
    if ensure_origin(repo):
        log(f"  the kit now follows {kit_url()}")
    before = current()
    pull_kit(repo)
    after = _version_in((repo / ".camarones" / "lib" / "common.py").read_text(encoding="utf-8", errors="replace"))
    after = after or before
    log(f"✔ already on the latest kit ({before})" if after == before
        else f"✔ kit updated {before} → {after} — every project using this global kit sees it now")
    from .common import WS_FILE
    if after != before and WS_FILE.exists():            # this project's playbook, conventions and kit skills
        subprocess.run(_uv_kit(repo, "init"), capture_output=True,
                       env={**os.environ, "CAMARONES_ROOT": str(ROOT), "PYTHONUTF8": "1"})
    return after


def relaunch_global() -> None:
    """Restart the wizard on the updated central kit, on the same project."""
    args = _uv_kit(KIT.parent, *sys.argv[1:])
    env = {**os.environ, "PYTHONUTF8": "1", "CAMARONES_GLOBAL": "1", "CAMARONES_ROOT": str(ROOT)}
    if IS_WIN:
        sys.exit(subprocess.run(args, env=env).returncode)
    os.execve(args[0], args, env)


def pull_kit(kit_repo: Path) -> None:
    """Fast-forward the kit clone; if upstream history was rewritten (rebased, amended), move onto it as long as
    every local commit already exists upstream by content and nothing is left uncommitted."""
    def git(*args: str) -> subprocess.CompletedProcess:
        return _git(kit_repo, *args)

    r = git("pull", "--ff-only", "--quiet")
    if r.returncode == 0:
        return
    if git("rev-parse", "--abbrev-ref", "@{u}").returncode != 0 or git("fetch", "--quiet").returncode != 0:
        raise RuntimeError(f"git pull failed in {kit_repo}: {(r.stderr or r.stdout).strip()}")
    if git("status", "--porcelain", "--untracked-files=no").stdout.strip():
        raise RuntimeError(f"the kit clone {kit_repo} has uncommitted changes — commit or discard them, then retry")
    if any(line.startswith("+") for line in git("cherry", "@{u}", "HEAD").stdout.splitlines()):
        raise RuntimeError(f"the kit clone {kit_repo} has local commits that are not upstream — "
                           "push or drop them, then retry")
    r = git("reset", "--hard", "--quiet", "@{u}")
    if r.returncode != 0:
        raise RuntimeError(f"could not move {kit_repo} onto upstream: {(r.stderr or r.stdout).strip()}")


PATTERNS = ("camarones-documenter*", "camarones-kit*")
STAGE = ROOT / "camarones-documenter-upgrade"


def vtuple(v: str | None) -> tuple:
    return tuple(int(x) for x in re.findall(r"\d+", v or "0")[:3])


def current() -> str:
    return VERSIONS["kit"]


def _dir_version(d: Path) -> tuple[str | None, Path | None]:
    for kit in (d, *[c for c in d.iterdir() if c.is_dir()]) if d.is_dir() else ():
        f = kit / ".camarones" / "lib" / "common.py"
        if f.exists():
            m = VER_RE.search(f.read_text(encoding="utf-8", errors="replace"))
            return (m.group(1) if m else "0"), kit
    return None, None


def _zip_version(z: Path) -> tuple[str | None, str | None]:
    try:
        with zipfile.ZipFile(z) as zf:
            for n in zf.namelist():
                if n.replace("\\", "/").endswith(".camarones/lib/common.py"):
                    m = VER_RE.search(zf.read(n).decode("utf-8", "replace"))
                    return (m.group(1) if m else "0"), n[: -len(".camarones/lib/common.py")]
    except (zipfile.BadZipFile, OSError):
        pass
    return None, None


def candidates() -> list[dict]:
    found: list[dict] = []
    for pat in PATTERNS:
        for d in ROOT.glob(pat):
            if d.is_dir() and d.resolve() != KIT.parent.resolve():
                v, kit = _dir_version(d)
                if v:
                    found.append({"kind": "dir", "path": d, "kit": kit, "version": v})
    for base in dict.fromkeys([ROOT, ROOT.parent, HOME / "Downloads"]):
        if not base.is_dir():
            continue
        for pat in PATTERNS:
            for z in base.glob(pat + ".zip"):
                v, prefix = _zip_version(z)
                if v:
                    found.append({"kind": "zip", "path": z, "prefix": prefix, "version": v})
    return sorted(found, key=lambda c: (vtuple(c["version"]), c["path"].stat().st_mtime), reverse=True)


def newest() -> dict | None:
    c = candidates()
    return c[0] if c and vtuple(c[0]["version"]) > vtuple(current()) else None


def stage(c: dict) -> Path:
    """Put the new kit in <project>/camarones-documenter-upgrade/ (the folder layout install_from_kit_folder expects)."""
    shutil.rmtree(STAGE, ignore_errors=True)
    if c["kind"] == "dir":
        if c["kit"].parent.resolve() == ROOT.resolve():
            return c["kit"]
        shutil.copytree(c["kit"], STAGE)
        return STAGE
    tmp = Path(tempfile.mkdtemp(prefix="camarones-"))
    with zipfile.ZipFile(c["path"]) as zf:
        zf.extractall(tmp)
    src = tmp / c["prefix"] if c["prefix"] else tmp
    shutil.move(str(src), str(STAGE))
    shutil.rmtree(tmp, ignore_errors=True)
    return STAGE


LEGACY = ["docker-compose.yml", "Dockerfile", "nginx.conf", "workspace.yaml", "build"]


def cleanup_legacy(log=print) -> list[str]:
    """Files older kits left in the project root → .camarones/.cache/legacy/ (moved, never deleted)."""
    moved = []
    for name in LEGACY:
        p = ROOT / name
        if not p.exists():
            continue
        if p.is_file():
            txt = p.read_text(encoding="utf-8", errors="replace")
            if name == "workspace.yaml" and (KIT / "workspace.yaml").exists():
                pass                                  # already migrated to .camarones/workspace.yaml
            elif not any(k in txt for k in ("camarones", "docs-portal", "build/site", "docs-kit")):
                continue
        elif not ((p / "site").exists() or (p / "portal").exists()):
            continue
        dst = CACHE / "legacy" / name
        dst.parent.mkdir(parents=True, exist_ok=True)
        if dst.exists():
            shutil.rmtree(dst, ignore_errors=True) if dst.is_dir() else dst.unlink()
        shutil.move(str(p), str(dst))
        moved.append(name)
        log(f"  moved old {name} → .camarones/.cache/legacy/")
    return moved


def relaunch(script: Path) -> None:
    """Start the (new) kit in a fresh process. os.execv breaks paths with spaces on Windows, so use a child there."""
    args = [sys.executable, str(script), *sys.argv[1:]]
    if IS_WIN:
        sys.exit(subprocess.run(args).returncode)
    os.execv(sys.executable, args)
