"""Launcher: what the app asks of the desktop it runs on. Open a URL in the person's browser, and run a command in a
terminal window of its own."""
from __future__ import annotations

from pathlib import Path
from typing import Protocol


class Launcher(Protocol):
    def open_url(self, url: str) -> None: ...

    def open_new_terminal(self, cmd: list[str], cwd: Path) -> bool: ...
