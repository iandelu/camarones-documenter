"""Real terminals (PTYs) held by the project server, so the desktop app shows an agent's own TUI in a canvas node
instead of a window of its own: the stdlib `pty` on macOS and Linux, ConPTY through pywinpty on Windows (when it does
not import, `available()` says so and sessions open in a window as before). They live as long as the server: its exit
ends them (`shutdown`).

A reader thread per terminal keeps what the program printed twice: in memory, a ring of the last RING bytes that a
client (re)connecting replays from its offset; on disk, `<cache>/terminals/<id>.log`, cut to its last LOG_MAX, to read
after the server is gone. `<id>.json` beside it holds who, where, the size, when it started and ended and its code; a
new server numbers its terminals after those files, so it never overwrites an earlier log.

On POSIX, Popen gives the program no controlling terminal, and without one a resize sends no SIGWINCH and Ctrl+C no
SIGINT: a stdlib one-liner (CTTY) makes the PTY the program's own and execs it, same pid (preexec_fn is not safe in a
threaded server). The program leads its own process group, so closing its terminal reaches what it started too."""
from __future__ import annotations

import functools, os, re, select, signal, struct, subprocess, sys, threading, time
from pathlib import Path

from .common import CACHE, IS_WIN, kill_tree, save_json

MAX_LIVE = 8                    # live terminals per project server
RING = 256 * 1024               # bytes kept in memory per terminal, for replay
LOG_MAX = 5 * 1024 * 1024       # a .log is cut to its last LOG_MAX once it passes LOG_MAX + LOG_SLACK,
LOG_SLACK = 1024 * 1024         # so it is not rewritten at every read
KEEP = 50                       # terminal files kept in DIR
INPUT_MAX = 256 * 1024          # input per request
INPUT_WAIT = 5.0                # seconds a program has to take input
COLS, ROWS = (10, 500), (5, 200)
DIR = CACHE / "terminals"
TICK = 0.5                      # how often a reader or a writer looks again
CTTY = "import fcntl, os, sys, termios; fcntl.ioctl(0, termios.TIOCSCTTY, 0); os.execvp(sys.argv[1], sys.argv[1:])"


class Unavailable(RuntimeError):
    """No PTY on this machine: pywinpty does not import, or the PTY cannot be created."""


class Ended(RuntimeError):
    """Input to a terminal whose program ended."""


class _Term:
    def __init__(self, meta: dict, proc, fd: int | None):
        self.meta, self.proc, self.fd = meta, proc, fd
        self.ring, self.end = bytearray(), 0    # the last bytes, and the offset after them
        self.over = False                       # no more input or resizes reach the PTY
        self.wlock = threading.Lock()           # one write at a time
        self.saving = threading.Lock()          # one .json write at a time, so the newest meta is written last
        self.finishing = threading.Lock()       # its reader and `shutdown` may both end it


_lock = threading.Condition(threading.Lock())  # _terms, every terminal's meta, ring and `over`, and _gen
_gen = 0                                        # bumped on output, an end, a new or forgotten terminal
_terms: dict[str, _Term] = {}                   # this server's terminals, in start order
_spawning = threading.Lock()                    # one id handed out at a time


def _bump() -> None:
    global _gen
    _gen += 1
    _lock.notify_all()


@functools.cache
def available() -> bool:
    if not IS_WIN:
        return True
    try:
        import winpty  # noqa: F401
    except ImportError:
        return False
    return True


def _size(cols: int, rows: int) -> tuple[int, int]:
    if not (COLS[0] <= cols <= COLS[1] and ROWS[0] <= rows <= ROWS[1]):
        raise ValueError(f"a terminal has {COLS[0]}–{COLS[1]} columns and {ROWS[0]}–{ROWS[1]} rows")
    return int(cols), int(rows)


def _winsize(fd: int, cols: int, rows: int) -> None:
    import fcntl, termios
    fcntl.ioctl(fd, termios.TIOCSWINSZ, struct.pack("HHHH", rows, cols, 0, 0))


def _new_id(name: str) -> str:
    prefix = "t-" + re.sub(r"[^A-Za-z0-9_.-]", "_", name) + "-"
    files = [p.stem for p in DIR.glob("t-*.json")]
    with _lock:
        taken = [*_terms, *files]
    nums = (re.fullmatch(re.escape(prefix) + r"([0-9]+)", x) for x in taken)
    return f"{prefix}{max((int(m[1]) for m in nums if m), default=0) + 1}"


