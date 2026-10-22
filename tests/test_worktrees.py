"""Unit worktrees (R11): a parallel unit writes its docs in its own cam-docs git worktree at <workspace>/.cw/<n>, on
branch cam/u/<n>-<unit>. Short numeric folders keep Windows paths valid and short; a killed run finds its worktree
again; the agent still sees every repo because the workspace stays the real one."""
from __future__ import annotations

import subprocess

import pytest

from conftest import load_kit
from fixtures.builder import rmtree


def git(path, *args):
    return subprocess.run(["git", *args], cwd=path, capture_output=True, text=True, check=True).stdout.strip()


@pytest.fixture
def wt(wired):
    from lib.harness.worktrees import Worktrees
    return Worktrees(wired.common.CTX)


def test_a_unit_gets_a_short_valid_folder_and_its_own_branch(wired, wt):
    w = wt.add("discovery:api")
    assert w.path == (wired.ws / ".cw" / "1").resolve() and w.n == 1
    assert w.branch == "cam/u/1-discovery-api"
    assert git(w.path, "rev-parse", "--abbrev-ref", "HEAD") == w.branch
    assert (w.path / "docs" / "overview.md").exists()                     # starts from the main cam-docs HEAD
    assert w.branch in git(wired.root, "branch", "--list", w.branch)


def test_numbers_are_reused_once_free(wt):
    a, b = wt.add("discovery:api"), wt.add("discovery:web")
    assert (a.n, b.n) == (1, 2)
    wt.remove("discovery:api")
    assert wt.add("flow:checkout").n == 1


def test_a_killed_run_finds_its_worktree_and_uncommitted_work(wired, wt):
    from lib.harness.worktrees import Worktrees
    w = wt.add("discovery:api")
    (w.path / "docs" / "draft.md").write_text("half done", encoding="utf-8")
    again = Worktrees(wired.common.CTX).add("discovery:api")              # a new process after a crash
    assert again.path == w.path and (again.path / "docs" / "draft.md").read_text(encoding="utf-8") == "half done"


def test_a_deleted_folder_is_rebuilt_from_its_branch(wired, wt):
    w = wt.add("discovery:api")
    (w.path / "docs" / "kept.md").write_text("committed", encoding="utf-8")
    git(w.path, "add", "-A")
    git(w.path, "commit", "-qm", "unit work")
    rmtree(w.path)
    again = wt.add("discovery:api")
    assert again.branch == w.branch and (again.path / "docs" / "kept.md").read_text(encoding="utf-8") == "committed"


def test_remove_leaves_no_folder_branch_or_registration(wired, wt):
    w = wt.add("discovery:api")
    (w.path / "docs" / "x.md").write_text("dirty", encoding="utf-8")
    wt.remove("discovery:api")
    assert not w.path.exists() and not git(wired.root, "branch", "--list", w.branch)
    assert str(w.path) not in git(wired.root, "worktree", "list") and wt.get("discovery:api") is None


def test_prune_forgets_worktrees_whose_folder_and_branch_are_gone(wired, wt):
    w = wt.add("discovery:api")
    rmtree(w.path)
    git(wired.root, "worktree", "prune")
    git(wired.root, "branch", "-D", w.branch)
    wt.prune()
    assert wt.get("discovery:api") is None and wt.list() == []


def test_windows_gets_long_paths(wired, monkeypatch):
    from lib.harness import worktrees
    monkeypatch.setattr(worktrees, "IS_WIN", True)
    worktrees.Worktrees(wired.common.CTX).add("discovery:api")
    assert git(wired.root, "config", "core.longpaths") == "true"


def test_worktrees_are_not_taken_for_repos(wired, wt):
    wt.add("discovery:api")
    assert ".cw" not in {r["name"] for r in wired.docs.detect_repos()}


