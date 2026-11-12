"""`camaron adr` moved to lib/interfaces/cli/commands/adr.py; this path stays for old imports."""
from __future__ import annotations

from .interfaces.cli.commands.adr import ACTIONS, Adr, add_parser, line, run

__facade__ = "lib.interfaces.cli.commands.adr"
__all__ = ["ACTIONS", "Adr", "add_parser", "line", "run"]
