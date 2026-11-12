"""Transitional (F2 of the hexagonal refactor): camarones.py's dispatch as it was, for the commands not yet moved to
interfaces/cli/commands/. Each group's move deletes its lines here; the file goes when nothing is left."""
from __future__ import annotations

import argparse, json, os, sys
from pathlib import Path

from lib.core.ctx import KIT
from lib.interfaces.cli.registry import CliContext, Command
from lib import docs, env, plan
from lib.common import VERSIONS, PREFS, cli_cmd, ROOT, CACHE, CAM_DIR, load_json


def cmd_trust(a) -> int:
    from lib import trust
    env.refresh_agent_config()
    rows = trust.grouped(trust.pending())
    if a.json:                                  # what is pending, for the desktop app (approving takes --yes)
        print(json.dumps({"pending": [dict(zip(("kind", "label", "detail", "status"), r)) for r in rows]},
                         ensure_ascii=False))
        return 0
    if not rows:
        env.link_workspace()
        print("✔ nothing to approve: the agent config and plugins are the kit's own or already approved on this machine")
        return 0
    print("Agent config and plugins not approved on this machine (Claude Code, Codex or the kit would load them):\n")
    for kind, label, detail, status in rows:
        print(f"  {status:<8} {kind:<8} {label}\n           {detail}")
    if not a.yes:
        if not sys.stdin.isatty():
            print(f"\nnot approved — check it, then run: {cli_cmd()} trust --yes")
            return 1
        try:
            answer = input("\nApprove all of this on this machine? [y/N] ")
        except (EOFError, KeyboardInterrupt):
            print(f"\nnot approved — check it, then run: {cli_cmd()} trust --yes")
            return 1
        if answer.strip().lower() not in ("y", "yes", "s", "si", "sí"):
            trust.decline()
            print("not approved: nothing in the list is loaded on this machine")
            return 1
    n = trust.approve()
    env.link_workspace()
    print(f"✔ approved {n} item(s); the workspace's agents load this config")
    return 0


