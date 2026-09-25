"""Team docs repo: cam-docs is a versioned repo the team shares. Joining clones it (or reuses what is already here),
sharing pulls then pushes on demand, and a joined project only prepares this machine instead of redoing team work."""
from __future__ import annotations

import os, subprocess, sys
from pathlib import Path

import pytest

from conftest import KIT_DIR


def git(cwd: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True,
                          encoding="utf-8").stdout.strip()


def bare(tmp_path: Path, name: str = "team-docs.git") -> Path:
    path = tmp_path / "remotes" / name
    path.mkdir(parents=True)
    git(path, "init", "-q", "--bare", "-b", "main")
    return path


def publish(kit, remote: Path) -> None:
    """The first teammate: a set-up project whose cam-docs is pushed to the team remote."""
    kit.env.init_templates("demo", log=lambda _: None)
    kit.plan.sync()
    kit.env.set_remote(str(remote))
    assert kit.env.share(log=lambda _: None)["status"] == "pushed"


def remote_files(remote: Path) -> set[str]:
    return set(git(remote, "ls-tree", "-r", "--name-only", "main").splitlines())


# ---------- same repo, different spellings ----------
@pytest.mark.parametrize("a, b", [
    ("git@github.com:Acme/team-docs.git", "https://github.com/acme/team-docs"),
    ("https://oauth2:tok@gitlab.example.com/g/sub/docs.git/", "ssh://git@gitlab.example.com:22/g/sub/docs"),
])
def test_remote_key_matches_the_same_repo(kit, a, b):
    assert kit.projects.remote_key(a) == kit.projects.remote_key(b)


def test_remote_key_tells_repos_apart(kit):
    k = kit.projects.remote_key
    assert k("git@github.com:acme/docs.git") != k("git@github.com:acme/api.git")
    assert k("git@github.com:acme/docs.git") != k("git@gitlab.com:acme/docs.git")


# ---------- join ----------
def test_join_an_empty_remote_starts_a_new_project_with_origin(kit, tmp_path):
    remote = bare(tmp_path)
    dest, joined = kit.projects.join(str(remote), tmp_path / "mate")
    assert dest == tmp_path / "mate" / "cam-docs" and not joined
    assert (dest / ".git").is_dir()
    assert kit.projects.remote_key(git(dest, "remote", "get-url", "origin")) == kit.projects.remote_key(str(remote))
    assert kit.projects.load()[0]["path"] == str(dest.resolve())


def test_join_a_team_project_clones_it(kit, tmp_path):
    remote = bare(tmp_path)
    publish(kit, remote)
    dest, joined = kit.projects.join(str(remote), tmp_path / "mate")
    assert joined
    assert (dest / ".camarones" / "workspace.yaml").exists() and (dest / "docs" / ".work" / "plan.yaml").exists()


def test_join_checks_out_the_pushed_branch_when_remote_head_is_unborn(kit, tmp_path):
    remote = bare(tmp_path)                                  # created with HEAD → main, first push came from master
    kit.env.init_templates("demo", log=lambda _: None)
    git(kit.root, "checkout", "-q", "-b", "master")
    publish(kit, remote)
    dest, joined = kit.projects.join(str(remote), tmp_path / "mate")
    assert joined and git(dest, "symbolic-ref", "--short", "HEAD") == "master"


def test_join_reuses_a_local_clone_and_pulls(kit, tmp_path):
    remote = bare(tmp_path)
    publish(kit, remote)
    dest, _ = kit.projects.join(str(remote), tmp_path / "mate")
    (dest / "local-note.txt").write_text("kept", encoding="utf-8")         # a clone again would have wiped this
    (kit.root / "docs" / "news.md").write_text("# News\n", encoding="utf-8")
    assert kit.env.share(log=lambda _: None)["status"] == "pushed"
    again, joined = kit.projects.join(str(remote), tmp_path / "mate")
    assert again == dest and joined
    assert (dest / "local-note.txt").exists() and (dest / "docs" / "news.md").exists()


