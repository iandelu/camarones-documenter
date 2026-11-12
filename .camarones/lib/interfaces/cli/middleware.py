"""What wraps every command run, outermost first: an error becomes one line and exit 1, then the run is counted in
the usage log (unless the command says not to), then the command runs."""
from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from typing import Callable, Sequence

from lib.interfaces.cli.registry import CliContext, Command

Next = Callable[[], int]


@dataclass(frozen=True)
class Invocation:
    command: Command
    args: argparse.Namespace
    cli: CliContext


Middleware = Callable[[Invocation, Next], int]


def errors_to_exit(inv: Invocation, nxt: Next) -> int:
    try:
        return nxt()
    except (RuntimeError, KeyError, ValueError, OSError) as e:
        print(f"🦐✖ {e}", file=sys.stderr)
        return 1


def record_usage(inv: Invocation, nxt: Next) -> int:
    if inv.command.records_usage(inv.args):
        from lib import usage
        usage.record(f"cli:{inv.args.cmd}")
    return nxt()


CHAIN: tuple[Middleware, ...] = (errors_to_exit, record_usage)


def dispatch(inv: Invocation, chain: Sequence[Middleware] = CHAIN) -> int:
    def step(i: int) -> int:
        if i == len(chain):
            return inv.command.run(inv.args, inv.cli)
        return chain[i](inv, lambda: step(i + 1))
    return step(0)
