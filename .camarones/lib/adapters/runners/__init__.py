"""Built-in agent runners. Plugins add more through the registry (roadmap R10)."""
from __future__ import annotations

from .claude import Claude
from .codex import Codex

_BUILTIN = {r.id: r for r in (Claude(), Codex())}


def builtin() -> list:
    return list(_BUILTIN.values())


def get(runner_id: str):
    return _BUILTIN[runner_id]
