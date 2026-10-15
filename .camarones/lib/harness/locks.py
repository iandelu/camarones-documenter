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

from ..common import IS_WIN, run

_held: dict[str, tuple[int, int]] = {}         # lock path → (holding thread, depth), for re-entrancy
_guard = threading.Lock()


class LockBusy(RuntimeError):
    def __init__(self, path: Path, holder: dict):
        self.path, self.holder = path, holder
        super().__init__(f"{path.name} is held by pid {holder.get('pid')} on {holder.get('host') or 'this machine'}")


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


class FileLock:
    def __init__(self, path: Path, wait: float = 30.0, ttl: float | None = None, info: dict | None = None):
        self.path, self.wait, self.ttl, self.info = Path(path), wait, ttl, info or {}
        self.key = str(self.path.resolve()) if self.path.parent.exists() else str(self.path.absolute())

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
            except FileExistsError:
                holder = self._read()
                if holder is None:
                    continue                     # released between the two calls
                if holder != checked or time.monotonic() - checked_at > 1:   # liveness can be slow (tasklist)
                    checked, checked_at = holder, time.monotonic()
                    if self._stale(holder) and self._read() == holder:
                        self.path.unlink(missing_ok=True)
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
        self.path.unlink(missing_ok=True)

    def __enter__(self) -> "FileLock":
        self.acquire()
        return self

    def __exit__(self, *exc) -> None:
        self.release()