def _start(argv: list[str], cwd: Path, env: dict, cols: int, rows: int):
    if IS_WIN:
        if not available():
            raise Unavailable("pywinpty is not installed")
        import winpty
        try:
            return winpty.PtyProcess.spawn(argv, cwd=str(cwd), env=env, dimensions=(rows, cols)), None
        except Exception as e:
            raise Unavailable(f"no ConPTY: {e}") from e
    import pty
    try:
        master, slave = pty.openpty()
    except OSError as e:
        raise Unavailable(f"no PTY: {e}") from e
    try:
        _winsize(master, cols, rows)
        # -I: the folder it starts in cannot shadow a module the one-liner imports
        proc = subprocess.Popen([sys.executable, "-I", "-c", CTTY, *argv], stdin=slave, stdout=slave, stderr=slave,
                                cwd=str(cwd), env=env, start_new_session=True, close_fds=True)
    except BaseException:
        os.close(master)
        raise
    finally:
        os.close(slave)                         # held here, the reader would never see the end
    os.set_blocking(master, False)              # a write the program does not take must not hold its writer forever
    return proc, master


def spawn(argv: list[str], cwd: Path, *, kind: str, agent: str, unit: str | None = None, session: str | None = None,
          cols: int = 80, rows: int = 24, env: dict | None = None) -> dict:
    """Starts `argv` on a new terminal; its metadata, also written to DIR/<id>.json."""
    cols, rows = _size(cols, rows)
    env = {**os.environ, **(env or {}), "TERM": "xterm-256color", "COLORTERM": "truecolor"}
    with _spawning:
        tid = _new_id(unit or kind)
        proc, fd = _start(argv, Path(cwd), env, cols, rows)
        t = _Term({"id": tid, "kind": kind, "unit": unit, "agent": agent, "session": session, "pid": proc.pid,
                   "cwd": str(cwd), "started": time.time(), "ended": None, "code": None, "cols": cols, "rows": rows,
                   "closed": False}, proc, fd)
        with _lock:
            _terms[tid] = t
            _bump()
    _save(t)                                    # before the reader: it makes DIR, where the log goes
    threading.Thread(target=_pump, args=(t,), daemon=True, name=f"pty {tid}").start()
    return _meta(t)


def _term(tid: str) -> _Term:
    with _lock:
        return _terms[tid]


def _meta(t: _Term) -> dict:
    with _lock:
        return dict(t.meta)


def get(tid: str) -> dict:
    return _meta(_term(tid))


def listing() -> list[dict]:
    with _lock:
        return [dict(t.meta) for t in _terms.values()]


def read(tid: str, offset: int) -> tuple[bytes, int]:
    """The bytes after `offset` still in the ring, and the offset after them. An offset the ring no longer holds, or
    one past its end (a client's from an earlier server), reads from the ring's start."""
    with _lock:
        t = _terms[tid]
        start = t.end - len(t.ring)
        if not start <= offset <= t.end:
            offset = start
        return bytes(t.ring[offset - start:]), t.end


def write(tid: str, data: str) -> None:
    """Types `data` into the terminal. A worker thread writes it, so a program that does not read holds that thread,
    never the caller: TimeoutError after INPUT_WAIT, and the write ends on its own when the program reads or ends."""
    t = _term(tid)
    deadline = time.monotonic() + INPUT_WAIT
    if not t.wlock.acquire(timeout=INPUT_WAIT):
        raise TimeoutError(f"{tid} is not taking input")
    if t.over:
        t.wlock.release()
        raise Ended(tid)
    done, failed = threading.Event(), []

    def work():
        try:
            _put(t, data)
        except Exception as e:
            failed.append(e)
        finally:
            t.wlock.release()
            done.set()
    threading.Thread(target=work, daemon=True, name=f"pty input {tid}").start()
    if not done.wait(max(0.0, deadline - time.monotonic())):
        raise TimeoutError(f"{tid} is not taking input")
    if failed:
        raise failed[0]


def _put(t: _Term, data: str) -> None:
    if IS_WIN:
        try:
            t.proc.write(data)
        except Exception as e:                  # EOFError once it ended; pywinpty's own error when its pipe broke
            raise Ended(t.meta["id"]) from e
        return
    view = memoryview(data.encode("utf-8"))
    while view:
        if t.over:                              # the reader closes the fd only once this write lets go of it
            raise Ended(t.meta["id"])
        if select.select([], [t.fd], [], TICK)[1]:
            try:
                view = view[os.write(t.fd, view):]
            except BlockingIOError:
                pass
            except OSError as e:
                raise Ended(t.meta["id"]) from e


def resize(tid: str, cols: int, rows: int) -> dict:
    cols, rows = _size(cols, rows)
    with _lock:
        t = _terms[tid]
        if t.over:
            return dict(t.meta)
        if IS_WIN:
            t.proc.setwinsize(rows, cols)
        else:
            _winsize(t.fd, cols, rows)
        t.meta.update(cols=cols, rows=rows)
    _save(t)
    return _meta(t)


