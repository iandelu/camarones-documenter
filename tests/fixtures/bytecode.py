"""Every test imports `lib` afresh and many run the CLI in a child process. With PYTHONDONTWRITEBYTECODE set, each of
those imports compiles the kit and its dependencies from source again: about a third of a second per test. The run keeps
compiled bytecode instead, in a folder of its own outside the repo and the venv, gone when the run ends; the workers and
every child process inherit it through the environment."""
from __future__ import annotations

import os, shutil, sys, tempfile

import pytest

PREFIX = pytest.StashKey[str]()


def pytest_configure(config) -> None:
    if hasattr(config, "workerinput") or not os.environ.get("PYTHONDONTWRITEBYTECODE"):
        return
    config.stash[PREFIX] = os.environ["PYTHONPYCACHEPREFIX"] = sys.pycache_prefix = tempfile.mkdtemp(prefix="camaron-pyc-")
    del os.environ["PYTHONDONTWRITEBYTECODE"]
    sys.dont_write_bytecode = False


def pytest_unconfigure(config) -> None:
    if PREFIX in config.stash:
        shutil.rmtree(config.stash[PREFIX], ignore_errors=True)
