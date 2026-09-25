"""Test-bench project for Camarón: two real repos (Spring PetClinic REST + Angular) pinned to a commit,
in a fixed folder you can document, break and reset as often as you like. Runs THIS checkout's kit against it.

  uv run scripts/sandbox.py reset       uninstall the docs (if any), wipe the folder, clone the pinned repos again
  uv run scripts/sandbox.py open        open the wizard of this kit on the sandbox
  uv run scripts/sandbox.py cli ARGS…   run a kit command on the sandbox (e.g. `cli status`, `cli uninstall --dry-run`)
  uv run scripts/sandbox.py uninstall   shortcut for `cli uninstall` (extra args are passed through)
  uv run scripts/sandbox.py traces      list what the kit left behind; exit 1 if anything (0 = pristine)

Folder: --dir, else $CAMARONES_SANDBOX, else ~/projects/camarones-sandbox. Clones are cached in .cache/sandbox/ of
this checkout (git-ignored), so a reset after the first one needs no network.
"""
from __future__ import annotations

import argparse, json, os, shutil, stat, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
KIT = REPO / ".camarones" / "camarones.py"
CACHE = REPO / ".cache" / "sandbox"
DEFAULT_DIR = Path.home() / "projects" / "camarones-sandbox"
CAM_DIR = "cam-docs"
# what the kit links from the workspace root into cam-docs (lib/env.py LINKS)
LINKS = (".claude", ".codex", ".agents", ".mcp.json", "AGENTS.md", "CLAUDE.md")
REPOS = {   # name → (url, branch, pinned commit)
    "spring-petclinic-rest": ("https://github.com/spring-petclinic/spring-petclinic-rest", "master",
                              "4cd8e1b0cd42578e882247d8801f6be5d402f118"),
    "spring-petclinic-angular": ("https://github.com/spring-petclinic/spring-petclinic-angular", "master",
                                 "1978a75eab0c803595d5cde75acc6a0a9bcff4de"),
}


def git(*args: str, cwd: Path | None = None, check: bool = True) -> str:
    r = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if check and r.returncode:
        raise SystemExit(f"git {' '.join(args)} failed:\n{r.stderr.strip()}")
    return r.stdout.strip()


def rmtree(path: Path) -> None:
    def onerror(fn, p, _exc):          # read-only git objects on Windows
        os.chmod(p, stat.S_IWRITE)
        fn(p)
    shutil.rmtree(path, onerror=onerror)


def cached(name: str, cache: Path = CACHE) -> Path:
    """A bare mirror of the repo that holds the pinned commit (fetched once)."""
    url, branch, sha = REPOS[name]
    mirror = cache / f"{name}.git"
    if not mirror.is_dir():
        mirror.parent.mkdir(parents=True, exist_ok=True)
        print(f"  cloning {url} (once, into {mirror})…")
        git("clone", "--quiet", "--bare", "--single-branch", "--branch", branch, url, str(mirror))
    if git("cat-file", "-t", sha, cwd=mirror, check=False) != "commit":
        git("fetch", "--quiet", "origin", branch, cwd=mirror)
    return mirror


def clone_all(folder: Path, cache: Path = CACHE) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    for name, (url, branch, sha) in REPOS.items():
        dest = folder / name
        git("clone", "--quiet", "--branch", branch, str(cached(name, cache)), str(dest))
        git("reset", "--quiet", "--hard", sha, cwd=dest)
        git("remote", "set-url", "origin", url, cwd=dest)
        print(f"  ✔ {name} @ {sha[:7]}")


def kit_env(folder: Path) -> dict:
    env = {k: v for k, v in os.environ.items() if k != "CAMARONES_GLOBAL"}
    env.update(CAMARONES_ROOT=str(folder / CAM_DIR), PYTHONUTF8="1")
    return env


def kit_cmd(folder: Path, args: list[str], **kw) -> subprocess.CompletedProcess:
    """This checkout's kit, pinned to the sandbox: CAMARONES_ROOT keeps it from resolving to the kit's own folder."""
    uv = shutil.which("uv")
    cmd = [uv, "run", "--quiet", "--script", str(KIT), *args] if uv else [sys.executable, str(KIT), *args]
    return subprocess.run(cmd, cwd=folder, env=kit_env(folder), **kw)


def traces(folder: Path, home: Path | None = None) -> list[str]:
    """Everything that makes the sandbox differ from a fresh clone of the pinned repos."""
    found = []
    if (folder / CAM_DIR).exists():
        found.append(f"{CAM_DIR}/ exists")
    for n in LINKS:
        p = folder / n
        if p.exists() or p.is_symlink():
            found.append(f"{n} in the sandbox root")
    for name, (_url, _branch, sha) in REPOS.items():
        d = folder / name
        if not d.is_dir():
            found.append(f"{name}: missing")
            continue
        if git("rev-parse", "HEAD", cwd=d) != sha:
            found.append(f"{name}: HEAD moved")
        dirty = git("status", "--porcelain", "--ignored", cwd=d)
        if dirty:
            found.append(f"{name}: {' | '.join(dirty.splitlines()[:5])}")
        exclude = d / ".git" / "info" / "exclude"
        if exclude.is_file() and "/openwiki" in exclude.read_text(encoding="utf-8").splitlines():
            found.append(f"{name}: /openwiki in .git/info/exclude")
    registry = (home or Path.home()) / ".camarones" / "projects.json"
    if registry.is_file():
        rows = json.loads(registry.read_text(encoding="utf-8") or "[]")
        found += [f"registry entry {r['path']}" for r in rows if Path(r["path"]).resolve().is_relative_to(folder.resolve())]
    return found


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--dir", type=Path, default=Path(os.environ.get("CAMARONES_SANDBOX", DEFAULT_DIR)))
    p.add_argument("cmd", choices=["reset", "open", "cli", "uninstall", "traces"])
    p.add_argument("args", nargs=argparse.REMAINDER)
    a = p.parse_args()
    folder = a.dir.expanduser().resolve()
    if folder == REPO or REPO in folder.parents:
        raise SystemExit("the sandbox must live outside this checkout")
    if a.cmd == "reset":
        if (folder / CAM_DIR / ".camarones" / "workspace.yaml").exists():
            print("🧹 uninstalling the previous documentation…")
            kit_cmd(folder, ["uninstall", "--yes", "--no-backup"])
        if folder.exists():
            rmtree(folder)
        print(f"🦐 sandbox → {folder}")
        clone_all(folder)
        print(f"ready: uv run scripts/sandbox.py open")
        return 0
    if a.cmd == "traces":
        left = traces(folder)
        print("\n".join(f"  • {t}" for t in left) if left else "✔ pristine: no trace of the kit")
        return 1 if left else 0
    if not folder.is_dir():
        raise SystemExit(f"{folder} does not exist — run `uv run scripts/sandbox.py reset` first")
    if a.cmd != "uninstall":
        (folder / CAM_DIR).mkdir(exist_ok=True)       # the wizard's first run bootstraps it
    args = [] if a.cmd == "open" else (["uninstall"] if a.cmd == "uninstall" else []) + a.args
    return kit_cmd(folder, args).returncode


if __name__ == "__main__":
    sys.exit(main())
