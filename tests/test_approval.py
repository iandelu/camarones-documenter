"""Pipeline approval gate: a node with `approval: true` does not finish on `plan done`. It waits as blocked, "awaiting
approval", until a person runs `plan approve <unit>` or presses Approve in the portal; its dependents wait for that,
autopilot and parallel runs never relaunch it, and a worktree unit's work is merged so it can be reviewed."""
from __future__ import annotations

import os, subprocess, sys

import pytest
import yaml

from conftest import KIT_DIR
from test_portal_actions import get, post, server  # noqa: F401 — the portal server fixture
from test_scheduler import fake, run, status  # noqa: F401 — the fake agent fixture


def gate(wired, node="discovery:*"):
    (wired.root / ".camarones" / "pipeline.yaml").write_text(
        yaml.safe_dump({"extends": "kit:full", "patch": [{"op": "set", "node": node, "approval": True}]}),
        encoding="utf-8")
    wired.plan.sync()


def test_done_waits_for_a_person(wired):
    gate(wired)
    wired.plan.set_status("setup", "done")
    u = wired.plan.set_status("discovery:api", "done", "pages written")
    assert u["status"] == "blocked" and wired.plan.awaiting(u)
    assert "plan approve discovery:api" in u["notes"] and "pages written" in u["notes"]
    for d in ("api", "web", "worker"):
        if d != "api":
            wired.plan.set_status(f"discovery:{d}", "done")
            wired.plan.approve(f"discovery:{d}", by="ana")
    ready = {u["id"] for u in wired.plan.available()}
    assert "discovery:api" not in ready and "discovery-cross" not in ready          # nobody relaunches or skips it
    u = wired.plan.approve("discovery:api", by="ana")
    assert u["status"] == "done" and "approved by ana" in u["notes"]
    assert "discovery-cross" in {u["id"] for u in wired.plan.available()}
    with pytest.raises(ValueError):
        wired.plan.approve("discovery:api", by="ana")                               # nothing to approve now


def test_units_without_the_setting_finish_as_before(wired):
    wired.plan.sync()
    assert wired.plan.set_status("setup", "done")["status"] == "done"


def test_the_setting_is_validated(wired):
    from lib.harness import pipeline
    spec, errors = pipeline.compose({"patch": [{"op": "set", "node": "setup", "approval": "yes"}]}, "full")
    assert any("approval" in e and "true or false" in e for e in errors), errors


def test_cli_approve(wired):
    gate(wired)
    wired.plan.set_status("setup", "done")
    env = {**os.environ, "CAMARONES_ROOT": str(wired.root)}
    cli = lambda *a: subprocess.run([sys.executable, str(KIT_DIR / "camarones.py"), "plan", *a], env=env,  # noqa: E731
                                    capture_output=True, text=True, encoding="utf-8")
    assert "discovery:api → blocked: awaiting approval" in cli("done", "discovery:api").stdout
    r = cli("approve", "discovery:api")
    assert r.returncode == 0 and "discovery:api → done" in r.stdout, r.stderr
    assert cli("approve", "discovery:api").returncode == 2


def test_portal_approve(wired, server):  # noqa: F811
    gate(wired)
    wired.plan.set_status("setup", "done")
    wired.plan.set_status("discovery:web", "done")
    unit = next(u for u in get(f"{server}/api/pipeline")["units"] if u["id"] == "discovery:web")
    assert unit["awaiting"] is True and unit["approval"] is True
    code, u = post(f"{server}/api/units/approve", {"unit": "discovery:web"})
    assert code == 200 and u["status"] == "done"
    assert post(f"{server}/api/units/approve", {"unit": "discovery:web"})[0] == 409
    assert post(f"{server}/api/units/approve", {"unit": "discovery:web"}, header=False)[0] == 403


def test_a_parallel_run_merges_the_work_but_leaves_the_gate_shut(wired, fake):  # noqa: F811
    gate(wired)
    fake["configure"](["fake"], sleep="0.2")
    wired.plan.set_status("setup", "done")
    run(wired, max_parallel=3, per_runner={"fake": 3}, max_units=3)
    assert {status(wired, f"discovery:{r}") for r in ("api", "web", "worker")} == {"blocked"}
    assert (wired.root / "docs" / "notes" / "discovery-api.md").exists()             # merged: ready to review
    assert not (wired.ws / ".cw").exists()
    assert not [e for e in fake["entries"]() if e["unit"] == "discovery-cross"]
