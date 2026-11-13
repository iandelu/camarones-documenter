"""The Launcher port (lib/ports/launcher.py) on the desktop: the default browser (`webbrowser`) and the platform's
terminal (a new console on Windows, Terminal.app through osascript on macOS, the first terminal emulator found on Linux)."""
from __future__ import annotations

import json
import subprocess
import webbrowser
from pathlib import Path

from lib.common import IS_MAC, IS_WIN, which


def open_url(url: str) -> None:
    webbrowser.open(url)


def open_new_terminal(cmd: list[str], cwd: Path) -> bool:
    """Launch `cmd` in its own terminal window, detached from this process, so an interactive agent session
    does not block the wizard. Returns False when no terminal emulator could be found — caller then falls
    back to running `cmd` in the current terminal."""
    import shlex
    try:
        if IS_WIN:
            subprocess.Popen(cmd, cwd=str(cwd), creationflags=subprocess.CREATE_NEW_CONSOLE)
            return True
        if IS_MAC:
            script = f"cd {shlex.quote(str(cwd))} && exec {shlex.join(cmd)}"
            subprocess.Popen(["osascript", "-e", f'tell application "Terminal" to do script {json.dumps(script)}'])
            return True
        inner = f"cd {shlex.quote(str(cwd))} && exec {shlex.join(cmd)}"
        for term, args in (("x-terminal-emulator", ["-e", "bash", "-lc", inner]),
                           ("gnome-terminal", ["--", "bash", "-lc", inner]),
                           ("konsole", ["-e", "bash", "-lc", inner]),
                           ("xterm", ["-e", "bash", "-lc", inner])):
            if which(term):
                subprocess.Popen([term, *args], cwd=str(cwd))
                return True
        return False
    except OSError:
        return False
