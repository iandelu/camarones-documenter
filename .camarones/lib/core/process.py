"""Cross-platform process helpers and the tool PATH (macOS, Windows, Linux)."""
from __future__ import annotations

import os, re, shutil, signal, subprocess, sys
from collections.abc import Callable
from pathlib import Path

from .platform import HOME, IS_WIN


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
    for d in [] if os.environ.get("CAMARONES_KEEP_PATH") else extra_bin_dirs():  # a PATH set on purpose (the test suite)
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


def stream(cmd: list[str], cwd: Path, log: Callable[[str], None], env: dict | None = None) -> int:
    """Run a long command and hand each output line to `log` (the portal shows it live)."""
    try:
        pr = subprocess.Popen([which(cmd[0]) or cmd[0], *cmd[1:]], cwd=str(cwd), stdin=subprocess.DEVNULL,
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8",
                              errors="replace", env={**os.environ, **(env or {})})
    except OSError as e:
        log(f"⚠ {cmd[0]}: {e}")
        return 127
    for line in pr.stdout:
        line = re.sub(r"\x1b\[[0-9;?]*[A-Za-z]", "", line).rstrip()
        if line.strip():
            log(line)
    return pr.wait()


# What a Claude Code session sets on whatever it launches, and what ties a shell to the host that opened it. A `claude`
# that inherits them is that session's child, and a child saves no transcript: the board has nothing to read and Continue
# nothing to reopen. Only these go: the same prefix also names a person's own settings (CLAUDE_CODE_USE_BEDROCK, …),
# without which a session may not even start, and a marker missing from this list only costs that transcript.
PARENT_SESSION = ("CLAUDECODE", "CLAUDE_CODE_CHILD_SESSION", "CLAUDE_CODE_SESSION_ID", "CLAUDE_CODE_SESSION_ATTENDED",
                  "CLAUDE_CODE_HOST_SESSION_ID", "CLAUDE_CODE_ENTRYPOINT", "CLAUDE_CODE_MESSAGING_SOCKET",
                  "CLAUDE_CODE_MESSAGING_TOKEN", "CLAUDE_CODE_EXECPATH", "CLAUDE_PID", "CLAUDE_EFFORT")


def leave_parent_session() -> None:
    """The kit run from inside a Claude Code session opens sessions of their own: everything it starts inherits this."""
    for name in PARENT_SESSION:
        os.environ.pop(name, None)


def kill_tree(pid: int, sig: int | None = None) -> bool:
    """The process and what it started; False when it was already gone. POSIX signals its process group (`pid` leads
    one: it was started with start_new_session); Windows has no groups, so taskkill walks the tree (`sig` ignored)."""
    if IS_WIN:
        return run(["taskkill", "/PID", str(pid), "/T", "/F"], check=False, quiet=True).returncode == 0
    try:
        os.killpg(pid, sig or signal.SIGTERM)
    except (ProcessLookupError, PermissionError):  # EPERM: macOS's answer for a group left with only its zombie
        return False
    return True


def uv() -> str:
    exe = which("uv") or os.environ.get("UV")
    if not exe:
        raise RuntimeError("uv not found — run the Camarón launcher (it installs uv).")
    return exe


def py() -> str:
    return sys.executable
