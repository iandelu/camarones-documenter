"""Wiring: everything lives in cam-docs, the service repos only get an untracked openwiki link (+ optional pointer)."""
from __future__ import annotations

import json, subprocess

from fixtures.builder import git


def porcelain(repo) -> set[str]:
    return set(git(repo, "status", "--porcelain").splitlines())


def test_repos_only_get_the_optional_claude_pointer(wired):
    # the openwiki link is excluded locally; the pointer block (opted in by the fixture) is the only visible change
    assert porcelain(wired.ws / "api") == {" M CLAUDE.md"}
    assert porcelain(wired.ws / "web") == {"?? CLAUDE.md"}
    for r in ("api", "web", "worker"):
        assert "/openwiki" in (wired.ws / r / ".git" / "info" / "exclude").read_text(encoding="utf-8").splitlines()
        assert wired.env._is_link(wired.ws / r / "openwiki")
        assert (wired.root / "wikis" / r).is_dir()


def test_repos_stay_clean_without_the_pointer(kit):
    env = kit.env
    for r in kit.docs.repo_names():
        env.wire_repo(r, log=lambda _: None, comps=["openwiki"])
        assert porcelain(kit.ws / r) == set()


def test_pointer_is_idempotent_and_keeps_the_teams_text(kit):
    f = kit.ws / "api" / "CLAUDE.md"
    before = f.read_text(encoding="utf-8")
    assert kit.env.add_repo_pointer("api") is True
    assert kit.env.add_repo_pointer("api") is False
    text = f.read_text(encoding="utf-8")
    assert text.startswith(before.rstrip()) and text.count(kit.env.POINTER_START) == 1


def test_link_never_replaces_a_real_file(kit):
    real = kit.ws / "AGENTS.md"
    real.write_text("team notes", encoding="utf-8")
    (kit.root / "AGENTS.md").write_text("kit", encoding="utf-8")
    assert kit.env.link(real, kit.root / "AGENTS.md", log=lambda _: None) is False
    assert real.read_text(encoding="utf-8") == "team notes"


def test_workspace_links_point_into_cam_docs(wired):
    assert set(wired.linked) >= {".claude", ".codex", ".agents"}     # folders link even without symlink rights
    for n in wired.linked:
        assert (wired.ws / n).resolve() == (wired.root / n).resolve()


def test_agents_md_refresh_only_touches_the_kit_block(wired):
    f = wired.root / "AGENTS.md"
    a, b = "<!-- camarones:start -->", "<!-- camarones:end -->"
    text = f.read_text(encoding="utf-8")
    edited = "# Mine\n\nteam rules\n\n" + text[:text.index(a)] + a + "\nstale\n" + b + text[text.index(b) + len(b):] + "\ntail\n"
    f.write_text(edited, encoding="utf-8")
    assert wired.env.refresh_block(wired.kit_dir / "templates" / "AGENTS.md", f, "demo")
    new = f.read_text(encoding="utf-8")
    assert new.startswith("# Mine\n\nteam rules") and new.endswith("\ntail\n") and "\nstale\n" not in new


def test_existing_claude_md_gets_the_agents_import(kit):
    f = kit.root / "CLAUDE.md"
    f.write_text("project notes\n", encoding="utf-8")
    kit.env.ensure_agents_import(f)
    kit.env.ensure_agents_import(f)
    assert f.read_text(encoding="utf-8") == "@AGENTS.md\n\nproject notes\n"


def test_agent_config_merges_with_the_users_own(kit):
    (kit.root / ".mcp.json").write_text(json.dumps({"mcpServers": {"mine": {"command": "x"}}}), encoding="utf-8")
    (kit.root / ".codex").mkdir()
    (kit.root / ".codex" / "config.toml").write_text('model = "o4"\n', encoding="utf-8")
    (kit.root / ".claude").mkdir()
    (kit.root / ".claude" / "settings.json").write_text(json.dumps({"hooks": {"PreToolUse": [
        {"hooks": [{"command": "graphify hook"}]}, {"hooks": [{"command": "my-hook"}]}]}}), encoding="utf-8")
    kit.env.write_agent_config(["likec4", "agents"])
    kit.env.write_agent_config(["likec4", "agents"])                  # idempotent
    mcp = json.loads((kit.root / ".mcp.json").read_text(encoding="utf-8"))["mcpServers"]
    assert set(mcp) == {"mine", "camarones", "likec4"}
    toml = (kit.root / ".codex" / "config.toml").read_text(encoding="utf-8")
    assert toml.startswith('model = "o4"') and toml.count(kit.env.CODEX_MCP_START) == 1
    st = json.loads((kit.root / ".claude" / "settings.json").read_text(encoding="utf-8"))
    assert st["hooks"]["PreToolUse"] == [{"hooks": [{"command": "my-hook"}]}]
    assert set(st["enabledMcpjsonServers"]) >= {"camarones", "likec4"}


def test_dropping_a_component_removes_its_mcp_server(kit):
    kit.env.write_agent_config(["likec4", "agents"])
    kit.env.write_agent_config(["agents"])
    assert "likec4" not in json.loads((kit.root / ".mcp.json").read_text(encoding="utf-8"))["mcpServers"]


def test_init_templates_never_overwrites_project_docs(kit):
    kit.env.init_templates(log=lambda _: None)
    page = kit.root / "docs" / "guides" / "tutorial.md"
    page.write_text("ours", encoding="utf-8")
    created = kit.env.init_templates(log=lambda _: None)
    assert page.read_text(encoding="utf-8") == "ours"
    assert "docs/guides/tutorial.md" not in created
    assert (kit.root / ".git").is_dir()                               # cam-docs is its own git repo


def test_migrate_cleaner_dry_run_reports_without_changing(kit):
    repo = kit.ws / "web"
    (repo / "graphify-out").mkdir()
    (repo / "graphify-out" / "graph.json").write_text("{}", encoding="utf-8")
    (repo / ".claude" / "skills" / "graphify").mkdir(parents=True)
    (repo / ".claude" / "skills" / "graphify" / "SKILL.md").write_text("x", encoding="utf-8")
    (repo / ".gitignore").write_text("graphify-out/\n", encoding="utf-8")
    before = subprocess.run(["git", "status", "--porcelain", "-uall"], cwd=repo, capture_output=True, text=True).stdout
    acts = kit.migrate.Cleaner("web", dry=True).run()
    assert any("graphify-out" in a for a in acts)
    assert any(".claude/skills/graphify" in a for a in acts)
    assert any(".gitignore" in a for a in acts)
    after = subprocess.run(["git", "status", "--porcelain", "-uall"], cwd=repo, capture_output=True, text=True).stdout
    assert before == after and (repo / "graphify-out" / "graph.json").exists()
