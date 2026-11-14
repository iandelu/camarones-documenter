"""The CLI's commands: one class per command, decorated with its catalog row, found by scanning `commands/`. Adding a
command is adding a module there. Loading the registry imports nothing outside lib.interfaces.cli: it runs on every
CLI start, in the catalog (read without a project) and before the global install picks a project, so each command
imports what it needs when it runs."""
from __future__ import annotations

import argparse
import importlib
import pkgutil
from dataclasses import dataclass
from functools import cache
from typing import TYPE_CHECKING, Callable, ClassVar

if TYPE_CHECKING:                       # a type only: loading the registry imports nothing outside the CLI
    from lib.app.services import Services

VERDICTS = ("portal", "app", "both", "cli")      # both: the portal shows it, the app runs it
ZONES = ("projects", "generate", "analyze", "check", "interviews", "team", "machine")
PACKAGE = "lib.interfaces.cli.commands"
# argparse prints this order in --help and in "invalid choice"; a command not listed comes after, by name
ORDER: tuple[str, ...] = (
    "help", "setup", "install", "upgrade", "new", "switch", "self-update", "unlink", "profile", "init", "sync",
    "detect", "changes", "llms", "graph", "arch", "arch-validate", "portal", "down", "wizard", "version", "repair",
    "history", "removed", "review", "hook", "hooks", "mcp", "doctor", "plugins", "export", "run", "eval", "ab", "pr",
    "blocks", "pages", "diagrams", "fresh", "kpis", "runs", "pipeline", "mark-documented", "status", "check", "confirm",
    "translated", "up", "wiki", "migrate", "uninstall", "docs", "ci", "plan", "checkpoint", "remote", "share", "trust",
    "join", "stats", "feedback", "arch-draft", "radar", "inventory", "bump", "health", "schemas", "interview", "stack",
    "prompt", "autopilot", "catalog", "board", "adr", "projects", "app", "config",
)


@dataclass(frozen=True)
class Spec:
    """A command's catalog row (where a person runs it, see lib/catalog.py) and how the CLI treats it. `reads`: the
    argument (dest) that makes the command only read, so the app runs it without asking first."""
    name: str
    verdict: str
    zone: str | None = None
    es: str = ""
    en: str = ""
    ai: bool = False
    destructive: bool = False
    reads: str | None = None
    aliases: tuple[str, ...] = ()
    project: bool = True        # a global install run outside a project picks one first
    usage: bool = True          # `cli:<name>` goes to the usage log


@dataclass(frozen=True)
class CliContext:
    parser: argparse.ArgumentParser
    services: Services | None = None


class Command:
    spec: ClassVar[Spec]

    def configure(self, parser: argparse.ArgumentParser) -> None:
        pass

    def run(self, args: argparse.Namespace, cli: CliContext) -> int:
        raise NotImplementedError

    def needs_project(self, rest: list[str]) -> bool:
        return self.spec.project

    def records_usage(self, args: argparse.Namespace) -> bool:
        return self.spec.usage


def _check(spec: Spec) -> None:
    if spec.verdict not in VERDICTS:
        raise ValueError(f"{spec.name}: verdict {spec.verdict!r} is not one of {', '.join(VERDICTS)}")
    if spec.verdict in ("app", "both"):
        if spec.zone not in ZONES or not (spec.es.strip() and spec.en.strip()):
            raise ValueError(f"{spec.name}: an {spec.verdict} command needs a zone ({', '.join(ZONES)}) and es/en labels")
    elif spec.zone is not None:
        raise ValueError(f"{spec.name}: a {spec.verdict} command has no zone")


def command(name: str, verdict: str, zone: str | None = None, *, es: str = "", en: str = "", ai: bool = False,
            destructive: bool = False, reads: str | None = None, aliases: tuple[str, ...] = (), project: bool = True,
            usage: bool = True) -> Callable[[type[Command]], type[Command]]:
    spec = Spec(name, verdict, zone, es, en, ai, destructive, reads, tuple(aliases), project, usage)
    _check(spec)

    def mark(cls: type[Command]) -> type[Command]:
        cls.spec = spec
        return cls
    return mark


def _rank(name: str) -> tuple[int, int, str]:
    return (0, ORDER.index(name), "") if name in ORDER else (1, 0, name)


@cache
def load(package: str = PACKAGE) -> dict[str, Command]:
    pkg = importlib.import_module(package)
    found: dict[str, Command] = {}
    taken: set[str] = set()
    for info in pkgutil.iter_modules(pkg.__path__):
        mod = importlib.import_module(f"{package}.{info.name}")
        for obj in vars(mod).values():
            if not (isinstance(obj, type) and issubclass(obj, Command) and obj.__module__ == mod.__name__
                    and "spec" in vars(obj)):
                continue
            names = (obj.spec.name, *obj.spec.aliases)
            twice = [n for n in names if n in taken]
            if twice:
                raise ValueError(f"command name used twice: {', '.join(twice)} ({mod.__name__}.{obj.__name__})")
            taken.update(names)
            found[obj.spec.name] = obj()
    return {name: found[name] for name in sorted(found, key=_rank)}


def find(commands: dict[str, Command], name: str) -> Command | None:
    if name in commands:
        return commands[name]
    return next((c for c in commands.values() if name in c.spec.aliases), None)


def add_all(subparsers: argparse._SubParsersAction, commands: dict[str, Command]) -> None:
    for cmd in commands.values():
        cmd.configure(subparsers.add_parser(cmd.spec.name, aliases=list(cmd.spec.aliases)))


def entries(commands: dict[str, Command]) -> dict[str, dict]:
    keys = ("verdict", "zone", "es", "en", "ai", "destructive", "reads")
    return {name: {k: getattr(cmd.spec, k) for k in keys} for name, cmd in commands.items()}
