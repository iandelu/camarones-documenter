"""FileLinks: what the app asks of the file system to link cam-docs into a workspace: symlinks and, on Windows without
symlink rights, junctions; a repo's local git excludes; the person's own workspace folders merged with the kit's
entries. A link is never followed when it is removed, and a real file of the person's is never replaced."""
from __future__ import annotations

from pathlib import Path
from typing import Protocol

from lib.ports import Log


class FileLinks(Protocol):
    LINKS: tuple[str, ...]
    KIT_IMPORT: str

    def _is_link(self, p: Path) -> bool: ...

    def _linked(self, p: Path) -> bool: ...

    def _unlink(self, p: Path) -> None: ...

    def link(self, dst: Path, target: Path, log: Log = ...) -> bool: ...

    def workspace_off(self, n: str) -> str | None: ...

    def _merge(self, n: str, log: Log) -> bool: ...

    def drop_kit_import(self, claude_md: Path) -> bool: ...

    def merged_links(self, names: tuple[str, ...] = ...) -> list[Path]: ...

    def link_repo_wiki(self, name: str, log: Log = ...) -> None: ...
