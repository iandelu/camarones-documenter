"""The CLI: the parser built from the command registry, then the command run through the middleware chain."""
from __future__ import annotations

import argparse
import sys

from lib.core.paths import cli_cmd
from lib.core.process import leave_parent_session
from lib.interfaces.cli import help_text, middleware, registry
from lib.interfaces.cli.registry import CliContext


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog=cli_cmd(), description=help_text.TEXT,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = p.add_subparsers(dest="cmd", required=True)
    registry.add_all(sp, registry.load())
    return p


def main(argv: list[str] | None = None) -> int:
    leave_parent_session()
    parser = build_parser()
    args = parser.parse_args((sys.argv[1:] if argv is None else argv) or ["wizard"])
    command = registry.find(registry.load(), args.cmd)
    return middleware.dispatch(middleware.Invocation(command, args, CliContext(parser)))
