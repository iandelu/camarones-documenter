"""The synthetic workspace and the wired project are built once per process and copied per test: every copy is its own,
complete and clean, and matches what building it from scratch gives."""
from __future__ import annotations

import json, os, sys
from pathlib import Path

import pytest

from conftest import REPO, load_kit, wire_project
from fixtures import builder
from fixtures.builder import REPOS, build_workspace, git, make_workspace, snapshot


def test_each_call_gets_its_own_copy(tmp_path):
    a, b = make_workspace(tmp_path / "a"), make_workspace(tmp_path / "b")
    (a / "api" / "README.md").write_text("changed\n", encoding="utf-8")
    assert (b / "api" / "README.md").read_text(encoding="utf-8") == "# api\n\nREST backend.\n"
    assert snapshot(make_workspace(tmp_path / "c") / "api") == snapshot(b / "api")


def test_a_copy_matches_a_fresh_build(tmp_path, isolated_env):
    copy, fresh = make_workspace(tmp_path / "copy"), build_workspace(tmp_path / "fresh")
    for r in REPOS:
        assert snapshot(copy / r) == snapshot(fresh / r)
        assert git(copy / r, "status", "--porcelain") == ""
        assert git(copy / r, "log", "--format=%an <%ae>") == "Test <test@example.com>\n"
    assert (copy / "cam-docs" / ".camarones" / "workspace.yaml").read_bytes() == \
        (fresh / "cam-docs" / ".camarones" / "workspace.yaml").read_bytes()


def test_a_copy_leaves_out_gits_sample_hooks_and_loose_objects(tmp_path, isolated_env):
    ws = make_workspace(tmp_path)
    assert not list(ws.glob("*/.git/hooks/*.sample"))
    assert all((ws / r / ".git" / "hooks").is_dir() for r in REPOS)
    assert not [o for o in ws.glob("*/.git/objects/??/*")]
    git(ws / "api", "commit", "-q", "--allow-empty", "-m", "next")
    assert git(ws / "api", "log", "--format=%s") == "next\ninitial\n"


def test_where_cloning_fails_a_copy_is_a_plain_copy(tmp_path, monkeypatch):
    src = make_workspace(tmp_path / "src")
    monkeypatch.setattr(builder, "clone", lambda a, b: False)
    builder.copy_tree(src, tmp_path / "copy")
    assert tree(tmp_path / "copy") == tree(src)


@pytest.mark.skipif(sys.platform != "darwin", reason="clonefile(2) is macOS")
def test_on_a_mac_a_copy_is_one_clone_of_its_own(tmp_path):
    src = make_workspace(tmp_path / "src")
    assert builder.clone(src, tmp_path / "copy")
    assert tree(tmp_path / "copy") == tree(src)
    (tmp_path / "copy" / "api" / "README.md").write_text("changed\n", encoding="utf-8")
    assert (src / "api" / "README.md").read_text(encoding="utf-8") == "# api\n\nREST backend.\n"


def test_a_copy_onto_a_folder_that_is_there_fails_and_leaves_it_alone(tmp_path):
    src = make_workspace(tmp_path / "src")
    (tmp_path / "taken" / "mine.txt").parent.mkdir()
    (tmp_path / "taken" / "mine.txt").write_text("keep\n", encoding="utf-8")
    with pytest.raises(FileExistsError):
        builder.copy_tree(src, tmp_path / "taken")
    assert [p.name for p in (tmp_path / "taken").iterdir()] == ["mine.txt"]


@pytest.mark.skipif(sys.platform == "win32", reason="symlinks need a right Windows does not give by default")
def test_drop_links_takes_every_link_and_nothing_else(tmp_path):
    (tmp_path / "repo" / "src").mkdir(parents=True)
    (tmp_path / "repo" / "src" / "a.py").write_text("a\n", encoding="utf-8")
    (tmp_path / "AGENTS.md").symlink_to("repo/src/a.py")
    (tmp_path / "repo" / "wiki").symlink_to("src", target_is_directory=True)
    builder.drop_links(tmp_path)
    assert sorted(p.relative_to(tmp_path).as_posix() for p in tmp_path.rglob("*")) == ["repo", "repo/src", "repo/src/a.py"]


