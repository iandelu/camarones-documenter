"""Is it right, is it working: prerequisites, the docs gate and trust report, the C4 model, the plan's units, golden
questions, A/B runs, KPIs, usage and project health."""
from __future__ import annotations

import argparse
import json
import sys

from lib.interfaces.cli.registry import CliContext, Command, command


@command("arch-validate", "app", "check", es="Validar el modelo C4", en="Validate the C4 model")
class ArchValidate(Command):
    def run(self, args: argparse.Namespace, cli: CliContext) -> int:
        ok, msg = cli.services.diagrams.arch_validate()
        print(msg or ("✓ Valid" if ok else "invalid"))
        return 0 if ok else 1


def cmd_doctor(a, cli: CliContext) -> int:
    from lib import env
    from lib.common import VERSIONS
    from lib.core.paths import cli_cmd
    if a.context:
        from lib import budget
        r = budget.standing()
        print(json.dumps(r, indent=2) if a.json else "\n".join(budget.report(r)))
    elif a.local:
        from lib.adapters.runners import local
        print("\n".join(local.report()))
    elif a.install:
        from lib import doctor
        ok = doctor.install(a.install)
        print(f"✔ {a.install} installed" if ok else f"✖ {a.install} could not be installed here: "
              f"{env.prerequisites().get(a.install, {}).get('hint', a.install)}", file=sys.stdout if ok else sys.stderr)
        return 0 if ok else 1
    elif a.json:
        from lib import doctor
        print(json.dumps(doctor.report(), indent=2, ensure_ascii=False))
    else:
        for k, v in env.prerequisites().items():
            print(f"{'✔' if v['ok'] else ('✖' if v['need'] else '·')} {k:<7} {v.get('found', '')}  {'' if v['ok'] else v['hint']}")
            if v.get("note"):
                print(f"          {v['note']}")
        for tname in ("graphify", "likec4", "mmdc"):
            print(f"  {tname:<9} {cli.services.toolchain.tool_version(tname) or 'missing'} (pinned {VERSIONS[tname]})")
        from lib import install_state
        from lib.core.paths import WS_FILE
        if WS_FILE.exists():
            off = install_state.drift()
            fix = [d for d in off if d.get("why") != "yours"]
            print("✔ kit files and links as installed" if not fix else
                  f"⚠ {len(fix)} kit file(s) or link(s) off — `{cli_cmd()} repair` puts them back:")
            for d in off:
                print(f"    {d['state']:<10} {d['path']}  ({d['what']}"
                      + ("; yours: kept, the kit never replaces it)" if d not in fix else ")"))
            from lib import skills as team_skills
            for sk in team_skills.outdated():
                print(f"⚠ skill {sk}: the kit's version changed since your team copy — "
                      f"`{cli_cmd()} skills diff {sk} --kit`")
        print(f"  openwiki  {'ok' if cli.services.toolchain.openwiki_installed() else 'missing'} (pinned {VERSIONS['openwiki']})")
        print(f"  gitleaks  {'ok' if cli.services.toolchain.tool_ok('gitleaks') else 'missing'} (pinned {VERSIONS['gitleaks']})")
    return 0


