"""File locks (R9): one writer at a time across processes and threads, on every OS. The lock is a file created with
O_EXCL holding {pid, host, ts}; a holder on this machine whose process is gone, or any holder older than `ttl`, is
taken over. Re-entrant in the thread that holds it, so a locked function may call another one."""
from __future__ import annotations

import json
import os
import socket
import threading
import time
from pathlib import Path

from ..common import IS_WIN, retry_busy

_held: dict[str, tuple[int, int]] = {}         # lock path → (holding thread, depth), for re-entrancy
_guard = threading.Lock()


class LockBusy(RuntimeError):
    def __init__(self, path: Path, holder: dict):
        self.path, self.holder = path, holder
        super().__init__(f"{path.name} is held by pid {holder.get('pid')} on {holder.get('host') or 'this machine'}")


def _win_pid_alive(pid: int) -> bool:
    """Asked of the OS directly: os.kill(pid, 0) would terminate the process on Windows, and tasklist is slow and,
    when it fails under load, made a live holder look dead (its lock was then taken from under it)."""
    import ctypes
    from ctypes import wintypes
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.OpenProcess.restype = wintypes.HANDLE
    k32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    k32.GetExitCodeProcess.argtypes = (wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD))
    k32.CloseHandle.argtypes = (wintypes.HANDLE,)
    h = k32.OpenProcess(0x1000, False, pid)     # PROCESS_QUERY_LIMITED_INFORMATION
    if not h:
        return ctypes.get_last_error() == 5     # ERROR_ACCESS_DENIED: it exists, it is someone else's
    try:
        code = wintypes.DWORD()
        return not k32.GetExitCodeProcess(h, ctypes.byref(code)) or code.value == 259    # STILL_ACTIVE
    finally:
        k32.CloseHandle(h)


def pid_alive(pid: int) -> bool:
    if pid == os.getpid():
        return True
    if IS_WIN:
        return _win_pid_alive(pid)
    try:
        os.kill(pid, 0)
    except PermissionError:
        return True
    except OSError:
        return False
    return True


class FileLock:
    def __init__(self, path: Path, wait: float = 30.0, ttl: float | None = None, info: dict | None = None):
        self.path, self.wait, self.ttl, self.info = Path(path), wait, ttl, info or {}
        # the folder, never the lock file: resolving the file opens it on Windows, and while another process reads or
        # deletes it the answer changes, so the holder no longer knew its own lock and waited for itself
        parent = self.path.parent.resolve() if self.path.parent.exists() else self.path.parent.absolute()
        self.key = os.path.normcase(str(parent / self.path.name))

    def _read(self) -> dict | None:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except FileNotFoundError:
            return None
        except (ValueError, OSError):
            return {}                            # being written right now, or damaged: judged by its age below

    def _stale(self, holder: dict) -> bool:
        try:
            age = time.time() - float(holder.get("ts") or self.path.stat().st_mtime)
        except (OSError, ValueError):
            return False
        if self.ttl is not None and age > self.ttl:
            return True
        pid, host = holder.get("pid"), holder.get("host")
        if not pid:
            return age > 5                       # an empty lock file older than a few seconds was never finished
        return host in (None, socket.gethostname()) and not pid_alive(int(pid))

    def acquire(self) -> None:
        me = threading.get_ident()
        with _guard:
            owner, depth = _held.get(self.key, (None, 0))
            if owner == me:
                _held[self.key] = (me, depth + 1)
                return
        deadline, checked, checked_at = time.monotonic() + self.wait, None, 0.0
        self.path.parent.mkdir(parents=True, exist_ok=True)
        while True:
            try:
                fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            except PermissionError:
                if not IS_WIN or time.monotonic() >= deadline:
                    raise
                time.sleep(0.02)                 # Windows: the last holder's file is still being deleted
                continue
            except FileExistsError:
                holder = self._read()
                if holder is None:
                    continue                     # released between the two calls
                if holder != checked or time.monotonic() - checked_at > 1:
                    checked, checked_at = holder, time.monotonic()
                    if self._stale(holder) and self._read() == holder:
                        try:
                            self.path.unlink(missing_ok=True)
                        except PermissionError:  # Windows: someone is reading it; look again
                            pass
                        continue
                if time.monotonic() >= deadline:
                    raise LockBusy(self.path, holder) from None
                time.sleep(0.02)
                continue
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump({"pid": os.getpid(), "host": socket.gethostname(), "ts": time.time(), **self.info}, fh)
            with _guard:
                _held[self.key] = (me, 1)
            return

    def release(self) -> None:
        with _guard:
            owner, depth = _held.get(self.key, (None, 0))
            if depth > 1:
                _held[self.key] = (owner, depth - 1)
                return
            _held.pop(self.key, None)
        retry_busy(lambda: self.path.unlink(missing_ok=True))     # Windows: a waiter is reading it right now

    def __enter__(self) -> "FileLock":
        self.acquire()
        return self

    def __exit__(self, *exc) -> None:
        self.release()
