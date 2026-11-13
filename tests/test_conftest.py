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


def test_a_folder_that_cannot_go_does_not_stop_the_others(tmp_path):
    reaper = Reaper()
    (tmp_path / "a-file").write_text("x", encoding="utf-8")       # rmtree refuses a file: the child carries on
    reaper.drop(tmp_path / "a-file")
    reaper.drop(tree(tmp_path / "good"))
    reaper.wait()
    assert (tmp_path / "a-file").exists() and not (tmp_path / "good").exists()


def test_a_missing_folder_is_no_error(tmp_path):
    reaper = Reaper()
    reaper.drop(tmp_path / "never-made")
    reaper.wait()


def test_a_tests_patches_never_reach_the_deleting(tmp_path, monkeypatch):
    """A test may patch an os function for the whole process (test_locks patches os.open); the folders of the tests
    before it are deleted where that patch cannot see them, nor they it."""
    seen, real = [], os.rmdir
    monkeypatch.setattr(os, "rmdir", lambda *a, **kw: (seen.append(a), real(*a, **kw))[1])
    reaper = Reaper()
    folder = tree(tmp_path / "t")
    reaper.drop(folder)
    reaper.wait()
    assert not folder.exists() and seen == []


def test_a_server_a_test_starts_stops_at_once():
    srv = ThreadingHTTPServer(("127.0.0.1", 0), BaseHTTPRequestHandler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    time.sleep(0.05)
    started = time.monotonic()
    srv.shutdown()
    srv.server_close()
    assert time.monotonic() - started < 0.25
