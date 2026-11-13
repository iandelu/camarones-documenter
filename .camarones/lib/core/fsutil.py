"""File helpers that survive Windows locks and half-written files."""
from __future__ import annotations

import json, os, shutil, stat, threading, time
from pathlib import Path


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


def is_link(p: Path) -> bool:
    """A symlink or a Windows junction (Python < 3.12 cannot tell a junction: it resolves somewhere else)."""
    return p.is_symlink() or (p.is_dir() and Path(os.path.realpath(p)) != Path(os.path.realpath(p.parent)) / p.name)


def through_link(root: Path, p: Path) -> bool:
    """Reaching `p` from `root` crosses a link, `p` itself included, or `p` is not under `root`. A symlink or junction
    committed anywhere on the way would carry a read or a write out of the project's real tree."""
    try:
        parts = p.relative_to(root).parts
    except ValueError:
        return True
    cur = root.resolve()
    for part in parts:
        cur = cur / part
        if part == ".." or cur.is_symlink() or (cur.exists() and cur.resolve() != cur):
            return True
    return False


def own_file(root: Path, p: Path) -> bool:
    """The kit may write its own file at `p`: no folder from `root` down to it is a link, and a link sitting at `p`
    is taken out first, so the write lands in a regular file and never goes through the link."""
    if through_link(root, p.parent):
        return False
    if is_link(p):
        try:
            p.unlink()
        except OSError:
            os.rmdir(p)                         # a Windows junction (the target is never followed)
    return True


def rmtree(path: Path) -> None:
    """shutil.rmtree that also removes read-only files (git objects on Windows)."""
    def onerror(fn, p, _exc):
        os.chmod(p, stat.S_IWRITE)
        fn(p)
    shutil.rmtree(path, onerror=onerror)
