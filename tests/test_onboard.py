"""Onboarding: what a folder picked in the desktop app is (project, repo, umbrella, code, empty). Offline."""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from fixtures.builder import make_repo, make_workspace, rmtree


def tree(folder: Path) -> dict[str, bytes | None]:
    """Every file and folder under `folder`, .git internals included: what 'inspect wrote nothing' means."""
    return {p.relative_to(folder).as_posix(): p.read_bytes() if p.is_file() else None for p in sorted(folder.rglob("*"))}


def umbrella(base: Path) -> Path:
    """<base>/demo/{api,web,worker} with no cam-docs: repos side by side, no project yet."""
    ws = make_workspace(base)
    rmtree(ws / "cam-docs")
    return ws


def set_kind(ws: Path, kind: str) -> None:
    f = ws / "cam-docs" / ".camarones" / "workspace.yaml"
    data = yaml.safe_load(f.read_text(encoding="utf-8"))
    data["project"]["kind"] = kind
    f.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


def test_inspect_umbrella_is_legacy(kit, tmp_path):
    ws = umbrella(tmp_path / "u")
    r = kit.onboard.inspect(ws)
    assert (r["case"], r["kind"], r["warning"]) == ("umbrella", "legacy", "")
    assert r["workspace"] == str(ws) and r["docs_root"] == str(ws / "cam-docs")
    assert {x["name"] for x in r["repos"]} == {"api", "web", "worker"}
    assert r["name"] == "demo" and r["siblings"] == []


def test_inspect_a_repo_uses_its_parent(kit, tmp_path):
    ws = umbrella(tmp_path / "u")
    r = kit.onboard.inspect(ws / "api")
    assert (r["case"], r["kind"]) == ("repo", "legacy")
    assert r["workspace"] == str(ws) and r["docs_root"] == str(ws / "cam-docs") and r["name"] == "demo"
    assert [x["name"] for x in r["repos"]] == ["api"]
    assert {x["name"] for x in r["siblings"]} == {"web", "worker"}


def test_inspect_a_repo_whose_parent_is_a_project(kit):
    r = kit.onboard.inspect(kit.ws / "api")
    assert r["case"] == "project"
    assert r["workspace"] == str(kit.ws) and r["docs_root"] == str(kit.ws / "cam-docs")


def test_inspect_existing_project(kit):
    assert kit.onboard.inspect(kit.ws)["kind"] == "legacy"           # no project.kind recorded: a 3.x/4.x project
    set_kind(kit.ws, "greenfield")
    for pick in (kit.ws, kit.ws / "cam-docs"):
        r = kit.onboard.inspect(pick)
        assert (r["case"], r["kind"]) == ("project", "greenfield")
        assert r["workspace"] == str(kit.ws) and r["docs_root"] == str(kit.ws / "cam-docs") and r["name"] == "demo"
        assert {x["name"] for x in r["repos"]} == {"api", "web", "worker"}


def test_inspect_legacy_docs_root_is_its_own_workspace(kit, tmp_path):
    root = tmp_path / "old"                                          # 3.x layout: the umbrella itself holds .camarones/
    (root / ".camarones").mkdir(parents=True)
    (root / ".camarones" / "workspace.yaml").write_text("project: {name: old}\nrepos: []\n", encoding="utf-8")
    r = kit.onboard.inspect(root)
    assert (r["case"], r["kind"], r["workspace"], r["docs_root"]) == ("project", "legacy", str(root), str(root))


def test_inspect_inside_cam_docs_is_the_project(kit):
    sub = kit.ws / "cam-docs" / "docs"
    sub.mkdir()
    r = kit.onboard.inspect(sub)
    assert r["case"] == "project" and r["docs_root"] == str(kit.ws / "cam-docs")


def test_inspect_code_without_git(kit, tmp_path):
    folder = tmp_path / "code"
    (folder / "src").mkdir(parents=True)
    (folder / "src" / "package.json").write_text("{}", encoding="utf-8")
    r = kit.onboard.inspect(folder)
    assert (r["case"], r["kind"], r["warning"]) == ("code", "legacy", "no-git")
    assert r["workspace"] == str(folder) and r["docs_root"] == str(folder / "cam-docs") and r["repos"] == []


@pytest.mark.parametrize("manifest", ["pom.xml", "go.mod", "Gemfile", "App.csproj"])
def test_inspect_code_manifest_at_the_top(kit, tmp_path, manifest):
    folder = tmp_path / "code"
    folder.mkdir()
    (folder / manifest).write_text("", encoding="utf-8")
    assert kit.onboard.inspect(folder)["case"] == "code"


def test_inspect_empty_is_greenfield(kit, tmp_path):
    folder = tmp_path / "blank"
    folder.mkdir()
    r = kit.onboard.inspect(folder)
    assert (r["case"], r["kind"], r["warning"], r["repos"]) == ("empty", "greenfield", "", [])
    assert r["workspace"] == str(folder) and r["name"] == "blank"


def test_inspect_looks_one_level_down_only(kit, tmp_path):
    folder = tmp_path / "deep"
    (folder / "a" / "b").mkdir(parents=True)
    (folder / "a" / "b" / "pom.xml").write_text("<project/>", encoding="utf-8")
    assert kit.onboard.inspect(folder)["case"] == "empty"


def test_inspect_ignores_a_project_far_up_the_tree(kit, tmp_path):
    folder = kit.ws / "elsewhere"                                    # not a repo, not inside the project's docs
    folder.mkdir()
    assert kit.onboard.inspect(folder)["case"] == "empty"


def test_inspect_writes_nothing(kit, tmp_path):
    base = tmp_path / "cases"
    ws = umbrella(base / "u")
    code = base / "code"
    (code / "src").mkdir(parents=True)
    (code / "src" / "go.mod").write_text("module x\n", encoding="utf-8")
    (base / "blank").mkdir()
    sub = kit.ws / "cam-docs" / "docs"
    sub.mkdir()
    picks = [ws, ws / "api", kit.ws, kit.ws / "api", kit.ws / "cam-docs", sub, code, base / "blank"]
    before = {p: tree(p) for p in (base, kit.ws)}
    for p in picks:
        kit.onboard.inspect(p)
    assert {p: tree(p) for p in (base, kit.ws)} == before


def test_kind_absent_reads_legacy(kit):
    assert kit.onboard.kind_of({"project": {}}) == "legacy"
    assert kit.onboard.kind_of({"project": {"kind": "greenfield"}}) == "greenfield"


def test_manifests(kit):
    assert kit.onboard.MANIFESTS == ("pom.xml", "build.gradle", "build.gradle.kts", "package.json", "pyproject.toml",
                                     "go.mod", "Cargo.toml", "pubspec.yaml", "composer.json", "Gemfile")


def test_detect_repos_takes_a_workspace(kit, tmp_path):
    other = tmp_path / "other"
    make_repo(other / "solo", {"go.mod": "module solo\n"})
    assert [r["name"] for r in kit.docs.detect_repos(other)] == ["solo"]
    assert [r["name"] for r in kit.docs.detect_repos()] == ["api", "web", "worker"]     # no argument: the kit's workspace
