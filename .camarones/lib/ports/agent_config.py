"""AgentConfig: what the app asks of the agent CLIs' own config. The MCP servers the kit offers (its own and
LikeC4's), the managed block it writes into Codex's config.toml, graphify's hooks and section taken out of an agent's
files, and the `camarones` MCP server in Claude Code's local scope for a service repo (kept in the user's Claude
config, nothing written into the repo)."""
from __future__ import annotations

import re
from typing import Protocol

from lib.ports import Log


class AgentConfig(Protocol):
    CODEX_MCP_RE: re.Pattern[str]
    GRAPHIFY_SECTION: re.Pattern[str]

    def camarones_mcp(self) -> dict: ...

    def likec4_mcp(self) -> dict: ...

    def codex_block(self, servers: dict) -> str: ...

    def without_graphify_hooks(self, data: dict) -> dict: ...

    def repo_mcp_entry(self, name: str) -> dict | None: ...

    def repo_mcp_registered(self, name: str) -> bool: ...

    def wire_repo_mcp(self, name: str, log: Log = ...) -> bool: ...

    def unwire_repo_mcp(self, name: str) -> bool: ...
