"""Global self-update: the central kit clone follows its upstream even when upstream history was rewritten, but never
throws away work that only exists in the clone."""
from __future__ import annotations

import importlib, os, shutil, subprocess
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


# ---------- official source, update check, installer ----------
REPO = Path(__file__).resolve().parent.parent


def kit_repo(path: Path, version: str) -> Path:
    """A minimal kit git repo whose .camarones/lib/common.py declares `version`."""
    lib = path / ".camarones" / "lib"
    lib.mkdir(parents=True)
    (lib / "common.py").write_text(f'VERSIONS = {{\n    "kit": "{version}",\n}}\n', encoding="utf-8")
    git(path, "init", "-q", "-b", "main")
    git(path, "add", ".")
    git(path, "commit", "-q", "-m", "feat: kit")
    return path


def bump(repo: Path, version: str) -> None:
    commit(repo, ".camarones/lib/common.py", f'VERSIONS = {{\n    "kit": "{version}",\n}}\n', f"feat: {version}")


@pytest.fixture
def central(kit, tmp_path, monkeypatch):
    """Upstream kit + a central clone of it; CAMARONES_KIT_URL points at the upstream (the "official" kit offline)."""
    upgrade = importlib.import_module("lib.upgrade")
    upstream = kit_repo(tmp_path / "official", upgrade.current())
    local = tmp_path / "central"
    git(tmp_path, "clone", "-q", str(upstream), str(local))
    monkeypatch.setenv("CAMARONES_KIT_URL", str(upstream))
    return upgrade, upstream, local


def test_check_reports_what_upstream_has(central):
    upgrade, upstream, local = central
    assert upgrade.check(local)["behind"] == 0
    bump(upstream, "9.9.9")
    commit(upstream, "notes.txt", "n\n", "docs: notes")
    info = upgrade.check(local)
    assert info == {"current": upgrade.current(), "latest": "9.9.9", "behind": 2}
    assert git(local, "rev-parse", "HEAD") != git(upstream, "rev-parse", "HEAD")      # checking never updates


def test_check_fails_cleanly_when_upstream_is_unreachable(central, monkeypatch, tmp_path):
    upgrade, _, local = central
    monkeypatch.setenv("CAMARONES_KIT_URL", str(tmp_path / "gone"))
    with pytest.raises(RuntimeError, match="could not reach"):
        upgrade.check(local)


def test_old_install_following_a_local_checkout_moves_to_the_official_kit(central, tmp_path):
    """Installs made before 3.8 cloned from the installer's checkout: origin was a folder, not the official repo."""
    upgrade, upstream, _ = central
    checkout = tmp_path / "my-checkout"
    git(tmp_path, "clone", "-q", str(upstream), str(checkout))
    old = tmp_path / "old-central"
    git(tmp_path, "clone", "-q", str(checkout), str(old))
    assert upgrade.ensure_origin(old) is True
    assert git(old, "remote", "get-url", "origin") == str(upstream)
    assert upgrade.ensure_origin(old) is False


def test_a_fork_origin_is_left_alone(central):
    upgrade, _, local = central
    git(local, "remote", "set-url", "origin", "https://example.com/me/fork.git")
    assert upgrade.ensure_origin(local) is False
    assert git(local, "remote", "get-url", "origin") == "https://example.com/me/fork.git"


def test_self_update_moves_the_origin_then_pulls(central, tmp_path, monkeypatch):
    upgrade, upstream, _ = central
    checkout = tmp_path / "my-checkout"
    git(tmp_path, "clone", "-q", str(upstream), str(checkout))
    old = tmp_path / "old-central"
    git(tmp_path, "clone", "-q", str(checkout), str(old))
    commit(upstream, "fix.txt", "fix\n", "fix: something")
    monkeypatch.setenv("CAMARONES_GLOBAL", "1")
    upgrade.self_update(lambda _m: None, repo=old)
    assert git(old, "remote", "get-url", "origin") == str(upstream)
    assert git(old, "rev-parse", "HEAD") == git(upstream, "rev-parse", "HEAD")


def test_self_update_refuses_a_project_local_kit(central):
    upgrade, _, local = central
    with pytest.raises(RuntimeError, match="local kit copy"):
        upgrade.self_update(lambda _m: None, repo=local)


@pytest.mark.skipif(not shutil.which("uv"), reason="the installer needs uv")
def test_installer_clones_the_official_kit_without_a_checkout(central, tmp_path):
    _, upstream, _ = central
    home = tmp_path / "fresh-home"
    home.mkdir()
    env = {**os.environ, "HOME": str(home), "USERPROFILE": str(home), "LOCALAPPDATA": str(home / "AppData"),
           "SHELL": "/bin/sh", "CAMARONES_KIT_URL": str(upstream)}
    if os.name == "nt":
        bindir = home / ".local" / "bin"
        env["PATH"] = f"{bindir};{env['PATH']}"                       # already on PATH: the installer never runs setx
        cmd, central_dir = ["cmd", "/c", str(REPO / "install-global.cmd")], home / "AppData" / "camarones-documenter" / "kit"
        launcher = bindir / "camaron.cmd"
    else:
        cmd, central_dir = ["sh", str(REPO / "install-global.sh")], home / ".camarones" / "kit"
        launcher = home / ".local" / "bin" / "camaron"
    for _ in range(2):                                                # second run updates in place
        r = subprocess.run(cmd, cwd=tmp_path, env=env, stdin=subprocess.DEVNULL, capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        assert r.returncode == 0, r.stdout + r.stderr
    assert git(central_dir, "remote", "get-url", "origin") == str(upstream)
    assert launcher.exists()
