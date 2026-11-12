"""fixtures/fast_git: on a Mac whose git is Apple's /usr/bin/git, the suite runs the git that one forwards to, without
paying xcrun's lookup on each of its thousands of git processes."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from fixtures import fast_git

links = pytest.mark.skipif(sys.platform == "win32", reason="the shim and its mirror exist only on macOS")


def fake_prefix(root: Path) -> Path:
    """<root>/usr with bin/git, bin/clang and libexec/git-core: the layout of Apple's developer tools."""
    usr = root / "usr"
    for rel in ("bin/git", "bin/clang", "libexec/git-core/git-upload-pack", "share/git-core/templates/x"):
        (usr / rel).parent.mkdir(parents=True, exist_ok=True)
        (usr / rel).write_text("", encoding="utf-8")
    return usr


@links
def test_the_mirror_holds_only_git_and_links_the_rest_of_its_prefix(tmp_path):
    usr = fake_prefix(tmp_path / "dev")
    bin_dir = fast_git.mirror(usr / "bin" / "git", tmp_path / "mirror")
    assert [p.name for p in bin_dir.iterdir()] == ["git"]
    assert (bin_dir / "git").resolve() == (usr / "bin" / "git").resolve()
    assert (bin_dir.parent / "libexec" / "git-core" / "git-upload-pack").exists()
    assert (bin_dir.parent / "share" / "git-core" / "templates" / "x").exists()


def test_nothing_changes_where_git_is_not_the_shim(monkeypatch):
    monkeypatch.setattr(fast_git, "IS_MAC", True)
    monkeypatch.setattr(fast_git.shutil, "which", lambda name, path=None: "/opt/homebrew/bin/git")
    assert fast_git.real_git() is None


def test_nothing_changes_off_macos(monkeypatch):
    monkeypatch.setattr(fast_git, "IS_MAC", False)
    assert fast_git.real_git() is None


def test_a_shim_xcrun_cannot_resolve_is_kept(monkeypatch):
    monkeypatch.setattr(fast_git, "IS_MAC", True)
    monkeypatch.setattr(fast_git.shutil, "which", lambda name, path=None: "/usr/bin/git")
    monkeypatch.setattr(fast_git.subprocess, "run", lambda *a, **k: subprocess.CompletedProcess(a, 1, "", "no tools"))
    assert fast_git.real_git() is None


@links
def test_install_puts_the_mirror_first_on_path(monkeypatch, tmp_path):
    usr = fake_prefix(tmp_path / "dev")
    monkeypatch.setattr(fast_git, "real_git", lambda: usr / "bin" / "git")
    monkeypatch.setenv("PATH", "/usr/bin")
    fast_git.install(tmp_path / "base")
    first = Path(os.environ["PATH"].split(os.pathsep)[0])
    assert first == tmp_path / "base" / "bin" and (first / "git").exists()


@pytest.mark.skipif(sys.platform != "darwin" or not Path("/usr/bin/xcrun").exists(), reason="Apple's git shim only")
def test_the_suite_runs_a_git_that_finds_its_own_helpers():
    git = shutil.which("git")
    assert Path(git).resolve() != Path("/usr/bin/git")
    exec_path = subprocess.run([git, "--exec-path"], capture_output=True, text=True, check=True).stdout.strip()
    assert (Path(exec_path) / "git-sh-setup").exists()
