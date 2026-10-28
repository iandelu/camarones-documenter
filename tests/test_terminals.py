"""PTYs in the project server (lib/terminals.py): a real terminal per session, on every OS (pywinpty on Windows)."""
from __future__ import annotations

import json, os, re, socket, subprocess, sys, time
from pathlib import Path
from types import SimpleNamespace

import pytest

ECHO = Path(__file__).parent / "fixtures" / "pty_echo.py"
ANSI = re.compile(rb"\x1b\[[0-?]*[ -/]*[@-~]|\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)|\r")


def until(cond, timeout=15.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if cond():
            return
        time.sleep(0.05)
    raise AssertionError("timed out")


def screen(t, tid) -> bytes:
    """What the program printed, without the terminal's escapes and carriage returns (ConPTY redraws with them)."""
    return ANSI.sub(b"", t.read(tid, 0)[0])


@pytest.fixture
def pty(kit):
    from lib import terminals

    def open_(argv=None, **kw):
        return terminals.spawn(argv or [sys.executable, str(ECHO)], kit.root, kind="update", agent="test", **kw)
    yield SimpleNamespace(t=terminals, open=open_)
    terminals.shutdown()


def test_a_program_runs_in_a_terminal_and_answers_what_is_typed(pty):
    m = pty.open(cols=90, rows=30)
    assert m["id"].startswith("t-update-") and m["pid"] and m["ended"] is None and (m["cols"], m["rows"]) == (90, 30)
    until(lambda: b"ready 90x30" in screen(pty.t, m["id"]))
    pty.t.write(m["id"], "hola\r")
    until(lambda: b"echo hola (4)" in screen(pty.t, m["id"]))
    assert pty.t.listing()[-1]["id"] == m["id"]


def test_a_resize_reaches_the_program(pty):
    m = pty.open()
    until(lambda: b"ready 80x24" in screen(pty.t, m["id"]))
    assert pty.t.resize(m["id"], 100, 40)["cols"] == 100
    pty.t.write(m["id"], "size\r")
    until(lambda: b"size 100x40" in screen(pty.t, m["id"]))
    with pytest.raises(ValueError):
        pty.t.resize(m["id"], 9, 40)


@pytest.mark.skipif(sys.platform == "win32", reason="SIGWINCH is POSIX; ConPTY resizes the console itself")
def test_the_terminal_is_the_programs_own_so_a_resize_signals_it(pty):
    m = pty.open()
    until(lambda: b"ready" in screen(pty.t, m["id"]))
    pty.t.resize(m["id"], 120, 33)
    until(lambda: b"winch 120x33" in screen(pty.t, m["id"]))


def test_the_end_of_a_program_is_kept_with_its_code(pty):
    m = pty.open()
    until(lambda: b"ready" in screen(pty.t, m["id"]))
    pty.t.write(m["id"], "exit\r")
    until(lambda: pty.t.get(m["id"])["ended"])
    assert pty.t.get(m["id"])["code"] == 3
    saved = json.loads((pty.t.DIR / f"{m['id']}.json").read_text(encoding="utf-8"))
    assert (saved["code"], saved["unit"], saved["kind"]) == (3, None, "update")
    with pytest.raises(pty.t.Ended):
        pty.t.write(m["id"], "hola\r")


# The app writes what a terminal printed before it opened the stream as history, with xterm's answers to old queries
# muted (a replayed DA or CPR would otherwise be typed into the program): the listing says where history ends.
def test_a_listed_terminal_says_how_far_its_output_goes(pty, monkeypatch):
    monkeypatch.setattr(pty.t, "FRESH", 0.2)
    m = pty.open()
    until(lambda: b"ready" in screen(pty.t, m["id"]))
    pty.t.write(m["id"], "exit\r")
    until(lambda: pty.t.get(m["id"])["ended"])
    listed = lambda: next(x for x in pty.t.listing() if x["id"] == m["id"])      # noqa: E731
    until(lambda: listed()["offset"] == pty.t.read(m["id"], 0)[1] > 0)
    saved = json.loads((pty.t.DIR / f"{m['id']}.json").read_text(encoding="utf-8"))
    assert "offset" not in saved and "offset" not in pty.t.get(m["id"])


# What a program printed in the last FRESH s is not history yet: an agent opened from another view queries the
# terminal on startup (crossterm's cursor position, which Codex waits 2 s for) before the canvas mounts and lists it.
def test_output_fresher_than_two_seconds_is_not_listed_as_history(pty, monkeypatch):
    assert pty.t.FRESH == 2.0
    monkeypatch.setattr(pty.t, "FRESH", 60)
    m = pty.open()
    until(lambda: b"ready" in screen(pty.t, m["id"]))
    pty.t.write(m["id"], "hola\r")
    until(lambda: b"echo hola (4)" in screen(pty.t, m["id"]))
    assert next(x for x in pty.t.listing() if x["id"] == m["id"])["offset"] == 0      # all of it is fresh
    monkeypatch.setattr(pty.t, "FRESH", 0.2)                                            # quiet for that long: all old
    until(lambda: next(x for x in pty.t.listing() if x["id"] == m["id"])["offset"] == pty.t.read(m["id"], 0)[1])


def test_output_is_kept_in_a_ring_and_a_log_both_bounded(pty, monkeypatch):
    monkeypatch.setattr(pty.t, "RING", 16 * 1024)
    monkeypatch.setattr(pty.t, "LOG_MAX", 64 * 1024)
    monkeypatch.setattr(pty.t, "LOG_SLACK", 16 * 1024)
    m = pty.open()
    until(lambda: b"ready" in screen(pty.t, m["id"]))
    for _ in range(10):
        pty.t.write(m["id"], "bytes 20000\r")
    pty.t.write(m["id"], "hola\r")
    until(lambda: b"echo hola (4)" in screen(pty.t, m["id"]))      # everything before it is out too
    data, end = pty.t.read(m["id"], 0)
    assert len(data) <= 16 * 1024 and end > 200_000
    assert pty.t.read(m["id"], end) == (b"", end)
    assert pty.t.read(m["id"], end + 999)[0] == data                   # a stale offset reads from the ring's start
    log = (pty.t.DIR / f"{m['id']}.log").read_bytes()
    assert 64 * 1024 <= len(log) <= 80 * 1024 and log.endswith(data)


def test_accents_are_kept_as_the_program_wrote_them(pty):
    m = pty.open()
    until(lambda: b"ready" in screen(pty.t, m["id"]))
    pty.t.write(m["id"], "accents\r")
    until(lambda: "año ─ fin".encode() in screen(pty.t, m["id"]))


def test_a_big_paste_is_written_whole(pty):
    m = pty.open()
    until(lambda: b"ready" in screen(pty.t, m["id"]))
    pty.t.write(m["id"], "a\r" * 20_000 + "end\r")                     # far more than a PTY's input buffer
    until(lambda: b"echo end (3)" in screen(pty.t, m["id"]), timeout=60)


@pytest.mark.skipif(sys.platform == "win32", reason="ConPTY keeps its own input buffer")
def test_input_to_a_program_that_does_not_read_gives_up(pty, monkeypatch):
    monkeypatch.setattr(pty.t, "INPUT_WAIT", 0.5)
    m = pty.open([sys.executable, "-c", "import time; print('asleep', flush=True); time.sleep(60)"])
    until(lambda: b"asleep" in screen(pty.t, m["id"]))
    with pytest.raises(TimeoutError):
        pty.t.write(m["id"], "y\r" * 100_000)    # whole lines: past its line limit a tty drops input, never waits


def test_closing_kills_the_program_and_what_it_started_then_forgets_it(pty):
    from lib.harness.locks import pid_alive
    m = pty.open([sys.executable, "-c", "import subprocess, sys, time; "
                  "p = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)']); "
                  "print('child', p.pid, flush=True); time.sleep(60)"])
    until(lambda: re.search(rb"child (\d+)", screen(pty.t, m["id"])))
    child = int(re.search(rb"child (\d+)", screen(pty.t, m["id"])).group(1))
    pty.t.close(m["id"])
    until(lambda: pty.t.get(m["id"])["ended"])
    assert pty.t.get(m["id"])["closed"] is True
    until(lambda: not pid_alive(child))
    assert pty.t.close(m["id"])["forgotten"] is True
    assert m["id"] not in [x["id"] for x in pty.t.listing()]


def test_shutdown_ends_every_terminal(pty):
    from lib.harness.locks import pid_alive
    a, b = pty.open(), pty.open()
    pty.t.shutdown()
    assert all(pty.t.get(x["id"])["ended"] for x in (a, b))
    until(lambda: not pid_alive(a["pid"]) and not pid_alive(b["pid"]))


@pytest.mark.skipif(sys.platform == "win32", reason="groups and SIGHUP are POSIX; taskkill /T /F takes the tree")
def test_shutdown_also_kills_what_ignores_the_hang_up(pty, monkeypatch):
    from lib.harness.locks import pid_alive
    monkeypatch.setattr(pty.t, "CLOSE_GRACE", 60)                      # a closed one: shutdown kills it, not Close
    stubborn = [sys.executable, "-c", "import subprocess, sys, time; subprocess.Popen([sys.executable, '-c', "
                "'import os, signal, time; signal.signal(signal.SIGHUP, signal.SIG_IGN); "
                "print(\"stubborn\", os.getpid(), flush=True); time.sleep(60)']); time.sleep(60)"]
    a, b = pty.open(stubborn), pty.open(stubborn)
    until(lambda: all(re.search(rb"stubborn (\d+)", screen(pty.t, x["id"])) for x in (a, b)))
    kids = [int(re.search(rb"stubborn (\d+)", screen(pty.t, x["id"])).group(1)) for x in (a, b)]
    pty.t.close(b["id"])
    pty.t.shutdown()
    until(lambda: not any(pid_alive(k) for k in kids))


def test_the_ninth_terminal_is_refused(pty, monkeypatch):
    assert pty.t.MAX_LIVE == 8
    monkeypatch.setattr(pty.t, "MAX_LIVE", 2)
    a, _ = pty.open(), pty.open()
    with pytest.raises(pty.t.Limit):
        pty.open()
    pty.t.close(a["id"])
    until(lambda: pty.t.get(a["id"])["ended"])
    pty.open()                                                         # room again


def test_a_unit_terminal_closes_its_session_record(pty, kit):
    from lib import sessions
    rec = sessions.start("discovery:api", "claude", None)
    m = pty.t.spawn(sessions.wrap(rec, [sys.executable, str(ECHO)]), kit.root, kind="unit", unit="discovery:api",
                    agent="claude")
    assert m["id"].startswith("t-discovery_api-")
    until(lambda: sessions.running(sessions.load("discovery:api")))      # inside session_run, as in a window
    assert pty.t.find("unit", "discovery:api")["id"] == m["id"]
    pty.t.close(m["id"])
    until(lambda: (sessions.load("discovery:api") or {}).get("ended"))
    assert not sessions.live(sessions.load("discovery:api")) and pty.t.find("unit", "discovery:api") is None


def test_a_record_taken_by_a_newer_session_is_left_alone(pty, kit):
    from lib import sessions
    rec = sessions.start("discovery:api", "claude", None)
    m = pty.t.spawn(sessions.wrap(rec, [sys.executable, str(ECHO)]), kit.root, kind="unit", unit="discovery:api",
                    agent="claude")
    until(lambda: sessions.running(sessions.load("discovery:api")))
    sessions.start("discovery:api", "codex", None)                       # a new session took the record
    pty.t.close(m["id"])
    until(lambda: pty.t.get(m["id"])["ended"])
    with pty.t._term(m["id"]).finishing:                                 # its end, the record's included, is done
        pass
    assert "ended" not in sessions.load("discovery:api")


def test_old_terminal_files_are_pruned_when_the_first_one_opens(pty, monkeypatch):
    monkeypatch.setattr(pty.t, "KEEP", 3)
    pty.t.DIR.mkdir(parents=True, exist_ok=True)
    for i in range(5):
        for ext in (".json", ".log"):
            f = pty.t.DIR / f"t-old-{i}{ext}"
            f.write_text("{}", encoding="utf-8")
            os.utime(f, (1000 + i, 1000 + i))
    m = pty.open()
    left = sorted(p.name for p in pty.t.DIR.glob("*.json"))
    assert left == sorted([f"{m['id']}.json", "t-old-3.json", "t-old-4.json"])
    assert not (pty.t.DIR / "t-old-0.log").exists()


# Windows, on every OS: a stand-in for pywinpty 3.1.0 (winpty.PTY, the Rust binding, and winpty.PtyProcess, its Python
# wrapper) with the two behaviours that bit. PtyProcess.spawn passes argv[0] unquoted as the application name and
# winpty-rs puts it in front of the command line, so a python.exe under "Program Files" ran as "C:\Program".
# PtyProcess.isalive() marks the process closed, after which close() leaves its two sockets open.
class FakePTY:
    def __init__(self, cols, rows, backend=None):
        self.size, self.alive, self.code, self.spawned, self.pid = (cols, rows), True, None, None, 4242

    def spawn(self, appname, cmdline=None, cwd=None, env=None):
        self.spawned = {"appname": appname, "cmdline": cmdline, "cwd": cwd, "env": env}
        return True

    def isalive(self):
        return self.alive

    def get_exitstatus(self):
        return self.code

    def set_size(self, cols, rows):
        self.size = (cols, rows)


class FakePtyProcess:
    def __init__(self, pty):
        assert isinstance(pty, FakePTY)
        self.pty, self.pid, self.closed = pty, pty.pid, False
        self.fileobj, self._server = socket.socketpair()

    @classmethod
    def spawn(cls, argv, cwd=None, env=None, dimensions=(24, 80)):
        pty = FakePTY(dimensions[1], dimensions[0])
        pty.spawn(argv[0], cwd=cwd, env="\0".join(f"{k}={v}" for k, v in env.items()) + "\0",
                  cmdline=" " + subprocess.list2cmdline(argv[1:]))
        return cls(pty)

    @property
    def exitstatus(self):
        return self.pty.get_exitstatus()

    def isalive(self):
        alive = self.pty.isalive()
        self.closed = not alive
        return alive

    def close(self, force=False):
        if not self.closed:
            self.fileobj.close()
            self._server.close()
            self.closed = True

    def read(self, size=1024):
        data = self.fileobj.recv(size)
        if not data:
            raise EOFError("Pty is closed")
        return data.decode("utf-8")

    def setwinsize(self, rows, cols):
        self.pty.set_size(cols, rows)


@pytest.fixture
def conpty(kit, monkeypatch):
    from lib import terminals
    monkeypatch.setitem(sys.modules, "winpty", SimpleNamespace(PTY=FakePTY, PtyProcess=FakePtyProcess))
    monkeypatch.setattr(terminals, "IS_WIN", True)
    monkeypatch.setattr(terminals, "TICK", 0.05)
    killed = []
    monkeypatch.setattr(terminals, "kill_tree", lambda pid, sig=None: killed.append(pid))
    terminals.available.cache_clear()
    yield SimpleNamespace(t=terminals, killed=killed)
    terminals.shutdown()
    terminals.available.cache_clear()


def test_on_windows_the_program_is_quoted_and_its_args_are_one_command_line(conpty, tmp_path):
    exe = r"C:\Program Files\Python 3.13\python.exe"
    argv = [exe, r"C:\kit dir\session_run.py", "-", "--", "claude", "--model", "x y"]
    proc, fd = conpty.t._start(argv, tmp_path, {"A": "1", "PATH": r"C:\bin"}, 100, 30)
    assert fd is None and isinstance(proc, FakePtyProcess) and proc.pty.size == (100, 30)
    assert proc.pty.spawned == {"appname": f'"{exe}"', "cmdline": r'"C:\kit dir\session_run.py" - -- claude --model "x y"',
                                "cwd": str(tmp_path), "env": "A=1\0PATH=" + "C:\\bin" + "\0"}


def test_on_windows_a_program_that_ended_lets_go_of_its_sockets(conpty, kit):
    m = conpty.t.spawn([sys.executable, "-c", "pass"], kit.root, kind="update", agent="test")
    proc = conpty.t._term(m["id"]).proc
    proc.pty.code, proc.pty.alive = 0, False              # it exited; nothing more to read, the socket still open
    until(lambda: conpty.t.get(m["id"])["ended"])
    assert conpty.t.get(m["id"])["code"] == 0
    assert proc.fileobj.fileno() == -1 and proc._server.fileno() == -1
