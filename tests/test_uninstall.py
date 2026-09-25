"""Undo everything: the project's docs, its links, every trace in the repos and (opt-in) the user-level files."""
from __future__ import annotations

import json, os, subprocess, sys, zipfile

import pytest

from conftest import KIT_DIR, wire_project
from fixtures.builder import git, snapshot

REPOS = ("api", "web", "worker")


@pytest.fixture
def before(un, monkeypatch):
    """Snapshots of the untouched repos, then the project gets documented (wired). Portal/docker are never touched."""
    kit = un
    snap = {r: snapshot(kit.ws / r) for r in REPOS}
    (kit.ws / "AGENTS.md").write_text("the team's own AGENTS.md\n", encoding="utf-8")   # a real file at the root
    wire_project(kit)
    kit.stopped = []
    monkeypatch.setattr(kit.env, "docker_down", lambda: kit.stopped.append("portal"))
    monkeypatch.setattr(kit.uninstall, "which", lambda name: None)
    monkeypatch.setattr(kit.uninstall, "BACKUP_DIR", kit.home.parent / "backups")
    return snap


@pytest.fixture
def un(kit):
    import importlib
    kit.uninstall = importlib.import_module("lib.uninstall")
    return kit


def run(kit, **kw):
    return kit.uninstall.run(log=lambda _: None, **kw)


# ---------- preview ----------
def test_preview_lists_every_trace_and_changes_nothing(un, before):
    kit = un
    during = {r: snapshot(kit.ws / r) for r in REPOS}
    labels = "\n".join(s.label for s in kit.uninstall.steps())
    for r in REPOS:
        assert f"{r}/openwiki" in labels and f"{r}/.git/info/exclude" in labels
    assert "api/CLAUDE.md" in labels and "web/CLAUDE.md" in labels
    for n in kit.linked:
        assert n in labels
    assert "cam-docs" in labels
    assert not any("AGENTS.md" in s.label for s in kit.uninstall.steps() if s.kind == "link")    # a real file
    assert {r: snapshot(kit.ws / r) for r in REPOS} == during and kit.root.is_dir()
    assert kit.stopped == []


def test_untouched_list_names_what_stays(un):
    text = "\n".join(un.uninstall.untouched())
    assert "npm" in text and "Claude Code" in text


# ---------- project ----------
def test_repos_are_left_exactly_as_committed(un, before):
    kit = un
    run(kit, backup=False)
    for r in REPOS:
        assert snapshot(kit.ws / r) == before[r], r
        assert git(kit.ws / r, "status", "--porcelain", "--ignored") == ""


def test_workspace_links_go_and_real_files_stay(un, before):
    kit = un
    run(kit, backup=False)
    assert not kit.root.exists()
    for n in (".claude", ".codex", ".agents", ".mcp.json", "CLAUDE.md"):
        assert not (kit.ws / n).exists() and not (kit.ws / n).is_symlink()
    assert (kit.ws / "AGENTS.md").read_text(encoding="utf-8") == "the team's own AGENTS.md\n"
    assert sorted(p.name for p in kit.ws.iterdir()) == ["AGENTS.md", *REPOS]
    assert kit.stopped == ["portal"]


def test_backup_zip_keeps_docs_and_history(un, before):
    kit = un
    (kit.root / ".camarones" / ".cache").mkdir(exist_ok=True)
    (kit.root / ".camarones" / ".cache" / "big.bin").write_bytes(b"x" * 10)
    zipped = run(kit)
    assert zipped and zipped.parent == kit.uninstall.BACKUP_DIR and zipped.suffix == ".zip"
    names = zipfile.ZipFile(zipped).namelist()
    assert "docs/overview.md" in names and any(n.startswith(".git/") for n in names)
    assert not any(".cache" in n for n in names)
    assert not kit.root.exists()


def test_no_backup_means_no_zip(un, before):
    assert run(un, backup=False) is None
    assert not un.uninstall.BACKUP_DIR.exists()


