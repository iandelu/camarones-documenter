"""This machine and this project's kit: setup and tools, repos, the plan profile, settings, the kit's own lifecycle
(install, upgrade, unlink, migrate, uninstall) and the servers (portal, C4 editor, MCP)."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from lib.interfaces.cli.registry import CliContext, Command, command


@command("setup", "app", "machine", es="Instalar herramientas y conectar agentes", en="Install tools and wire the agents")
class Setup(Command):
    def configure(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--ci", action="store_true")
        parser.add_argument("--profile", choices=["quick", "full"])

    def run(self, args: argparse.Namespace, cli: CliContext) -> int:
        from lib import env, plan
        if args.profile:
            env.set_profile(args.profile)
        env.init_templates()
        env.setup(ci=args.ci)
        if not args.ci:
            plan.sync()
            plan.set_status("setup", "done", "cli setup")
            from lib import install_state
            install_state.mark_setup()
        return 0


@command("install", "cli")
class Install(Command):
    def configure(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("destination", type=Path)
        parser.add_argument("--profile", choices=["quick", "full"], default="quick")
        parser.add_argument("--dry-run", action="store_true")

    def run(self, args: argparse.Namespace, cli: CliContext) -> int:
        from lib.core.ctx import KIT
        from lib.install import install
        install(KIT.parent, args.destination, args.profile, dry_run=args.dry_run)
        return 0


@command("upgrade", "app", "machine", es="Actualizar el kit del proyecto desde una copia",
         en="Update the project's kit from a copy")
class Upgrade(Command):
    def configure(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("source", type=Path)
        parser.add_argument("--dry-run", action="store_true")

    def run(self, args: argparse.Namespace, cli: CliContext) -> int:
        from lib.core.paths import ROOT
        from lib.install import install
        install(args.source, ROOT, update=True, dry_run=args.dry_run)
        return 0


@command("self-update", "app", "machine", es="Actualizar el kit global", en="Update the global kit", project=False)
class SelfUpdate(Command):
    def run(self, args: argparse.Namespace, cli: CliContext) -> int:
        from lib.upgrade import self_update
        self_update(print)
        return 0


@command("unlink", "app", "machine", es="Quitar la copia local del kit", en="Remove the local kit copy",
         destructive=True)
class Unlink(Command):
    def run(self, args: argparse.Namespace, cli: CliContext) -> int:
        from lib.core.paths import ROOT
        from lib.install import unlink
        removed = unlink(ROOT)
        print("Kit code removed from this project — it now resolves against the global kit."
              if removed else "Nothing to remove — this project has no local kit copy.")
        return 0


@command("profile", "app", "machine", es="Cambiar el plan entre rápido y completo",
         en="Switch the plan between quick and full")
class Profile(Command):
    def configure(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("name", choices=["quick", "full"])

    def run(self, args: argparse.Namespace, cli: CliContext) -> int:
        from lib import env, plan
        env.set_profile(args.name)
        plan.sync()
        print(f"Profile: {args.name}. Progress kept. Run setup to prepare the selected tools.")
        return 0


@command("sync", "app", "machine", es="Clonar o actualizar los repos", en="Clone or pull the repos")
class Sync(Command):
    def run(self, args: argparse.Namespace, cli: CliContext) -> int:
        from lib import docs
        docs.sync_repos()
        from lib import genblocks
        if r := genblocks.refresh()["updated"]:
            print(f"✔ generated blocks refreshed in {len(r)} page(s)")
        return 0


@command("detect", "app", "machine", es="Añadir los repos encontrados en la carpeta",
         en="Add the repos found in the folder")
class Detect(Command):
    def run(self, args: argparse.Namespace, cli: CliContext) -> int:
        from lib import docs
        ws = docs.workspace()
        known = set(docs.repo_names())
        new = [r for r in docs.detect_repos() if r["name"] not in known]
        ws["repos"] += new
        docs.save_workspace(ws)
        print(f"added {len(new)} repo(s): {', '.join(r['name'] for r in new) or '—'}")
        return 0


@command("arch", "cli")
class Arch(Command):
    def run(self, args: argparse.Namespace, cli: CliContext) -> int:
        cli.services.diagrams.arch_start()
        return 0


@command("down", "app", "machine", es="Parar el portal", en="Stop the portal")
class Down(Command):
    def run(self, args: argparse.Namespace, cli: CliContext) -> int:
        from lib import env
        env.docker_down()
        return 0


@command("version", "app", "machine", es="Versión del kit y de sus herramientas", en="Kit and tool versions",
         project=False)
class Version(Command):
    def run(self, args: argparse.Namespace, cli: CliContext) -> int:
        from lib.common import VERSIONS
        print(f"Camarón {VERSIONS['kit']} — " + ", ".join(f"{k} {v}" for k, v in VERSIONS.items() if k != "kit"))
        return 0


@command("repair", "app", "machine", es="Reponer lo que el kit gestiona", en="Put back what the kit owns")
class Repair(Command):
    def run(self, args: argparse.Namespace, cli: CliContext) -> int:
        from lib import install_state
        from lib.core.ctx import CAM_DIR
        from lib.core.paths import cli_cmd
        left = install_state.repair()
        yours = [d for d in left if d.get("why") == "yours"]
        print("✔ kit files and links restored" if not left else "\n".join(
            [f"⚠ still off ({len(left)}):"]
            + [f"    {d['state']:<10} {d['path']}{'  (yours: kept)' if d in yours else ''}" for d in left]
            + ([f"  links held back: review the agent config with `{cli_cmd()} trust`"]
               if any(d["state"] == "not linked" and d not in yours for d in left) else [])
            + ([f"  yours: a file of yours is there and the kit never replaces it — move it into {CAM_DIR}/ to "
                "share it with the team, or leave it as it is"] if yours else [])))
        return 0


@command("mcp", "cli", project=False, usage=False)
class Mcp(Command):
    def configure(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--http", action="store_true")
        parser.add_argument("--port", type=int, default=8765)

    def run(self, args: argparse.Namespace, cli: CliContext) -> int:
        from lib import mcp
        if not args.http:
            mcp.serve_stdio()
            return 0
        srv = mcp.http_server(port=args.port)
        print(f"camarones MCP on http://127.0.0.1:{srv.server_address[1]}/mcp — header "
              f"`Authorization: Bearer <token>`, token in {mcp.TOKEN_FILE}", file=sys.stderr)
        try:
            srv.serve_forever()
        except KeyboardInterrupt:
            pass
        return 0


@command("up", "cli")
class Up(Command):
    def configure(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--port", type=int, default=8080)
        parser.add_argument("--docker", action="store_true")
        parser.add_argument("--static", "--no-docker", dest="static", action="store_true")
        parser.add_argument("--foreground", action="store_true")

    def run(self, args: argparse.Namespace, cli: CliContext) -> int:
        from lib import env
        from lib.core.paths import CACHE
        if args.foreground:
            from lib.interfaces.http.server import run_server
            run_server(args.port, static=args.static)
        elif args.docker or args.static:
            if not (CACHE / "site" / "index.html").exists():
                env.portal()
            (env.docker_up if args.docker else env.serve_local)(args.port)
        else:
            env.serve_editor(args.port)
        return 0


@command("migrate", "app", "machine", es="Mover un proyecto antiguo a cam-docs", en="Move an older project into cam-docs",
         destructive=True, reads="dry_run")
class Migrate(Command):
    def configure(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--yes", action="store_true")
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--finish", action="store_true", help=argparse.SUPPRESS)

    def run(self, args: argparse.Namespace, cli: CliContext) -> int:
        from lib import migrate
        return migrate.main(yes=args.yes, dry_run=args.dry_run, finish=args.finish)


@command("uninstall", "app", "machine", es="Desinstalar el proyecto", en="Uninstall the project", destructive=True,
         reads="dry_run")
class Uninstall(Command):
    def configure(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--yes", action="store_true")
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--global", dest="user_level", action="store_true")
        parser.add_argument("--no-backup", action="store_true")
        parser.add_argument("--backup-dir", type=Path)
        board = parser.add_mutually_exclusive_group()
        board.add_argument("--keep-board", dest="keep_board", action="store_const", const=True, default=None)
        board.add_argument("--drop-board", dest="keep_board", action="store_const", const=False)

    def run(self, args: argparse.Namespace, cli: CliContext) -> int:
        from lib import uninstall
        return uninstall.main(include_global=args.user_level, dry_run=args.dry_run, yes=args.yes,
                              backup=not args.no_backup, backup_dir=args.backup_dir, keep_board=args.keep_board)


@command("config", "app", "machine", es="Idioma y modelos de esta máquina", en="Language and models of this machine")
class Config(Command):
    def configure(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("action", nargs="?", default="get", choices=["get", "set"])
        parser.add_argument("key", nargs="?")
        parser.add_argument("value", nargs="?")
        parser.add_argument("--json", action="store_true")

    def run(self, args: argparse.Namespace, cli: CliContext) -> int:
        from lib import machine
        try:
            if args.action == "set":
                if not args.key or args.value is None:
                    raise ValueError("usage: config set KEY VALUE")
                machine.set_setting(args.key, args.value)
            s = machine.settings()
            if args.key and args.key not in s:
                raise ValueError(f"unknown setting {args.key}: one of {', '.join(s)}")
        except ValueError as e:
            print(f"✖ {e}", file=sys.stderr)
            return 2
        if args.json:
            print(json.dumps(s if not args.key else {args.key: s[args.key]}))
        elif args.key:
            print(s[args.key])
        else:
            for k, v in s.items():
                print(f"{k:<12} {v}")
        return 0
