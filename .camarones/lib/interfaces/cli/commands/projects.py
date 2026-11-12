"""The projects on this machine: create, join or switch to one (lib/interfaces/cli/launch.py does that before parsing),
prepare this one, and list, register, inspect or adopt folders (the desktop app's hub)."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from lib.interfaces.cli.registry import CliContext, Command, command


@command("new", "app", "projects", es="Crear un proyecto nuevo", en="Create a new project")
class New(Command):
    def configure(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("name")
        parser.add_argument("--from", dest="from_url", default="")
        parser.add_argument("--no-open", action="store_true")

    def run(self, args: argparse.Namespace, cli: CliContext) -> int:
        return 0                                    # launch.prelaunch created it and restarted the script there


@command("switch", "app", "projects", es="Abrir otro proyecto registrado", en="Open another registered project")
class Switch(Command):
    def run(self, args: argparse.Namespace, cli: CliContext) -> int:
        return 0                                    # launch.prelaunch picked it and restarted the script there


@command("init", "app", "projects", es="Preparar este proyecto (plantillas y plan)",
         en="Prepare this project (templates and plan)")
class Init(Command):
    def run(self, args: argparse.Namespace, cli: CliContext) -> int:
        from lib import docs, env, plan
        env.init_templates()
        docs.save_workspace(docs.workspace())   # persist workspace.yaml even with 0 repos yet — global
        plan.sync()                             # install's marker lookup (find_project_marker) needs it on disk
        return 0


@command("join", "app", "projects", es="Unirse al cam-docs del equipo", en="Join the team's cam-docs")
class Join(Command):
    def configure(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("url")
        parser.add_argument("folder", nargs="?", type=Path)
        parser.add_argument("--no-open", action="store_true")

    def run(self, args: argparse.Namespace, cli: CliContext) -> int:
        return 0                                    # launch.prelaunch joined it and restarted the script there


@command("projects", "app", "projects",
         es="Proyectos registrados; --inspect mira una carpeta, --adopt la vuelve proyecto, --git-init pone en git su "
            "código",
         en="Registered projects; --inspect reads a folder, --adopt makes it a project, --git-init puts its code under "
            "git",
         project=False)
class Projects(Command):
    def configure(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--json", action="store_true")
        parser.add_argument("--add", type=Path)
        # the desktop start screen's way in (it calls them itself); own dests, apart from `pages --adopt`
        parser.add_argument("--inspect", dest="inspect_dir", type=Path, metavar="DIR",
                            help="what a folder is, writes nothing")
        parser.add_argument("--adopt", dest="adopt_dir", type=Path, metavar="DIR", help="make a folder a project")
        parser.add_argument("--name", dest="adopt_name", metavar="NAME", help="the project's name, with --adopt")
        parser.add_argument("--git-init", dest="git_init_dir", type=Path, metavar="DIR",
                            help="git init the code folders without a repository")

    def run(self, args: argparse.Namespace, cli: CliContext) -> int:
        if args.inspect_dir or args.adopt_dir or args.git_init_dir:
            return _onboard(args)
        from lib import projects
        if args.add:
            from lib.core.ctx import docs_root
            root = docs_root(args.add)
            if not (args.add.is_dir() and (root / ".camarones" / "workspace.yaml").is_file()):
                print(f"✖ {args.add} is not a Camarón project (no cam-docs/.camarones/workspace.yaml)", file=sys.stderr)
                return 1
            projects.register(root)
            row = {"name": root.parent.name if root.name == "cam-docs" else root.name, "path": str(root), "exists": True}
            print(json.dumps(row, ensure_ascii=False) if args.json else f"✔ {row['name']} → {root}")
            return 0
        # a project registered by its docs root is named after its workspace folder, not "cam-docs"
        rows = [{"name": Path(r["path"]).parent.name if r["name"] == "cam-docs" else r["name"], "path": r["path"],
                 "exists": Path(r["path"]).is_dir()} for r in projects.load()]
        if args.json:
            print(json.dumps(rows, indent=2, ensure_ascii=False))
        for r in rows if not args.json else ():
            print(f"{r['name']:<24} {r['path']}{'' if r['exists'] else '  (missing)'}")
        return 0


def _onboard(a: argparse.Namespace) -> int:
    """The desktop start screen's way in: what a picked folder is, then make it a project (no project globals
    needed)."""
    from lib import onboard, projects
    try:
        if a.inspect_dir:
            if not a.inspect_dir.is_dir():
                raise ValueError(f"not a folder: {a.inspect_dir}")
            info = onboard.inspect(a.inspect_dir)
            if a.json:
                print(json.dumps(info, ensure_ascii=False))
            for k, v in info.items() if not a.json else ():
                print(f"{k:<10} {v}")
        elif a.git_init_dir:
            done = onboard.git_init(a.git_init_dir)
            print(json.dumps({"initialised": [str(p) for p in done]}, ensure_ascii=False) if a.json
                  else "\n".join(f"✔ git init {p}" for p in done))
        else:
            dest = onboard.start(a.adopt_dir, a.adopt_name)
            print(json.dumps({"path": str(dest)}, ensure_ascii=False) if a.json else f"✔ {dest}")
    except (ValueError, RuntimeError, OSError) as e:
        print(f"✖ {e}", file=sys.stderr)
        code = ("taken" if isinstance(e, projects.Taken) else getattr(e, "code", "") if isinstance(e, onboard.Refused)
                else "git-init" if a.git_init_dir else "")
        if a.json and code:                                     # the app words it: a stable code, not this line
            print(json.dumps({"error": code, "detail": str(e)}, ensure_ascii=False))
        return 1
    return 0
