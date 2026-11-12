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
    c = sp.add_parser("confirm"); c.add_argument("files", nargs="+"); c.add_argument("--by", required=True)
    t = sp.add_parser("translated"); t.add_argument("files", nargs="+")
    ci = sp.add_parser("ci"); ci.add_argument("forge", nargs="?", choices=["gitlab", "github"])
    cp = sp.add_parser("checkpoint"); cp.add_argument("message", nargs="?", default="progress")
    rm = sp.add_parser("remote"); rm.add_argument("url", nargs="?")
    sh = sp.add_parser("share"); sh.add_argument("--auto", choices=["on", "off"])
    tr = sp.add_parser("trust"); tr.add_argument("--yes", action="store_true"); tr.add_argument("--json", action="store_true")
    fb = sp.add_parser("feedback"); fb.add_argument("file"); fb.add_argument("text"); fb.add_argument("--by", default="")
    iv = sp.add_parser("interview"); iv.add_argument("action", choices=["mode", "export", "import", "status"])
    iv.add_argument("args", nargs="*"); iv.add_argument("--lang", default="es", choices=["es", "en"])
    iv.add_argument("--json", action="store_true")
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


NO_USAGE = ("help", "mcp", "wizard")


class Legacy(Command):
    """A command run_legacy still dispatches; it goes when its group moves to commands/."""

    def __init__(self, name: str) -> None:
        self.name = name

    def run(self, args: argparse.Namespace, cli: CliContext) -> int:
        return run_legacy(args, cli.parser)

    def records_usage(self, args: argparse.Namespace) -> bool:
        return not (args.cmd in NO_USAGE or (args.cmd == "board" and getattr(args, "action", None) == "merge-driver"))
