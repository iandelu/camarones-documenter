"""Wiring: everything lives in cam-docs, the service repos only get an untracked openwiki link (+ optional pointer)."""
from __future__ import annotations

import json, subprocess, sys
from pathlib import Path

import pytest

from fixtures.builder import git


def porcelain(repo) -> set[str]:
    return set(git(repo, "status", "--porcelain").splitlines())


def test_repos_only_get_the_optional_claude_pointer(wired):
    # the openwiki link is excluded locally; the pointer block (opted in by the fixture) is the only visible change
    assert porcelain(wired.ws / "api") == {" M CLAUDE.md"}
    assert porcelain(wired.ws / "web") == {"?? CLAUDE.md"}
    for r in ("api", "web", "worker"):
        assert "/openwiki" in (wired.ws / r / ".git" / "info" / "exclude").read_text(encoding="utf-8").splitlines()
        assert wired.services.links._is_link(wired.ws / r / "openwiki")
        assert (wired.root / "wikis" / r).is_dir()


def test_repos_stay_clean_without_the_pointer(kit):
    for r in kit.docs.repo_names():
        kit.services.setup.wire_repo(r, log=lambda _: None, comps=["openwiki"])
        assert porcelain(kit.ws / r) == set()


def test_pointer_is_idempotent_and_keeps_the_teams_text(kit):
    f = kit.ws / "api" / "CLAUDE.md"
    before = f.read_text(encoding="utf-8")
    assert kit.services.setup.add_repo_pointer("api") is True
    assert kit.services.setup.add_repo_pointer("api") is False
    text = f.read_text(encoding="utf-8")
    assert text.startswith(before.rstrip()) and text.count(kit.services.setup.POINTER_START) == 1


def test_link_never_replaces_a_real_file(kit):
    real = kit.ws / "AGENTS.md"
    real.write_text("team notes", encoding="utf-8")
    (kit.root / "AGENTS.md").write_text("kit", encoding="utf-8")
    assert kit.services.links.link(real, kit.root / "AGENTS.md", log=lambda _: None) is False
    assert real.read_text(encoding="utf-8") == "team notes"


def test_workspace_links_point_into_cam_docs(wired):
    assert set(wired.linked) >= {".claude", ".codex", ".agents"}     # folders link even without symlink rights
    for n in wired.linked:
        assert (wired.ws / n).resolve() == (wired.root / n).resolve()


def test_linking_again_keeps_the_links_quietly(wired):
    """Windows without symlink rights links folders as junctions: a second setup must see them as its own links."""
    said = []
    assert set(wired.services.setup.link_workspace(log=said.append)) == set(wired.linked)
    assert not [m for m in said if "already exists" in m]


def test_agents_md_refresh_only_touches_the_kit_block(wired):
    f = wired.root / "AGENTS.md"
    a, b = "<!-- camarones:start -->", "<!-- camarones:end -->"
    text = f.read_text(encoding="utf-8")
    edited = "# Mine\n\nteam rules\n\n" + text[:text.index(a)] + a + "\nstale\n" + b + text[text.index(b) + len(b):] + "\ntail\n"
    f.write_text(edited, encoding="utf-8")
    assert wired.services.templates.refresh_block(wired.kit_dir / "templates" / "AGENTS.md", f, "demo")
    new = f.read_text(encoding="utf-8")
    assert new.startswith("# Mine\n\nteam rules") and new.endswith("\ntail\n") and "\nstale\n" not in new


def test_existing_claude_md_gets_the_agents_import(kit):
    f = kit.root / "CLAUDE.md"
    f.write_text("project notes\n", encoding="utf-8")
    kit.services.templates.ensure_agents_import(f)
    kit.services.templates.ensure_agents_import(f)
    assert f.read_text(encoding="utf-8") == "@AGENTS.md\n\nproject notes\n"


