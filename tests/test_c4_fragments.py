"""C4 in fragments (R14): units that run in parallel each write their own .c4 file, so they never edit the same one.
Shared files (model.c4, spec.c4, views.c4, deployment.c4) are left to in-place units, which run one at a time."""
from __future__ import annotations

import os, shutil, subprocess, time

import pytest

needs_likec4 = pytest.mark.skipif(not shutil.which("likec4"), reason="likec4 not installed")

MODEL = "model {\n  customer = actor 'Customer'\n  demo = system 'Demo' {\n    web = webapp 'Web'\n  }\n  customer -> demo.web 'uses'\n}\n"
VIEWS = "views {\n  view index { include * }\n}\n"
REPO = ("model {\n  extend demo {\n    api = service 'API'\n  }\n  extend demo.api {\n    orders = component 'Orders'\n  }\n"
        "  demo.web -> demo.api 'calls'\n}\nviews {\n  view api_components of demo.api { include * }\n}\n")
FLOW = ("views {\n  dynamic view flow_checkout {\n    customer -> demo.web 'opens checkout'\n"
        "    demo.web -> demo.api 'POST /orders'\n  }\n}\n")


def arch(kit, files):
    d = kit.env.arch_dir()
    spec = (kit.kit_dir / "templates" / "docs" / "architecture" / "spec.c4").read_text(encoding="utf-8")
    for rel, text in {"likec4.config.json": '{"name": "demo"}', "spec.c4": spec, **files}.items():
        f = d / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text, encoding="utf-8", newline="\n")
    return d


@needs_likec4
def test_repo_and_flow_fragments_validate_with_the_shared_model(kit):
    arch(kit, {"model.c4": MODEL, "views.c4": VIEWS, "repos/api.c4": REPO, "flows/checkout.c4": FLOW})
    ok, msg = kit.env.arch_validate()
    assert ok, msg


@needs_likec4
def test_two_fragments_declaring_the_same_element_fail(kit):
    arch(kit, {"model.c4": MODEL, "views.c4": VIEWS, "repos/api.c4": REPO,
               "repos/api-again.c4": "model {\n  extend demo {\n    api = service 'API again'\n  }\n}\n"})
    ok, msg = kit.env.arch_validate()
    assert not ok and "Duplicate" in msg


def test_the_c4_viewer_goes_stale_when_a_fragment_changes(kit):
    d = arch(kit, {"model.c4": MODEL})
    built = kit.env.VIEWERS / "architecture" / "index.html"
    built.parent.mkdir(parents=True, exist_ok=True)
    built.write_text("<html>", encoding="utf-8")
    old = time.time() - 100
    for f in (d / "model.c4", d / "spec.c4", built):
        os.utime(f, (old, old))
    assert not kit.env.viewers()["c4"]["stale"]
    (d / "flows").mkdir(exist_ok=True)
    (d / "flows" / "checkout.c4").write_text(FLOW, encoding="utf-8")
    assert kit.env.viewers()["c4"]["stale"]


def test_integration_notes_a_parallel_unit_that_edited_a_shared_c4_file(wired):
    from lib.harness import integrate
    from lib.harness.worktrees import Worktrees
    wired.plan.sync()
    w = Worktrees(wired.common.CTX).add("repo-brief:api")
    f = w.path / "docs" / "architecture" / "model.c4"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(MODEL, encoding="utf-8")
    (w.path / "docs" / "architecture" / "repos").mkdir()
    (w.path / "docs" / "architecture" / "repos" / "api.c4").write_text(REPO, encoding="utf-8")
    events = []
    r = integrate.integrate("repo-brief:api", wired.common.CTX, gates=[], emit=lambda k, **f: events.append((k, f)))
    assert r.outcome == "merged"
    assert ("c4.shared", {"unit": "repo-brief:api", "files": ["docs/architecture/model.c4"]}) in events


def test_the_playbook_sends_parallel_units_to_their_fragments(kit):
    text = (kit.kit_dir / "PLAYBOOK.md").read_text(encoding="utf-8")
    flow = text.split("\n## flow\n", 1)[1].split("\n## ", 1)[0]
    brief = " ".join(text.split("\n## repo-brief", 1)[1].split("\n## ", 1)[0].split())
    assert "docs/architecture/flows/<slug>.c4" in flow and "views.c4" not in flow
    assert "extend" in brief and "do not edit `model.c4`" in brief
