"""The team's shared work: the cam-docs remote, checkpoints and sharing, the agent config this machine trusts, method
hooks, plugins, CI, exports and the portal export, review requests, removals, confirmations, translations and
feedback."""
from __future__ import annotations

import argparse
import json
import os
import sys

from lib.interfaces.cli.registry import CliContext, Command, command


@command("portal", "app", "team", es="Exportar el portal de solo lectura", en="Export the read-only portal")
class Portal(Command):
    def run(self, args: argparse.Namespace, cli: CliContext) -> int:
        cli.services.export_site.portal()
        return 0


@command("removed", "both", "team", es="Anotar algo quitado a propósito", en="Record something removed on purpose")
class Removed(Command):
    def configure(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("action", choices=["add"])
        parser.add_argument("what")
        parser.add_argument("--why", required=True)
        parser.add_argument("--decision", default="")

    def run(self, args: argparse.Namespace, cli: CliContext) -> int:
        from lib import removed
        print(f"✔ {removed.add(args.what, args.why, args.decision)}: {args.what}")
        return 0


@command("review", "cli")
class Review(Command):
    def configure(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("action", choices=["request", "wait", "list"])
        parser.add_argument("target", nargs="?")
        parser.add_argument("--note", default="")
        parser.add_argument("--by", default="agent")
        parser.add_argument("--timeout", type=float, default=3600)

    def run(self, args: argparse.Namespace, cli: CliContext) -> int:
        from lib import review
        from lib.core.paths import cli_cmd
        if args.action == "list":
            print(json.dumps(review.open_requests(), indent=2, ensure_ascii=False))
        elif not args.target:
            print("usage: review request PAGE [--note TEXT] | review wait ID [--timeout S]", file=sys.stderr)
            return 2
        elif args.action == "request":
            rid = review.request(args.target, by=args.by, note=args.note)
            print(json.dumps({"id": rid, "path": args.target, "next": f"{cli_cmd()} review wait {rid}"}))
        else:
            try:
                print(json.dumps(review.wait(args.target, timeout=args.timeout), ensure_ascii=False))
            except KeyError:
                print(f"✖ no review request {args.target}", file=sys.stderr)
                return 2
        return 0


@command("hook", "cli")
class Hook(Command):
    def configure(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("name", choices=["session-start", "post-edit", "stop"])

    def run(self, args: argparse.Namespace, cli: CliContext) -> int:
        from lib import hooks
        return hooks.main(args.name)


@command("hooks", "app", "team", es="Hooks del método para Claude Code", en="Method hooks for Claude Code")
class Hooks(Command):
    def configure(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("state", nargs="?", choices=["on", "off"])
        parser.add_argument("--json", action="store_true")

    def run(self, args: argparse.Namespace, cli: CliContext) -> int:
        from lib import hooks
        if args.state:
            hooks.set_enabled(args.state == "on")
        if args.json:
            print(json.dumps({"enabled": hooks.enabled()}))
            return 0
        print(f"method hooks: {'on' if hooks.enabled() else 'off'}" + (
            " — SessionStart (plan state), PostToolUse (check the page just edited), Stop (remind once to update docs)"
            if hooks.enabled() else ""))
        return 0


def cmd_plugin_store(a) -> int:
    from lib.core.paths import cli_cmd
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


@command("plugins", "app", "team", es="Plugins del kit y del proyecto", en="Plugins of the kit and the project")
class Plugins(Command):
    def configure(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--json", action="store_true")
        parser.add_argument("action", nargs="?", default="list",
                            choices=["list", "add", "update", "outdated", "remove", "enable", "disable"])
        parser.add_argument("target", nargs="?")
        parser.add_argument("--to", default="")

    def run(self, args: argparse.Namespace, cli: CliContext) -> int:
        from lib.harness import plugins
        if args.action in ("enable", "disable"):
            ok = (plugins.enable if args.action == "enable" else plugins.disable)(args.target or "")
            if not ok:
                print(f"✖ no plugin called {args.target}", file=sys.stderr)
                return 2
            print(f"✔ {args.target} {'enabled' if args.action == 'enable' else 'disabled'} on this machine")
            return 0
        if args.action != "list":
            return cmd_plugin_store(args)
        from lib.core.paths import ROOT
        rows = plugins.rows()
        if args.json:
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
        return 0


@command("export", "app", "team", es="Exportar a PDF, tour, Confluence o Notion", en="Export to PDF, tour, Confluence or Notion")
class Export(Command):
    def configure(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("what", choices=["pdf", "print", "tour", "codetour", "confluence", "notion"])
        parser.add_argument("page", nargs="?")

    def run(self, args: argparse.Namespace, cli: CliContext) -> int:
        from lib import exporters
        try:
            if args.what in ("pdf", "print"):
                out = exporters.export_pdf() if args.what == "pdf" else exporters.export_print()
                print(f"✔ {out}" + ("" if out.suffix == ".pdf" or args.what == "print" else
                                    "  (no headless Chrome/Chromium/Edge found: print this page to PDF from a browser)"))
            elif args.what in ("tour", "codetour"):
                if not args.page:
                    print(f"usage: export {args.what} flows/<flow>.md", file=sys.stderr)
                    return 2
                if args.what == "tour":
                    print(f"✔ {exporters.export_tour(args.page)}  (open it; → and ← move between steps)")
                else:
                    print(f"✔ {exporters.export_codetour(args.page)}  (VS Code with the CodeTour extension: "
                          f"open the workspace folder, then CodeTour: Start Tour)")
            else:
                print(f"✔ {exporters.export_to(args.what)} page(s) published to {args.what}")
        except exporters.ExportError as e:
            print(f"✖ {e}", file=sys.stderr)
            return 2
        return 0


@command("confirm", "portal")
class Confirm(Command):
    def configure(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("files", nargs="+")
        parser.add_argument("--by", required=True)

    def run(self, args: argparse.Namespace, cli: CliContext) -> int:
        from lib import docs
        for f in docs.confirm(args.files, args.by):
            print(f"confirmed {f} by {args.by}")
        return 0


@command("translated", "both", "team", es="Marcar páginas como traducidas", en="Stamp pages as translated")
class Translated(Command):
    def configure(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("files", nargs="+")

    def run(self, args: argparse.Namespace, cli: CliContext) -> int:
        from lib import docs
        for f in docs.translated(args.files):
            print("stamped", f)
        return 0


@command("ci", "app", "team", es="Instalar la pipeline de CI", en="Install the CI pipeline")
class Ci(Command):
    def configure(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("forge", nargs="?", choices=["gitlab", "github"])

    def run(self, args: argparse.Namespace, cli: CliContext) -> int:
        from lib import ci
        ci.install_ci(args.forge)
        return 0


@command("checkpoint", "both", "team", es="Guardar el progreso en un commit local", en="Save progress in a local commit")
class Checkpoint(Command):
    def configure(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("message", nargs="?", default="progress")

    def run(self, args: argparse.Namespace, cli: CliContext) -> int:
        print("✔ committed locally" if cli.services.share.checkpoint_commit(args.message) else "no checkpoint commit")
        return 0


@command("remote", "both", "team", es="Ver o fijar el repo cam-docs del equipo", en="Show or set the team's cam-docs repo")
class Remote(Command):
    def configure(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("url", nargs="?")

    def run(self, args: argparse.Namespace, cli: CliContext) -> int:
        if args.url:
            cli.services.share.set_remote(args.url)
        print(cli.services.share.docs_remote() or "no remote — set one with: remote URL")
        return 0


@command("share", "both", "team", es="Sincronizar con el equipo (pull y push)", en="Sync with the team (pull and push)")
class Share(Command):
    def configure(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--auto", choices=["on", "off"])

    def run(self, args: argparse.Namespace, cli: CliContext) -> int:
        if args.auto:
            cli.services.share.set_auto_share(args.auto == "on")
            print(f"auto-share: {args.auto}")
            return 0
        r = cli.services.share.share()
        why = f" ({r['reason']})" if r.get("reason") else ""
        print(f"{r['status']}{why}{': ' + r['detail'] if r['detail'] else ''}")
        return 0 if r["status"] in ("pushed", "up-to-date", "nothing") else 1


def cmd_trust(a, cli: CliContext) -> int:
    from lib import trust
    from lib.core.paths import cli_cmd
    cli.services.setup.refresh_agent_config()
    rows = trust.grouped(trust.pending())
    if a.json:                                  # what is pending, for the desktop app (approving takes --yes)
        print(json.dumps({"pending": [dict(zip(("kind", "label", "detail", "status"), r)) for r in rows]},
                         ensure_ascii=False))
        return 0
    if not rows:
        cli.services.setup.link_workspace()
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
    cli.services.setup.link_workspace()
    print(f"✔ approved {n} item(s); the workspace's agents load this config")
    return 0


@command("trust", "app", "team", es="Aprobar la configuración de agentes de esta máquina",
         en="Approve the agent config on this machine", reads="json")
class Trust(Command):
    def configure(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--yes", action="store_true")
        parser.add_argument("--json", action="store_true")

    def run(self, args: argparse.Namespace, cli: CliContext) -> int:
        return cmd_trust(args, cli)


@command("feedback", "portal")
class Feedback(Command):
    def configure(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("file")
        parser.add_argument("text")
        parser.add_argument("--by", default="")

    def run(self, args: argparse.Namespace, cli: CliContext) -> int:
        from lib import docs, plan
        docs.add_feedback(args.file, args.text, args.by or os.environ.get("USER", "human"))
        plan.ensure("review-fixes", "review-fixes")
        print(f"feedback recorded in {plan._at(docs.FEEDBACK)}; unit review-fixes is ready")
        return 0
