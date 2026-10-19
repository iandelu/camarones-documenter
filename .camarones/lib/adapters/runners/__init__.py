"""Agent runners: code adapters, command runners from the kit's own plugins (lib/plugins/, e.g. Gemini) and command
runners this machine defines in ~/.camarones.json (`runners:`). Team config (workspace.yaml) only names runners, and a
project plugin that defines one is not loaded until approved, so a shared repo cannot make a teammate's machine run
something new."""
from __future__ import annotations

from ...common import PREFS, load_json
from .claude import Claude
from .codex import Codex
from ...harness import plugins
from .command import CommandRunner
from .opencode import OpenCode

_CODE = {r.id: r for r in (Claude(), Codex(), OpenCode())}


def _from(d: dict) -> CommandRunner:
    return CommandRunner(d["id"], d.get("label", d["id"]), d["argv"], d.get("interactive"), d.get("model_args"),
                         d.get("limit_hints"))


def builtin() -> list:
    """Code adapters, then the kit's plugin runners, then those of project plugins this machine approved."""
    out = dict(_CODE)
    for p in plugins.discover():
        if p.active:
            for d in p.provides.get("runners") or []:
                out.setdefault(d["id"], _from(d))
    return list(out.values())


def machine() -> list:
    defs = load_json(PREFS, {}).get("runners") or {}
    taken = {r.id for r in builtin()}
    return [_from({"id": rid, **d}) for rid, d in defs.items() if rid not in taken and d.get("argv")]


def all() -> list:                                          # noqa: A001
    return builtin() + machine()


def available() -> list:
    return [r for r in all() if r.available()]


def get(runner_id: str):
    for r in all():
        if r.id == runner_id:
            return r
    raise KeyError(runner_id)