def test_other_layouts_are_templates_of_their_own(tmp_path):
    ws = make_workspace(tmp_path, repos=("api",), name="solo")
    assert sorted(p.name for p in ws.iterdir()) == ["api", "cam-docs"]
    assert "name: solo" in (ws / "cam-docs" / ".camarones" / "workspace.yaml").read_text(encoding="utf-8")


def tree(ws: Path) -> dict[str, object]:
    """Every file of a workspace but git's internals; a link counts as where it leads, inside the workspace."""
    out: dict[str, object] = {}
    for p in sorted(ws.rglob("*")):
        rel = p.relative_to(ws).as_posix()
        if "/.git/" in f"/{rel}/" and not rel.endswith(".git/info/exclude") or p.suffix == ".sample":
            continue
        real = Path(os.path.realpath(p))
        if real != p.parent.resolve() / p.name:
            out[rel] = ("link", real.relative_to(ws.resolve()).as_posix())
        elif p.is_file() and not any(q in out for q in _parents(rel)):
            out[rel] = p.read_bytes()
    return out


def _parents(rel: str) -> list[str]:
    parts = rel.split("/")
    return ["/".join(parts[:i]) for i in range(1, len(parts))]


def records(home: Path, root: Path) -> dict[str, dict]:
    """The per-machine records under ~/.camarones, with this project's root and its hashed file name made neutral."""
    from lib import trust
    key = trust.store_path(root).name
    return {p.relative_to(home).as_posix().replace(key, "<root>"):
            {**json.loads(p.read_text(encoding="utf-8")), "root": "<root>"}
            for p in sorted(home.rglob("*.json"))}


def test_a_wired_copy_matches_a_project_wired_from_scratch(wired, tmp_path):
    copy = (wired.ws, wired.home, wired.root, sorted(wired.linked), tree(wired.ws))
    copy_records = records(wired.home, wired.root)
    home = tmp_path / "fresh" / "home"
    home.mkdir(parents=True)
    os.environ["HOME"] = os.environ["USERPROFILE"] = str(home)       # isolated_env puts them back
    ws = make_workspace(tmp_path / "fresh")
    fresh = wire_project(load_kit(ws / "cam-docs", home, ws))
    assert sorted(fresh.linked) == copy[3] and copy[3]
    assert tree(ws) == copy[4]
    assert records(home, fresh.root) == copy_records and copy_records
    logs = {git(r, "log", "--format=%s %an") for r in (copy[2], fresh.root)}
    assert len(logs) == 1 and logs.pop().count("\n") == 1
    assert git(copy[2], "status", "--porcelain") == git(fresh.root, "status", "--porcelain") == ""


@pytest.fixture
def first_on_its_worker_with_a_stray_author(monkeypatch):
    import conftest
    monkeypatch.setattr(conftest, "_templates", {})
    monkeypatch.setenv("GIT_AUTHOR_NAME", "Someone Else")


def test_the_wired_template_never_takes_what_the_first_test_set(first_on_its_worker_with_a_stray_author, wired):
    assert git(wired.root, "log", "--format=%an") == "Test\n"


def test_a_test_that_wires_by_hand_after_kit_still_can(kit):
    assert not hasattr(kit, "linked")
    assert wire_project(kit).linked


def test_fresh_kit_imports_reuse_compiled_bytecode_kept_outside_the_repo():
    assert not sys.dont_write_bytecode and not os.environ.get("PYTHONDONTWRITEBYTECODE")
    prefix = sys.pycache_prefix or os.environ.get("PYTHONPYCACHEPREFIX")
    assert prefix is None or REPO.resolve() not in Path(prefix).resolve().parents
