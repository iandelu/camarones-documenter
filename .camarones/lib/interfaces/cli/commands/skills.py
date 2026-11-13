"""`camaron skills`: the agents' skills from the command line. One positional `action` plus positionals (no nested
subparsers, so `catalog.args_of` reads it). Each action calls `lib/skills.py`; nothing here knows how a skill is
rendered or a note is written. Errors are one plain line on stderr and exit 2, with no joke; --json prints data and no
prose."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from lib.interfaces.cli.registry import CliContext, Command, command

ACTIONS = ("list", "fork", "diff", "reset", "note", "notes")
_USAGE = {"list": "list", "fork": "fork NAME", "diff": "diff NAME [--kit]", "reset": "reset NAME",
          "note": "note SKILL TEXT --source retro|review|board [--step S] [--change ID] [--ref URL]",
          "notes": "notes [SKILL]"}
# flags that only mean something for some actions: anywhere else they are an error, not silently ignored
_ONLY = (("kit", "--kit", "diff"), ("source", "--source", "note"), ("step", "--step", "note"),
         ("change", "--change", "note"), ("ref", "--ref", "note"))


def add_parser(sp) -> None:
    Skills().configure(sp.add_parser("skills"))


@command("skills", "cli")
class Skills(Command):
    def run(self, args: argparse.Namespace, cli: CliContext) -> int:
        return run(args)

    def configure(self, b: argparse.ArgumentParser) -> None:
        b.add_argument("action", choices=ACTIONS)
        b.add_argument("args", nargs="*")
        b.add_argument("--kit", action="store_true")
        b.add_argument("--source")
        b.add_argument("--step")
        b.add_argument("--change")
        b.add_argument("--ref")
        b.add_argument("--json", action="store_true")


def _misplaced(a) -> str | None:
    for dest, flag, action in _ONLY:
        if getattr(a, dest, None) not in (None, False) and a.action != action:
            return f"✖ {flag} only goes with: {action}"
    return None


def _wrong_usage(a) -> str | None:
    n = len(a.args)
    if a.action == "list":
        ok = n == 0
    elif a.action == "notes":
        ok = n <= 1
    elif a.action == "note":
        ok = n >= 2 and a.source is not None
    else:
        ok = n == 1
    return None if ok else f"✖ usage: camaron skills {_USAGE[a.action]}"


def _who() -> str:
    from lib.app import portal_views
    return portal_views.reviewer()


def _rel(path: Path) -> str:
    from lib.core.paths import ROOT
    try:
        return path.resolve().relative_to(Path(ROOT).resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _rerender() -> None:
    from lib.app import services
    services.current().setup.refresh_agent_config()


def _done(a, data: dict, line: str) -> int:
    print(json.dumps(data, ensure_ascii=False, indent=2) if a.json else line)
    return 0


def _list(a) -> int:
    from lib import skills
    outdated = set(skills.outdated())
    names = sorted(set(skills.kit_names()) | set(skills.team_names()))
    rows = [{"name": n, "origin": skills.origin(n), "outdated": n in outdated, "description": skills.description(n)}
            for n in names]
    skipped = skills.ignored()
    if a.json:
        print(json.dumps({"skills": rows, "ignored": skipped}, ensure_ascii=False, indent=2))
        return 0
    for r in rows:
        print(f"{r['name']}  {r['origin']}" + ("  (kit changed since your copy)" if r["outdated"] else ""))
    for s in skipped:
        print(f"· skipped .camarones/skills/{s['name']}: {s['why']}", file=sys.stderr)
    return 0


def _fork(a) -> int:
    from lib import skills
    path = skills.fork(a.args[0])
    _rerender()
    return _done(a, {"name": a.args[0], "path": _rel(path)},
                 f"✔ team copy of {a.args[0]}: {_rel(path)} — edit it and commit it in a docs PR")


def _diff(a) -> int:
    from lib import skills
    text = skills.diff(a.args[0], against_fork=a.kit)
    if a.json:
        print(json.dumps({"name": a.args[0], "diff": text}, ensure_ascii=False, indent=2))
    else:
        print(text.rstrip("\n") if text else f"{a.args[0]}: same as the kit")
    return 0


def _reset(a) -> int:
    from lib import skills
    path = skills.reset(a.args[0])
    _rerender()
    return _done(a, {"name": a.args[0], "path": _rel(path)},
                 f"✔ {a.args[0]} follows the kit again (your copy: {_rel(path)})")


def _note(a) -> int:
    from lib import skills
    path = skills.add_note(a.args[0], " ".join(a.args[1:]), a.source, _who(), step=a.step or "",
                           change=a.change or "", ref=a.ref or "")
    return _done(a, {"skill": a.args[0], "path": _rel(path)}, f"✔ note added to {_rel(path)}")


def _notes(a) -> int:
    from lib import skills
    rows = skills.notes(a.args[0] if a.args else None)
    if a.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return 0
    if not rows:
        print("No skill notes yet.", file=sys.stderr)
        return 0
    tree: dict[str, dict[str, list[dict]]] = {}
    for n in rows:
        tree.setdefault(n["skill"], {}).setdefault(n["step"] or "-", []).append(n)
    for skill, steps in tree.items():
        print(f"{skill} ({sum(len(v) for v in steps.values())})")
        for step, items in steps.items():
            print(f"  {step} ({len(items)})")
            for n in items:
                print(f"    {n['date']} {n['source']} {n['change'] or '-'} {n['by']} — {n['text']}")
    return 0


_RUN = {"list": _list, "fork": _fork, "diff": _diff, "reset": _reset, "note": _note, "notes": _notes}


def run(a) -> int:
    wrong = _misplaced(a) or _wrong_usage(a)
    if wrong:
        print(wrong, file=sys.stderr)
        return 2
    try:
        return _RUN[a.action](a)
    except (ValueError, OSError) as e:
        print(f"✖ {e}", file=sys.stderr)
    return 2
