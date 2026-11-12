"""What conftest does around every test: a passing test's tmp_path goes in the background, and a server a test starts
stops as soon as it is told to."""
from __future__ import annotations

import os
import stat
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from fixtures.reaper import Reaper


def tree(base):
    (base / "a" / "b").mkdir(parents=True)
    ro = base / "a" / "b" / "object"
    ro.write_text("x", encoding="utf-8")
    os.chmod(ro, stat.S_IREAD)                  # git's objects are read-only: Windows refuses to delete them as they are
    (base / "top.txt").write_text("y", encoding="utf-8")
    return base


def test_a_dropped_folder_is_gone_once_the_reaper_has_caught_up(tmp_path):
    reaper = Reaper()
    folders = [tree(tmp_path / f"t{i}") for i in range(3)]
    for f in folders:
        reaper.drop(f)
    reaper.wait()
    assert not any(f.exists() for f in folders)


def test_drop_returns_before_the_folder_is_deleted(tmp_path):
    gate = threading.Event()
    reaper = Reaper(remove=lambda p: gate.wait(5))
    started = time.monotonic()
    reaper.drop(tree(tmp_path / "t"))
    assert time.monotonic() - started < 1 and (tmp_path / "t").exists()
    gate.set()
    reaper.wait()


def test_a_folder_that_cannot_go_does_not_stop_the_others(tmp_path):
    calls = []

    def remove(p):
        calls.append(p.name)
        if p.name == "bad":
            raise OSError("held by a child process")
    reaper = Reaper(remove=remove)
    for name in ("bad", "good"):
        reaper.drop(tmp_path / name)
    reaper.wait()
    assert calls == ["bad", "good"]


def test_a_missing_folder_is_no_error(tmp_path):
    reaper = Reaper()
    reaper.drop(tmp_path / "never-made")
    reaper.wait()


def test_a_server_a_test_starts_stops_at_once():
    srv = ThreadingHTTPServer(("127.0.0.1", 0), BaseHTTPRequestHandler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    time.sleep(0.05)
    started = time.monotonic()
    srv.shutdown()
    srv.server_close()
    assert time.monotonic() - started < 0.25
