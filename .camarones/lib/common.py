"""Shared paths, versions and cross-platform process helpers (macOS, Windows, Linux)."""
from __future__ import annotations

import json, os, platform, shutil, subprocess, sys, threading, time
from contextlib import contextmanager
from pathlib import Path

KIT = Path(__file__).resolve().parent.parent          # .camarones/
IS_WIN = platform.system() == "Windows"
IS_MAC = platform.system() == "Darwin"
HOME = Path.home()

VERSIONS = {
    "kit": "3.14.0",
    "openwiki": "0.5.2",
    "likec4": "1.59.4",
    "graphify": "0.9.65",
    "mmdc": "11.17.0",        # mermaid-cli 11.x = mermaid 11, the major the portal renders with (serve.py VENDOR)
    "gitleaks": "8.30.1",
    "node_min_major": 22,
}


CAM_DIR = "cam-docs"      # per-workspace folder (its own git repo) holding docs + agent config, next to the repos


def find_project_marker(start: Path) -> Path | None:
    """Walk up from `start` (like git does for .git/) looking for a project's .camarones/workspace.yaml, either
    directly or inside a sibling cam-docs/ folder (the workspace root that holds all repos). Lets one central kit
    (global install) serve many projects without CAMARONES_ROOT set by hand."""
    cur = start.resolve()
    for d in (cur, *cur.parents):
        # cam-docs first: a workspace folder that holds a cam-docs project is never a project of its own
        if (d / CAM_DIR / ".camarones" / "workspace.yaml").exists():
            return d / CAM_DIR
        if (d / ".camarones" / "workspace.yaml").exists():
            return d
    return None


def docs_root(path: Path) -> Path:
    """A registered/requested project path → its docs root: the workspace folder of a cam-docs project means
    its cam-docs/ (otherwise opening the workspace folder would bootstrap a second, legacy project there)."""
    path = path.resolve()
    return path / CAM_DIR if (path / CAM_DIR / ".camarones" / "workspace.yaml").exists() else path


def find_root() -> Path:
    """The docs root = <workspace>/cam-docs (legacy: the umbrella folder itself), overridable with CAMARONES_ROOT.
    Resolution order: CAMARONES_ROOT env var > a workspace.yaml found walking up from the cwd > KIT.parent
    (legacy: the kit copy lives inside the project it documents)."""
    env = os.environ.get("CAMARONES_ROOT")
    if env:
        return docs_root(Path(env))
    marker = find_project_marker(Path.cwd())
    return marker if marker else KIT.parent


ROOT = find_root()
CAM_LAYOUT = ROOT.name == CAM_DIR                  # cam-docs layout: repos are ROOT's siblings, not its children
WORKSPACE = ROOT.parent if CAM_LAYOUT else ROOT     # folder holding the repos; agents are launched here
DOCS = ROOT / "docs"
WORK = DOCS / ".work"          # plan, handoff, session log (committed, hidden from portal)
WS_FILE = ROOT / ".camarones" / "workspace.yaml"   # project config: per-project, never shared across projects
CACHE = ROOT / ".camarones" / ".cache"             # generated, git-ignored: portal build, site, code graph, vendor cache
GRAPHS = ROOT / "graph"                            # per-repo graphify output (git-ignored), kept out of the repos


def repo_dir(name: str) -> Path:
    return WORKSPACE / name


def ws_rel(path: str) -> str:
    """A ROOT-relative path as seen from WORKSPACE, where agents run (cam-docs/docs/… vs docs/… in legacy layout)."""
    return f"{CAM_DIR}/{path}" if CAM_LAYOUT else path


def rel_file(f: Path) -> str:
    """ROOT-relative posix path; files outside ROOT (a repo's wiki) get a ../ path that still joins with ROOT."""
    return Path(os.path.relpath(f, ROOT)).as_posix()


def cli_cmd() -> str:
    """How humans/agents invoke Camarón on this OS; legacy launchers remain a compatibility fallback."""
    if os.environ.get("CAMARONES_GLOBAL") or not (ROOT / "camaron.command").exists() and which("camaron"):
        return "camaron"
    if (ROOT / ("camaron.cmd" if IS_WIN else "camaron.command")).exists():
        return r".\camaron.cmd" if IS_WIN else "./camaron.command"
    return r".\camarones.cmd" if IS_WIN else "./camarones.command"


# ---------- PATH & tools ----------
def sdkman_dir() -> Path:
    return Path(os.environ.get("SDKMAN_DIR", HOME / ".sdkman"))


def extra_bin_dirs() -> list[Path]:
    dirs = [HOME / ".local" / "bin", HOME / ".cargo" / "bin"]
    # SDKMAN (java, maven, gradle…) is initialised only in interactive shells: add its "current" candidates explicitly
    cand = sdkman_dir() / "candidates"
    if cand.is_dir():
        dirs += sorted(p / "current" / "bin" for p in cand.iterdir() if (p / "current" / "bin").is_dir())
    if os.environ.get("JAVA_HOME"):
        dirs.append(Path(os.environ["JAVA_HOME"]) / "bin")
    if IS_WIN:
        appdata = os.environ.get("APPDATA")
        if appdata:
            dirs.append(Path(appdata) / "npm")
        pf = Path(os.environ.get("ProgramFiles", r"C:\Program Files"))
        local = Path(os.environ.get("LOCALAPPDATA", HOME / "AppData" / "Local"))
        # where winget puts freshly installed tools, so they work without reopening the terminal
        dirs += [pf / "nodejs", pf / "Git" / "cmd", pf / "Docker" / "Docker" / "resources" / "bin",
                 local / "Microsoft" / "WinGet" / "Links", HOME / ".local" / "bin"]
    else:
        dirs += [Path("/opt/homebrew/bin"), Path("/usr/local/bin")]
    return dirs


