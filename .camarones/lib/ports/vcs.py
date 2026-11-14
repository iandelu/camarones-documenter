"""Vcs: what the app asks of git. Which project paths a checkpoint commit stages."""
from __future__ import annotations

from typing import Protocol


class Vcs(Protocol):
    def checkpoint_paths(self) -> list[str]: ...
