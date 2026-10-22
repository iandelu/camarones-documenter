"""Keep the computer awake while a run lasts: a laptop that sleeps mid-session breaks the agent's connection.
caffeinate on macOS (tied to this process, so it ends with it), SetThreadExecutionState on Windows, systemd-inhibit on
Linux when present. Where none applies, nothing happens and the run goes on."""
from __future__ import annotations

import contextlib
import os
import subprocess

from ..common import IS_MAC, IS_WIN, which


@contextlib.contextmanager
def keep_awake():
    """Yields how the computer is kept awake ("caffeinate", "windows", "systemd-inhibit"), or None."""
    proc, how = None, None
    try:
        if IS_WIN:
            import ctypes
            ctypes.windll.kernel32.SetThreadExecutionState(0x80000000 | 0x00000001)   # ES_CONTINUOUS | SYSTEM_REQUIRED
            how = "windows"
        elif IS_MAC and which("caffeinate"):
            proc = subprocess.Popen([which("caffeinate"), "-i", "-w", str(os.getpid())])
            how = "caffeinate"
        elif which("systemd-inhibit"):
            proc = subprocess.Popen([which("systemd-inhibit"), "--what=sleep:idle", "--who=camaron",
                                     "--why=documentation run", "sleep", "infinity"],
                                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            how = "systemd-inhibit"
    except (OSError, AttributeError):
        proc, how = None, None
    try:
        yield how
    finally:
        if proc is not None:
            proc.terminate()
            with contextlib.suppress(Exception):
                proc.wait(timeout=5)
        if how == "windows":
            with contextlib.suppress(Exception):
                import ctypes
                ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)