def test_agent_config_merges_with_the_users_own(kit):
    (kit.root / ".mcp.json").write_text(json.dumps({"mcpServers": {"mine": {"command": "x"}}}), encoding="utf-8")
    (kit.root / ".codex").mkdir()
    (kit.root / ".codex" / "config.toml").write_text('model = "o4"\n', encoding="utf-8")
    (kit.root / ".claude").mkdir()
    (kit.root / ".claude" / "settings.json").write_text(json.dumps({"hooks": {"PreToolUse": [
        {"hooks": [{"command": "graphify hook"}]}, {"hooks": [{"command": "my-hook"}]}]}}), encoding="utf-8")
    kit.services.setup.write_agent_config(["likec4", "agents"])
    kit.services.setup.write_agent_config(["likec4", "agents"])       # idempotent
    mcp = json.loads((kit.root / ".mcp.json").read_text(encoding="utf-8"))["mcpServers"]
    assert set(mcp) == {"mine", "camarones", "likec4"}
    toml = (kit.root / ".codex" / "config.toml").read_text(encoding="utf-8")
    assert toml.startswith('model = "o4"') and toml.count(kit.services.agent_config.CODEX_MCP_START) == 1
    st = json.loads((kit.root / ".claude" / "settings.json").read_text(encoding="utf-8"))
    assert st["hooks"]["PreToolUse"] == [{"hooks": [{"command": "my-hook"}]}]
    assert set(st["enabledMcpjsonServers"]) >= {"camarones", "likec4"}


def test_dropping_a_component_removes_its_mcp_server(kit):
    kit.services.setup.write_agent_config(["likec4", "agents"])
    kit.services.setup.write_agent_config(["agents"])
    assert "likec4" not in json.loads((kit.root / ".mcp.json").read_text(encoding="utf-8"))["mcpServers"]


def test_init_templates_never_overwrites_project_docs(kit):
    kit.services.templates.init_templates(log=lambda _: None)
    page = kit.root / "docs" / "guides" / "tutorial.md"
    page.write_text("ours", encoding="utf-8")
    created = kit.services.templates.init_templates(log=lambda _: None)
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


def test_migrate_cleanup_restores_head_bytes_and_line_endings(kit):
    repo = kit.ws / "api"
    head = (repo / "CLAUDE.md").read_bytes()
    with (repo / "CLAUDE.md").open("a", encoding="utf-8", newline="\r\n") as fh:    # what a Windows text write leaves
        fh.write("\n## graphify\nuse graphify-out/\n")
    (repo / ".gitignore").write_bytes(b"target/\ngraphify-out/\n")
    kit.migrate.Cleaner("api", dry=False).run()
    assert (repo / "CLAUDE.md").read_bytes() == head
    assert (repo / ".gitignore").read_bytes() == b"target/\n"
    assert porcelain(repo) == set()


# ---------- a workspace that already had its own agent config ----------
def own_folder(wired, n=".claude"):
    """The person's own folder at the workspace root, made before the kit (Claude Code's local settings in it)."""
    p = wired.ws / n
    if p.is_symlink() or wired.services.links._linked(p):
        wired.services.links._unlink(p)
    p.mkdir()
    (p / "settings.local.json").write_text('{"permissions": {"allow": ["Bash(ls)"]}}', encoding="utf-8")
    return p


def file_links(wired) -> bool:
    """Windows without symlink rights links folders (junctions) but not files: the fixture's AGENTS.md says which."""
    return wired.services.links._linked(wired.ws / "AGENTS.md")


def test_a_real_agent_folder_gets_the_kit_s_entries_linked_in(wired):
    """Repair cannot link a folder that is the person's: it links the kit's entries inside it and keeps theirs."""
    from lib import install_state
    mine = own_folder(wired)
    assert any(d["path"].endswith("/.claude") and d.get("why") == "missing" for d in install_state.drift())
    assert ".claude" in wired.services.setup.link_workspace(log=lambda _: None) or not file_links(wired)
    assert (mine / "settings.local.json").read_text(encoding="utf-8").startswith('{"permissions"')
    assert (mine / "skills").resolve() == (wired.root / ".claude" / "skills").resolve()
    if not file_links(wired):
        return
    assert not any(d["path"].endswith("/.claude") for d in install_state.drift())
    said = []
    assert ".claude" in wired.services.setup.link_workspace(log=said.append)       # again: nothing to do, nothing said
    assert not [m for m in said if ".claude" in m]


