"""`camaron app`: the desktop app. The kit's own `desktop/` folder (Electron main process, no build step) on the
Electron version pinned in VERSIONS, installed once with npm into ~/.camarones/desktop (no admin rights, nothing in the
project). The app calls this same CLI back with the interpreter and kit it is given, so it never needs uv on PATH.

Optional: without Node.js the CLI, the wizard and the portal keep working, and the error says what to install."""
from __future__ import annotations

import json, os, subprocess, sys
from pathlib import Path

from .common import HOME, IS_MAC, IS_WIN, KIT, ROOT, VERSIONS, WS_FILE, run
from .env import node_major

DEST = HOME / ".camarones" / "desktop"
ELECTRON = DEST / "node_modules" / "electron"


def installed_version() -> str:
    try:
        return json.loads((ELECTRON / "package.json").read_text(encoding="utf-8")).get("version", "")
    except (FileNotFoundError, json.JSONDecodeError):
        return ""


def binary() -> Path:
    """Electron's npm package names its executable in path.txt (electron.exe, Electron.app/…/Electron, electron)."""
    return ELECTRON / "dist" / (ELECTRON / "path.txt").read_text(encoding="utf-8").strip()


def ensure(log=print) -> Path:
    if node_major() < VERSIONS["node_min_major"]:
        raise RuntimeError(f"the desktop app needs Node.js >= {VERSIONS['node_min_major']} (`camaron setup` installs "
                           "it); the CLI and the wizard work without it")
    want = VERSIONS["electron"]
    if installed_version() != want or not (ELECTRON / "path.txt").is_file():
        log(f"installing the desktop app's Electron {want} into {DEST} (once)…")
        DEST.mkdir(parents=True, exist_ok=True)
        run(["npm", "install", "--prefix", str(DEST), "--no-audit", "--no-fund", "--save-exact", f"electron@{want}"],
            quiet=True)
    if not (ELECTRON / "path.txt").is_file():   # npm 11 skips dependency install scripts: Electron's downloads the binary
        log("downloading Electron's binary…")
        run(["node", str(ELECTRON / "install.js")], cwd=ELECTRON, quiet=True)
    return binary()


def no_sandbox() -> bool:
    """Linux distributions that restrict unprivileged user namespaces (Ubuntu 24.04+) stop Electron's sandbox from
    npm's copy (its chrome-sandbox is not setuid root). The windows only load this machine's own portal server."""
    if IS_WIN or IS_MAC:
        return False
    try:
        return Path("/proc/sys/kernel/apparmor_restrict_unprivileged_userns").read_text().strip() == "1"
    except OSError:
        return False


def command(electron: Path) -> tuple[list[str], dict]:
    env = {k: v for k, v in os.environ.items() if k not in ("CAMARONES_APP_TOKEN", "ELECTRON_RUN_AS_NODE")}
    env.update({"CAMARONES_PY": sys.executable, "CAMARONES_KIT": str(KIT), "PYTHONUTF8": "1"})
    if WS_FILE.exists():                       # opened from a project: the app starts on it
        env["CAMARONES_ROOT"] = str(ROOT)
    else:
        env.pop("CAMARONES_ROOT", None)
    return [str(electron), str(KIT / "desktop"), *(["--no-sandbox"] if no_sandbox() else [])], env


def launch(log=print) -> None:
    cmd, env = command(ensure(log))
    kw: dict = {"env": env, "stdin": subprocess.DEVNULL, "stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL}
    if IS_WIN:
        kw["creationflags"] = 0x00000008 | 0x00000200          # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
    else:
        kw["start_new_session"] = True
    subprocess.Popen(cmd, **kw)
    log("🦐 camarón's desktop app is opening")
