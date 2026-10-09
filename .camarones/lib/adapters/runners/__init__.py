"""Agent runners: the kit's built-ins plus command runners this machine defines in ~/.camarones.json (`runners:`).
Team config (workspace.yaml) only names runners; it never defines commands, so a shared repo cannot make a
teammate's machine run something new."""
from __future__ import annotations

from ...common import PREFS, load_json
from .claude import Claude
from .codex import Codex
from .command import GEMINI, CommandRunner
from .opencode import OpenCode

_BUILTIN = {r.id: r for r in (Claude(), Codex(), OpenCode(), CommandRunner("gemini", **GEMINI))}


def builtin() -> list:
    return list(_BUILTIN.values())


def machine() -> list:
    defs = load_json(PREFS, {}).get("runners") or {}
    return [CommandRunner(rid, d.get("label", rid), d["argv"], d.get("interactive"), d.get("model_args"),
                          d.get("limit_hints")) for rid, d in defs.items() if rid not in _BUILTIN and d.get("argv")]


def all() -> list:                                          # noqa: A001
    return builtin() + machine()


def available() -> list:
    return [r for r in all() if r.available()]


def get(runner_id: str):
    for r in all():
        if r.id == runner_id:
            return r
    raise KeyError(runner_id)