def test_a_worktree_context_reads_its_tree_keeps_state_in_main_and_sees_the_repos(wired, wt, monkeypatch):
    w = wt.add("discovery:api")
    from lib.harness.ctx import Ctx
    ctx = Ctx.for_root(w.path, state_root=wired.root, workspace=wired.ws)
    assert ctx.docs == w.path / "docs" and ctx.work == wired.root.resolve() / "docs" / ".work"
    assert ctx.workspace == wired.ws.resolve() and ctx.ws_rel("docs/a.md") == ".cw/1/docs/a.md"
    monkeypatch.setenv("CAMARONES_STATE_ROOT", str(wired.root))
    monkeypatch.setenv("CAMARONES_WORKSPACE", str(wired.ws))
    k = load_kit(w.path, wired.home, wired.ws)
    assert k.common.WORKSPACE == wired.ws.resolve() and k.common.repo_dir("api") == wired.ws.resolve() / "api"
    assert k.common.ws_rel("docs/a.md") == ".cw/1/docs/a.md"


def test_ws_rel_is_unchanged_for_the_main_tree(kit):
    assert kit.common.ws_rel("docs/a.md") == "cam-docs/docs/a.md"


def test_uninstall_removes_unit_worktrees(wired, wt):
    wt.add("discovery:api")
    import importlib
    un = importlib.import_module("lib.uninstall")
    assert any(".cw" in s.label for s in un.steps() if s.kind == "delete")
    un.run(backup=False, log=lambda _: None)
    assert not (wired.ws / ".cw").exists()


def test_a_worktree_session_is_told_where_to_write_and_not_to_checkpoint(wired, wt, monkeypatch):
    wired.plan.sync()
    w = wt.add("discovery:api")
    monkeypatch.setenv("CAMARONES_STATE_ROOT", str(wired.root))
    monkeypatch.setenv("CAMARONES_WORKSPACE", str(wired.ws))
    k = load_kit(w.path, wired.home, wired.ws)
    text = k.plan.prompt("discovery:api", "en", unattended=True)
    assert "`.cw/1/`" in text and "checkpoint" not in text
    assert "cam-docs/docs/.work/handoff.md" in text                     # the shared handoff, read from main
    assert "cam-docs/docs/.work/units/discovery__api.handoff.md" in text   # this unit's own handoff
    assert "`.cw/1/.camarones/PLAYBOOK.md`" in text
    kit_cmd = f'run --quiet --script "{k.common.KIT / "camarones.py"}"'
    assert kit_cmd in text and "`camaron plan" not in text          # this exact kit, not whatever is on PATH


def test_the_main_session_prompt_is_unchanged(wired):
    wired.plan.sync()
    text = wired.plan.prompt("discovery:api", "en", unattended=True)
    assert "checkpoint \"discovery:api\"" in text and "`cam-docs/docs/.work/handoff.md`" in text and ".cw/" not in text


def test_cli_checkpoints_work_from_a_unit_worktree(wired, wt):
    """Found on the sandbox (eval comply): `plan note` printed the checkpoint path relative to the worktree, but the
    notes live in main's state root, so it crashed after saving."""
    import os, sys
    from conftest import KIT_DIR
    wired.plan.sync()
    w = wt.add("discovery:api")
    env = {**os.environ, "CAMARONES_ROOT": str(w.path), "CAMARONES_STATE_ROOT": str(wired.root),
           "CAMARONES_WORKSPACE": str(wired.ws)}
    cli = lambda *a: subprocess.run([sys.executable, str(KIT_DIR / "camarones.py"), *a], env=env,  # noqa: E731
                                    capture_output=True, text=True, encoding="utf-8")
    r = cli("plan", "note", "discovery:api", "half done")
    assert r.returncode == 0 and "cam-docs/docs/.work/units/" in r.stdout, r.stderr
    assert "half done" in wired.plan.last_note("discovery:api")
    r = cli("feedback", "docs/overview.md", "too long", "--by", "ana")
    assert r.returncode == 0, r.stderr
