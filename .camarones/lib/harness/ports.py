"""Ports: what the harness needs from an adapter, so agents and tools plug in without touching the core."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Protocol

Outcome = Literal["ok", "limited", "failed"]


@dataclass(frozen=True)
class RunRequest:
    prompt: str                    # one line: multi-line args do not survive Windows .cmd shims, so point to a file
    cwd: Path
    env: dict = field(default_factory=dict)
    model: str | None = None
    interactive: bool = False      # a terminal session for a person, instead of a headless run
    resume: bool = False           # interactive only: reopen the agent's last conversation in cwd
    allow_tools: tuple[str, ...] | None = None   # headless, edits allowed but tools limited; None = unattended, full access


@dataclass(frozen=True)
class Invocation:
    argv: list[str]
    cwd: Path
    env: dict


class Runner(Protocol):
    """An agent CLI. `build` is pure so each adapter's argv can be pinned by tests; `parse` maps one line of the
    agent's output to normalised events: log, tool.call, file.changed, usage, result, error. Usage events add up:
    a run's cost is the sum of its usage events."""
    id: str
    label: str

    def available(self) -> bool: ...

    def build(self, req: RunRequest) -> Invocation: ...

    def parse(self, line: str) -> list[dict]: ...

    def classify(self, rc: int, tail: str) -> Outcome: ...
