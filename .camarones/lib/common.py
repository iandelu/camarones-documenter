"""Shared paths, versions and cross-platform process helpers (macOS, Windows, Linux)."""
from __future__ import annotations

import json, os, platform, shutil, stat, subprocess, sys, threading, time
from pathlib import Path

from .harness.ctx import KIT, CAM_DIR, Ctx, docs_root, find_project_marker, find_root  # noqa: F401  (re-exported)

IS_WIN = platform.system() == "Windows"
IS_MAC = platform.system() == "Darwin"
HOME = Path.home()
PREFS = HOME / ".camarones.json"              # per-machine choices: language, models, runners, routing

VERSIONS = {
    "kit": "4.75.0",
    "backlog_md": "1.55.3",   # Backlog.md, the compatibility check of the board (tests/e2e/test_backlogmd.py)
    "openwiki": "0.5.2",
    "likec4": "1.59.4",
    "graphify": "0.9.65",
    "mmdc": "11.17.0",        # mermaid-cli 11.x = mermaid 11, the major the portal renders with (serve.py VENDOR)
    "gitleaks": "8.30.1",
    "osv-scanner": "2.6.0",
    "node_min_major": 22,
    "electron": "44.7.0",     # the desktop app (`camaron app`), installed into ~/.camarones/desktop
    "uv": "0.12.18",          # the uv image the generated GitLab jobs run in (lib/ci.py)
}


CTX = Ctx.from_env()
ROOT = CTX.root
CAM_LAYOUT = CTX.cam_layout                        # cam-docs layout: repos are ROOT's siblings, not its children
WORKSPACE = CTX.workspace                          # folder holding the repos; agents are launched here
DOCS = CTX.docs
WORK = CTX.work                # plan, handoff, session log (committed, hidden from portal); CAMARONES_STATE_ROOT moves it
WS_FILE = CTX.ws_file                              # project config: per-project, never shared across projects
CACHE = CTX.cache                                  # generated, git-ignored: portal build, site, code graph, vendor cache
GRAPHS = CTX.graphs                                # per-repo graphify output (git-ignored), kept out of the repos


def repo_dir(name: str) -> Path:
    return WORKSPACE / name


def ws_rel(path: str) -> str:
    """A ROOT-relative path as seen from WORKSPACE, where agents run: cam-docs/docs/…, docs/… in the legacy layout,
    .cw/<n>/docs/… in a unit's worktree."""
    return Path(os.path.relpath(ROOT / path, WORKSPACE)).as_posix()


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
    """shutil.which, except that on Windows only PATH is searched: shutil looks in the current folder first, so a
    launcher or a planted program in the folder a command runs from would win over the real one."""
    if not IS_WIN or os.path.dirname(name):
        return shutil.which(name)
    exts = [e for e in os.environ.get("PATHEXT", ".COM;.EXE;.BAT;.CMD").split(";") if e]
    names = [name] if any(name.lower().endswith(e.lower()) for e in exts) else [name + e for e in exts]
    for d in os.environ.get("PATH", "").split(os.pathsep):
        d = d.strip().strip('"')
        for n in names if d else ():
            f = os.path.join(d, n)
            if os.path.isfile(f):
                return f
    return None


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


def retry_busy(fn, tries: int = 50):
    """Windows refuses to open or replace a file another process holds open for a moment: try again briefly."""
    for attempt in range(tries):
        try:
            return fn()
        except PermissionError:
            if attempt == tries - 1:
                raise
            time.sleep(0.02)


def load_json(p: Path, default):
    try:
        return json.loads(retry_busy(lambda: p.read_text(encoding="utf-8")))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def save_json(p: Path, data) -> None:
    """Write through a temp file and replace in one step: a reader polling `p` sees the old or the new file, whole."""
    p.parent.mkdir(parents=True, exist_ok=True)
    dst = p.resolve()                           # a symlinked file is written through, not replaced by a copy
    tmp = dst.with_name(f".{dst.name}.{os.getpid()}.{threading.get_ident()}.tmp")
    try:
        tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        if dst.exists():
            shutil.copymode(dst, tmp)           # keeps a 0600 file 0600, as writing in place did
        retry_busy(lambda: os.replace(tmp, dst))
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise


def py() -> str:
    return sys.executable


def rmtree(path: Path) -> None:
    """shutil.rmtree that also removes read-only files (git objects on Windows)."""
    def onerror(fn, p, _exc):
        os.chmod(p, stat.S_IWRITE)
        fn(p)
    shutil.rmtree(path, onerror=onerror)
