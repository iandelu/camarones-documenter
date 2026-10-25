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


# ---------- first-run state shared by the CLI and the app: name, start, steps ----------
def ws_yaml(root: Path) -> dict:
    return yaml.safe_load((root / ".camarones" / "workspace.yaml").read_text(encoding="utf-8"))


def test_steps_by_mode_and_kind(kit):
    o = kit.onboard
    assert o.steps("new", "legacy") == ("name", "repos", "tools", "setup", "stack", "arch", "intro")
    assert o.steps("new", "greenfield") == ("name", "repos", "tools", "setup", "intro")
    assert o.steps("join", "legacy") == o.steps("join", "greenfield") == ("tools", "setup", "intro")


def test_steps_unknown_kind_reads_legacy(kit):
    assert kit.onboard.steps("new", "greenfiled") == kit.onboard.steps("new", "legacy")


def test_steps_live_in_onboard_and_the_wizard_reexports_them(kit):
    assert kit.wizard.STEPS is kit.onboard.STEPS and kit.wizard.LEGACY_STEPS is kit.onboard.LEGACY_STEPS
    assert kit.wizard.JOIN_STEPS == kit.onboard.steps("join", "legacy")
    assert kit.wizard.first_run_mode is kit.onboard.first_run_mode


def test_start_umbrella(kit, tmp_path):
    ws = umbrella(tmp_path / "u")
    root = kit.onboard.start(ws)
    assert root == (ws / "cam-docs").resolve()
    data = ws_yaml(root)
    assert data["project"]["kind"] == "legacy"
    assert [r["name"] for r in data["repos"]] == ["api", "web", "worker"]
    state = kit.common.load_json(kit.onboard.firstrun_file(root), {})
    assert (state["name"], state["done"]) == ("repos", False)
    assert any(Path(r["path"]).resolve() == root for r in kit.projects.load())


def test_start_a_repo_preselects_only_it(kit, tmp_path):
    ws = umbrella(tmp_path / "u")
    root = kit.onboard.start(ws / "api")
    assert root == (ws / "cam-docs").resolve()
    assert [r["name"] for r in ws_yaml(root)["repos"]] == ["api"]


def test_start_empty_is_greenfield(kit, tmp_path):
    (tmp_path / "blank").mkdir()
    root = kit.onboard.start(tmp_path / "blank")
    data = ws_yaml(root)
    assert data["project"]["kind"] == "greenfield" and data["repos"] == []


def test_start_is_idempotent(kit, tmp_path):
    ws = umbrella(tmp_path / "u")
    root = kit.onboard.start(ws)
    first = (root / ".camarones" / "workspace.yaml").read_bytes()
    assert kit.onboard.start(ws) == root
    assert (root / ".camarones" / "workspace.yaml").read_bytes() == first


def test_start_on_a_project_writes_nothing(kit):
    root = kit.root
    kit.onboard.save_position(root, "tools", "new")
    files = [root / ".camarones" / "workspace.yaml", kit.onboard.firstrun_file(root)]
    before = [f.read_bytes() for f in files]
    assert kit.onboard.start(kit.ws) == root.resolve()
    assert [f.read_bytes() for f in files] == before


def test_start_keeps_a_human_name(kit, tmp_path):
    folder = tmp_path / "Mi Proyecto Ñandú"
    make_repo(folder / "api", {"go.mod": "module api\n"})
    root = kit.onboard.start(folder)
    project = ws_yaml(root)["project"]
    assert project["name"] == "Mi Proyecto Ñandú"
    assert project["id"] == kit.onboard.name_project({"project": {}}, "Mi Proyecto Ñandú", "x")["project"]["id"]
    assert root == (folder / "cam-docs").resolve() and not (root / "cam-docs").exists()


def test_start_writes_what_the_cli_name_step_writes(kit, fake_wizard, tmp_path):
    ws = umbrella(tmp_path / "u")
    project = ws_yaml(kit.onboard.start(ws, "Mi Proyecto"))["project"]
    project.pop("kind")
    fake_wizard(["Mi Proyecto"]).fr_name(kit.docs.workspace())
    cli = kit.docs.workspace()["project"]
    assert project == {k: cli[k] for k in ("name", "id", "canonical_language", "translations")}


def test_start_on_something_that_is_not_a_folder(kit, tmp_path):
    f = tmp_path / "a-file.txt"
    f.write_text("x", encoding="utf-8")
    for bad in (f, tmp_path / "missing"):
        with pytest.raises(ValueError, match=bad.name):
            kit.onboard.start(bad)


def test_inspect_an_unreadable_folder_reads_as_no_repos(kit, tmp_path, monkeypatch):
    (tmp_path / "locked").mkdir()

    def denied(*_a, **_k):
        raise PermissionError("denied")

    monkeypatch.setattr(kit.projects, "has_repos", denied)
    r = kit.onboard.inspect(tmp_path / "locked")
    assert (r["case"], r["repos"]) == ("empty", [])
    monkeypatch.setattr(kit.docs, "detect_repos", denied)
    assert kit.onboard.inspect(tmp_path / "locked")["repos"] == []


def test_name_project_defaults_and_fallback(kit):
    p = kit.onboard.name_project({"project": {"translations": ["fr"], "canonical_language": "es"}}, "  ", "Demo Dir")["project"]
    assert (p["name"], p["id"], p["canonical_language"], p["translations"]) == ("Demo Dir", "demo-dir", "es", ["fr"])


def test_state_written_by_the_app_resumes_the_cli(kit):
    o, root = kit.onboard, kit.root
    o.save_position(root, "setup", "new")
    state = kit.common.load_json(o.firstrun_file(root), {})
    assert state == {"step": o.STEPS.index("setup"), "name": "setup", "done": False}
    assert kit.wizard.resume_step(state) == o.STEPS.index("setup")
    o.save_position(root, "tools", "join")
    state = kit.common.load_json(o.firstrun_file(root), {})
    assert state["mode"] == "join" and o.first_run_mode(state, True, False) == "join"
    o.finish(root, 3)
    assert kit.common.load_json(o.firstrun_file(root), {}) == {"step": 3, "done": True}


def test_firstrun_file_is_the_wizards(kit):
    assert kit.onboard.firstrun_file(kit.root) == kit.wizard.FIRSTRUN
