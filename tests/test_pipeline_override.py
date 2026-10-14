"""Project override (R8): cam-docs/.camarones/pipeline.yaml extends a kit pipeline, adds nodes and patches existing
ones (disable, needs, set tier/runner). A broken override leaves the stored plan untouched and says what is wrong,
by YAML path."""
from __future__ import annotations

import json, subprocess

import pytest
import yaml


@pytest.fixture
def project(kit):
    path = kit.root / ".camarones" / "pipeline.yaml"

    def write(data):
        if data is None:
            path.unlink(missing_ok=True)
        else:
            path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
        return kit.plan.sync()
    return write


def units(data):
    return {u["id"]: u for u in data["units"]}


def test_disable_drops_the_unit_and_reenabling_brings_it_back(kit, project):
    kit.plan.sync()
    u = units(project({"extends": "kit:full", "patch": [{"op": "disable", "node": "ci"}]}))["ci"]
    assert u["status"] == "dropped" and "pipeline.yaml" in u["notes"]
    u = units(project(None))["ci"]
    assert u["status"] == "todo" and u["notes"] == ""


def test_disable_with_a_wildcard_and_done_units_stay_done(kit, project):
    kit.plan.sync()
    kit.plan.set_status("repo-brief:api", "done")
    data = units(project({"patch": [{"op": "disable", "node": "repo-brief:*"}]}))
    assert data["repo-brief:api"]["status"] == "done"
    assert data["repo-brief:web"]["status"] == "dropped"
    assert "repo-brief:web" not in data["arch-system"]["deps"]


def test_needs_add_and_remove(kit, project):
    data = units(project({"patch": [{"op": "needs", "node": "domain", "add": ["data"], "remove": ["interview-language"]}]}))
    assert data["domain"]["deps"] == ["data"]


def test_the_project_can_add_nodes(kit, project):
    data = units(project({"nodes": [{"id": "security-review", "type": "security-review", "needs": ["arch-system"]}]}))
    assert data["security-review"]["deps"] == ["arch-system"] and data["security-review"]["phase"] == 5


def test_extends_picks_the_base_pipeline(kit, project):
    kit.plan.sync()
    data = units(project({"extends": "kit:quick"}))
    assert data["quick-overview"]["status"] == "todo" and data["discovery-cross"]["status"] == "dropped"


def test_a_broken_override_leaves_the_plan_alone_and_says_where(kit, project):
    before = kit.plan.sync()
    after = project({"extends": "kit:full", "nodes": [
        {"id": "a", "type": "domain"}, {"id": "b", "type": "domain"}, {"id": "c", "type": "domain"},
        {"id": "d", "type": "domain", "needs": ["ghost"]}]})
    assert after["units"] == before["units"]
    assert "nodes[3].needs: unknown node 'ghost'" in kit.plan.pipeline_problems()


def test_patch_errors_name_the_patch_entry(kit, project):
    project({"extends": "kit:nope", "patch": []})
    assert any(p.startswith("extends: unknown pipeline 'kit:nope'") for p in kit.plan.pipeline_problems())
    project({"patch": [{"op": "explode", "node": "ci"}, {"op": "disable", "node": "nope"},
                       {"op": "set", "node": "ci", "colour": "red"}, {"op": "set", "node": "i18n", "tier": "huge"}]})
    problems = kit.plan.pipeline_problems()
    assert any(p.startswith("patch[0].op: unknown op 'explode'") for p in problems)
    assert "patch[1].node: unknown node 'nope'" in problems
    assert any(p.startswith("patch[2]: 'colour'") for p in problems)
    assert any("tier" in p and "huge" in p for p in problems)


def test_unit_settings_come_from_the_type_then_the_patch(kit, project):
    project(None)
    assert kit.plan.settings("i18n")["tier"] == "bounded"
    assert kit.plan.settings("domain") == {"tier": "agentic-heavy"}
    project({"patch": [{"op": "set", "node": "domain", "runner": "codex:o5"}]})
    assert kit.plan.settings("domain") == {"tier": "agentic-heavy", "runner": "codex:o5"}


@pytest.fixture
def pilot(kit, monkeypatch):
    calls = []

    def run_agent(agent, text, lang, uid, echo):
        calls.append((agent, uid))
        kit.plan.set_status(uid, "done")
        return subprocess.CompletedProcess([agent], 0, "", "")
    monkeypatch.setattr(kit.plan, "which", lambda name: f"/bin/{name}")
    monkeypatch.setattr(kit.plan, "_run_agent", run_agent)
    monkeypatch.setattr(kit.plan, "prompt", lambda uid, lang="es", unattended=False: "p")
    return calls


def test_autopilot_uses_the_runner_a_node_asks_for(kit, project, pilot):
    project({"patch": [{"op": "set", "node": "discovery:{repo}", "runner": "codex"}]})
    kit.plan.set_status("setup", "done")
    kit.plan.run_autopilot(max_units=1, echo=lambda _: None)
    assert pilot == [("codex", "discovery:api")]


def test_autopilot_routes_each_unit_by_its_tier(kit, project, pilot):
    from lib.common import PREFS, save_json
    save_json(PREFS, {"routing": {"bounded": ["codex"]}})
    project({"patch": [{"op": "set", "node": "discovery:*", "tier": "bounded"}]})
    kit.plan.set_status("setup", "done")
    kit.plan.run_autopilot(max_units=1, echo=lambda _: None)
    assert pilot == [("codex", "discovery:api")]


def test_schema_for_editors_matches_the_code(kit):
    from lib.harness import pipeline, routing
    schema = json.loads((pipeline.DIR / "schema.json").read_text(encoding="utf-8"))
    defs = schema["$defs"]
    assert set(defs["patch"]["properties"]["op"]["enum"]) == set(pipeline.OPS)
    assert set(defs["condition"]["enum"]) == set(pipeline.CONDITIONS)
    assert set(defs["tier"]["enum"]) == set(routing.TIERS)
