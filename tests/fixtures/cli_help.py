"""The help texts and subcommand order of an entry script's parser, as JSON, so two entry scripts can be compared.

Usage: python cli_help.py <script>"""
from __future__ import annotations

import argparse
import json
import runpy
import sys

if __name__ == "__main__":
    script = sys.argv[1]
    sys.argv = [script]
    parser = runpy.run_path(script, run_name="cli_help")["build_parser"]()
    act = next(a for a in parser._actions if isinstance(a, argparse._SubParsersAction))
    texts = {"": parser.format_help(), **{name: sub.format_help() for name, sub in act.choices.items()}}
    print(json.dumps({"order": list(act.choices), "help": texts}, ensure_ascii=False))