def close(tid: str) -> dict:
    """A live terminal: its program and what it started are hung up, and killed if still there 3 s later. An ended
    one is forgotten: gone from `listing`, its files kept."""
    with _lock:
        t = _terms[tid]
        if t.meta["ended"] is not None:
            del _terms[tid]
            _bump()
            return {**t.meta, "forgotten": True}
        t.meta["closed"] = True
        _bump()
    _save(t)
    if IS_WIN:
        kill_tree(t.meta["pid"])
    else:
        kill_tree(t.meta["pid"], signal.SIGHUP)
        hard = threading.Timer(3, kill_tree, (t.meta["pid"], signal.SIGKILL))
        hard.daemon = True
        hard.start()
    return _meta(t)


def wait(seen: int, timeout: float) -> int:
    """Blocks while nothing changed since generation `seen`, at most `timeout` s; the current generation."""
    with _lock:
        _lock.wait_for(lambda: _gen != seen, timeout)
        return _gen


def shutdown() -> None:
    """Ends every live terminal, for the server's exit: hung up, killed if still there 2 s later, then ended."""
    with _lock:
        live = [t for t in _terms.values() if t.meta["ended"] is None]
    for t in live:
        kill_tree(t.meta["pid"], None if IS_WIN else signal.SIGHUP)

    def settle(timeout: float) -> bool:
        with _lock:
            return _lock.wait_for(lambda: all(t.meta["ended"] is not None for t in live), timeout)
    if not settle(2):
        for t in live:
            if t.meta["ended"] is None and not IS_WIN:
                kill_tree(t.meta["pid"], signal.SIGKILL)
        settle(1)
    for t in live:
        _finish(t)                              # a reader still at it (something holds the PTY) stops at its next look


def _pump(t: _Term) -> None:
    """The terminal's reader: its output to the ring and the log, until the PTY ends, or the program exited and TICK s
    passed with nothing to read (something it started may hold the PTY open)."""
    src = t.proc.fileobj if IS_WIN else t.fd
    try:
        while not t.over:
            if not select.select([src], [], [], TICK)[0]:
                if not _alive(t):
                    break
                continue
            data = _take(t)
            if data is None:
                break
            if data:
                _output(t, data)
    finally:
        with _lock:
            t.over = True
        if IS_WIN:
            try:
                t.proc.close()
            except Exception:
                pass
        else:
            with t.wlock:                       # a write under way sees `over` within TICK s
                os.close(t.fd)
        _finish(t)


def _take(t: _Term) -> bytes | None:
    """What the program printed since the last read: b"" for nothing yet, None at the end."""
    if IS_WIN:
        try:
            return t.proc.read(65536).encode("utf-8")
        except (EOFError, OSError):
            return None
    try:
        return os.read(t.fd, 65536) or None
    except BlockingIOError:
        return b""
    except OSError:                             # EIO: Linux's end of a PTY
        return None


def _output(t: _Term, data: bytes) -> None:
    _log(t, data)                               # first: what the ring shows is in the log already
    with _lock:
        t.ring += data
        if len(t.ring) > RING:
            del t.ring[:len(t.ring) - RING]
        t.end += len(data)
        _bump()


def _log(t: _Term, data: bytes) -> None:
    f = DIR / f"{t.meta['id']}.log"
    try:
        with f.open("ab") as fh:
            fh.write(data)
            size = fh.tell()
        if size > LOG_MAX + LOG_SLACK:
            with f.open("rb") as fh:
                fh.seek(size - LOG_MAX)
                tail = fh.read()
            f.write_bytes(tail)
    except OSError:                             # a full disk, or a reader holding it on Windows: the ring has it
        pass


def _alive(t: _Term) -> bool:
    return t.proc.isalive() if IS_WIN else t.proc.poll() is None


def _finish(t: _Term) -> None:
    """The one place a terminal ends: its code, `ended`, the .json rewritten. Called by its reader, and by `shutdown`
    for one whose reader is still at it."""
    with t.finishing:
        if t.meta["ended"] is not None:
            return
        code = _reap(t)
        with _lock:
            t.over = True
            t.meta.update(ended=time.time(), code=code)
            _bump()
        _save(t)


def _reap(t: _Term) -> int | None:
    """The program's exit code. One still running once its terminal is over (it let go of the PTY) is killed: nothing
    started here runs on without a terminal to see it."""
    for last in (False, True):
        end = time.monotonic() + 2
        while _alive(t) and time.monotonic() < end:
            time.sleep(0.05)
        if last or not _alive(t):
            break
        kill_tree(t.meta["pid"], None if IS_WIN else signal.SIGKILL)
    if _alive(t):
        return None
    return t.proc.exitstatus if IS_WIN else t.proc.returncode


def _save(t: _Term) -> None:
    with t.saving:
        meta = _meta(t)
        try:
            save_json(DIR / f"{meta['id']}.json", meta)
        except OSError:                         # the terminal works on without its file, as without its log
            pass
