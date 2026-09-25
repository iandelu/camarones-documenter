"""Project resolution, the project registry and the non-destructive kit install."""
from __future__ import annotations

import subprocess

import pytest

from conftest import REPO


def marker(folder):
    (folder / ".camarones").mkdir(parents=True, exist_ok=True)
    (folder / ".camarones" / "workspace.yaml").write_text("project: {}\n", encoding="utf-8")
    return folder


def test_marker_walk_up_prefers_cam_docs(kit, tmp_path):
    w = tmp_path / "w"
    marker(w)                                   # a stray legacy marker in the workspace folder itself
    marker(w / "cam-docs")
    (w / "api" / "src").mkdir(parents=True)
    assert kit.common.find_project_marker(w / "api" / "src") == (w / "cam-docs").resolve()
    assert kit.common.find_project_marker(w) == (w / "cam-docs").resolve()


def test_workspace_folder_resolves_to_its_cam_docs(kit, tmp_path):
    w = tmp_path / "w"
    marker(w / "cam-docs")
    assert kit.common.docs_root(w) == (w / "cam-docs").resolve()
    assert kit.common.docs_root(tmp_path / "plain") == (tmp_path / "plain").resolve()


def test_kit_resolves_root_from_env(kit):
    assert kit.common.ROOT == kit.root.resolve()
    assert kit.common.CAM_LAYOUT and kit.common.WORKSPACE == kit.ws.resolve()
    assert kit.common.HOME == kit.home                  # tests never see the real home folder


def test_registry_one_row_per_project_and_skips_stale(kit, tmp_path):
    p = kit.projects
    p.register(kit.ws)
    p.register(kit.root, name="demo")
    p.register(tmp_path / "gone")                       # stale: kept in the file, not listed
    rows = p.list_registered()
    assert [r["path"] for r in rows] == [str(kit.root.resolve())]
    assert any("gone" in r["path"] for r in p.load())


def test_register_moves_to_top_without_duplicates(kit, tmp_path):
    p = kit.projects
    for n in ("a", "b"):
        (tmp_path / n).mkdir()
        p.register(tmp_path / n)
    p.register(tmp_path / "a")
    assert [r["name"] for r in p.load()] == ["a", "b"]


def test_adopt_refuses_a_non_empty_non_git_cam_docs(kit, tmp_path):
    w = tmp_path / "other"
    (w / "cam-docs").mkdir(parents=True)
    (w / "cam-docs" / "notes.txt").write_text("mine", encoding="utf-8")
    with pytest.raises(ValueError):
        kit.projects.adopt(w)
    assert (w / "cam-docs" / "notes.txt").read_text(encoding="utf-8") == "mine"


def test_adopt_registers_an_existing_project(kit):
    assert kit.projects.adopt(kit.ws) == kit.ws / "cam-docs"
    assert kit.projects.load()[0]["path"] == str((kit.ws / "cam-docs").resolve())


# ---------- install / unlink ----------
def test_install_dry_run_writes_nothing(kit, tmp_path):
    dest = tmp_path / "proj"
    res = kit.install.install(REPO, dest, dry_run=True, log=lambda _: None)
    assert res["dry_run"] and res["changed"]
    assert not dest.exists()


def test_install_refuses_to_overwrite_a_differing_file_without_upgrade(kit, tmp_path):
    dest = tmp_path / "proj"
    kit.install.install(REPO, dest, log=lambda _: None)
    readme = dest / ".camarones" / "README.md"
    readme.write_text("edited", encoding="utf-8")
    with pytest.raises(ValueError, match="differs"):
        kit.install.install(REPO, dest, log=lambda _: None)
    assert readme.read_text(encoding="utf-8") == "edited"


def test_install_refuses_home_and_the_kit_itself(kit):
    with pytest.raises(ValueError):
        kit.install.install(REPO, REPO / "sub", dry_run=True, log=lambda _: None)
    with pytest.raises(ValueError):
        kit.install.install(REPO, kit.home, dry_run=True, log=lambda _: None)


def test_unlink_strips_kit_code_and_keeps_config(kit, tmp_path):
    dest = tmp_path / "proj"
    kit.install.install(REPO, dest, log=lambda _: None)
    removed = kit.install.unlink(dest, log=lambda _: None)
    assert "camarones.cmd" in removed and ".camarones/lib/" in removed
    assert not (dest / ".camarones" / "lib").exists()
    assert (dest / ".camarones" / "workspace.yaml").is_file()
    assert (dest / ".camarones" / "install.json").is_file()


# ---------- launching tools ----------
def test_a_tool_that_cannot_start_is_not_available(kit, monkeypatch):
    def boom(*a, **kw):
        raise OSError(4551, "blocked by Smart App Control")
    monkeypatch.setattr(subprocess, "run", boom)
    r = kit.common.run(["anything"], check=False)
    assert r.returncode == 127
    with pytest.raises(RuntimeError, match="not found"):
        kit.common.run(["anything"])
    assert kit.common.out(["anything"]) == ""
