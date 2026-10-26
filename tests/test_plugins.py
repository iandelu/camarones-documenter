"""Plugins (R10): a folder with a plugin.yaml manifest. The kit's own pieces use the same format; a project's plugins
live in cam-docs/.camarones/plugins/. Whether a plugin runs code is computed, never trusted from the manifest, and a
plugin that runs code is not loaded until it is approved (R28)."""
from __future__ import annotations

import json

import pytest
import yaml


@pytest.fixture
def plugins(kit):
    from lib.harness import plugins
    return plugins


def make(kit, name, manifest, files=()):
    d = kit.root / ".camarones" / "plugins" / name
    d.mkdir(parents=True, exist_ok=True)
    (d / "plugin.yaml").write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
    for f in files:
        (d / f).write_text("x", encoding="utf-8")
    return d


def by_name(found):
    return {p.name: p for p in found}


def test_gemini_ships_as_a_builtin_plugin(plugins, kit):
    g = by_name(plugins.discover())["gemini"]
    assert g.source == "kit" and g.runs_code and g.active and not g.errors
    from lib.adapters import runners
    assert runners.get("gemini").label == "Gemini CLI"


def test_a_config_only_project_plugin_is_active(plugins, kit):
    make(kit, "plans", {"name": "plans", "version": "1.0.0", "kit": ">=3.16,<5", "provides": {"pipelines": ["p.yaml"]}})
    p = by_name(plugins.discover())["plans"]
    assert p.source == "project" and not p.runs_code and not p.steers_agents and p.active


def test_a_prompt_plugin_steers_agents_and_waits_for_approval(plugins, kit):
    make(kit, "adr-style", {"name": "adr-style", "version": "1.0.0", "kit": ">=3.16,<5",
                            "provides": {"prompts": ["prompts/adr.md"]}})
    p = by_name(plugins.discover())["adr-style"]
    assert not p.runs_code and p.steers_agents and p.needs_trust and not p.active


@pytest.mark.parametrize("provides,files", [
    ({"runners": [{"id": "aider", "argv": ["aider", "{prompt}"]}]}, ()),
    ({"checks": [{"id": "lint", "entry": "check.py:run"}]}, ()),
    ({"hooks": [{"event": "Stop", "command": "echo"}]}, ()),
    ({"mcp": [{"name": "srv", "command": "node"}]}, ()),
    ({"prompts": ["p.md"]}, ("helper.py",)),
    ({"prompts": ["p.md"]}, ("run.sh",)),
])
def test_anything_that_runs_code_waits_for_approval(plugins, kit, provides, files):
    make(kit, "risky", {"name": "risky", "version": "0.1.0", "runs_code": False, "provides": provides}, files)
    p = by_name(plugins.discover())["risky"]
    assert p.runs_code and not p.active and "approval" in p.status


def test_a_project_runner_plugin_is_not_registered(plugins, kit):
    make(kit, "aider", {"name": "aider", "version": "0.1.0",
                        "provides": {"runners": [{"id": "aider", "argv": ["aider", "{prompt}"]}]}})
    from lib.adapters import runners
    with pytest.raises(KeyError):
        runners.get("aider")


def test_manifest_problems_are_reported_by_path(plugins, kit):
    make(kit, "bad", {"name": "Bad Name", "version": "one", "kit": ">=9,<10", "provides": {"widgets": []}})
    p = by_name(plugins.discover())["bad"]
    assert not p.active
    assert "name: use lowercase letters, digits and dashes (got 'Bad Name')" in p.errors
    assert "version: not a semantic version (got 'one')" in p.errors
    assert any(e.startswith("kit: needs kit >=9,<10") for e in p.errors)
    assert "provides.widgets: unknown kind (use checks, exporters, hooks, mcp, pipelines, prompts, runners, skills, types)" in p.errors


def test_a_folder_without_a_readable_manifest_is_reported(plugins, kit):
    d = kit.root / ".camarones" / "plugins" / "broken"
    d.mkdir(parents=True)
    (d / "plugin.yaml").write_text("name: [unclosed", encoding="utf-8")
    p = by_name(plugins.discover())["broken"]
    assert not p.active and p.errors and p.errors[0].startswith("plugin.yaml")


@pytest.mark.parametrize("spec,version,ok", [
    (">=3.16,<4", "3.16.0", True), (">=3.16,<4", "4.0.0", False), (">=3.16,<4", "3.9.9", False),
    ("==3.16.2", "3.16.2", True), ("", "3.16.0", True), (">3.15", "3.15.10", True)])
def test_kit_ranges(plugins, spec, version, ok):
    assert plugins.satisfies(version, spec) is ok


def test_the_cli_lists_plugins_as_json(kit, plugins, capsys):
    make(kit, "adr-style", {"name": "adr-style", "version": "1.0.0", "provides": {"prompts": ["p.md"]}})
    rows = plugins.rows()
    names = [r["name"] for r in rows]
    assert "gemini" in names and "adr-style" in names
    row = next(r for r in rows if r["name"] == "adr-style")
    assert row == {"name": "adr-style", "version": "1.0.0", "source": "project", "provides": ["prompts"],
                   "runs_code": False, "sends_data": False, "status": plugins.NEEDS_APPROVAL, "errors": []}
    assert next(r for r in rows if r["name"] == "confluence")["sends_data"] is True
    json.dumps(rows)


def test_plugins_command(kit):
    import os, subprocess, sys
    make(kit, "risky", {"name": "risky", "version": "0.1.0", "provides": {"hooks": [{"event": "Stop", "command": "x"}]}})
    env = {**os.environ, "CAMARONES_ROOT": str(kit.root)}
    out = subprocess.run([sys.executable, str(kit.kit_dir / "camarones.py"), "plugins"], env=env, capture_output=True,
                         text=True, encoding="utf-8")
    assert out.returncode == 0, out.stderr
    assert "gemini" in out.stdout and "risky" in out.stdout and "needs approval" in out.stdout
    js = subprocess.run([sys.executable, str(kit.kit_dir / "camarones.py"), "plugins", "--json"], env=env,
                        capture_output=True, text=True, encoding="utf-8")
    assert {r["name"] for r in json.loads(js.stdout)} >= {"gemini", "risky"}


def test_a_kit_plugin_can_be_turned_off_on_this_machine(plugins, kit):
    """Gemini ships with the kit and is on by default; turning it off sticks on this machine and drops its runner."""
    assert plugins.disable("gemini")
    g = by_name(plugins.discover())["gemini"]
    assert not g.active and g.status == plugins.OFF
    assert "gemini" not in [r["id"] for r in plugins.provided("runners")]
    row = next(r for r in plugins.rows() if r["name"] == "gemini")
    assert row["status"] == plugins.OFF and row["source"] == "kit"
    assert plugins.enable("gemini")
    assert by_name(plugins.discover())["gemini"].active


def test_turning_off_a_plugin_keeps_the_other_approvals(plugins, kit):
    make(kit, "adr-style", {"name": "adr-style", "version": "1.0.0", "provides": {"prompts": ["p.md"]}})
    assert plugins.enable("adr-style")
    assert plugins.disable("gemini")
    assert by_name(plugins.discover())["adr-style"].active
    assert plugins.disable("adr-style")
    assert not by_name(plugins.discover())["adr-style"].active
