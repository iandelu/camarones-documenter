"""`camaron skills` moved to lib/interfaces/cli/commands/skills.py; this path stays for old imports."""
from __future__ import annotations

from .interfaces.cli.commands.skills import ACTIONS, Skills, add_parser, run

__facade__ = "lib.interfaces.cli.commands.skills"
__all__ = ["ACTIONS", "Skills", "add_parser", "run"]