def test_join_reuses_a_registered_project_with_that_remote(kit, tmp_path):
    remote = bare(tmp_path)
    publish(kit, remote)
    kit.projects.register(kit.root)
    dest, joined = kit.projects.join(str(remote), tmp_path / "elsewhere")
    assert dest == kit.root.resolve() and joined
    assert not (tmp_path / "elsewhere").exists()


def test_join_refuses_a_cam_docs_with_another_remote(kit, tmp_path):
    remote, other = bare(tmp_path), bare(tmp_path, "other.git")
    dest = tmp_path / "mate" / "cam-docs"
    dest.mkdir(parents=True)
    git(dest, "init", "-q")
    git(dest, "remote", "add", "origin", str(other))
    with pytest.raises(ValueError):
        kit.projects.join(str(remote), tmp_path / "mate")
    assert git(dest, "remote", "get-url", "origin") == str(other)


def test_join_an_unreachable_remote_creates_nothing(kit, tmp_path):
    with pytest.raises(RuntimeError):
        kit.projects.join(str(tmp_path / "nowhere.git"), tmp_path / "mate")
    assert not (tmp_path / "mate").exists()


def test_create_with_a_url_joins(kit, tmp_path):
    remote = bare(tmp_path)
    publish(kit, remote)
    dest = kit.projects.create("Mate", at=tmp_path, url=str(remote))
    assert dest == tmp_path / "mate" / "cam-docs"
    assert (dest / ".camarones" / "workspace.yaml").exists()


# ---------- share ----------
def test_share_without_remote_says_so(kit):
    kit.env.init_templates("demo", log=lambda _: None)
    assert kit.env.share(log=lambda _: None)["status"] == "no-remote"


def test_share_pushes_the_checkpoint(kit, tmp_path):
    remote = bare(tmp_path)
    publish(kit, remote)
    assert ".camarones/workspace.yaml" in remote_files(remote)
    assert kit.env.share(log=lambda _: None)["status"] == "up-to-date"


def test_share_pulls_team_work_before_pushing(kit, tmp_path):
    remote = bare(tmp_path)
    publish(kit, remote)
    mate, _ = kit.projects.join(str(remote), tmp_path / "mate")
    (mate / "docs" / "from-mate.md").write_text("# Mate\n", encoding="utf-8")
    git(mate, "add", "-A")
    git(mate, "commit", "-q", "-m", "mate")
    git(mate, "push", "-q", "origin", "main")
    (kit.root / "docs" / "from-me.md").write_text("# Me\n", encoding="utf-8")
    assert kit.env.share(log=lambda _: None)["status"] == "pushed"
    assert {"docs/from-mate.md", "docs/from-me.md"} <= remote_files(remote)
    assert (kit.root / "docs" / "from-mate.md").exists()


def test_share_conflict_leaves_the_local_work_untouched(kit, tmp_path):
    remote = bare(tmp_path)
    (kit.root / "docs").mkdir(parents=True, exist_ok=True)
    (kit.root / "docs" / "page.md").write_text("base\n", encoding="utf-8")
    publish(kit, remote)
    mate, _ = kit.projects.join(str(remote), tmp_path / "mate")
    (mate / "docs" / "page.md").write_text("theirs\n", encoding="utf-8")
    git(mate, "commit", "-q", "-am", "theirs")
    git(mate, "push", "-q", "origin", "main")
    (kit.root / "docs" / "page.md").write_text("mine\n", encoding="utf-8")
    r = kit.env.share(log=lambda _: None)
    assert r["status"] == "conflict"
    assert (kit.root / "docs" / "page.md").read_text(encoding="utf-8") == "mine\n"
    assert not (kit.root / ".git" / "rebase-merge").exists() and not (kit.root / ".git" / "rebase-apply").exists()
    assert git(remote, "show", "main:docs/page.md") == "theirs"


def test_set_remote_replaces_origin(kit, tmp_path):
    kit.env.init_templates("demo", log=lambda _: None)
    a, b = bare(tmp_path, "a.git"), bare(tmp_path, "b.git")
    kit.env.set_remote(str(a))
    kit.env.set_remote(str(b))
    assert kit.env.docs_remote() == str(b)


