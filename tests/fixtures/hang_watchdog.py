"""A test that never returns must not hold CI until its job limit with nothing to show for it: xdist cannot report a
worker that does not answer. Past LIMIT seconds the worker dumps every thread's stack and exits, from faulthandler's C
thread, which needs no GIL. xdist then reports the test as crashed and the run ends (--max-worker-restart=0 in
pyproject.toml); its summary shows the dump."""
from __future__ import annotations

import faulthandler, os, shutil, tempfile
from pathlib import Path

import pytest

LIMIT = float(os.environ.get("CAMARONES_TEST_HANG_LIMIT", 600))
DUMPS = "CAMARONES_TEST_HANG_DUMPS"     # a folder the workers inherit: a test's capture swallows a worker's stderr
_dump = None


def pytest_configure(config) -> None:
    if not hasattr(config, "workerinput"):
        os.environ[DUMPS] = tempfile.mkdtemp(prefix="camaron-hangs-")


@pytest.hookimpl(wrapper=True)
def pytest_runtest_protocol(item):
    global _dump
    if _dump is None:
        _dump = (Path(os.environ[DUMPS]) / f"{os.getpid()}.txt").open("w", encoding="utf-8")
    faulthandler.dump_traceback_later(LIMIT, exit=True, file=_dump)
    try:
        return (yield)
    finally:
        faulthandler.cancel_dump_traceback_later()


def pytest_terminal_summary(terminalreporter) -> None:
    for f in sorted(Path(os.environ[DUMPS]).glob("*.txt")):
        text = f.read_text(encoding="utf-8", errors="replace").strip()
        if text:
            terminalreporter.section(f"a hung test's worker, past {LIMIT:.0f} s")
            terminalreporter.line(text)


def pytest_unconfigure(config) -> None:
    if not hasattr(config, "workerinput"):
        shutil.rmtree(os.environ.pop(DUMPS, ""), ignore_errors=True)
