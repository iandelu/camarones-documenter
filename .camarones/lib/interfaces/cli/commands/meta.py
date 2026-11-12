"""The CLI's own commands: its help, the wizard, the catalog of commands and the desktop app."""
from __future__ import annotations

import argparse
import json
import sys

from lib.interfaces.cli.registry import CliContext, Command, command


@command("help", "cli", project=False, usage=False)
class Help(Command):
    def run(self, args: argparse.Namespace, cli: CliContext) -> int:
        print(cli.parser.description)
        return 0


@command("wizard", "cli", usage=False)
class Wizard(Command):
    def run(self, args: argparse.Namespace, cli: CliContext) -> int:
        from lib.wizard import W
        W().run()
        return 0


def cmd_catalog(a, parser: argparse.ArgumentParser) -> int:
    from lib import catalog
    data = catalog.describe(parser)
    if a.json:
        print(json.dumps(data, indent=2, ensure_ascii=False))
    elif a.markdown:
        print(catalog.triage_markdown(data["commands"]), end="")
    elif not a.check:
        for c in data["commands"]:
            print(f"{c['name']:<16} {c['verdict']:<7} {c['zone'] or '':<11} {c['en']}")
    if data["unlisted"] or data["unknown"]:
        print(f"✖ catalog out of sync — not in lib/catalog.py: {', '.join(data['unlisted']) or '—'}; "
              f"not in the parser: {', '.join(data['unknown']) or '—'}", file=sys.stderr)
        return 1
    return 0


@command("catalog", "cli", project=False)
class Catalog(Command):
    def configure(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--json", action="store_true")
        parser.add_argument("--markdown", action="store_true")
        parser.add_argument("--check", action="store_true")

    def run(self, args: argparse.Namespace, cli: CliContext) -> int:
        return cmd_catalog(args, cli.parser)


@command("app", "cli", project=False)
class App(Command):
    def run(self, args: argparse.Namespace, cli: CliContext) -> int:
        from lib import desktop
        desktop.launch()
        return 0
