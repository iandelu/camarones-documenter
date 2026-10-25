"""Every CLI command with its verdict: where a person runs it. The contract between the CLI, the portal (the team's
viewer: reading, editing, review, pipeline status, interviews, sync) and the desktop app (machine work: processes,
AI, tools). Arguments are read from the real argparse parser, never written twice; `catalog --check` fails when a
command is added to the parser and not here (or the other way round).

Pure module: no project state, so the portal, the app and the tests read it without a workspace."""
from __future__ import annotations

import argparse

VERDICTS = ("portal", "app", "both", "cli")      # both: the portal shows it, the app runs it
ZONES = ("projects", "generate", "analyze", "check", "interviews", "team", "machine")


def _e(verdict: str, zone: str | None = None, es: str = "", en: str = "", ai: bool = False,
       destructive: bool = False, reads: str | None = None) -> dict:
    """`reads`: the argument (dest) that makes the command only read, so a command that otherwise asks first (`trust`
    approves with --yes) runs without asking when it is set (`trust --json` only lists)."""
    return {"verdict": verdict, "zone": zone, "es": es, "en": en, "ai": ai, "destructive": destructive, "reads": reads}


CLI = _e("cli")
COMMANDS: dict[str, dict] = {
    # projects: the app's hub
    "new": _e("app", "projects", "Crear un proyecto nuevo", "Create a new project"),
    "join": _e("app", "projects", "Unirse al cam-docs del equipo", "Join the team's cam-docs"),
    "switch": _e("app", "projects", "Abrir otro proyecto registrado", "Open another registered project"),
    "projects": _e("app", "projects", "Proyectos registrados en esta máquina", "Projects registered on this machine"),
    "init": _e("app", "projects", "Preparar este proyecto (plantillas y plan)", "Prepare this project (templates and plan)"),
    # generate: AI and the plan
    "run": _e("app", "generate", "Documentar las unidades listas en paralelo", "Document the ready units in parallel",
              ai=True),
    "autopilot": _e("app", "generate", "Documentar una unidad tras otra, sin vigilancia",
                    "Document one unit after another, unattended", ai=True),
    "wiki": _e("app", "generate", "Generar o actualizar la wiki de un repo", "Generate or update a repo's wiki", ai=True),
    "pr": _e("app", "generate", "Qué deja desactualizado un PR y proponer el arreglo",
             "What a PR leaves out of date, and propose the fix", ai=True),
    "plan": _e("both", "generate", "El plan de trabajo: ver, añadir, reabrir, aprobar",
               "The work plan: show, add, reopen, approve"),
    "runs": _e("both", "generate", "Qué hizo y costó cada ejecución", "What each run did and cost"),
    # analyze: static analysis, no AI
    "arch-draft": _e("app", "analyze", "Borrador C4 desde el código, sin IA", "C4 draft from the code, no AI"),
    "radar": _e("app", "analyze", "Stack y herramientas que ya usan los repos", "Stack and tools the repos already use"),
    "inventory": _e("both", "analyze", "Dependencias de cada repo y sus vulnerabilidades",
                    "Each repo's dependencies and their vulnerabilities"),
    "schemas": _e("app", "analyze", "Tablas y colecciones de cada repo", "Each repo's tables and collections"),
    "blocks": _e("app", "analyze", "Datos leídos del código para los bloques generados",
                 "Facts read from the code for the generated blocks"),
    "diagrams": _e("app", "analyze", "Diagramas desde el código, sin IA", "Diagrams from the code, no AI"),
    "history": _e("app", "analyze", "Historia del proyecto desde git", "The project's history from git"),
    "graph": _e("app", "analyze", "Reconstruir el grafo de código", "Rebuild the code graph"),
    "llms": _e("app", "analyze", "Regenerar llms.txt", "Regenerate llms.txt"),
    "changes": _e("both", "analyze", "Ficheros cambiados desde la última documentación",
                  "Files changed since the docs were last updated"),
    "fresh": _e("both", "analyze", "Páginas cuyo código citado cambió", "Pages whose cited code changed"),
    "mark-documented": _e("app", "analyze", "Marcar los commits actuales como documentados",
                          "Record the current commits as documented"),
    # check: is it right, is it working
    "doctor": _e("app", "check", "Requisitos y versiones de las herramientas", "Prerequisites and tool versions"),
    "check": _e("app", "check", "Comprobar la calidad de la documentación", "Check the quality of the docs"),
    "status": _e("both", "check", "Informe de confianza de las páginas", "Trust report of the pages"),
    "arch-validate": _e("app", "check", "Validar el modelo C4", "Validate the C4 model"),
    "pipeline": _e("both", "check", "Las unidades del plan y dónde trabaja cada una",
                   "The plan's units and where each one works"),
    "eval": _e("app", "check", "Preguntas de control sobre la documentación", "Golden questions over the docs", ai=True),
    "ab": _e("app", "check", "La misma pregunta con y sin cam-docs", "The same question with and without cam-docs",
             ai=True),
    "kpis": _e("both", "check", "¿Funciona? Coste, cobertura, confianza y uso", "Is it working? Cost, coverage, trust, use"),
    "stats": _e("both", "check", "Uso de la documentación por el equipo", "How the team uses the docs"),
    # interviews
    "interview": _e("both", "interviews", "Cuestionario de entrevista: modo, exportar, importar, estado",
                    "Interview questionnaire: mode, export, import, status"),
    # team: shared repo, agent config, CI
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
    # machine: tools, settings, lifecycle
    "setup": _e("app", "machine", "Instalar herramientas y conectar agentes", "Install tools and wire the agents"),
    "sync": _e("app", "machine", "Clonar o actualizar los repos", "Clone or pull the repos"),
    "detect": _e("app", "machine", "Añadir los repos encontrados en la carpeta", "Add the repos found in the folder"),
    "stack": _e("app", "machine", "Corregir el stack de un repo", "Fix a repo's stack"),
    "profile": _e("app", "machine", "Cambiar el plan entre rápido y completo", "Switch the plan between quick and full"),
    "repair": _e("app", "machine", "Reponer lo que el kit gestiona", "Put back what the kit owns"),
    "config": _e("app", "machine", "Idioma y modelos de esta máquina", "Language and models of this machine"),
    "upgrade": _e("app", "machine", "Actualizar el kit del proyecto desde una copia", "Update the project's kit from a copy"),
    "self-update": _e("app", "machine", "Actualizar el kit global", "Update the global kit"),
    "version": _e("app", "machine", "Versión del kit y de sus herramientas", "Kit and tool versions"),
    "down": _e("app", "machine", "Parar el portal", "Stop the portal"),
    "unlink": _e("app", "machine", "Quitar la copia local del kit", "Remove the local kit copy", destructive=True),
    "migrate": _e("app", "machine", "Mover un proyecto antiguo a cam-docs", "Move an older project into cam-docs",
                  destructive=True, reads="dry_run"),
    "uninstall": _e("app", "machine", "Desinstalar el proyecto", "Uninstall the project", destructive=True,
                    reads="dry_run"),
    # the portal's own: reading and review
    "confirm": _e("portal"),
    "feedback": _e("portal"),
    # CLI only: agents, hooks, servers and terminal tools
    "help": CLI, "install": CLI, "wizard": CLI, "arch": CLI, "up": CLI, "mcp": CLI, "hook": CLI, "review": CLI,
    "prompt": CLI, "catalog": CLI, "app": CLI,
}


def subparsers(parser: argparse.ArgumentParser) -> dict[str, argparse.ArgumentParser]:
    act = next(a for a in parser._actions if isinstance(a, argparse._SubParsersAction))
    return dict(act.choices)


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
