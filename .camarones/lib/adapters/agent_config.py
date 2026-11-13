"""The AgentConfig port (lib/ports/agent_config.py) on the agent CLIs' config: the MCP entries the kit offers (its own
server and LikeC4's), Codex's managed block, graphify's hooks and section taken out, and the `camarones` server in
Claude Code's local scope for each service repo."""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

from lib.common import HOME, IS_WIN, KIT, ROOT, cli_cmd, load_json, repo_dir, run, which, ws_rel
from lib.ports import Log


def camarones_mcp() -> dict:
    """MCP entry for the kit's own server — no API keys; it resolves the project by walking up from its cwd."""
    if cli_cmd() in ("camaron", "camarones"):              # a global install: the same command on every machine
        cli = cli_cmd()                                    # Windows: a .cmd shim, which MCP hosts cannot spawn
        return {"command": "cmd", "args": ["/c", cli, "mcp"]} if IS_WIN else {"command": cli, "args": ["mcp"]}
    return {"command": "uv", "args": ["run", "--quiet", "--script", str(KIT / "camarones.py"), "mcp"]}


def likec4_mcp() -> dict:
    """LikeC4's own MCP server (built into the pinned CLI, offline) over docs/architecture: agents can query the C4
    model ("who calls X?") while writing it. The path is workspace-relative — agents start in the workspace root.
    Windows: likec4 is a .cmd shim, which MCP hosts cannot spawn directly."""
    args = ["mcp", "--stdio", ws_rel("docs/architecture")]
    return {"command": "cmd", "args": ["/c", "likec4", *args]} if IS_WIN else {"command": "likec4", "args": args}


CODEX_MCP_START, CODEX_MCP_END = "# CAMARONES:MCP:START", "# CAMARONES:MCP:END"
CODEX_MCP_RE = re.compile(rf"{CODEX_MCP_START}.*?{CODEX_MCP_END}\n?", re.S)


def codex_block(servers: dict) -> str:
    body = [f"[mcp_servers.{name}]\ncommand = {json.dumps(s['command'])}\nargs = {json.dumps(s['args'])}\n"
            for name, s in servers.items()]
    return f"{CODEX_MCP_START}\n" + "\n".join(body) + f"{CODEX_MCP_END}\n" if body else ""


GRAPHIFY_SECTION = re.compile(r"\n*^## graphify\n.*?(?=^## |\Z)", re.S | re.M)


def without_graphify_hooks(data: dict) -> dict:
    """graphify's hooks assume a graphify-out/ in the cwd; the kit keeps graphs in cam-docs/graph/ instead."""
    for event, groups in list((data.get("hooks") or {}).items()):
        groups = [g for g in groups if not any("graphify" in h.get("command", "") for h in g.get("hooks", []))]
        if groups:
            data["hooks"][event] = groups
        else:
            del data["hooks"][event]
    if data.get("hooks") == {}:
        del data["hooks"]
    return data


def claude_config() -> Path:
    """Claude Code's own config file, where `--scope local` MCP servers live per folder."""
    return Path(os.environ.get("CLAUDE_CONFIG_DIR") or HOME) / ".claude.json"


def repo_mcp_entry(name: str) -> dict | None:
    """The `camarones` MCP server Claude Code has for this repo's folder in its local scope, if any."""
    data = load_json(claude_config(), {}) if claude_config().is_file() else {}
    want = os.path.normcase(str(repo_dir(name).resolve()))
    for folder, cfg in (data.get("projects") or {}).items():
        if os.path.normcase(str(Path(folder).resolve())) == want and isinstance(cfg, dict):
            entry = (cfg.get("mcpServers") or {}).get("camarones")
            return entry if isinstance(entry, dict) else None
    return None


def repo_mcp_registered(name: str) -> bool:
    entry = repo_mcp_entry(name)
    return bool(entry) and (entry.get("env") or {}).get("CAMARONES_ROOT") == str(ROOT)


def wire_repo_mcp(name: str, log: Log = print) -> bool:
    """Claude Code opened inside a service repo reaches the docs: the `camarones` MCP server in Claude Code's local
    scope for that folder (stored in the user's Claude config, nothing in the repo), pointed at this cam-docs.
    Returns whether it registered it now."""
    if not which("claude") or not repo_dir(name).is_dir() or repo_mcp_registered(name):
        return False
    if repo_mcp_entry(name):                                  # registered for another cam-docs (moved project)
        run(["claude", "mcp", "remove", "--scope", "local", "camarones"], cwd=repo_dir(name), check=False, quiet=True)
    m = camarones_mcp()
    r = run(["claude", "mcp", "add", "--scope", "local", "camarones", "-e", f"CAMARONES_ROOT={ROOT}", "--",
             m["command"], *m["args"]], cwd=repo_dir(name), check=False, quiet=True)   # -e takes many: name first
    ok = r.returncode == 0 and repo_mcp_registered(name)
    log(f"✔ {name}: Claude Code opened in this repo finds the docs (camarones MCP)" if ok
        else f"⚠ {name}: could not register the camarones MCP for Claude Code")
    return ok


def unwire_repo_mcp(name: str) -> bool:
    if not repo_mcp_entry(name) or not which("claude") or not repo_dir(name).is_dir():
        return False
    run(["claude", "mcp", "remove", "--scope", "local", "camarones"], cwd=repo_dir(name), check=False, quiet=True)
    return repo_mcp_entry(name) is None
