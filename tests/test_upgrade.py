"""Global self-update: the central kit clone follows its upstream even when upstream history was rewritten, but never
throws away work that only exists in the clone."""
from __future__ import annotations

import importlib, subprocess
from pathlib import Path

import pytest


def git(cwd: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True,
                          encoding="utf-8").stdout.strip()


def commit(repo: Path, name: str, text: str, msg: str) -> None:
    (repo / name).write_text(text, encoding="utf-8")
    git(repo, "add", name)
    git(repo, "commit", "-q", "-m", msg)


@pytest.fixture
def clone(kit, tmp_path):
    upstream = tmp_path / "upstream"
    upstream.mkdir()
    git(upstream, "init", "-q", "-b", "main")
    commit(upstream, "a.txt", "a\n", "feat: a")
    commit(upstream, "b.txt", "b\n", "feat: b\n\nCo-Authored-By: someone")
    local = tmp_path / "kit"
    git(tmp_path, "clone", "-q", str(upstream), str(local))
    git(upstream, "commit", "-q", "--amend", "-m", "feat: b")          # history rewritten upstream, same content
    commit(upstream, "c.txt", "c\n", "feat: c")
    return importlib.import_module("lib.upgrade"), upstream, local


def test_pull_follows_rewritten_upstream_history(clone):
    upgrade, upstream, local = clone
    upgrade.pull_kit(local)
    assert git(local, "rev-parse", "HEAD") == git(upstream, "rev-parse", "HEAD")


def test_pull_keeps_commits_that_only_exist_in_the_clone(clone):
    upgrade, _, local = clone
    commit(local, "mine.txt", "mine\n", "feat: local work")
    head = git(local, "rev-parse", "HEAD")
    with pytest.raises(RuntimeError, match="local commits"):
        upgrade.pull_kit(local)
    assert git(local, "rev-parse", "HEAD") == head


def test_pull_keeps_uncommitted_changes(clone):
    upgrade, _, local = clone
    (local / "a.txt").write_text("edited\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="uncommitted"):
        upgrade.pull_kit(local)
    assert (local / "a.txt").read_text(encoding="utf-8") == "edited\n"