def test_only_this_project_leaves_the_registry(un, before, tmp_path):
    kit = un
    other = tmp_path / "other" / "cam-docs"
    other.mkdir(parents=True)
    kit.projects.register(other)
    kit.projects.register(kit.root)
    kit.projects.register(kit.ws)
    run(kit, backup=False)
    assert [r["path"] for r in kit.projects.load()] == [str(other.resolve())]


def test_a_pending_openwiki_run_is_undone_first(un, before):
    kit = un
    kit.env.wiki_open("api", log=lambda _: None)
    (kit.ws / "api" / "AGENTS.md").write_text("openwiki snippet", encoding="utf-8")
    (kit.ws / "api" / "CLAUDE.md").write_text("openwiki snippet", encoding="utf-8")
    run(kit, backup=False)
    assert snapshot(kit.ws / "api") == before["api"]


def test_legacy_graphify_traces_are_deleted_not_moved(un, before):
    kit = un
    repo = kit.ws / "worker"
    (repo / "graphify-out").mkdir()
    (repo / "graphify-out" / "graph.json").write_text("{}", encoding="utf-8")
    (repo / ".claude" / "skills" / "graphify").mkdir(parents=True)
    (repo / ".claude" / "skills" / "graphify" / "SKILL.md").write_text("x", encoding="utf-8")
    run(kit, backup=False)
    assert snapshot(repo) == before["worker"]


def test_a_repo_dropped_from_workspace_yaml_is_cleaned_too(un, before):
    kit = un
    ws = kit.docs.workspace()
    ws["repos"] = [r for r in ws["repos"] if r["name"] != "web"]
    kit.docs.save_workspace(ws)
    run(kit, backup=False)
    assert snapshot(kit.ws / "web") == before["web"]


# ---------- user-level (opt-in) ----------
@pytest.fixture
def home_files(un):
    h = un.home
    (h / ".camarones.json").write_text('{"lang": "es"}', encoding="utf-8")
    cam = h / ".camarones"
    for rel, text in {"projects.json": "[]", "hosts.json": json.dumps({"github.com": {"kind": "github", "user": "me"}}),
                      "credentials.json": "{}", "bin/gitleaks-8/gitleaks.exe": "x", "kit/.camarones/camarones.py": "kit"}.items():
        (cam / rel).parent.mkdir(parents=True, exist_ok=True)
        (cam / rel).write_text(text, encoding="utf-8")
    (h / ".openwiki").mkdir()
    (h / ".openwiki" / ".env").write_text("OPENAI_API_KEY=sk-mine\nOPENWIKI_TELEMETRY_DISABLED=1\n", encoding="utf-8")
    return h


def test_user_files_stay_unless_asked(un, before, home_files):
    run(un, backup=False)
    assert (home_files / ".camarones.json").exists() and (home_files / ".camarones" / "hosts.json").exists()
    assert "TELEMETRY" in (home_files / ".openwiki" / ".env").read_text(encoding="utf-8")


def test_global_cleanup_keeps_the_central_kit_and_the_users_keys(un, before, home_files, monkeypatch):
    kit, deleted = un, []
    monkeypatch.setattr(kit.uninstall.creds, "delete", deleted.append)
    run(kit, backup=False, include_global=True)
    assert deleted == ["github.com"]
    assert not (home_files / ".camarones.json").exists()
    assert sorted(p.name for p in (home_files / ".camarones").iterdir()) == ["kit"]
    assert (home_files / ".openwiki" / ".env").read_text(encoding="utf-8") == "OPENAI_API_KEY=sk-mine\n"


def test_global_cleanup_removes_an_env_file_the_kit_alone_wrote(un, before, home_files):
    (home_files / ".openwiki" / ".env").write_text("OPENWIKI_TELEMETRY_DISABLED=1\n", encoding="utf-8")
    shutil_kit = home_files / ".camarones" / "kit"
    import shutil
    shutil.rmtree(shutil_kit)
    run(un, backup=False, include_global=True)
    assert not (home_files / ".openwiki").exists() and not (home_files / ".camarones").exists()


