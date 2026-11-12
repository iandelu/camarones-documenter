"""The interview questionnaire: how interviews run, the offline form for the team, importing its answers, and who
answered what."""
from __future__ import annotations

import argparse
import json
import sys

from lib.interfaces.cli.registry import CliContext, Command, command


def cmd_interview(a) -> int:
    from lib import docs, plan, questionnaire
    try:
        if a.action == "mode":
            if a.args:
                plan.set_interview_mode(a.args[0])
            print(docs.interview_mode())
        elif a.action == "export":
            for f in questionnaire.export(a.lang):
                print(f)
        elif a.action == "import":
            if not a.args:
                print("usage: interview import FILE|DIR …", file=sys.stderr); return 2
            results = questionnaire.import_files(a.args)
            for f, who, err in results:
                print(f"✔ {who}: {f.name}" if who else f"✖ {f.name}: {err}")
            if not results:
                print("no answers files found", file=sys.stderr)
            return 0 if results and all(who for _, who, _ in results) else 1
        else:
            s = questionnaire.status()
            if a.json:
                print(json.dumps(s, indent=2, ensure_ascii=False))
                return 0
            print(f"{s['questions']} questions · answered by: "
                  + (", ".join(f"{r['name']} ({r['answered']})" for r in s["respondents"]) or "nobody yet"))
            print("unanswered: " + (", ".join(s["unanswered"]) or "-"))
            for c in s["conflicts"]:
                print(f"disagree {c['id']}: " + "; ".join(f"{v} ← {', '.join(n)}" for v, n in c["answers"].items()))
    except ValueError as e:
        print(e, file=sys.stderr)
        return 2
    return 0


@command("interview", "both", "interviews", es="Cuestionario de entrevista: modo, exportar, importar, estado",
         en="Interview questionnaire: mode, export, import, status")
class Interview(Command):
    def configure(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("action", choices=["mode", "export", "import", "status"])
        parser.add_argument("args", nargs="*")
        parser.add_argument("--lang", default="es", choices=["es", "en"])
        parser.add_argument("--json", action="store_true")

    def run(self, args: argparse.Namespace, cli: CliContext) -> int:
        return cmd_interview(args)
