"""The synthetic workspace is built once per process and copied per call: every copy is its own, complete and clean."""
from __future__ import annotations

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


def test_other_layouts_are_templates_of_their_own(tmp_path):
    ws = make_workspace(tmp_path, repos=("api",), name="solo")
    assert sorted(p.name for p in ws.iterdir()) == ["api", "cam-docs"]
    assert "name: solo" in (ws / "cam-docs" / ".camarones" / "workspace.yaml").read_text(encoding="utf-8")
