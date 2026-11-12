"""Moved to lib/core/locks.py; this path keeps old imports working."""
from ..core.locks import FileLock, LockBusy, pid_alive

__facade__ = "lib.core.locks"
__all__ = ["FileLock", "LockBusy", "pid_alive"]
