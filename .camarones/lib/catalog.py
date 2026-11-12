"""Every CLI command with its verdict: where a person runs it. The contract between the CLI, the portal (the team's
viewer: reading, editing, review, pipeline status, interviews, sync) and the desktop app (machine work: processes,
AI, tools). Arguments are read from the real argparse parser, never written twice; `catalog --check` fails when a
command is added to the parser and not here (or the other way round).

Pure module: no project state, so the portal, the app and the tests read it without a workspace."""
from __future__ import annotations

import argparse

from .interfaces.cli import registry
from .interfaces.cli.registry import VERDICTS, ZONES


def _e(verdict: str, zone: str | None = None, es: str = "", en: str = "", ai: bool = False,
       destructive: bool = False, reads: str | None = None) -> dict:
    """`reads`: the argument (dest) that makes the command only read, so a command that otherwise asks first (`trust`
    approves with --yes) runs without asking when it is set (`trust --json` only lists)."""
    return {"verdict": verdict, "zone": zone, "es": es, "en": en, "ai": ai, "destructive": destructive, "reads": reads}


CLI = _e("cli")
_LEFT: dict[str, dict] = {             # the commands still dispatched by interfaces/cli/legacy.py
    # interviews
    "interview": _e("both", "interviews", "Cuestionario de entrevista: modo, exportar, importar, estado",
                    "Interview questionnaire: mode, export, import, status"),
    # team: shared repo, agent config, CI
    "board": _e("both", "team", "El tablero: historias, épicas y su estado", "The board: stories, epics and their status"),
    "adr": _e("app", "team", "Decisiones (ADR): listar, crear, aceptar", "Decisions (ADRs): list, create, accept"),
    "remote": _e("both", "team", "Ver o fijar el repo cam-docs del equipo", "Show or set the team's cam-docs repo"),
    "share": _e("both", "team", "Sincronizar con el equipo (pull y push)", "Sync with the team (pull and push)"),
    "checkpoint": _e("both", "team", "Guardar el progreso en un commit local", "Save progress in a local commit"),
    "trust": _e("app", "team", "Aprobar la configuración de agentes de esta máquina",
                "Approve the agent config on this machine", reads="json"),
    "hooks": _e("app", "team", "Hooks del método para Claude Code", "Method hooks for Claude Code"),
    "plugins": _e("app", "team", "Plugins del kit y del proyecto", "Plugins of the kit and the project"),
    "ci": _e("app", "team", "Instalar la pipeline de CI", "Install the CI pipeline"),
    "portal": _e("app", "team", "Exportar el portal de solo lectura", "Export the read-only portal"),
    "export": _e("app", "team", "Exportar a PDF, tour, Confluence o Notion", "Export to PDF, tour, Confluence or Notion"),
    "removed": _e("both", "team", "Anotar algo quitado a propósito", "Record something removed on purpose"),
    "translated": _e("both", "team", "Marcar páginas como traducidas", "Stamp pages as translated"),
    # the portal's own: reading and review
    "confirm": _e("portal"),
    "feedback": _e("portal"),
    # CLI only: agents, hooks, servers and terminal tools
    "hook": CLI, "review": CLI, "prompt": CLI,
}


COMMANDS: dict[str, dict] = {**_LEFT, **registry.entries(registry.load())}


def subparsers(parser: argparse.ArgumentParser) -> dict[str, argparse.ArgumentParser]:
    """Each command once: argparse maps an alias to the same parser as its command."""
    act = next(a for a in parser._actions if isinstance(a, argparse._SubParsersAction))
    seen: set[int] = set()
    return {name: sub for name, sub in act.choices.items() if not (id(sub) in seen or seen.add(id(sub)))}


def drift(names) -> tuple[list[str], list[str]]:
    """(in the parser but not here, here but not in the parser)."""
    names = set(names)
    return sorted(names - COMMANDS.keys()), sorted(COMMANDS.keys() - names)


def _kind(a: argparse.Action) -> str:
    if isinstance(a, (argparse._StoreTrueAction, argparse._StoreFalseAction)):
        return "bool"
    if isinstance(a, argparse._StoreConstAction):
        return "const"
    if a.choices:
        return "choice"
    if a.type is int:
        return "int"
    if a.type is float:
        return "float"
    if getattr(a.type, "__name__", "") in ("Path", "WindowsPath", "PosixPath"):
        return "path"
    return "str"


def _jsonable(v):
    return v if v is None or isinstance(v, (bool, int, float, str, list)) else str(v)


def args_of(sub: argparse.ArgumentParser) -> list[dict]:
    rows = []
    for a in sub._actions:
        if isinstance(a, argparse._HelpAction) or a.help == argparse.SUPPRESS:
            continue
        row = {"dest": a.dest, "flag": max(a.option_strings, key=len) if a.option_strings else None, "kind": _kind(a),
               "default": _jsonable(a.default), "choices": list(a.choices) if a.choices else None,
               "required": bool(a.required), "positional": not a.option_strings,
               "many": a.nargs in ("+", "*") or (isinstance(a.nargs, int) and a.nargs > 1)}
        if row["kind"] == "const":
            row["const"] = _jsonable(a.const)
        rows.append(row)
    return rows


def describe(parser: argparse.ArgumentParser) -> dict:
    """The catalog as data: one row per command known to both sides, plus the drift lists (empty when in sync)."""
    subs = subparsers(parser)
    unlisted, unknown = drift(subs)
    commands = []
    for name in sorted(subs.keys() & COMMANDS.keys()):
        args = args_of(subs[name])
        commands.append({"name": name, **COMMANDS[name], "args": args,
                         "json": any(a["flag"] == "--json" for a in args),
                         "confirm": "--yes" if any(a["flag"] == "--yes" for a in args) else None})
    return {"commands": commands, "unlisted": unlisted, "unknown": unknown}


def triage_markdown(commands: list[dict]) -> str:
    """docs/research/cli-triage.md, regenerated with `catalog --markdown`."""
    where = {"portal": "portal", "app": "desktop app", "both": "portal shows it, the app runs it", "cli": "CLI only"}
    lines = ["# CLI triage: where each command lives", "",
             "Generated from `.camarones/lib/catalog.py` by `camaron catalog --markdown` — do not edit by hand.",
             "The portal is the team's viewer (reading, editing, review, pipeline status, interviews, sync); the",
             "desktop app runs everything that starts a process, calls a model or changes this machine; the CLI keeps",
             "every command either way.", ""]
    for verdict in VERDICTS:
        rows = [c for c in commands if c["verdict"] == verdict]
        lines += [f"## {where[verdict].capitalize()} ({len(rows)})", "",
                  "| Command | Zone | AI | Destructive | --json |", "|---|---|---|---|---|"]
        for c in rows:
            lines.append(f"| `{c['name']}` | {c['zone'] or '—'} | {'yes' if c['ai'] else ''} | "
                         f"{'yes' if c['destructive'] else ''} | {'yes' if c['json'] else ''} |")
        lines.append("")
    return "\n".join(lines)
