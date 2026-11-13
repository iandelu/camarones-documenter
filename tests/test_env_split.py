"""The split of lib/env.py (hexagonal refactor F4): every name it defines has one home, a moved name lives in its home,
and kit code outside the new modules reaches a moved name only through services (lib/app/services.py)."""
from __future__ import annotations

import ast
import importlib
import re

from conftest import KIT_DIR, REPO
from fixtures import archscan

# The names env.py defined before the split (top-level def, class and assignment targets), generated once with ast.
ENV_NAMES = frozenset({
    "ALL_COMPONENTS", "AUTO_SHARE", "C4_TITLE_RE", "C4_VIEW_RE", "CHECKPOINT_PATHS", "CODEX_MCP_END", "CODEX_MCP_RE",
    "CODEX_MCP_START", "COVERAGE", "ENGINE_DOWN", "ENGINE_HELP", "EXTRAS", "GRAPHIFY_SECTION", "JVM_MARKERS",
    "KIT_DOCS", "KIT_DOCS_STAMP", "KIT_IMPORT", "KIT_TOOLS", "LINKS", "LOCAL_ONLY", "Log", "OPENWIKI_INSTALL",
    "OPENWIKI_REPO_FILES", "POINTER_END", "POINTER_START", "PROVIDER_KEYS", "RENDERED_SKILLS", "SERVE_PID", "SHARED",
    "STARTER_MARK", "TEMPLATES", "VIEWERS", "WIKI_LINK_RE", "WIKI_LOCK", "WIKI_SCOPE", "WIKI_STAMP", "WikiAbort",
    "_WikiRun", "_append_lines", "_git_said", "_ident", "_inside", "_is_link", "_kit_doc_files", "_linked", "_merge",
    "_own_file", "_points_at", "_raw", "_real", "_real_skills_dir", "_remote_host", "_rendered_entry", "_sha",
    "_shared", "_sharing", "_stderr", "_unlink", "add_repo_pointer", "arch_dir", "arch_start", "arch_validate",
    "auto_share", "board_repair", "build_c4", "build_graphs", "c4_views", "camarones_mcp", "checkpoint_commit",
    "checkpoint_paths", "claude_config", "code_graphs", "codex_block", "components", "compose_cmd", "detect_forge",
    "docker_down", "docker_ready", "docker_up", "docs_remote", "drop_kit_import", "edited_kit_docs",
    "ensure_agents_import", "export_site", "fill", "forge_edit_base", "git_exclude", "graph", "graph_repo",
    "image_context", "init_templates", "install_ci", "install_graphify_skill", "install_prereq", "install_tools",
    "java_info", "jvm_repos", "kit_skill_files", "likec4_mcp", "link", "link_repo_wiki", "link_workspace",
    "merged_links", "newest", "node_major", "npm_global", "npm_global_version", "old_wikis", "open_new_terminal",
    "open_url", "openwiki_credentials", "openwiki_generate", "openwiki_installed", "openwiki_wired", "portal",
    "portal_steps", "portal_token", "portal_url", "prerequisites", "project_id", "refresh_agent_config",
    "refresh_block", "repo_changed_at", "repo_graph", "repo_mcp_entry", "repo_mcp_registered", "serve_editor",
    "serve_local", "set_auto_share", "set_components", "set_profile", "set_remote", "setup", "setup_steps", "share",
    "skill_files", "stamp_wiki", "starter_brief", "stop_local", "stream", "sync_kit_docs", "sync_status", "tool_ok",
    "tool_version", "unlink_agent_config", "unwire_repo_mcp", "viewers", "wiki_brief_kind", "wiki_brief_ready",
    "wiki_close", "wiki_engine_help", "wiki_engines", "wiki_graph", "wiki_lock", "wiki_nav", "wiki_old", "wiki_open",
    "wiki_pages", "wiki_prompt", "wiki_scope", "wiki_workdir", "wikis", "wire_one", "wire_openwiki", "wire_repo",
    "wire_repo_mcp", "wire_umbrella", "without_graphify_hooks", "workspace_off", "writable", "write_agent_config",
    "write_codex_mcp", "write_kit_skills",
})
REEXPORTS = {"pid_alive", "git_failure"}            # env imports these two for its callers (P13)

