"""This repo credits people only: .githooks/commit-msg drops AI co-author trailers, pre-push refuses any that slipped
in, and scripts/githooks.py installs both where every worktree finds them."""
from __future__ import annotations

import importlib.util, subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
HOOKS = REPO / ".githooks"
TRAILER = "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
GENERATED = "🤖 Generated with [Claude Code](https://claude.com/claude-code)"
HUMAN = "Co-Authored-By: Ana Pérez <ana@example.com>"


def git(cwd: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=cwd, check=check, capture_output=True, text=True, encoding="utf-8")


def commit(repo: Path, msg: str, *extra: str) -> subprocess.CompletedProcess:
    note = repo.parent / "msg.txt"
    note.write_text(msg, encoding="utf-8")
    target = repo / "f.txt"
    target.write_text(target.read_text(encoding="utf-8") + "x" if target.exists() else "x", encoding="utf-8")
    git(repo, "add", "f.txt")
    return git(repo, "commit", "-q", "-F", str(note), *extra, check=False)


def message(repo: Path, rev: str = "HEAD") -> str:
    return git(repo, "log", "-1", "--format=%B", rev).stdout.strip()


@pytest.fixture
def repo(isolated_env, tmp_path):
    r = tmp_path / "repo"
    r.mkdir()
    git(r, "init", "-q", "-b", "main")
    git(r, "config", "core.hooksPath", str(HOOKS))
    return r


@pytest.fixture
def pushed(repo, tmp_path):
    remote = tmp_path / "remote.git"
    git(tmp_path, "init", "-q", "--bare", "-b", "main", str(remote))
    git(repo, "remote", "add", "origin", str(remote))
    commit(repo, "feat: start")
    git(repo, "push", "-q", "-u", "origin", "main")
    return repo, remote


def test_commit_drops_claude_trailer_and_generated_line(repo):
    assert commit(repo, f"feat: x\n\nbody\n\n{GENERATED}\n\n{TRAILER}\n{HUMAN}\n").returncode == 0
    assert message(repo) == f"feat: x\n\nbody\n\n{HUMAN}"


def test_commit_keeps_people_and_mentions_of_claude(repo):
    msg = "feat(runners): the claude runner reads its model\n\nCo-Authored-By: Claudia Ruiz <claudia@example.com>"
    assert commit(repo, msg).returncode == 0
    assert message(repo) == msg


def test_merge_commit_drops_claude_trailer(repo):
    commit(repo, "feat: base")
    git(repo, "switch", "-q", "-c", "topic")
    commit(repo, "feat: topic")
    git(repo, "switch", "-q", "main")
    git(repo, "merge", "-q", "--no-ff", "topic", "-m", f"Merge topic into main\n\n{TRAILER}")
    assert message(repo) == "Merge topic into main"


def test_push_refuses_a_commit_that_still_credits_claude(pushed):
    repo, remote = pushed
    commit(repo, f"feat: sneaky\n\n{TRAILER}", "--no-verify")
    sha = git(repo, "rev-parse", "--short", "HEAD").stdout.strip()
    result = git(repo, "push", "-q", "origin", "main", check=False)
    assert result.returncode != 0
    assert sha in result.stderr
    assert git(remote, "rev-parse", "main").stdout != git(repo, "rev-parse", "HEAD").stdout


def test_push_checks_only_commits_the_remote_lacks(pushed):
    repo, _ = pushed
    commit(repo, f"feat: old\n\n{TRAILER}", "--no-verify")
    git(repo, "push", "-q", "--no-verify", "origin", "main")
    commit(repo, "feat: clean")
    assert git(repo, "push", "-q", "origin", "main", check=False).returncode == 0
    git(repo, "switch", "-q", "-c", "topic")
    commit(repo, "feat: topic")
    assert git(repo, "push", "-q", "origin", "topic", check=False).returncode == 0


def test_installer_puts_hooks_where_every_worktree_runs_them(isolated_env, tmp_path):
    main = tmp_path / "main"
    main.mkdir()
    git(main, "init", "-q", "-b", "main")
    commit(main, "feat: start")
    wt = tmp_path / "wt"
    git(main, "worktree", "add", "-q", "-b", "side", str(wt))
    spec = importlib.util.spec_from_file_location("githooks", REPO / "scripts" / "githooks.py")
    githooks = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(githooks)

    installed = githooks.install(wt)

    shared = (main / ".git" / "hooks").resolve()
    assert sorted(p.name for p in installed) == ["commit-msg", "pre-push"]
    assert all(p.resolve().parent == shared for p in installed)
    assert commit(wt, f"feat: side\n\n{TRAILER}").returncode == 0
    assert message(wt) == "feat: side"
