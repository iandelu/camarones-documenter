"""WikiEngine: what the app asks of OpenWiki (the wiki engine). Whether it can run headless (a provider key) and
whether an agent reaches its MCP tools, the commands that wire it into a project, and the open/close of a run: a real
openwiki/ folder in the repo seeded from cam-docs/wikis/<repo>, then moved back, one run at a time."""
from __future__ import annotations

from contextlib import AbstractContextManager
from typing import Protocol

from lib.ports import Log


class WikiEngine(Protocol):
    OPENWIKI_INSTALL: list[list[str]]

    def openwiki_credentials(self) -> bool: ...

    def openwiki_wired(self, host: str) -> bool: ...

    def wiki_open(self, repo: str, log: Log = ...) -> None: ...

    def wiki_close(self, repo: str, log: Log = ...) -> bool: ...

    def wiki_workdir(self, repo: str, log: Log = ...) -> AbstractContextManager[None]: ...

    def wiki_lock(self, repo: str) -> AbstractContextManager[None]: ...
