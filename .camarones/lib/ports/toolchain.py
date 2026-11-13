"""Toolchain: what the app asks of the machine's tools. The Node.js major on PATH, the OS package manager's install of
a prerequisite (git, node, docker, java, the agent CLIs), the version a tool reports, `npm install -g` (falling back to
~/.local), and whether a pinned tool (graphify, likec4, OpenWiki, mermaid-cli, gitleaks) is installed at its pin."""
from __future__ import annotations

from typing import Protocol

from lib.ports import Log


class Toolchain(Protocol):
    def node_major(self) -> int: ...

    def install_prereq(self, name: str, log: Log = ...) -> bool: ...

    def tool_version(self, name: str) -> str: ...

    def npm_global(self, pkg: str, log: Log) -> None: ...

    def openwiki_installed(self) -> bool: ...

    def tool_ok(self, name: str) -> bool: ...
