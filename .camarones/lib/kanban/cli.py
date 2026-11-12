"""`camaron board` moved to lib/interfaces/cli/commands/board.py; this path stays for old imports."""
from __future__ import annotations

from ..interfaces.cli.commands.board import ACTIONS, Board, add_parser, line, note, run

__facade__ = "lib.interfaces.cli.commands.board"
__all__ = ["ACTIONS", "Board", "add_parser", "line", "note", "run"]
