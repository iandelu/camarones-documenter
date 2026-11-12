"""File locks (R9): one writer at a time across processes and threads, on every OS. The lock is a file created with
O_EXCL holding {pid, host, ts}; a holder on this machine whose process is gone, or any holder older than `ttl`, is
taken over. Re-entrant in the thread that holds it, so a locked function may call another one. Waiters take turns
(`_Turn`): a holder that takes the lock again at once cannot keep it from them."""
from __future__ import annotations

import json
import os
import socket
import threading
import time
from pathlib import Path

from .fsutil import retry_busy
from .platform import IS_WIN

_held: dict[str, tuple[int, int]] = {}         # lock path → (holding thread, depth), for re-entrancy
_guard = threading.Lock()
TURN_GRACE = 2.0                                # seconds a free lock waits for the waiter whose turn it is


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

    def _read(self, path: Path | None = None) -> dict | None:
        try:
            data = json.loads((path or self.path).read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except FileNotFoundError:
            return None
        except (ValueError, OSError):
            return {}                            # being written right now, or damaged: judged by its age below

    def _stale(self, holder: dict, path: Path | None = None) -> bool:
        try:
            age = time.time() - float(holder.get("ts") or (path or self.path).stat().st_mtime)
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
        turn, my_turn = _Turn(self), False
        try:
            while True:
                if not my_turn and time.monotonic() < deadline and turn.someone_elses():
                    time.sleep(0.02)
                    continue
                try:
                    fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                except PermissionError:
                    if not IS_WIN or time.monotonic() >= deadline:
                        raise
                    time.sleep(0.02)             # Windows: the last holder's file is still being deleted
                    continue
                except FileExistsError:
                    holder = self._read()
                    if holder is None:
                        continue                 # released between the two calls
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
                    my_turn = my_turn or turn.claim()
                    time.sleep(0.005 if my_turn else 0.02)
                    continue
                with os.fdopen(fd, "w", encoding="utf-8") as fh:
                    json.dump({"pid": os.getpid(), "host": socket.gethostname(), "ts": time.time(), **self.info}, fh)
                with _guard:
                    _held[self.key] = (me, 1)
                return
        finally:
            if my_turn:
                turn.drop()

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


class _Turn:
    """The next turn at a lock: a file beside it that the first waiter claims and a holder taking the lock again
    defers to. Without it a waiter polling every 20 ms got in only if it looked in the instant between a release and
    the next acquire, so a holder locking over and over kept the lock past the waiter's deadline. Only fairness
    rests on it: exclusivity is the lock file's alone."""

    def __init__(self, lock: FileLock):
        self.lock, self.path = lock, lock.path.with_name(lock.path.name + ".next")
        self.me = {"pid": os.getpid(), "host": socket.gethostname(), "tid": threading.get_ident()}
        self.seen, self.free_since = None, None

    def claim(self) -> bool:
        try:
            fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except (FileExistsError, PermissionError):
            return False
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump({**self.me, "ts": time.time()}, fh)
        return True

    def _mine(self, holder: dict) -> bool:
        return all(holder.get(k) == v for k, v in self.me.items())

    def drop(self) -> None:
        held = self.lock._read(self.path)
        if not held or self._mine(held):        # unreadable counts as ours: a turn of ours left behind stalls others
            retry_busy(lambda: self.path.unlink(missing_ok=True))

    def someone_elses(self) -> bool:
        """Another waiter holds the turn: it goes first, unless it is gone or leaves the lock free for TURN_GRACE."""
        holder = self.lock._read(self.path)
        if holder is None:
            return False
        if holder != self.seen:
            self.seen, self.free_since = holder, None
        if os.path.exists(self.lock.path):
            self.free_since = None
        else:
            self.free_since = self.free_since or time.monotonic()
        coming = self.free_since is None or time.monotonic() - self.free_since < TURN_GRACE
        if coming and not self._mine(holder) and not self.lock._stale(holder, self.path):
            return True
        if self.lock._read(self.path) == holder:     # gone, or not coming: the turn is free again
            try:
                self.path.unlink(missing_ok=True)
            except PermissionError:              # Windows: someone is reading it; look again
                pass
        return False
