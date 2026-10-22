"""Routing by tier (H10, H21): each kind of work has an ordered list of targets (`runner` or `runner:model`) and the
first installed one runs it. Defaults < workspace.yaml `agents.routing` (team) < ~/.camarones.json `routing` (machine).
Local models are reached only through OpenCode and are kept off agentic-heavy work unless a node allows it."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

TIERS = ("agentic-heavy", "bounded", "judge")
DEFAULT = ["claude", "codex"]
LOCAL_PROVIDERS = {"ollama", "lmstudio", "llama.cpp", "llamacpp"}


@dataclass(frozen=True)
class Route:
    runner: str
    model: str | None = None

    @property
    def local(self) -> bool:
        return bool(self.model) and self.model.split("/", 1)[0].lower() in LOCAL_PROVIDERS

    def __str__(self) -> str:
        return f"{self.runner}:{self.model}" if self.model else self.runner


def parse(target: str) -> Route:
    runner, _, model = target.strip().partition(":")
    return Route(runner, model or None)


def table(workspace: dict, prefs: dict) -> dict[str, list[str]]:
    out = {t: list(DEFAULT) for t in TIERS}
    for source in ((workspace.get("agents") or {}).get("routing") or {}, prefs.get("routing") or {}):
        for tier, targets in source.items():
            if tier not in TIERS:
                raise ValueError(f"unknown routing tier '{tier}' (use one of: {', '.join(TIERS)})")
            out[tier] = [str(t) for t in targets]
    return out


def candidates(tier: str, routes: dict[str, list[str]], allow_local: bool = False) -> tuple[list[Route], list[str]]:
    keep, notes = [], []
    for target in routes[tier]:
        r = parse(target)
        if r.local and r.runner != "opencode":
            notes.append(f"{target}: local models run through OpenCode — use opencode:{r.model}")
        elif r.local and tier == "agentic-heavy" and not allow_local:
            notes.append(f"{target}: local models are not used for agentic-heavy work (the node must allow it)")
        else:
            keep.append(r)
    return keep, notes


def pick(tier: str, routes: dict[str, list[str]], available: Callable[[str], bool],
         allow_local: bool = False) -> tuple[Route | None, list[str]]:
    keep, notes = candidates(tier, routes, allow_local)
    for r in keep:
        if available(r.runner):
            return r, notes
        notes.append(f"{r}: {r.runner} is not installed" + (" (needed for local models)" if r.local else ""))
    return None, notes
