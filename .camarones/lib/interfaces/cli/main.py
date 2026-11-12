"""The CLI: the parser built from the command registry, then the command run through the middleware chain."""
from __future__ import annotations

import argparse
import sys

from lib.core.paths import cli_cmd
from lib.core.process import leave_parent_session
from lib.interfaces.cli import help_text, legacy, middleware, registry
from lib.interfaces.cli.registry import CliContext, Command


def _keep_order(sp: argparse._SubParsersAction) -> None:
    """Transitional: legacy and the registry both add subparsers until F2 ends. `choices` is also argparse's
    name → parser map, so it is reordered in place."""
    items = sorted(sp.choices.items(), key=lambda kv: registry._rank(kv[0]))
    sp.choices.clear()
    sp.choices.update(items)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog=cli_cmd(), description=help_text.TEXT,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = p.add_subparsers(dest="cmd", required=True)
    legacy.add_legacy(sp)
    registry.add_all(sp, registry.load())
    _keep_order(sp)
    return p


def command_for(name: str) -> Command:
    return registry.find(registry.load(), name) or legacy.Legacy(name)


def main(argv: list[str] | None = None) -> int:
    leave_parent_session()
    parser = build_parser()
    args = parser.parse_args((sys.argv[1:] if argv is None else argv) or ["wizard"])
    return middleware.dispatch(middleware.Invocation(command_for(args.cmd), args, CliContext(parser)))