def add_legacy(sp: argparse._SubParsersAction) -> None:
    """Today's build_parser body after add_subparsers, minus the commands moved to commands/."""
    sp.add_parser("portal")
    rmv = sp.add_parser("removed"); rmv.add_argument("action", choices=["add"]); rmv.add_argument("what")
    rmv.add_argument("--why", required=True); rmv.add_argument("--decision", default="")
    rv = sp.add_parser("review"); rv.add_argument("action", choices=["request", "wait", "list"])
    rv.add_argument("target", nargs="?"); rv.add_argument("--note", default=""); rv.add_argument("--by", default="agent")
    rv.add_argument("--timeout", type=float, default=3600)
    hk = sp.add_parser("hook"); hk.add_argument("name", choices=["session-start", "post-edit", "stop"])
    hks = sp.add_parser("hooks"); hks.add_argument("state", nargs="?", choices=["on", "off"])
    hks.add_argument("--json", action="store_true")
    pg = sp.add_parser("plugins"); pg.add_argument("--json", action="store_true")
    pg.add_argument("action", nargs="?", default="list",
                    choices=["list", "add", "update", "outdated", "remove", "enable", "disable"])
    exp = sp.add_parser("export"); exp.add_argument("what", choices=["pdf", "print", "tour", "codetour", "confluence", "notion"])
    exp.add_argument("page", nargs="?")
    pg.add_argument("target", nargs="?"); pg.add_argument("--to", default="")
    rn = sp.add_parser("run"); rn.add_argument("--parallel", type=int, default=2); rn.add_argument("--per-runner", default="")
    rn.add_argument("--max-units", type=int); rn.add_argument("--lang", default="es")
    rn.add_argument("--include-interviews", action="store_true"); rn.add_argument("--poll-seconds", type=int, default=900)
    rn.add_argument("--policy", choices=["on-conflict", "never"], default="on-conflict")
    rn.add_argument("--only", nargs="+", default=None, help="run only these units (when they are ready)")
    prp = sp.add_parser("pr"); prp.add_argument("action", choices=["fresh", "propose"]); prp.add_argument("repo")
    prp.add_argument("--head", default=""); prp.add_argument("--ref", default=""); prp.add_argument("--runner", default="")
    prp.add_argument("--dry-run", action="store_true"); prp.add_argument("--comment", action="store_true")
    prp.add_argument("--preview", action="store_true")
    prp.add_argument("--base", default=""); prp.add_argument("--files", nargs="+"); prp.add_argument("--json", action="store_true")
    prp.add_argument("--post", action="store_true"); prp.add_argument("--lang", default="en", choices=["en", "es"])
    rs = sp.add_parser("runs"); rs.add_argument("run_id", nargs="?"); rs.add_argument("--json", action="store_true")
    c = sp.add_parser("confirm"); c.add_argument("files", nargs="+"); c.add_argument("--by", required=True)
    t = sp.add_parser("translated"); t.add_argument("files", nargs="+")
    w = sp.add_parser("wiki"); w.add_argument("repos", nargs="+"); w.add_argument("--engine", default="")
    w.add_argument("--init", dest="mode", action="store_const", const="init", default="")
    w.add_argument("--update", dest="mode", action="store_const", const="update")
    w.add_argument("--open", dest="mode", action="store_const", const="open")
    w.add_argument("--close", dest="mode", action="store_const", const="close")
    w.add_argument("--force", action="store_true")
    dr = sp.add_parser("docs"); dr.add_argument("action", choices=["reset"])
    dm = dr.add_mutually_exclusive_group(required=True)
    dm.add_argument("--redo", dest="mode", action="store_const", const="redo")
    dm.add_argument("--wipe", dest="mode", action="store_const", const="wipe")
    dr.add_argument("--templates", action="store_true"); dr.add_argument("--dry-run", action="store_true")
    dr.add_argument("--yes", action="store_true")
    ci = sp.add_parser("ci"); ci.add_argument("forge", nargs="?", choices=["gitlab", "github"])
    pl = sp.add_parser("plan"); pl.add_argument("action", nargs="?", default="show",
                                                choices=["show", "sync", "next", "start", "note", "done", "block", "drop", "add", "redo", "approve",
                                                         "cost"])
    pl.add_argument("unit", nargs="?"); pl.add_argument("title", nargs="?")
    pl.add_argument("--note"); pl.add_argument("--type", default="flow"); pl.add_argument("--deps", nargs="*")
    pl.add_argument("--json", action="store_true")
    pl.add_argument("--also", nargs="*", default=[])
    cp = sp.add_parser("checkpoint"); cp.add_argument("message", nargs="?", default="progress")
    rm = sp.add_parser("remote"); rm.add_argument("url", nargs="?")
    sh = sp.add_parser("share"); sh.add_argument("--auto", choices=["on", "off"])
    tr = sp.add_parser("trust"); tr.add_argument("--yes", action="store_true"); tr.add_argument("--json", action="store_true")
    fb = sp.add_parser("feedback"); fb.add_argument("file"); fb.add_argument("text"); fb.add_argument("--by", default="")
    iv = sp.add_parser("interview"); iv.add_argument("action", choices=["mode", "export", "import", "status"])
    iv.add_argument("args", nargs="*"); iv.add_argument("--lang", default="es", choices=["es", "en"])
    iv.add_argument("--json", action="store_true")
    pr = sp.add_parser("prompt"); pr.add_argument("unit"); pr.add_argument("--lang", default="es")
    pr.add_argument("--unattended", action="store_true")
    ap = sp.add_parser("autopilot"); ap.add_argument("--lang", default="es"); ap.add_argument("--max-units", type=int)
    ap.add_argument("--poll-seconds", type=int, default=900); ap.add_argument("--include-interviews", action="store_true")
    from lib.kanban import cli as board_cli
    board_cli.add_parser(sp)
    from lib import adr_cli
    adr_cli.add_parser(sp)


