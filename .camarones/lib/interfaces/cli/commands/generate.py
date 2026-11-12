"""Documenting with AI and the plan: parallel and sequential runs, wikis, pull requests' docs, the work plan, the docs
reset, what past runs did, and an agent's prompt for a unit."""
from __future__ import annotations

import argparse
import json
import sys

from lib.interfaces.cli.registry import CliContext, Command, command


@command("run", "app", "generate", es="Documentar las unidades listas en paralelo", en="Document the ready units in parallel",
         ai=True)
class Run(Command):
    def configure(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--parallel", type=int, default=2)
        parser.add_argument("--per-runner", default="")
        parser.add_argument("--max-units", type=int)
        parser.add_argument("--lang", default="es")
        parser.add_argument("--include-interviews", action="store_true")
        parser.add_argument("--poll-seconds", type=int, default=900)
        parser.add_argument("--policy", choices=["on-conflict", "never"], default="on-conflict")
        parser.add_argument("--only", nargs="+", default=None, help="run only these units (when they are ready)")

    def run(self, args: argparse.Namespace, cli: CliContext) -> int:
        from lib.harness import scheduler
        try:
            slots = scheduler.parse_slots(args.per_runner)
        except ValueError as e:
            print(f"✖ --per-runner {e}", file=sys.stderr)
            return 2
        scheduler.run_parallel(lang=args.lang, max_parallel=max(1, args.parallel), per_runner=slots,
                               max_units=args.max_units, poll_seconds=args.poll_seconds,
                               include_interviews=args.include_interviews, policy=args.policy,
                               only=set(args.only) if args.only else None)
        return 0


def cmd_pr(a) -> int:
    from lib import docs
    from lib import pr
    if a.action == "propose":
        from lib import propose
        try:
            if a.dry_run:
                p = propose.plan_for(a.repo, ref=a.ref or None, base=a.base or None, runner=a.runner or None,
                                     lang=a.lang)
                print(json.dumps(p, indent=2, ensure_ascii=False) if a.json else
                      f"branch {p['branch']} · runner {p['target']} · base {p['base']} · ref {p['ref']}\n"
                      f"fetch: {' '.join(p['fetch']) if p['fetch'] else '(already local)'}\n"
                      f"agent: {' '.join(p['argv'])}\n\n{p['prompt']}")
                return 0
            r = propose.propose(a.repo, ref=a.ref or None, base=a.base or None, runner=a.runner or None, lang=a.lang,
                                comment=a.comment, with_preview=a.preview)
        except propose.ProposeError as e:
            print(f"✖ {e}", file=sys.stderr)
            return 2
        print(json.dumps(r, indent=2, ensure_ascii=False) if a.json else
              "\n".join(f"{k}: {v}" for k, v in r.items() if v not in ("", None)))
        return 0
    if a.repo not in docs.repo_names():
        print(f"unknown repo {a.repo}: one of {', '.join(docs.repo_names()) or '—'}", file=sys.stderr)
        return 2
    base = a.base or (None if a.files else "main")
    result = pr.impact(a.repo, base=base, files=a.files, head=a.head or None)
    if a.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0
    body = pr.comment(result, a.lang)
    print(body)
    if a.post:
        print(pr.post(body, affected=bool(result["pages"])))
    return 0                                     # a warning, never a failed pipeline (H27)


@command("pr", "app", "generate", es="Qué deja desactualizado un PR y proponer el arreglo",
         en="What a PR leaves out of date, and propose the fix", ai=True)
class Pr(Command):
    def configure(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("action", choices=["fresh", "propose"])
        parser.add_argument("repo")
        parser.add_argument("--head", default="")
        parser.add_argument("--ref", default="")
        parser.add_argument("--runner", default="")
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--comment", action="store_true")
        parser.add_argument("--preview", action="store_true")
        parser.add_argument("--base", default="")
        parser.add_argument("--files", nargs="+")
        parser.add_argument("--json", action="store_true")
        parser.add_argument("--post", action="store_true")
        parser.add_argument("--lang", default="en", choices=["en", "es"])

    def run(self, args: argparse.Namespace, cli: CliContext) -> int:
        return cmd_pr(args)


def _run_line(r: dict) -> str:
    state = "interrupted" if r["interrupted"] else ("finished" if r["finished"] else "running?")
    return (f"{r['run']}  {(r['started'] or '')[:16].replace('T', ' ')}  {r['done']}/{r['units']} done  "
            f"{r['limited']} limited  {r['failed']} failed  {r['seconds']:.0f}s  {r['tokens_in']} in / {r['tokens_out']} out"
            f"  ${r['cost_usd']:.2f}  {state}")


def cmd_runs(a) -> int:
    from lib.core.paths import cli_cmd
    from lib.harness import runs
    if a.run_id:
        if a.run_id not in runs.ids():
            print(f"✖ no run {a.run_id} (see `{cli_cmd()} runs`)", file=sys.stderr)
            return 1
        d = runs.detail(a.run_id)
        if a.json:
            print(json.dumps(d, indent=2, ensure_ascii=False))
            return 0
        print(_run_line(runs.summary(a.run_id)))
        width = max((len(u["unit"]) for u in d["units"]), default=0)
        for u in d["units"]:
            print(f"  {u['unit']:<{width}}  {u['runner'] or '-':<10} {u['isolation'] or '-':<9} {u['outcome'] or 'running':<8} "
                  f"{u['status'] or '-':<8} {u['merge'] or '-':<11} {u['seconds'] or 0:>7}s  {u['tokens_in']:>8} in "
                  f"{u['tokens_out']:>7} out  ${u['cost_usd']:.2f}")
        return 0
    rows = runs.rows()
    if a.json:
        print(json.dumps(rows, indent=2, ensure_ascii=False))
    elif not rows:
        print(f"No runs yet: `{cli_cmd()} run` or `{cli_cmd()} autopilot` record one each time.")
    for r in rows if not a.json else []:
        print(_run_line(r))
    return 0


@command("runs", "both", "generate", es="Qué hizo y costó cada ejecución", en="What each run did and cost")
class Runs(Command):
    def configure(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("run_id", nargs="?")
        parser.add_argument("--json", action="store_true")

    def run(self, args: argparse.Namespace, cli: CliContext) -> int:
        return cmd_runs(args)


@command("wiki", "app", "generate", es="Generar o actualizar la wiki de un repo", en="Generate or update a repo's wiki",
         ai=True)
class Wiki(Command):
    def configure(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("repos", nargs="+")
        parser.add_argument("--engine", default="")
        parser.add_argument("--init", dest="mode", action="store_const", const="init", default="")
        parser.add_argument("--update", dest="mode", action="store_const", const="update")
        parser.add_argument("--open", dest="mode", action="store_const", const="open")
        parser.add_argument("--close", dest="mode", action="store_const", const="close")
        parser.add_argument("--force", action="store_true")

    def run(self, args: argparse.Namespace, cli: CliContext) -> int:
        from lib import env
        from lib.common import VERSIONS
        if args.mode in ("open", "close"):
            for r in args.repos:
                if args.mode == "open":
                    env.wiki_open(r)
                    print(f"{r}/openwiki/: real folder — run the OpenWiki MCP lifecycle, then `wiki {r} --close`")
                elif env.wiki_close(r):
                    if env.wiki_pages(r):          # a manual MCP session follows the current PLAYBOOK scope
                        env.stamp_wiki(r, mode="manual", kit=VERSIONS["kit"])
                    print(f"{r}/openwiki/: moved to cam-docs/wikis/{r}/, repo restored")
            return 0
        failed = []
        for i, r in enumerate(args.repos):
            try:
                if not env.openwiki_generate(r, args.mode, engine=args.engine, force=args.force):
                    failed.append(r)
            except env.WikiAbort as e:
                print(f"✖ {e}" + (f"\n  not started: {', '.join(args.repos[i + 1:])}" if args.repos[i + 1:] else ""),
                      file=sys.stderr)
                return 1
            except RuntimeError as e:
                print(f"✖ {e}", file=sys.stderr)
                failed.append(r)
        return 1 if failed else 0


@command("docs", "app", "generate", es="Rehacer la documentación (reabrir las unidades) o borrarla y empezar de cero",
         en="Redo the docs (reopen the units) or wipe them and start over", destructive=True, reads="dry_run")
class Docs(Command):
    def configure(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("action", choices=["reset"])
        mode = parser.add_mutually_exclusive_group(required=True)
        mode.add_argument("--redo", dest="mode", action="store_const", const="redo")
        mode.add_argument("--wipe", dest="mode", action="store_const", const="wipe")
        parser.add_argument("--templates", action="store_true")
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--yes", action="store_true")

    def run(self, args: argparse.Namespace, cli: CliContext) -> int:
        from lib import reset
        return reset.main(args.mode, dry_run=args.dry_run, yes=args.yes, templates=args.templates)


def cmd_plan(a) -> int:
    from lib import env, plan
    from lib.core.paths import ROOT
    for problem in plan.pipeline_problems():
        print(f"✖ .camarones/pipeline.yaml — {problem} (the plan is left as it was)", file=sys.stderr)
    if a.action == "sync" or not plan.PLAN.exists():
        plan.sync()
    if a.action in ("show", "sync"):
        data = plan.load()
        print(json.dumps(data, indent=2, ensure_ascii=False) if a.json else plan.render(data))
    elif a.action == "next":
        ready = plan.available()
        if a.json:
            print(json.dumps(ready, indent=2, ensure_ascii=False))
        elif not ready:
            print("Plan complete 🦐 — use `prompt update` after code changes.")
        else:
            d, t = plan.progress()
            print(f"Progress {d}/{t}. Ready next:")
            for i, u in enumerate(ready[:6], 1):
                print(f"  {i}. {u['id']:<28} {u['title']}{'  [in progress]' if u['status'] == 'doing' else ''}"
                      f"{'  [wizard]' if u['runner'] == 'wizard' else ''}")
                if u["status"] == "doing" and plan.last_note(u["id"]):
                    print(f"       last checkpoint: {plan.last_note(u['id'])}")
    elif a.action == "note":
        if not a.unit or not (a.title or a.note):
            print('usage: plan note <unit> "what is done / what is next"'); return 2
        f = plan.note(a.unit, a.title or a.note)
        print(f"checkpoint saved → {plan._at(f)}")
    elif a.action in ("start", "done", "block", "drop"):
        if not a.unit:
            print("unit id required"); return 2
        status = {"start": "doing", "done": "done", "block": "blocked", "drop": "dropped"}[a.action]
        u = plan.set_status(a.unit, status, a.note)
        print(f"{u['id']} → {u['status']}" + (f": {u['notes']}" if plan.awaiting(u) else ""))
        if u.get("reopened"):
            print("reopened to refine with what it settled: " + ", ".join(u["reopened"]))
        if status != "doing" and env.checkpoint_commit(f"{u['id']} {u['status']}"):
            print("✔ docs committed locally (checkpoint)")
    elif a.action == "cost":
        from lib.harness import ledger
        ledger.harvest()
        b = ledger.bill()
        print(json.dumps(b, indent=2, ensure_ascii=False) if a.json else "\n".join(ledger.lines(b)))
    elif a.action == "approve":
        if not a.unit:
            print("usage: plan approve <unit>"); return 2
        from lib.core.process import out
        try:
            u = plan.approve(a.unit, by=out(["git", "-C", str(ROOT), "config", "user.name"]) or "cli")
        except ValueError as e:
            print(f"✖ {e}", file=sys.stderr); return 2
        print(f"{u['id']} → done ({u['notes']})")
        if env.checkpoint_commit(f"{u['id']} approved"):
            print("✔ docs committed locally (checkpoint)")
    elif a.action == "redo":
        if not a.unit:
            print("usage: plan redo <unit> [--also <dependent> …]"); return 2
        for u in plan.redo(a.unit, a.also):
            print(f"{u['id']} → todo (redo; was done {str(u['redo'])[:10]})")
        still = plan.dependents(plan.load(), a.unit)
        if still:
            print("Still done, built on it (reopen with --also if they need redoing): " + ", ".join(u["id"] for u in still))
        if env.checkpoint_commit(f"redo {a.unit}"):
            print("✔ docs committed locally (checkpoint)")
    elif a.action == "add":
        if not a.unit or not a.title:
            print('usage: plan add <id> "<title>" [--type flow] [--deps a b]'); return 2
        u = plan.add(a.unit, a.title, a.type, a.deps)
        print(f"added {u['id']} ({u['type']}) deps={u['deps']}")
    return 0


@command("plan", "both", "generate", es="El plan de trabajo: ver, añadir, reabrir, aprobar y ver su coste",
         en="The work plan: show, add, reopen, approve and see its cost")
class Plan(Command):
    def configure(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("action", nargs="?", default="show",
                            choices=["show", "sync", "next", "start", "note", "done", "block", "drop", "add", "redo",
                                     "approve", "cost"])
        parser.add_argument("unit", nargs="?")
        parser.add_argument("title", nargs="?")
        parser.add_argument("--note")
        parser.add_argument("--type", default="flow")
        parser.add_argument("--deps", nargs="*")
        parser.add_argument("--json", action="store_true")
        parser.add_argument("--also", nargs="*", default=[])

    def run(self, args: argparse.Namespace, cli: CliContext) -> int:
        return cmd_plan(args)


@command("prompt", "cli")
class Prompt(Command):
    def configure(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("unit")
        parser.add_argument("--lang", default="es")
        parser.add_argument("--unattended", action="store_true")

    def run(self, args: argparse.Namespace, cli: CliContext) -> int:
        from lib import plan
        print(plan.prompt(args.unit, lang=args.lang, unattended=args.unattended))
        return 0


@command("autopilot", "app", "generate", es="Documentar una unidad tras otra, sin vigilancia",
         en="Document one unit after another, unattended", ai=True)
class Autopilot(Command):
    def configure(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--lang", default="es")
        parser.add_argument("--max-units", type=int)
        parser.add_argument("--poll-seconds", type=int, default=900)
        parser.add_argument("--include-interviews", action="store_true")

    def run(self, args: argparse.Namespace, cli: CliContext) -> int:
        from lib import plan
        try:
            plan.run_autopilot(lang=args.lang, max_units=args.max_units, poll_seconds=args.poll_seconds,
                               include_interviews=args.include_interviews)
        except KeyboardInterrupt:
            print("\nAutopilot interrupted — progress is saved; `plan next` shows where to resume.")
        return 0
