"""Transitional (F2 of the hexagonal refactor): camarones.py's dispatch as it was, for the commands not yet moved to
interfaces/cli/commands/. Each group's move deletes its lines here; the file goes when nothing is left."""
from __future__ import annotations

import argparse

from lib.interfaces.cli.registry import CliContext, Command


def add_legacy(sp: argparse._SubParsersAction) -> None:
    """Today's build_parser body after add_subparsers, minus the commands moved to commands/."""


def run_legacy(a: argparse.Namespace, p: argparse.ArgumentParser) -> int:
    """Today's main() dispatch, minus the commands moved to commands/."""
    return 0


NO_USAGE = ("help", "mcp", "wizard")


class Legacy(Command):
    """A command run_legacy still dispatches; it goes when its group moves to commands/."""

    def __init__(self, name: str) -> None:
        self.name = name

    def run(self, args: argparse.Namespace, cli: CliContext) -> int:
        return run_legacy(args, cli.parser)

    def records_usage(self, args: argparse.Namespace) -> bool:
        return not (args.cmd in NO_USAGE or (args.cmd == "board" and getattr(args, "action", None) == "merge-driver"))
