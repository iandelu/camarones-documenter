"""Runs keep the computer awake (a real run stopped when a laptop slept mid-session): caffeinate on macOS,
SetThreadExecutionState on Windows, systemd-inhibit on Linux when present; nothing breaks where none applies."""
from __future__ import annotations

import os

import pytest


@pytest.fixture
def awake(kit):
    from lib.harness import awake
    return awake


class FakeProc:
    def __init__(self, argv, **kw):
        self.argv, self.done = argv, False

    def terminate(self):
        self.done = True

    def wait(self, timeout=None):
        return 0


def test_macos_uses_caffeinate_tied_to_this_process(awake, monkeypatch):
    started = []
    monkeypatch.setattr(awake, "IS_MAC", True)
    monkeypatch.setattr(awake, "IS_WIN", False)
    monkeypatch.setattr(awake, "which", lambda n: f"/usr/bin/{n}" if n == "caffeinate" else None)
    monkeypatch.setattr(awake.subprocess, "Popen", lambda argv, **kw: started.append(FakeProc(argv)) or started[-1])
    with awake.keep_awake() as how:
        assert how == "caffeinate"
        assert started[0].argv == ["/usr/bin/caffeinate", "-i", "-w", str(os.getpid())]
    assert started[0].done


def test_linux_uses_systemd_inhibit_when_present(awake, monkeypatch):
    started = []
    monkeypatch.setattr(awake, "IS_MAC", False)
    monkeypatch.setattr(awake, "IS_WIN", False)
    monkeypatch.setattr(awake, "which", lambda n: "/usr/bin/systemd-inhibit" if n == "systemd-inhibit" else None)
    monkeypatch.setattr(awake.subprocess, "Popen", lambda argv, **kw: started.append(FakeProc(argv)) or started[-1])
    with awake.keep_awake() as how:
        assert how == "systemd-inhibit" and started[0].argv[:2] == ["/usr/bin/systemd-inhibit", "--what=sleep:idle"]
    assert started[0].done


def test_nothing_available_is_fine(awake, monkeypatch):
    monkeypatch.setattr(awake, "IS_MAC", False)
    monkeypatch.setattr(awake, "IS_WIN", False)
    monkeypatch.setattr(awake, "which", lambda n: None)
    with awake.keep_awake() as how:
        assert how is None


def test_runs_keep_the_computer_awake(kit, monkeypatch):
    from lib.harness import awake, scheduler
    used = []
    import contextlib

    @contextlib.contextmanager
    def fake():
        used.append(True)
        yield "test"
    monkeypatch.setattr(awake, "keep_awake", fake)
    monkeypatch.setattr(kit.plan, "which", lambda n: None)                 # no agent: the run ends at once
    scheduler.run_parallel(echo=lambda _: None, poll=0.01)
    kit.plan.run_autopilot(echo=lambda _: None)
    assert len(used) == 1                         # autopilot without agents returns before starting a run