def run_legacy(a: argparse.Namespace, p: argparse.ArgumentParser) -> int:
    """Today's main() dispatch, minus the commands moved to commands/."""
    if a.cmd == "board":
        from lib.kanban import cli as board_cli
        return board_cli.run(a)
    elif a.cmd == "adr":
        from lib import adr_cli
        return adr_cli.run(a)
    elif a.cmd == "confirm":
        for f in docs.confirm(a.files, a.by):
            print(f"confirmed {f} by {a.by}")
    elif a.cmd == "translated":
        for f in docs.translated(a.files):
            print("stamped", f)
    elif a.cmd == "portal":
        env.portal()
    elif a.cmd == "wiki":
        if a.mode in ("open", "close"):
            for r in a.repos:
                if a.mode == "open":
                    env.wiki_open(r)
                    print(f"{r}/openwiki/: real folder — run the OpenWiki MCP lifecycle, then `wiki {r} --close`")
                elif env.wiki_close(r):
                    if env.wiki_pages(r):          # a manual MCP session follows the current PLAYBOOK scope
                        env.stamp_wiki(r, mode="manual", kit=VERSIONS["kit"])
                    print(f"{r}/openwiki/: moved to cam-docs/wikis/{r}/, repo restored")
            return 0
        failed = []
        for i, r in enumerate(a.repos):
            try:
                if not env.openwiki_generate(r, a.mode, engine=a.engine, force=a.force):
                    failed.append(r)
            except env.WikiAbort as e:
                print(f"✖ {e}" + (f"\n  not started: {', '.join(a.repos[i + 1:])}" if a.repos[i + 1:] else ""), file=sys.stderr)
                return 1
            except RuntimeError as e:
                print(f"✖ {e}", file=sys.stderr)
                failed.append(r)
        return 1 if failed else 0
    elif a.cmd == "docs":
        from lib import reset
        return reset.main(a.mode, dry_run=a.dry_run, yes=a.yes, templates=a.templates)
    elif a.cmd == "removed":
        from lib import removed
        print(f"✔ {removed.add(a.what, a.why, a.decision)}: {a.what}")
    elif a.cmd == "review":
        from lib import review
        if a.action == "list":
            print(json.dumps(review.open_requests(), indent=2, ensure_ascii=False))
        elif not a.target:
            print("usage: review request PAGE [--note TEXT] | review wait ID [--timeout S]", file=sys.stderr)
            return 2
        elif a.action == "request":
            rid = review.request(a.target, by=a.by, note=a.note)
            print(json.dumps({"id": rid, "path": a.target, "next": f"{cli_cmd()} review wait {rid}"}))
        else:
            try:
                print(json.dumps(review.wait(a.target, timeout=a.timeout), ensure_ascii=False))
            except KeyError:
                print(f"✖ no review request {a.target}", file=sys.stderr)
                return 2
    elif a.cmd == "hook":
        from lib import hooks
        return hooks.main(a.name)
    elif a.cmd == "hooks":
        from lib import hooks
        if a.state:
            hooks.set_enabled(a.state == "on")
        if a.json:
            print(json.dumps({"enabled": hooks.enabled()}))
            return 0
        print(f"method hooks: {'on' if hooks.enabled() else 'off'}" + (
            " — SessionStart (plan state), PostToolUse (check the page just edited), Stop (remind once to update docs)"
            if hooks.enabled() else ""))
    elif a.cmd == "ci":
        env.install_ci(a.forge)
    elif a.cmd == "run":
        from lib.harness import scheduler
        try:
            slots = scheduler.parse_slots(a.per_runner)
        except ValueError as e:
            print(f"✖ --per-runner {e}", file=sys.stderr)
            return 2
        scheduler.run_parallel(lang=a.lang, max_parallel=max(1, a.parallel), per_runner=slots, max_units=a.max_units,
                               poll_seconds=a.poll_seconds, include_interviews=a.include_interviews, policy=a.policy,
                               only=set(a.only) if a.only else None)
    elif a.cmd == "runs":
        return cmd_runs(a)
    elif a.cmd == "pr":
        return cmd_pr(a)
    elif a.cmd == "plugins" and a.action in ("enable", "disable"):
        from lib.harness import plugins
        ok = (plugins.enable if a.action == "enable" else plugins.disable)(a.target or "")
        if not ok:
            print(f"✖ no plugin called {a.target}", file=sys.stderr)
            return 2
        print(f"✔ {a.target} {'enabled' if a.action == 'enable' else 'disabled'} on this machine")
    elif a.cmd == "plugins" and a.action != "list":
        return cmd_plugin_store(a)
    elif a.cmd == "export":
        from lib import exporters
        try:
            if a.what in ("pdf", "print"):
                out = exporters.export_pdf() if a.what == "pdf" else exporters.export_print()
                print(f"✔ {out}" + ("" if out.suffix == ".pdf" or a.what == "print" else
                                    "  (no headless Chrome/Chromium/Edge found: print this page to PDF from a browser)"))
            elif a.what in ("tour", "codetour"):
                if not a.page:
                    print(f"usage: export {a.what} flows/<flow>.md", file=sys.stderr)
                    return 2
                if a.what == "tour":
                    print(f"✔ {exporters.export_tour(a.page)}  (open it; → and ← move between steps)")
                else:
                    print(f"✔ {exporters.export_codetour(a.page)}  (VS Code with the CodeTour extension: "
                          f"open the workspace folder, then CodeTour: Start Tour)")
            else:
                print(f"✔ {exporters.export_to(a.what)} page(s) published to {a.what}")
        except exporters.ExportError as e:
            print(f"✖ {e}", file=sys.stderr)
            return 2
    elif a.cmd == "plugins":
        from lib.harness import plugins
        rows = plugins.rows()
        if a.json:
            print(json.dumps(rows, indent=2, ensure_ascii=False))
            return 0
        for r in rows:
            mark = {"active": "✔", "invalid": "✖"}.get(r["status"], "·")
            print(f"{mark} {r['name']:<16} {r['version']:<8} {r['source']:<8} {', '.join(r['provides']) or '-':<22} "
                  f"{'runs code' if r['runs_code'] else 'config only':<12} {r['status']}")
            for e in r["errors"]:
                print(f"    {e}")
        if not any(r["source"] == "project" for r in rows):
            print(f"No project plugins yet: add a folder with a plugin.yaml in {plugins.PROJECT_DIR.relative_to(ROOT.parent)}")
    elif a.cmd == "plan":
        return cmd_plan(a)
    elif a.cmd == "interview":
        return cmd_interview(a)
    elif a.cmd == "checkpoint":
        print("✔ committed locally" if env.checkpoint_commit(a.message) else "no checkpoint commit")
    elif a.cmd == "remote":
        if a.url:
            env.set_remote(a.url)
        print(env.docs_remote() or "no remote — set one with: remote URL")
    elif a.cmd == "share" and a.auto:
        env.set_auto_share(a.auto == "on")
        print(f"auto-share: {a.auto}")
    elif a.cmd == "share":
        r = env.share()
        why = f" ({r['reason']})" if r.get("reason") else ""
        print(f"{r['status']}{why}{': ' + r['detail'] if r['detail'] else ''}")
        return 0 if r["status"] in ("pushed", "up-to-date", "nothing") else 1
    elif a.cmd == "trust":
        return cmd_trust(a)
    elif a.cmd == "feedback":
        docs.add_feedback(a.file, a.text, a.by or os.environ.get("USER", "human"))
        plan.ensure("review-fixes", "review-fixes")
        print(f"feedback recorded in {plan._at(docs.FEEDBACK)}; unit review-fixes is ready")
    elif a.cmd == "prompt":
        print(plan.prompt(a.unit, lang=a.lang, unattended=a.unattended))
    elif a.cmd == "autopilot":
        try:
            plan.run_autopilot(lang=a.lang, max_units=a.max_units, poll_seconds=a.poll_seconds,
                               include_interviews=a.include_interviews)
        except KeyboardInterrupt:
            print("\nAutopilot interrupted — progress is saved; `plan next` shows where to resume.")
    return 0


