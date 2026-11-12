"""The command catalog moved to lib/interfaces/cli/catalog.py (rows from each command's @command decorator); this
path stays for old imports."""
from __future__ import annotations

from .interfaces.cli.catalog import (
    COMMANDS, VERDICTS, ZONES, args_of, describe, drift, subparsers, triage_markdown,
)

__facade__ = "lib.interfaces.cli.catalog"
__all__ = ["COMMANDS", "VERDICTS", "ZONES", "args_of", "describe", "drift", "subparsers", "triage_markdown"]