def test_an_entry_of_the_person_s_in_their_folder_is_kept_and_named_as_theirs(wired):
    from lib import install_state
    mine = own_folder(wired)
    (mine / "skills").mkdir()
    (mine / "skills" / "ours.md").write_text("ours\n", encoding="utf-8")
    wired.services.setup.link_workspace(log=lambda _: None)
    assert not wired.services.links._linked(mine / "skills") and (mine / "skills" / "ours.md").is_file()
    off = {d["path"]: d for d in install_state.drift()}
    assert off[f"{wired.ws.name}/.claude"]["why"] == "yours"


def test_the_person_s_own_claude_md_imports_the_kit_rules(wired):
    from lib import install_state
    if not file_links(wired):                               # no linked AGENTS.md: nothing to import
        return
    mine = wired.ws / "CLAUDE.md"
    wired.services.links._unlink(mine)
    mine.write_text("# Our workspace\n\nRead this first.\n", encoding="utf-8")
    assert any(d["path"].endswith("/CLAUDE.md") for d in install_state.drift())
    assert "CLAUDE.md" in wired.services.setup.link_workspace(log=lambda _: None)
    text = mine.read_text(encoding="utf-8")
    assert text.startswith("# Our workspace\n\nRead this first.\n") and text.rstrip().endswith("@AGENTS.md")
    assert not any(d["path"].endswith("/CLAUDE.md") for d in install_state.drift())
    wired.services.setup.link_workspace(log=lambda _: None)
    assert mine.read_text(encoding="utf-8") == text                                   # once
    assert wired.services.links.drop_kit_import(mine) is True
    assert mine.read_text(encoding="utf-8") == "# Our workspace\n\nRead this first.\n"
    assert wired.services.links.drop_kit_import(mine) is False


def test_a_file_of_the_person_s_that_cannot_be_merged_is_named_as_theirs(wired):
    from lib import install_state
    agents = wired.ws / "AGENTS.md"
    if wired.services.links._linked(agents):
        wired.services.links._unlink(agents)
    agents.write_text("the team's own\n", encoding="utf-8")
    off = {d["path"]: d for d in install_state.drift()}
    assert off[f"{wired.ws.name}/AGENTS.md"]["why"] == "yours"
    wired.services.setup.link_workspace(log=lambda _: None)
    assert agents.read_text(encoding="utf-8") == "the team's own\n"


def test_the_import_keeps_the_person_s_line_endings_and_comes_out_byte_for_byte(wired):
    if not file_links(wired):
        return
    mine = wired.ws / "CLAUDE.md"
    wired.services.links._unlink(mine)
    original = b"# Ours\r\n\r\nWindows notes.\r\n"
    mine.write_bytes(original)
    wired.services.setup.link_workspace(log=lambda _: None)
    merged = mine.read_bytes()
    assert merged.startswith(original) and b"@AGENTS.md\r\n" in merged and b"\n" not in merged.replace(b"\r\n", b"")
    assert wired.services.links.drop_kit_import(mine) is True
    assert mine.read_bytes() == original


def test_a_claude_md_without_a_final_newline_comes_back_as_it_was(wired):
    if not file_links(wired):
        return
    mine = wired.ws / "CLAUDE.md"
    wired.services.links._unlink(mine)
    mine.write_bytes(b"# Ours")
    wired.services.setup.link_workspace(log=lambda _: None)
    assert mine.read_bytes().startswith(b"# Ours\n") and b"@AGENTS.md" in mine.read_bytes()
    wired.services.links.drop_kit_import(mine)
    assert mine.read_bytes() == b"# Ours"


@pytest.mark.skipif(sys.platform != "win32", reason="junctions are Windows only")
def test_a_junction_is_linked_and_unlinked_without_following_it(kit, tmp_path):
    """Windows junctions (mklink /J) are what the kit falls back to without symlink rights: seen as links, and removed
    without touching what they lead to."""
    t, p = tmp_path / "t", tmp_path / "p"
    t.mkdir()
    (t / "keep.txt").write_text("kept", encoding="utf-8")
    subprocess.run(["cmd", "/c", "mklink", "/J", str(p), str(t)], check=True, capture_output=True)
    assert kit.services.links._linked(p)
    if hasattr(Path, "is_junction"):              # _is_link sees a junction only through Path.is_junction (Python 3.12+)
        assert kit.services.links._is_link(p)
    kit.services.links._unlink(p)
    assert not p.exists() and not p.is_symlink()
    assert (t / "keep.txt").read_text(encoding="utf-8") == "kept"