# ---------- wizard: a joined project only prepares this machine ----------
@pytest.mark.parametrize("state, shared, local, mode", [
    ({"done": True}, True, False, "done"),
    ({}, False, False, "new"),                                  # brand-new project
    ({"step": 3, "name": "setup"}, True, False, "new"),         # a first run in progress is resumed as it was
    ({"step": 2, "name": "tools", "mode": "join"}, True, False, "join"),
    ({}, True, False, "join"),                                  # team project cloned here, machine not ready
    ({}, True, True, "done"),                                   # pre-2.4 install on its own machine
])
def test_first_run_mode(kit, state, shared, local, mode):
    assert kit.wizard.first_run_mode(state, shared, local) == mode


def test_join_first_run_skips_the_team_steps(kit, fake_wizard, monkeypatch):
    ran = []
    for step in ("fr_name", "fr_repos", "fr_tools", "fr_setup", "fr_stack", "fr_arch", "fr_intro"):
        monkeypatch.setattr(kit.wizard.W, step, lambda self, ws, s=step: ran.append(s))
    assert fake_wizard([]).first_run(mode="join")
    assert ran == ["fr_tools", "fr_setup", "fr_intro"]
    assert kit.common.load_json(kit.wizard.FIRSTRUN, {})["done"]


def test_join_first_run_resumes_on_its_step(kit, fake_wizard, monkeypatch):
    ran = []
    for step in ("fr_tools", "fr_setup", "fr_intro"):
        monkeypatch.setattr(kit.wizard.W, step, lambda self, ws, s=step: ran.append(s))
    start = kit.wizard.resume_step({"step": 3, "name": "setup", "mode": "join"})
    fake_wizard([]).first_run(start, mode="join")
    assert ran == ["fr_setup", "fr_intro"]


def test_share_menu_sets_the_remote_and_asks_before_pushing(kit, fake_wizard, tmp_path, monkeypatch):
    kit.env.init_templates("demo", log=lambda _: None)
    remote = bare(tmp_path)
    w = fake_wizard([str(remote), False])                               # URL, then "no" to publishing
    w.do_share()
    assert kit.env.docs_remote() == str(remote) and not remote_files_safe(remote)
    w = fake_wizard([True])
    w.do_share()
    assert ".camarones/workspace.yaml" in remote_files(remote)


def remote_files_safe(remote: Path) -> set[str]:
    r = subprocess.run(["git", "ls-tree", "-r", "--name-only", "main"], cwd=remote, capture_output=True, text=True)
    return set(r.stdout.split()) if r.returncode == 0 else set()


def test_share_strings_exist_in_both_languages(kit):
    T = kit.wizard.T
    for key in ("m_share", "sh_url", "sh_confirm", "join_welcome"):
        assert key in T["es"] and key in T["en"]


# ---------- CLI ----------
def cli(root: Path | None, cwd: Path, *args: str, **extra: str):
    env = {**os.environ, "PYTHONUTF8": "1", **extra}
    env.pop("CAMARONES_ROOT", None)
    if root:
        env["CAMARONES_ROOT"] = str(root)
    return subprocess.run([sys.executable, str(KIT_DIR / "camarones.py"), *args], env=env, cwd=cwd,
                          capture_output=True, text=True, encoding="utf-8", input="")   # a pipe: NUL is a tty on Windows


def test_cli_remote_share_and_join(kit, tmp_path):
    kit.env.init_templates("demo", log=lambda _: None)
    remote = bare(tmp_path)
    r = cli(kit.root, kit.ws, "remote", str(remote))
    assert r.returncode == 0, r.stdout + r.stderr
    r = cli(kit.root, kit.ws, "share")
    assert r.returncode == 0, r.stdout + r.stderr
    assert ".camarones/workspace.yaml" in remote_files(remote)
    mate = tmp_path / "mate"
    mate.mkdir()
    r = cli(None, mate, "join", str(remote), PYTHONUTF8="0", PYTHONIOENCODING="cp1252")   # a Windows pipe
    assert r.returncode == 0, r.stdout + r.stderr
    assert (mate / "cam-docs" / ".camarones" / "workspace.yaml").exists()
