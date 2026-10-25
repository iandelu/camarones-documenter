"""File locks (R9): one writer at a time for plan.yaml and OpenWiki runs, across processes and threads, on every OS.
A lock left by a dead process (or older than its TTL, for another machine) is taken over."""
from __future__ import annotations

import json, os, socket, subprocess, sys, threading, time

import pytest


@pytest.fixture
def locks(kit):
    from lib.harness import locks
    return locks


def dead_pid() -> int:
    p = subprocess.Popen([sys.executable, "-c", "pass"])
    p.wait()
    return p.pid


def test_a_lock_is_exclusive_and_released(locks, tmp_path):
    path = tmp_path / "x.lock"
    with locks.FileLock(path, info={"repo": "api"}):
        held = json.loads(path.read_text(encoding="utf-8"))
        assert held["pid"] == os.getpid() and held["host"] == socket.gethostname() and held["repo"] == "api"
    assert not path.exists()


def test_reentrant_in_the_same_thread(locks, tmp_path):
    lock = locks.FileLock(tmp_path / "x.lock")
    with lock:
        with locks.FileLock(tmp_path / "x.lock", wait=0):
            pass
        assert (tmp_path / "x.lock").exists()
    assert not (tmp_path / "x.lock").exists()


def test_another_thread_waits_its_turn(locks, tmp_path):
    order = []

    def worker(name):
        with locks.FileLock(tmp_path / "x.lock", wait=5):
            order.append(f"{name}+")
            time.sleep(0.05)
            order.append(f"{name}-")
    threads = [threading.Thread(target=worker, args=(n,)) for n in "ab"]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert order in (["a+", "a-", "b+", "b-"], ["b+", "b-", "a+", "a-"])


def test_a_live_holder_makes_it_busy(locks, tmp_path):
    path = tmp_path / "x.lock"
    path.write_text(json.dumps({"pid": os.getpid(), "host": socket.gethostname(), "ts": time.time(), "repo": "web"}),
                    encoding="utf-8")
    with pytest.raises(locks.LockBusy) as e:
        with locks.FileLock(path, wait=0):
            pass
    assert e.value.holder["repo"] == "web"


def test_a_dead_holder_is_taken_over(locks, tmp_path):
    path = tmp_path / "x.lock"
    path.write_text(json.dumps({"pid": dead_pid(), "host": socket.gethostname(), "ts": time.time()}), encoding="utf-8")
    with locks.FileLock(path, wait=0):
        assert json.loads(path.read_text(encoding="utf-8"))["pid"] == os.getpid()


def test_another_machines_lock_expires_only_after_its_ttl(locks, tmp_path):
    path = tmp_path / "x.lock"
    path.write_text(json.dumps({"pid": 1, "host": "elsewhere", "ts": time.time()}), encoding="utf-8")
    with pytest.raises(locks.LockBusy):
        with locks.FileLock(path, wait=0, ttl=60):
            pass
    path.write_text(json.dumps({"pid": 1, "host": "elsewhere", "ts": time.time() - 120}), encoding="utf-8")
    with locks.FileLock(path, wait=0, ttl=60):
        pass


def test_reentrancy_never_depends_on_resolving_the_lock_file(locks, tmp_path, monkeypatch):
    """On Windows resolving the lock file opens it, and while another process reads or deletes it the result can
    differ: the holder then waited for itself until LockBusy."""
    path = tmp_path / "x.lock"
    real = type(path).resolve

    def resolve(self, *a, **kw):
        if self.name == "x.lock" and self.exists():
            return type(path)(str(tmp_path).upper()) / "X.LOCK"
        return real(self, *a, **kw)
    with locks.FileLock(path):
        monkeypatch.setattr(type(path), "resolve", resolve)
        with locks.FileLock(path, wait=0):
            pass
        assert path.exists()
    assert not path.exists()


