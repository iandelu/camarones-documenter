"""PTYs in the project server (lib/terminals.py): a real terminal per session, on every OS (pywinpty on Windows)."""
from __future__ import annotations

import json, re, sys, time
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