def cmd_interview(a) -> int:
    from lib import questionnaire
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


def cmd_runs(a) -> int:
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


def cmd_plugin_store(a) -> int:
    from lib.harness import plugin_store
    try:
        if a.action == "add":
            if not a.target:
                print("usage: plugins add <folder | git:<url>@<tag>[#subfolder]>", file=sys.stderr)
                return 2
            p = plugin_store.add(a.target)
            print(f"✔ {p.name} {p.manifest.get('version')} vendored in .camarones/plugins/{p.name} (plugins.lock)")
            if p.needs_trust:
                print(f"  It {'runs code' if p.runs_code else 'steers agents'}: approve it on this machine with "
                      f"`{cli_cmd()} trust` before it is used.")
        elif a.action == "update":
            changes = plugin_store.update(a.target or None, to=a.to or None)
            for c in changes:
                f = c["files"]
                print(f"✔ {c['name']} {c['from']} → {c['to']}: +{len(f['added'])} −{len(f['removed'])} ~{len(f['changed'])}")
                for kind, mark in (("added", "+"), ("removed", "-"), ("changed", "~")):
                    for name in f[kind]:
                        print(f"    {mark} {name}")
                if c["needs_trust"]:
                    print(f"  It changed: `{cli_cmd()} trust` asks you to approve it again.")
            if not changes:
                print("✔ plugins already match their source")
        elif a.action == "outdated":
            rows = plugin_store.outdated()
            if a.json:
                print(json.dumps(rows, indent=2))
                return 0
            for r in rows:
                print(f"  {r['name']:<16} {r['version']} → {r['latest']}   ({r['source']})")
            if not rows:
                print("✔ every vendored plugin is on its latest version")
        else:
            plugin_store.remove(a.target or "")
            print(f"✔ {a.target} removed from .camarones/plugins and plugins.lock")
    except plugin_store.PluginError as e:
        print(f"✖ {e}", file=sys.stderr)
        return 2
    return 0


def cmd_pr(a) -> int:
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


def _run_line(r: dict) -> str:
    state = "interrupted" if r["interrupted"] else ("finished" if r["finished"] else "running?")
    return (f"{r['run']}  {(r['started'] or '')[:16].replace('T', ' ')}  {r['done']}/{r['units']} done  "
            f"{r['limited']} limited  {r['failed']} failed  {r['seconds']:.0f}s  {r['tokens_in']} in / {r['tokens_out']} out"
            f"  ${r['cost_usd']:.2f}  {state}")


def cmd_plan(a) -> int:
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
        from lib.common import out
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


NO_USAGE = ("help", "mcp", "wizard")


class Legacy(Command):
    """A command run_legacy still dispatches; it goes when its group moves to commands/."""

    def __init__(self, name: str) -> None:
        self.name = name

    def run(self, args: argparse.Namespace, cli: CliContext) -> int:
        return run_legacy(args, cli.parser)

    def records_usage(self, args: argparse.Namespace) -> bool:
        return not (args.cmd in NO_USAGE or (args.cmd == "board" and getattr(args, "action", None) == "merge-driver"))