def test_global_preview_warns_about_other_projects(un, before, home_files, tmp_path):
    other = tmp_path / "other" / "cam-docs"
    other.mkdir(parents=True)
    un.projects.register(other)
    labels = "\n".join(s.label for s in un.uninstall.steps(include_global=True))
    assert "~/.camarones.json" in labels and "1" in labels and "other" in labels


# ---------- guards ----------
def test_guard_legacy_layout(un, monkeypatch):
    monkeypatch.setattr(un.uninstall, "CAM_LAYOUT", False)
    assert "migrate" in un.uninstall.guard()
    with pytest.raises(RuntimeError):
        run(un)


def test_guard_kit_inside_the_project(un, monkeypatch):
    monkeypatch.setattr(un.uninstall, "KIT", un.root / ".camarones")
    assert un.uninstall.guard()


def test_guard_running_openwiki(un, before, monkeypatch):
    un.env.WIKI_LOCK.parent.mkdir(parents=True, exist_ok=True)
    un.env.WIKI_LOCK.write_text('{"pid": 999999, "repo": "api"}', encoding="utf-8")
    monkeypatch.setattr(un.env, "pid_alive", lambda pid: True)
    assert "OpenWiki" in un.uninstall.guard()
    monkeypatch.setattr(un.env, "pid_alive", lambda pid: False)
    assert un.uninstall.guard() is None


def test_guard_not_a_project(un):
    (un.root / ".camarones" / "workspace.yaml").unlink()
    assert un.uninstall.guard()


def test_guard_refuses_home_as_workspace(un, monkeypatch):
    monkeypatch.setattr(un.uninstall, "WORKSPACE", un.home)
    assert un.uninstall.guard()


# ---------- CLI ----------
def cli(kit, *args, stdin=""):
    env = {**os.environ, "CAMARONES_ROOT": str(kit.root), "PYTHONUTF8": "1"}
    return subprocess.run([sys.executable, str(KIT_DIR / "camarones.py"), "uninstall", *args], env=env, input=stdin,
                          capture_output=True, text=True, encoding="utf-8", cwd=kit.ws)


def test_cli_dry_run_changes_nothing(un, before):
    r = cli(un, "--dry-run")
    assert r.returncode == 0, r.stderr
    assert "cam-docs" in r.stdout and un.root.is_dir()
    assert "web/openwiki" in r.stdout


def test_cli_asks_for_the_project_name(un, before):
    r = cli(un, "--no-backup", stdin="wrong\n")
    assert r.returncode == 1 and un.root.is_dir()
    r = cli(un, "--no-backup", stdin="demo\n")
    assert r.returncode == 0, r.stdout + r.stderr
    assert not un.root.exists()


def test_cli_yes_with_backup_dir(un, before, tmp_path):
    r = cli(un, "--yes", "--backup-dir", str(tmp_path / "bk"))
    assert r.returncode == 0, r.stdout + r.stderr
    assert not un.root.exists() and list((tmp_path / "bk").glob("demo-*.zip"))
    for n in REPOS:
        assert snapshot(un.ws / n) == before[n]


# ---------- wizard ----------
@pytest.fixture
def wiz(un, before, fake_wizard, monkeypatch):
    monkeypatch.setattr(un.wizard.time, "sleep", lambda _s: None)
    monkeypatch.setattr(un.wizard.console, "clear", lambda *a, **kw: None)
    return fake_wizard


def test_wizard_wrong_name_deletes_nothing(un, wiz):
    w = wiz([False, "not-demo"])
    assert w.do_uninstall() is None
    assert un.root.is_dir()


def test_wizard_escape_deletes_nothing(un, wiz):
    assert wiz([None]).do_uninstall() is None
    assert un.root.is_dir()


def test_wizard_uninstall_leaves_and_closes(un, wiz):
    un.common.save_json(un.wizard.FIRSTRUN, {"step": 6, "done": True})
    un.plan.sync()
    w = wiz(["uninstall", False, "demo"])
    w._run()                                                   # returns without asking anything else
    assert not un.root.exists()
    assert list(un.uninstall.BACKUP_DIR.glob("demo-*.zip"))