# The plan's Name map: each home (a dotted module under lib; `ci` is lib/ci.py) and the names it receives.
_MAP: dict[str, tuple[str, ...]] = {
    "ports": ("Log",),
    "adapters.system.os_open": ("open_url", "open_new_terminal"),
    "adapters.likec4": ("arch_dir", "arch_validate", "arch_start", "C4_VIEW_RE", "C4_TITLE_RE", "c4_views"),
    "adapters.fs_links": (
        "LINKS", "LOCAL_ONLY", "KIT_IMPORT", "_append_lines", "git_exclude", "_is_link", "_linked", "_unlink", "link",
        "_points_at", "_inside", "workspace_off", "_raw", "_merge", "drop_kit_import", "merged_links",
        "link_repo_wiki"),
    "adapters.agent_config": (
        "camarones_mcp", "likec4_mcp", "CODEX_MCP_START", "CODEX_MCP_END", "CODEX_MCP_RE", "codex_block",
        "GRAPHIFY_SECTION", "without_graphify_hooks", "claude_config", "repo_mcp_entry", "repo_mcp_registered",
        "wire_repo_mcp", "unwire_repo_mcp"),
    "adapters.prereqs": (
        "node_major", "install_prereq", "tool_version", "npm_global", "npm_global_version", "openwiki_installed",
        "tool_ok"),
    "adapters.graphify": ("repo_graph", "graph_repo"),
    "adapters.openwiki": (
        "PROVIDER_KEYS", "openwiki_credentials", "openwiki_wired", "OPENWIKI_INSTALL", "OPENWIKI_REPO_FILES",
        "wiki_open", "wiki_close", "wiki_workdir", "wiki_lock"),
    "core.paths": ("WIKI_STAMP", "WIKI_LOCK"),
    "adapters.docker": ("docker_ready", "image_context"),
    "adapters.git.checkpoint": ("CHECKPOINT_PATHS", "checkpoint_paths"),
    "app.components": ("KIT_TOOLS", "EXTRAS", "ALL_COMPONENTS", "components", "set_profile", "set_components"),
    "app.templates": (
        "TEMPLATES", "KIT_DOCS", "KIT_DOCS_STAMP", "_real", "_own_file", "fill", "kit_skill_files", "skill_files",
        "RENDERED_SKILLS", "_real_skills_dir", "_rendered_entry", "write_kit_skills", "init_templates",
        "ensure_agents_import", "_kit_doc_files", "_sha", "edited_kit_docs", "sync_kit_docs", "refresh_block"),
    "app.viewers": (
        "VIEWERS", "build_c4", "code_graphs", "build_graphs", "graph", "newest", "repo_changed_at", "viewers"),
    "app.setup": (
        "JVM_MARKERS", "jvm_repos", "java_info", "prerequisites", "install_tools", "POINTER_START", "POINTER_END",
        "write_codex_mcp", "install_graphify_skill", "write_agent_config", "refresh_agent_config", "wire_repo",
        "add_repo_pointer", "wire_one", "wire_umbrella", "setup_steps", "setup", "link_workspace",
        "unlink_agent_config"),
    "app.share": (
        "AUTO_SHARE", "SHARED", "_sharing", "auto_share", "set_auto_share", "sync_status", "docs_remote", "set_remote",
        "_remote_host", "_git_said", "_ident", "share", "_shared", "_stderr", "board_repair", "checkpoint_commit"),
    "app.wiki": (
        "ENGINE_HELP", "wiki_engines", "wire_openwiki", "wiki_engine_help", "wiki_pages", "WIKI_LINK_RE", "wiki_nav",
        "WIKI_SCOPE", "wiki_scope", "stamp_wiki", "wiki_old", "old_wikis", "STARTER_MARK", "COVERAGE",
        "starter_brief", "wiki_brief_kind", "wiki_brief_ready", "wikis", "wiki_prompt", "WikiAbort", "ENGINE_DOWN",
        "_WikiRun", "openwiki_generate", "wiki_graph"),
    "core.process": ("stream",),
    "app.portal": (
        "SERVE_PID", "serve_local", "serve_editor", "portal_url", "portal_token", "stop_local", "project_id",
        "compose_cmd", "docker_up", "docker_down"),
    "app.export_site": ("forge_edit_base", "export_site", "portal", "portal_steps", "writable"),
    "ci": ("detect_forge", "install_ci"),
}
HOME: dict[str, str] = {name: home for home, names in _MAP.items() for name in names}
# MOVED: the homes whose names have moved; each task adds its own
MOVED: set[str] = {"ports", "adapters.system.os_open", "adapters.likec4", "adapters.fs_links", "adapters.agent_config",
                   "adapters.prereqs", "adapters.graphify", "adapters.openwiki", "core.paths"}
