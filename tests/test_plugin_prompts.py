"""R25: prompts and skills as versioned plugins. A pipeline node names the plugin it uses (`uses: adr-style@1`, also
through `patch: set`); the unit's prompt then carries that plugin's prompts, labelled with its version, and points to
its skills. Only an approved plugin with the pinned major version is used."""
from __future__ import annotations

import pytest
import yaml


def make(kit, version="1.2.0"):
    d = kit.root / ".camarones" / "plugins" / "adr-style"
    (d / "skills" / "adr").mkdir(parents=True, exist_ok=True)
    (d / "plugin.yaml").write_text(yaml.safe_dump({"name": "adr-style", "version": version,
                                                   "provides": {"prompts": ["adr.md"], "skills": ["skills/adr"]}}),
                                   encoding="utf-8")
    (d / "adr.md").write_text("Every ADR names the people who decided and links the ticket.\n", encoding="utf-8")
    (d / "skills" / "adr" / "SKILL.md").write_text("---\nname: adr\n---\nWrite ADRs.\n", encoding="utf-8")
    return d


def pin(kit, uses):
    (kit.root / ".camarones" / "pipeline.yaml").write_text(yaml.safe_dump(
        {"extends": "kit:full", "patch": [{"op": "set", "node": "decisions-quality", "uses": uses}]}), encoding="utf-8")


@pytest.fixture
def approved(wired):
    import importlib
    trust = importlib.import_module("lib.trust")
    make(wired)
    trust.approve()
    wired.plan.sync()
    return wired


def test_the_unit_prompt_carries_the_plugins_prompt(approved):
    pin(approved, "adr-style@1")
    text = approved.plan.prompt("decisions-quality", "en")
    assert "adr-style 1.2.0" in text and "names the people who decided" in text
    assert ".camarones/plugins/adr-style/skills/adr" in text


def test_other_units_are_unchanged(approved):
    pin(approved, "adr-style@1")
    assert "adr-style" not in approved.plan.prompt("domain", "en")


def test_a_wrong_major_is_a_pipeline_error(approved):
    pin(approved, "adr-style@2")
    assert any("uses: adr-style is 1.2.0, the node needs 2.x" in p for p in approved.plan.pipeline_problems())


def test_an_unapproved_plugin_is_never_put_in_a_prompt(wired):
    make(wired)
    wired.plan.sync()
    pin(wired, "adr-style@1")
    assert any("needs approval" in p for p in wired.plan.pipeline_problems())
    assert "names the people who decided" not in wired.plan.prompt("decisions-quality", "en")
