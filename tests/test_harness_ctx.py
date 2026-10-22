"""Ctx: where a project lives, built per docs root so one process can address several trees (worktrees, A/B runs)."""
from __future__ import annotations

from conftest import load_kit
from fixtures.builder import make_workspace


def test_two_contexts_in_one_process_do_not_mix(kit, tmp_path):
    from lib.harness.ctx import Ctx
    other = make_workspace(tmp_path / "other")
    a, b = Ctx.for_root(kit.root), Ctx.for_root(other / "cam-docs")
    assert a.work != b.work and a.cache != b.cache and a.workspace != b.workspace
    assert b.cam_layout and b.workspace == other.resolve()
    assert b.work == (other / "cam-docs" / "docs" / ".work").resolve()


def test_state_root_holds_the_plan_while_docs_come_from_the_tree(kit, tmp_path):
    from lib.harness.ctx import Ctx
    tree = make_workspace(tmp_path / "tree") / "cam-docs"
    ctx = Ctx.for_root(tree, state_root=kit.root)
    assert ctx.docs == tree.resolve() / "docs"
    assert ctx.work == kit.root.resolve() / "docs" / ".work"
    assert ctx.runs == kit.root.resolve() / ".camarones" / ".cache" / "runs"


def test_common_globals_derive_from_the_process_context(kit):
    c = kit.common
    assert (c.ROOT, c.WORKSPACE, c.DOCS, c.WORK, c.CACHE) == (c.CTX.root, c.CTX.workspace, c.CTX.docs, c.CTX.work, c.CTX.cache)
    assert c.ROOT == kit.root.resolve() and c.CAM_LAYOUT


def test_state_root_env_redirects_the_plan_only(kit, tmp_path, monkeypatch):
    main = kit.root
    tree = make_workspace(tmp_path / "tree") / "cam-docs"
    monkeypatch.setenv("CAMARONES_STATE_ROOT", str(main))
    k = load_kit(tree, kit.home, tree.parent)
    assert k.common.DOCS == tree.resolve() / "docs"
    assert k.plan.PLAN == main.resolve() / "docs" / ".work" / "plan.yaml"
