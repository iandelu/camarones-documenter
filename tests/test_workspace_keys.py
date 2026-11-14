"""A repo's own keys in workspace.yaml (`stack:` fixed by a person or an agent, `wiki:`) survive `setup` and the
wizard's repos screen: neither rewrites a repo row from scratch."""
from __future__ import annotations

STACK = "Python 3.10+ · React 19 + Vite 8"


def seed(kit):
    ws = kit.docs.workspace()
    ws["repos"][0].update(stack=STACK, wiki=False)
    kit.docs.save_workspace(ws)
    return ws["repos"][0]["name"]


def row(kit, name):
    return next(r for r in kit.docs.workspace()["repos"] if r["name"] == name)


def test_cli_setup_keeps_a_repos_stack(kit, monkeypatch):
    """What `camaron setup` runs (camarones.py), with the tool installs stubbed out."""
    name = seed(kit)
    monkeypatch.setattr(kit.services.setup, "prerequisites", lambda: {})
    monkeypatch.setattr(kit.services.setup, "install_tools", lambda *a, **kw: None)
    monkeypatch.setattr(kit.services.viewers, "graph", lambda *a, **kw: None)
    kit.services.templates.init_templates(log=lambda _: None)
    kit.services.setup.setup(log=lambda _: None)
    kit.plan.sync()
    kit.plan.set_status("setup", "done", "cli setup")
    r = row(kit, name)
    assert r["stack"] == STACK and r["wiki"] is False


def test_wizard_repos_pick_keeps_a_repos_own_keys(kit, fake_wizard):
    """Re-picking the repos found in the folder (Repos › pick) used to replace each row with the bare detected one."""
    name = seed(kit)
    found = [r["name"] for r in kit.docs.detect_repos()]
    assert name in found
    w = fake_wizard(["pick", found, "go"])
    w.banner = lambda *a, **kw: None
    w.fr_repos(kit.docs.workspace())
    r = row(kit, name)
    assert r["stack"] == STACK and r["wiki"] is False