def busy_once(monkeypatch, obj, name):
    """obj.name raises PermissionError the first time, as on Windows while another process reads the lock file."""
    real, calls = getattr(obj, name), []

    def fn(*a, **kw):
        calls.append(a)
        if len(calls) == 1:
            raise PermissionError(13, "in use")
        return real(*a, **kw)
    monkeypatch.setattr(obj, name, fn)
    return calls


def test_release_waits_out_a_reader_holding_the_lock_file(locks, tmp_path, monkeypatch):
    path = tmp_path / "x.lock"
    with locks.FileLock(path):
        calls = busy_once(monkeypatch, type(path), "unlink")
    assert not path.exists() and len(calls) == 2


def test_acquire_waits_out_a_lock_file_being_deleted(locks, tmp_path, monkeypatch):
    path = tmp_path / "x.lock"
    monkeypatch.setattr(locks, "IS_WIN", True)
    calls = busy_once(monkeypatch, locks.os, "open")         # Windows: a file pending delete cannot be created
    with locks.FileLock(path, wait=5):
        assert path.exists()
    assert len(calls) == 2


def test_liveness_is_asked_of_the_os_without_a_child_process(locks, monkeypatch):
    def no_child(*_a, **_kw):                   # tasklist could fail or time out under load and free a live lock
        raise AssertionError("pid_alive must not spawn a process")
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    monkeypatch.setattr(subprocess, "run", no_child)
    monkeypatch.setattr(subprocess, "Popen", no_child)
    try:
        assert locks.pid_alive(os.getpid()) and locks.pid_alive(child.pid)
    finally:
        child.kill()
        child.wait()
    assert not locks.pid_alive(child.pid)


def test_a_lock_written_by_an_older_kit_is_understood(locks, tmp_path):
    path = tmp_path / "wiki.lock"
    path.write_text(json.dumps({"pid": dead_pid(), "repo": "api"}), encoding="utf-8")       # 3.x format: no host, no ts
    with locks.FileLock(path, wait=0):
        pass


WRITER = """
import sys
sys.path.insert(0, sys.argv[1])
from lib import plan
tag = sys.argv[2]
for i in range(50):
    plan.add(f"flow:{tag}-{i}", f"Flow {tag} {i}")
    plan.set_status("ci", "doing", note=f"{tag}-{i}")
"""


def test_two_processes_writing_the_plan_lose_nothing(kit):
    kit.plan.sync()
    env = {**os.environ, "CAMARONES_ROOT": str(kit.root)}
    procs = [subprocess.Popen([sys.executable, "-c", WRITER, str(kit.kit_dir), tag], env=env) for tag in "ab"]
    assert [p.wait(timeout=120) for p in procs] == [0, 0]
    ids = {u["id"] for u in kit.plan.load()["units"]}
    assert {f"flow:{t}-{i}" for t in "ab" for i in range(50)} <= ids


def test_the_plan_lock_lives_outside_git(kit):
    lock = kit.plan.PLAN_LOCK
    assert ".cache" in lock.parts and kit.common.CTX.state_root in lock.parents


def test_only_one_wiki_run_at_a_time(kit, tmp_path):
    env = kit.env
    env.WIKI_LOCK.parent.mkdir(parents=True, exist_ok=True)
    env.WIKI_LOCK.write_text(json.dumps({"pid": os.getpid(), "host": socket.gethostname(), "ts": time.time(),
                                         "repo": "web"}), encoding="utf-8")
    with pytest.raises(RuntimeError, match="another OpenWiki run is in progress \\(web"):
        with env.wiki_lock("api"):
            pass
    env.WIKI_LOCK.unlink()
    with env.wiki_lock("api"):
        assert json.loads(env.WIKI_LOCK.read_text(encoding="utf-8"))["repo"] == "api"
    assert not env.WIKI_LOCK.exists()


def test_a_busy_plan_inside_a_wiki_run_is_not_reported_as_a_wiki_run(kit, locks):
    with pytest.raises(locks.LockBusy):
        with kit.env.wiki_lock("api"):
            raise locks.LockBusy(kit.plan.PLAN_LOCK, {"pid": 1})
    assert not kit.env.WIKI_LOCK.exists()