@command("doctor", "app", "check", es="Requisitos y versiones de las herramientas", en="Prerequisites and tool versions")
class Doctor(Command):
    def configure(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--local", action="store_true")
        parser.add_argument("--context", action="store_true")
        parser.add_argument("--json", action="store_true")
        parser.add_argument("--install", choices=["git", "node", "docker", "java", "claude", "codex"])

    def run(self, args: argparse.Namespace, cli: CliContext) -> int:
        return cmd_doctor(args, cli)


def cmd_eval(a) -> int:
    from lib import plan
    from lib.core.paths import cli_cmd
    from lib.harness import evals
    if a.action == "comply":
        from lib.harness import comply
        if len(a.ids) != 1:
            print("usage: eval comply UNIT [--runner T] [--json]  (run it on the sandbox, not on a real project)",
                  file=sys.stderr)
            return 2
        try:
            r = comply.run(a.ids[0], runner=a.runner or None, echo=(lambda _: None) if a.json else print)
        except (KeyError, ValueError) as e:
            print(f"✖ {e}", file=sys.stderr)
            return 2
        if a.json:
            print(json.dumps(r, indent=2, ensure_ascii=False))
            return 0
        print(f"{r['unit']}: {r['status']} · {r['pages']} page(s) written · {r['compliant']} follow the method"
              + (f" · score {r['score']}" if r["score"] is not None else ""))
        for path, v in r["by_page"].items():
            for issue in v["issues"] + [f"missing source {s}" for s in v["orphan_sources"]]:
                print(f"  {path}: {issue}")
        return 0
    if a.action == "draft":
        u = evals.draft_unit()
        print(f"✔ unit {u['id']} added: run it from the wizard, `{cli_cmd()} run` or `{cli_cmd()} autopilot`")
        return 0
    if a.action == "confirm":
        if not a.ids or not a.by:
            print("usage: eval confirm <id>… --by <name>", file=sys.stderr)
            return 2
        try:
            print(f"✔ confirmed: {', '.join(evals.confirm(a.ids, a.by))}")
        except KeyError as e:
            print(f"✖ {e.args[0]}", file=sys.stderr)
            return 1
        return 0
    qs = evals.load()
    for p in evals.problems(qs):
        print(f"✖ evals/questions.yaml — {p}", file=sys.stderr)
    if a.action == "list":
        if a.json:
            print(json.dumps(qs, indent=2, ensure_ascii=False))
        elif not qs:
            print(f"No golden questions yet: `{cli_cmd()} eval draft` adds a unit that proposes them.")
        for q in qs if not a.json else []:
            print(f"  {'✔' if q.get('x-confirmed') else '·'} {q.get('id', '?'):<22} {q.get('q', '')}"
                  + ("" if q.get("x-confirmed") else "  (draft)"))
        return 0
    runner = a.runner
    if not runner:
        found = plan._agents(lambda _: None)
        if not found:
            print("✖ no agent installed for the questions (see `camaron doctor`)", file=sys.stderr)
            return 1
        runner = found[0]
    judge = None
    if a.judge:
        judge = a.judge if a.judge != "auto" else next(iter(plan._agents(lambda _: None, "judge")), None)
    if not (evals.confirmed(qs) or (a.all and qs)):
        print(f"No confirmed questions to ask: `{cli_cmd()} eval list`, then `{cli_cmd()} eval confirm <id> --by <name>`.")
        return 1
    r = evals.run(runner, judge=judge, include_drafts=a.all, echo=(lambda _: None) if a.json else print)
    if a.json:
        print(json.dumps(r, indent=2, ensure_ascii=False))
    else:
        print(f"Score {r['score']} over {len(r['questions'])} question(s) with {runner}"
              + (f", judge {r['judge']}" if r["judge"] is not None else "")
              + (f" — {r['drafts_skipped']} draft(s) not asked" if r["drafts_skipped"] else ""))
    return 0


def cmd_ab(a) -> int:
    from lib import plan
    from lib.core.fsutil import load_json
    from lib.core.paths import PREFS, cli_cmd
    from lib.harness import ab, evals
    if a.action == "sample":                        # Claude Code's UserPromptSubmit hook: silent, never fails
        ab.sample_from_hook()
        return 0
    if a.action == "sampling":
        if a.state not in ("on", "off"):
            s = ab.sampling()
            print(f"project: {'on' if s['enabled'] else 'off'} (rate {s['rate']}) · this machine: "
                  f"{'on' if load_json(PREFS, {}).get('ab_sampling') else 'off'} · samples kept: {len(ab.samples())}")
            return 0
        on = a.state == "on"
        ab.set_machine_sampling(on)
        (ab.install_hook if on else ab.remove_hook)()
        print(f"✔ sampling {'on' if on else 'off'} on this machine" + (
            "" if not on or ab.sampling()["enabled"] else
            " — the project still has it off: set `ab: {sampling: {enabled: true, rate: 0.05}}` in workspace.yaml"))
        return 0
    if a.task or a.replay:
        if not ab.enabled():
            print("✖ A/B runs are turned off for this project (ab.enabled: false in workspace.yaml)", file=sys.stderr)
            return 1
        runner = a.runner or next(iter(plan._agents(lambda _: None)), None)
        if not runner:
            print("✖ no agent installed (see `camaron doctor`)", file=sys.stderr)
            return 1
        import shlex
        check = shlex.split(a.check) if a.check else None
        tasks = [a.task] if a.task else [s["prompt"] for s in ab.samples()[-a.max:]]
        if not tasks:
            print("No sampled prompts on this machine yet (`camaron ab sampling on`).", file=sys.stderr)
            return 1
        out = [ab.run_task(t, runner, check=check, echo=(lambda _: None) if a.json else print) for t in tasks]
        if a.json:
            print(json.dumps(out if len(out) > 1 else out[0], indent=2, ensure_ascii=False))
            return 0
        for r in out:
            print(f"\n{r['task'][:100]}")
            for side in ("with", "without"):
                s = r[side]
                print(f"  {side + ' cam-docs':<18} {s['tokens_in'] + s['tokens_cache']:>9} context tokens  {s['seconds']:>6}s  "
                      f"{s['tool_calls']:>3} tool calls  {s['files_changed']:>2} files  check: {s['check'] or '-'}")
        return 0
    if not a.qa and not a.golden:
        print('usage: ab --qa "QUESTION" | --golden | --task "TASK" [--check CMD] | --replay | sampling on|off',
              file=sys.stderr)
        return 2
    if not ab.enabled():
        print("✖ A/B runs are turned off for this project (ab.enabled: false in workspace.yaml)", file=sys.stderr)
        return 1
    questions = [{"id": "qa", "q": a.qa}] if a.qa else evals.confirmed(evals.load())
    if not questions:
        print(f"No confirmed golden questions: `{cli_cmd()} eval list`.", file=sys.stderr)
        return 1
    runner = a.runner or next(iter(plan._agents(lambda _: None)), None)
    if not runner:
        print("✖ no agent installed (see `camaron doctor`)", file=sys.stderr)
        return 1
    judge = (a.judge if a.judge != "auto" else next(iter(plan._agents(lambda _: None, "judge")), None)) if a.judge else None
    r = ab.run(questions, runner, judge=judge, echo=(lambda _: None) if a.json else print)
    if a.json:
        print(json.dumps(r, indent=2, ensure_ascii=False))
        return 0
    w, wo = r["totals"]["with"], r["totals"]["without"]
    print(f"{'':<14}{'with cam-docs':>16}{'without':>14}")
    for k in ab.METRICS:
        if w.get(k) is not None or wo.get(k) is not None:
            print(f"{k:<14}{'-' if w.get(k) is None else w[k]:>16}{'-' if wo.get(k) is None else wo[k]:>14}")
    if r["tokens_saved_pct"] is not None:
        print(f"cam-docs read {r['tokens_saved_pct']}% less context (input + cached tokens)" if r["tokens_saved_pct"] >= 0
              else f"cam-docs read {-r['tokens_saved_pct']}% more context (input + cached tokens)")
    return 0


# What each reason key of lib/health.py reads like (the apps translate the keys themselves)
HEALTH_REASONS = {
    "machine.missing": "{n} missing tools", "machine.unchecked": "not checked on this machine",
    "machine.drift": "{n} kit files changed", "docs.stale": "{n} stale pages", "docs.suspect": "{n} pages to re-check",
    "docs.context": "{n} tokens over the context budget", "docs.noEvals": "no confirmed golden questions",
    "docs.review": "{n} pages waiting for review", "docs.unread": "{n} sources could not be read",
    "code.vulnHigh": "{n} high or critical vulnerabilities", "code.vulnMedium": "{n} medium vulnerabilities",
    "code.noScan": "vulnerabilities never scanned", "code.oldScan": "last vulnerability scan {n} days ago",
    "code.gateFailed": "{n} repos failing the SonarQube quality gate",
    "code.lowCoverage": "{n} repos under the minimum coverage", "code.highDebt": "{n} high-impact debt items",
    "code.unread": "{n} sources could not be read"}
HEALTH_FIGURES = {"machine.tools": "tools checked", "machine.missing": "missing", "docs.stale": "stale pages",
                  "docs.review": "pages waiting for review", "code.libraries": "libraries",
                  "code.vulnHigh": "high or critical vulnerabilities"}
HEALTH_MARKS = {"ok": "✔", "warn": "!", "bad": "✖", None: " "}
HEALTH_GATES = {"OK": "passed", "WARN": "warning", "ERROR": "failed"}


def _health_sonar_cell(sonar) -> str:
    """The gate word when SonarQube's figures are there ("(stale)" after a failed read keeps the old ones), else yes/no.
    A block that is only `{error}` could not be read: a dash."""
    if not isinstance(sonar, dict) or ("error" in sonar and "used" not in sonar):
        return "—"
    server = sonar.get("server")
    if isinstance(server, dict):
        return HEALTH_GATES.get(server.get("gate"), "—") + (" (stale)" if "error" in sonar else "")
    return "—" if "error" in sonar else "yes" if sonar.get("used") else "no"


def _health_repo_row(name: str, repo: dict, state, scanned: bool) -> str:
    def cells(r: dict) -> list[str]:
        sonar, cov, vulns, debt = _health_sonar_cell(r.get("sonar")), r.get("coverage"), r.get("vulns"), r.get("debt")
        cov = f"{cov['percent']}%" if isinstance(cov, dict) and isinstance(cov.get("percent"), (int, float)) else "—"
        if not scanned or not isinstance(vulns, dict) or "error" in vulns:
            vulns = "—"
        else:
            vulns = ", ".join(f"{n} {s}" for s, n in vulns.items()) or "0"
        if isinstance(debt, list):
            high = sum(1 for d in debt if isinstance(d, dict) and d.get("impact") == "high")
            debt = f"{len(debt)} ({high} high)" if high else str(len(debt))
        else:
            debt = "—"
        return [sonar, cov, vulns, debt]
    if "error" in repo:
        rest = ["unread"] + ["—"] * 3
    elif repo.get("cloned") is False:
        rest = ["—"] * 4 + ["not cloned"]
    else:
        rest = cells(repo)
    return f"{HEALTH_MARKS.get(state, ' ')} {name:<20}" + "".join(f"{c:<16}" for c in rest[:4]) + (rest[4] if len(rest) > 4 else "")


def cmd_health(a) -> int:
    from lib import health
    snap = None if a.refresh else health.load()
    if snap is None:                                    # the first time, or --refresh; --json keeps stdout clean
        snap = health.build(log=(lambda m: print(m, file=sys.stderr)) if a.json else print)
    if a.json:
        print(json.dumps(snap, indent=2, ensure_ascii=False))
        return 0
    print(f"Project health · {snap.get('at') or '—'}")
    verdict = snap.get("verdict") or []
    for area in ("machine", "docs", "code"):
        info = (snap.get("areas") or {}).get(area) or {}
        reasons = [v for v in verdict if v["key"].split(".")[0] == area]
        said = [HEALTH_REASONS.get(v["key"], v["key"]).format(n="—" if v.get("n") is None else v["n"]) for v in reasons]
        if not said:
            said = [f"{HEALTH_FIGURES.get(f['key'], f['key'])}: {'—' if f.get('n') is None else f['n']}"
                    for f in info.get("figures") or []]
        print(f"{HEALTH_MARKS.get(info.get('state'), '?')} {area.capitalize()}: {', '.join(said) or '—'}")
    repos = snap.get("repos")
    if isinstance(repos, dict) and "error" not in repos and repos:
        scanned = bool((snap.get("inventory") or {}).get("scanned"))
        print(f"\n  {'repo':<20}{'Sonar':<16}{'coverage':<16}{'vulns':<16}{'debt'}")
        for name, repo in repos.items():
            print(_health_repo_row(name, repo, (snap.get("repo_state") or {}).get(name), scanned).rstrip())
    return 0


def cmd_kpis(a) -> int:
    from lib.core.paths import cli_cmd
    from lib.harness import kpis, runs
    if a.compare:
        missing = [r for r in a.compare if r not in runs.ids()]
        if missing:
            print(f"✖ no run {', '.join(missing)} (see `{cli_cmd()} runs`)", file=sys.stderr)
            return 1
        c = kpis.compare(*a.compare)
        if a.json:
            print(json.dumps(c, indent=2, ensure_ascii=False))
            return 0
        print(f"{'':<18}{c['a']['run']:>26}{c['b']['run']:>26}{'change':>12}")
        for k in kpis.NUMERIC:
            va, vb = c["a"].get(k), c["b"].get(k)
            d = c["delta"].get(k)
            print(f"{k:<18}{'-' if va is None else va:>26}{'-' if vb is None else vb:>26}"
                  f"{'' if d is None else f'{d:+g}':>12}")
        return 0
    r = kpis.report(months=a.months, run_check=not a.no_check)
    if a.json:
        print(json.dumps(r, indent=2, ensure_ascii=False))
        return 0
    print("Cost and speed (all runs of the team, per month)")
    for m in r["runs"]:
        print(f"  {m['month']}  {m['runs']} runs  {m['done']}/{m['units']} units done  {m['limited']} limited  "
              f"{m['failed']} failed  {m['hours']} h  {m['tokens_in'] + m['tokens_cache']} in (cached included) / "
              f"{m['tokens_out']} out  ${m['cost_usd']:.2f}"
              + (f"  ${m['cost_per_unit']:.2f}/unit" if m["cost_per_unit"] is not None else "")
              + (f"  ×{m['parallelism']} parallel" if m["parallelism"] else ""))
    c = r["coverage"]
    print(f"Coverage and quality\n  {c['repos_with_brief']}/{c['repos']} repos with a brief  {c['flows']} flows  "
          f"{c['c4_files']} C4 files" + ("" if c["check_errors"] is None else
                                         f"  check: {c['check_errors']} errors, {c['check_warnings']} warnings"))
    t = r["trust"]
    print(f"Trust and freshness\n  {t['pages']} pages  {t['confirmed_pct']}% confirmed  {t['draft']} drafts  "
          f"{t['needs_reconfirm']} to re-confirm  {t['repos_changed']} repos changed since documented  "
          f"plan {t['plan_done']}/{t['plan_total']}"
          + (f"\n  people changed {round(100 * t['ai_edit_avg'])}% of the AI's words before confirming "
             f"({t['ai_pages_confirmed']} page{'' if t['ai_pages_confirmed'] == 1 else 's'})" if t.get("ai_edit_avg") is not None else ""))
    u = r["usefulness"]
    print(f"Usefulness (this month)\n  {u['agent_queries'] or 0} agent queries  {u['human_queries'] or 0} portal reads  "
          f"{u['searches'] or 0} searches, {u['no_results_pct'] or 0}% with no result"
          + (f"\n  golden questions: score {u['eval_score']}" + (f", judge {u['eval_judge']}" if u["eval_judge"] is not None
                                                                else "") + f" ({str(u['eval_at'])[:10]})"
             if u.get("eval_score") is not None else f"\n  golden questions: none run yet (`{cli_cmd()} eval`)"))
    return 0


def cmd_pipeline(a) -> int:
    from lib import plan
    problems = plan.pipeline_problems()
    if a.action == "validate":
        for p in problems:
            print(f"✖ .camarones/pipeline.yaml — {p}")
        if not problems:
            print("✔ pipeline valid" + ("" if plan.OVERRIDE.exists() else " (kit pipeline, no .camarones/pipeline.yaml)"))
        return 1 if problems else 0
    spec, _ = plan.project_pipeline()
    units = [] if problems else plan.pipeline_units()
    if a.json:
        print(json.dumps({"pipeline": spec.get("name"), "override": plan.OVERRIDE.exists(), "problems": problems,
                          "units": units}, indent=2, ensure_ascii=False))
        return 1 if problems else 0
    print(f"Pipeline {spec.get('name')}" + (" (with .camarones/pipeline.yaml)" if plan.OVERRIDE.exists() else ""))
    for p in problems:
        print(f"✖ {p}")
    width = max((len(u["id"]) for u in units), default=0)
    for u in units:
        how = u["runner"] or u["tier"]
        print(f"  {'·' if not u['disabled'] else '-'} {u['id']:<{width}}  {u['isolation']:<9} {how:<16} "
              f"{'disabled' if u['disabled'] else ('← ' + ', '.join(u['needs']) if u['needs'] else '')}")
    return 1 if problems else 0


@command("eval", "app", "check", es="Preguntas de control sobre la documentación", en="Golden questions over the docs",
         ai=True)
class Eval(Command):
    def configure(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("action", nargs="?", default="list", choices=["list", "run", "draft", "confirm", "comply"])
        parser.add_argument("ids", nargs="*")
        parser.add_argument("--runner", default="")
        parser.add_argument("--judge", default="")
        parser.add_argument("--all", action="store_true")
        parser.add_argument("--json", action="store_true")
        parser.add_argument("--by", default="")

    def run(self, args: argparse.Namespace, cli: CliContext) -> int:
        return cmd_eval(args)


@command("ab", "app", "check", es="La misma pregunta con y sin cam-docs", en="The same question with and without cam-docs",
         ai=True)
class Ab(Command):
    def configure(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--qa", default="")
        parser.add_argument("--golden", action="store_true")
        parser.add_argument("action", nargs="?", choices=["sample", "sampling"])
        parser.add_argument("state", nargs="?", choices=["on", "off"])
        parser.add_argument("--task", default="")
        parser.add_argument("--check", default="")
        parser.add_argument("--replay", action="store_true")
        parser.add_argument("--max", type=int, default=3)
        parser.add_argument("--runner", default="")
        parser.add_argument("--judge", default="")
        parser.add_argument("--json", action="store_true")

    def run(self, args: argparse.Namespace, cli: CliContext) -> int:
        return cmd_ab(args)


@command("kpis", "both", "check", es="¿Funciona? Coste, cobertura, confianza y uso",
         en="Is it working? Cost, coverage, trust, use")
class Kpis(Command):
    def configure(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--json", action="store_true")
        parser.add_argument("--months", type=int, default=3)
        parser.add_argument("--no-check", action="store_true")
        parser.add_argument("--compare", nargs=2, metavar="RUN")

    def run(self, args: argparse.Namespace, cli: CliContext) -> int:
        return cmd_kpis(args)


@command("pipeline", "both", "check", es="Las unidades del plan y dónde trabaja cada una",
         en="The plan's units and where each one works")
class Pipeline(Command):
    def configure(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("action", choices=["show", "validate"])
        parser.add_argument("--json", action="store_true")

    def run(self, args: argparse.Namespace, cli: CliContext) -> int:
        return cmd_pipeline(args)


@command("status", "both", "check", es="Informe de confianza de las páginas", en="Trust report of the pages")
class Status(Command):
    def configure(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--json", action="store_true")

    def run(self, args: argparse.Namespace, cli: CliContext) -> int:
        from lib import docs
        rows = docs.collect()
        if args.json:
            print(json.dumps(rows, indent=2, ensure_ascii=False))
        else:
            icon = {"confirmed": "✅", "needs-reconfirm": "⚠️ ", "draft": "✨"}
            for r in rows:
                extra = ([f"ORPHAN({len(r['orphan_sources'])})"] if r["orphan_sources"] else []) + \
                        [f"{k}:{v}" for k, v in r["i18n"].items() if v != "current"]
                print(f"{icon[r['trust']]} {r['path']:<60} {' '.join(extra)}")
            s = docs.summary(rows)
            print(f"\n{s['total']} docs — confirmed {s['confirmed']}, needs-reconfirm {s['needs-reconfirm']}, "
                  f"draft {s['draft']}, orphans {s['orphans']}, untranslated {s['untranslated']}")
        return 0


@command("check", "app", "check", es="Comprobar la calidad de la documentación", en="Check the quality of the docs")
class Check(Command):
    def configure(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--strict", action="store_true")
        parser.add_argument("--secrets", action="store_true", help="only the secret scan (CI gate before committing)")

    def run(self, args: argparse.Namespace, cli: CliContext) -> int:
        from lib import docs
        errors, warns = docs.check(args.strict, secrets_only=args.secrets)
        for w in warns:
            print("WARN ", w)
        for e in errors:
            print("ERROR", e)
        return 1 if errors else 0


@command("stats", "both", "check", es="Uso de la documentación por el equipo", en="How the team uses the docs")
class Stats(Command):
    def configure(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--json", action="store_true")
        parser.add_argument("--months", type=int, default=3)
        parser.add_argument("--record", choices=["on", "off"])

    def run(self, args: argparse.Namespace, cli: CliContext) -> int:
        from lib import usage
        if args.record:
            usage.set_enabled(args.record == "on")
            print(f"usage stats: {args.record}")
            return 0
        r = usage.report(months=args.months)
        print(json.dumps(r, indent=2, ensure_ascii=False) if args.json else usage.render_md(r))
        return 0


@command("health", "app", "check", es="Salud del proyecto: máquina, docs y código", en="Project health: machine, docs and code")
class Health(Command):
    def configure(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--json", action="store_true")
        parser.add_argument("--refresh", action="store_true")

    def run(self, args: argparse.Namespace, cli: CliContext) -> int:
        return cmd_health(args)