def ensure_path() -> None:
    parts = os.environ.get("PATH", "").split(os.pathsep)
    for d in extra_bin_dirs():
        if d.is_dir() and str(d) not in parts:
            parts.insert(0, str(d))
    os.environ["PATH"] = os.pathsep.join(parts)
    # quiet, private defaults for every child process
    os.environ.setdefault("NO_UPDATE_NOTIFIER", "1")
    os.environ.setdefault("DO_NOT_TRACK", "1")
    os.environ.setdefault("OPENWIKI_TELEMETRY_DISABLED", "1")
    os.environ.setdefault("PYTHONUTF8", "1")
    java_cur = sdkman_dir() / "candidates" / "java" / "current"
    if not os.environ.get("JAVA_HOME") and java_cur.is_dir():
        os.environ["JAVA_HOME"] = str(java_cur)


ensure_path()


def which(name: str) -> str | None:
    return shutil.which(name)


def run(cmd: list[str], cwd: Path | None = None, check: bool = True, quiet: bool = False,
        capture: bool = False, env: dict | None = None) -> subprocess.CompletedProcess:
    """Run a command resolving Windows .cmd shims (npm, npx, likec4, openwiki are .cmd on Windows)."""
    exe = which(cmd[0]) or cmd[0]
    full = [exe, *cmd[1:]]
    kw: dict = {"cwd": str(cwd) if cwd else None, "env": {**os.environ, **(env or {})}}
    if capture or quiet:
        kw.update(capture_output=True, text=True, encoding="utf-8", errors="replace")
    try:
        r = subprocess.run(full, **kw)
    except OSError as e:
        # a tool that is missing, unreadable, or blocked (e.g. Windows Smart App Control /
        # WinError 4551) must not crash the wizard — treat it like "not available" instead
        if check:
            raise RuntimeError(f"'{cmd[0]}' not found — run setup / install it first ({e})") from None
        return subprocess.CompletedProcess(full, 127, "", str(e))
    if check and r.returncode != 0:
        msg = (r.stderr or r.stdout or "").strip()[-2000:] if (capture or quiet) else ""
        raise RuntimeError(f"command failed ({r.returncode}): {' '.join(cmd)}\n{msg}")
    return r


def out(cmd: list[str], cwd: Path | None = None) -> str:
    r = run(cmd, cwd=cwd, check=False, capture=True)
    return (r.stdout or "").strip() if r.returncode == 0 else ""


def uv() -> str:
    exe = which("uv") or os.environ.get("UV")
    if not exe:
        raise RuntimeError("uv not found — run the Camarón launcher (it installs uv).")
    return exe


def load_json(p: Path, default):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def save_json(p: Path, data) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def py() -> str:
    return sys.executable


def pid_alive(pid: int) -> bool:
    if IS_WIN:                                  # os.kill(pid, 0) would terminate the process on Windows
        r = run(["tasklist", "/FI", f"PID eq {pid}", "/NH"], check=False, capture=True)
        return str(pid) in (r.stdout or "")
    try:
        os.kill(pid, 0)
    except PermissionError:
        return True
    except OSError:
        return False
    return True


_LOCKS: dict[str, threading.RLock] = {}
_HELD: dict[str, int] = {}
_LOCKS_GUARD = threading.Lock()


def _lock_is_stale(path: Path, stale: float) -> bool:
    try:
        age = time.time() - path.stat().st_mtime
        pid = int(path.read_text(encoding="utf-8").strip() or 0)
    except (OSError, ValueError):
        return False                            # being written or just removed: look again on the next try
    return age > stale or bool(pid and pid != os.getpid() and not pid_alive(pid))


@contextmanager
def file_lock(path: Path, timeout: float = 15, stale: float = 120, reentrant: bool = True):
    """Mutual exclusion across processes and threads (macOS, Windows, Linux): an O_EXCL lock file holding the
    holder's pid. A lock left by a dead process, or older than `stale` seconds, is taken over. Re-entrant within
    one thread, so a locked helper may call another."""
    key = os.path.normcase(os.path.abspath(path))
    with _LOCKS_GUARD:
        rl = _LOCKS.setdefault(key, threading.RLock())
    if not rl.acquire(timeout=timeout):
        raise RuntimeError(f"{path.name} is busy (another session is writing) — try again")
    try:
        if _HELD.get(key):
            if not reentrant:
                raise RuntimeError(f"{path.name} is busy (another session is writing) — try again")
            _HELD[key] += 1
            try:
                yield
            finally:
                _HELD[key] -= 1
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        deadline, checked = time.monotonic() + timeout, 0.0
        while True:
            try:
                fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                break
            except (FileExistsError, PermissionError):  # Windows: PermissionError while the old one is being deleted
                pass
            now = time.monotonic()
            if now - checked > 1:
                checked = now
                if _lock_is_stale(path, stale):
                    try:
                        path.unlink(missing_ok=True)
                    except PermissionError:
                        pass
                    continue
            if now > deadline:
                raise RuntimeError(f"{path.name} is busy (another session is writing) — try again")
            time.sleep(0.03)
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(str(os.getpid()))
        _HELD[key] = 1
        try:
            yield
        finally:
            _HELD[key] = 0
            try:
                path.unlink(missing_ok=True)
            except PermissionError:
                pass
    finally:
        rl.release()