NEW: set[str] = {home for home in _MAP if home.startswith(("adapters.", "app."))}   # the modules F4 creates

TEST_READS = (re.compile(r"(?<![\w.])(?:kit\.)?(?:\w+\.)?env\.([A-Za-z_]\w*)"), re.compile(r"lib\.env\.([A-Za-z_]\w*)"),
              re.compile(r"setattr\(\s*(?:\w+\.)*env\s*,\s*[\"']([A-Za-z_]\w*)[\"']"))   # setattr(kit.env, "name", …)
SERVICES = "app.services"


def test_every_env_name_has_one_home():
    listed = [name for names in _MAP.values() for name in names]
    assert sorted({n for n in listed if listed.count(n) > 1}) == []
    assert set(HOME) == ENV_NAMES


def test_moved_names_live_in_their_home(kit):
    env = vars(importlib.import_module("lib.env"))
    wrong = []
    for name, home in sorted(HOME.items()):
        if home not in MOVED:
            continue
        mod = importlib.import_module(f"lib.{home}")
        if not hasattr(mod, name):
            wrong.append(f"lib.{home} has no {name}")
        elif home.startswith(("adapters.", "app.")) or home == "ci":
            if name in env:
                wrong.append(f"lib.env still defines {name} (moved to lib.{home})")
        elif name in env and env[name] is not getattr(mod, name):        # ports, core.*: env may import it
            wrong.append(f"lib.env's {name} is not lib.{home}'s")
    assert wrong == []


def _is_facade(path) -> bool:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return any(isinstance(t, ast.Name) and t.id == "__facade__"
               for n in tree.body if isinstance(n, ast.Assign) for t in n.targets)


def test_moved_code_is_reached_through_services():
    mods = archscan.modules(KIT_DIR)
    env_facade = _is_facade(mods["env"])
    bad = sorted(f"{a} -> {b}" for a, b in archscan.edges(mods)
                 if b in NEW and not (a in NEW or a == "bootstrap" or (a == "env" and env_facade)))
    assert bad == [], ("outside the new modules, kit code reaches a moved name through services "
                       "(cli.services, req.services or services.current()), never by importing its module:\n"
                       + "\n".join(bad))


def test_no_test_reaches_a_moved_name_through_env():
    found = []
    for f in sorted((REPO / "tests").rglob("*.py")):
        for i, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            names = {m.group(1) for pattern in TEST_READS for m in pattern.finditer(line)}  # "lib.env.X" hits both
            found += [f"{f.relative_to(REPO).as_posix()}:{i}: {n} (read or patch lib.{HOME[n]})"
                      for n in sorted(names) if HOME.get(n) in MOVED]
    assert found == []


def _install_calls(mods) -> list[str]:
    """Each call of lib.app.services.install, as `module:line`, however the module imported it."""
    out = []
    for name, path in mods.items():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        holders: set[str] = set()                    # names bound to the services module
        direct: set[str] = set()                     # names bound to its install()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and (node.level or archscan._is_kit(node.module)):
                target = archscan._from_target(name, path.name == "__init__.py", node)
                for a in node.names:
                    if (f"{target}.{a.name}" if target else a.name) == SERVICES:
                        holders.add(a.asname or a.name)
                    elif target == SERVICES and a.name == "install":
                        direct.add(a.asname or a.name)
            elif isinstance(node, ast.Import):
                holders |= {a.asname or a.name for a in node.names if archscan._strip_root(a.name) == SERVICES}
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            f = node.func
            if (isinstance(f, ast.Name) and f.id in direct) or (
                    isinstance(f, ast.Attribute) and f.attr == "install" and ast.unparse(f.value) in holders):
                out.append(f"{name}:{node.lineno}")
    return out


def test_only_the_cli_entry_imports_bootstrap():
    mods = archscan.modules(KIT_DIR)
    assert sorted(a for a, b in archscan.edges(mods) if b == "bootstrap") == ["interfaces.cli.main"]
    assert {c.split(":")[0] for c in _install_calls(mods)} - {SERVICES} == {"bootstrap"}


def test_the_guard_sees_the_setattr_form():
    seen = {m.group(1) for line in ('monkeypatch.setattr(kit.env, "zz", f)', "monkeypatch.setattr(wired.env, 'x', f)",
                                    'monkeypatch.setattr( agents.env , "y", f)')
            for m in TEST_READS[2].finditer(line)}
    assert seen == {"zz", "x", "y"}
    assert not TEST_READS[2].search('monkeypatch.setattr(kit.services.launcher, "zz", f)')
