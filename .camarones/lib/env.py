"""env's helpers moved to lib/adapters and lib/app; tests/test_env_split.py HOME names each home; this path stays for old imports."""
from __future__ import annotations

from .adapters.agent_config import (
    CODEX_MCP_END, CODEX_MCP_RE, CODEX_MCP_START, GRAPHIFY_SECTION, camarones_mcp, claude_config, codex_block,
    likec4_mcp, repo_mcp_entry, repo_mcp_registered, unwire_repo_mcp, wire_repo_mcp, without_graphify_hooks,
)
from .adapters.docker import docker_ready, image_context
from .adapters.fs_links import (
    KIT_IMPORT, LINKS, LOCAL_ONLY, _append_lines, _inside, _is_link, _linked, _merge, _points_at, _raw, _unlink,
    drop_kit_import, git_exclude, link, link_repo_wiki, merged_links, workspace_off,
)
from .adapters.git.checkpoint import CHECKPOINT_PATHS, checkpoint_paths
from .adapters.graphify import graph_repo, repo_graph
from .adapters.likec4 import C4_TITLE_RE, C4_VIEW_RE, arch_dir, arch_start, arch_validate, c4_views
from .adapters.openwiki import (
    OPENWIKI_INSTALL, OPENWIKI_REPO_FILES, PROVIDER_KEYS, openwiki_credentials, openwiki_wired, wiki_close, wiki_lock,
    wiki_open, wiki_workdir,
)
from .adapters.prereqs import (
    install_prereq, node_major, npm_global, npm_global_version, openwiki_installed, tool_ok, tool_version,
)
from .adapters.system.os_open import open_new_terminal, open_url
from .app.components import ALL_COMPONENTS, EXTRAS, KIT_TOOLS, components, set_components, set_profile
from .app.export_site import export_site, forge_edit_base, portal, portal_steps, writable
from .app.portal import (
    SERVE_PID, compose_cmd, docker_down, docker_up, portal_token, portal_url, project_id, serve_editor, serve_local,
    stop_local,
)
from .app.setup import (
    JVM_MARKERS, POINTER_END, POINTER_START, add_repo_pointer, install_graphify_skill, install_tools, java_info,
    jvm_repos, link_workspace, prerequisites, refresh_agent_config, setup, setup_steps, unlink_agent_config, wire_one,
    wire_repo, wire_umbrella, write_agent_config, write_codex_mcp,
)
from .app.share import (
    AUTO_SHARE, SHARED, _git_said, _ident, _remote_host, _shared, _sharing, _stderr, auto_share, board_repair,
    checkpoint_commit, docs_remote, set_auto_share, set_remote, share, sync_status,
)
from .app.templates import (
    KIT_DOCS, KIT_DOCS_STAMP, RENDERED_SKILLS, TEMPLATES, _kit_doc_files, _own_file, _real, _real_skills_dir,
    _rendered_entry, _sha, edited_kit_docs, ensure_agents_import, fill, init_templates, kit_skill_files, refresh_block,
    skill_files, sync_kit_docs, write_kit_skills,
)
from .app.viewers import VIEWERS, build_c4, build_graphs, code_graphs, graph, newest, repo_changed_at, viewers
from .app.wiki import (
    COVERAGE, ENGINE_DOWN, ENGINE_HELP, STARTER_MARK, WIKI_LINK_RE, WIKI_SCOPE, WikiAbort, _WikiRun, old_wikis,
    openwiki_generate, stamp_wiki, starter_brief, wiki_brief_kind, wiki_brief_ready, wiki_engine_help, wiki_engines,
    wiki_graph, wiki_nav, wiki_old, wiki_pages, wiki_prompt, wiki_scope, wikis, wire_openwiki,
)
from .ci import detect_forge, install_ci
from .core.locks import pid_alive
from .core.paths import WIKI_LOCK, WIKI_STAMP
from .core.process import stream
from .ports import Log
from .projects import git_failure

__facade__ = "lib.app and lib.adapters"
__all__ = [
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
    "ensure_agents_import", "export_site", "fill", "forge_edit_base", "git_exclude", "git_failure", "graph",
    "graph_repo", "image_context", "init_templates", "install_ci", "install_graphify_skill", "install_prereq",
    "install_tools", "java_info", "jvm_repos", "kit_skill_files", "likec4_mcp", "link", "link_repo_wiki",
    "link_workspace", "merged_links", "newest", "node_major", "npm_global", "npm_global_version", "old_wikis",
    "open_new_terminal", "open_url", "openwiki_credentials", "openwiki_generate", "openwiki_installed",
    "openwiki_wired", "pid_alive", "portal", "portal_steps", "portal_token", "portal_url", "prerequisites",
    "project_id", "refresh_agent_config", "refresh_block", "repo_changed_at", "repo_graph", "repo_mcp_entry",
    "repo_mcp_registered", "serve_editor", "serve_local", "set_auto_share", "set_components", "set_profile",
    "set_remote", "setup", "setup_steps", "share", "skill_files", "stamp_wiki", "starter_brief", "stop_local", "stream",
    "sync_kit_docs", "sync_status", "tool_ok", "tool_version", "unlink_agent_config", "unwire_repo_mcp", "viewers",
    "wiki_brief_kind", "wiki_brief_ready", "wiki_close", "wiki_engine_help", "wiki_engines", "wiki_graph", "wiki_lock",
    "wiki_nav", "wiki_old", "wiki_open", "wiki_pages", "wiki_prompt", "wiki_scope", "wiki_workdir", "wikis", "wire_one",
    "wire_openwiki", "wire_repo", "wire_repo_mcp", "wire_umbrella", "without_graphify_hooks", "workspace_off",
    "writable", "write_agent_config", "write_codex_mcp", "write_kit_skills",
]
