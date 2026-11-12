"""The shape of an argparse parser as plain data, so the CLI surface can be snapshotted and compared.

As a script it prints the shape of `camarones.build_parser()`."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path, PurePath


def jsonable(v):
    if v is None or isinstance(v, (bool, int, float, str)):
        return v
    if isinstance(v, (list, tuple)):
        return [jsonable(x) for x in v]
    if isinstance(v, PurePath):
        return "<Path>"
    return f"<{type(v).__name__}>"


def _row(a: argparse.Action) -> dict:
    return {
        "dest": a.dest,
        "options": sorted(a.option_strings),
        "nargs": jsonable(a.nargs),
        "default": jsonable(a.default),
        "const": jsonable(a.const),
        "choices": None if a.choices is None else jsonable(list(a.choices)),
        "required": bool(a.required),
        "action": type(a).__name__,
    }


def shape(parser: argparse.ArgumentParser) -> dict:
    args, subs = [], {}
    for a in parser._actions:
        if isinstance(a, argparse._HelpAction):
            continue
        if isinstance(a, argparse._SubParsersAction):
            by_parser: dict[int, str] = {}
            for name, sp in a.choices.items():
                if id(sp) in by_parser:
                    subs[by_parser[id(sp)]]["aliases"].append(name)
                    continue
                by_parser[id(sp)] = name
                subs[name] = {"aliases": [], **shape(sp)}
            continue
        args.append(_row(a))
    return {"args": args, "subcommands": subs}


if __name__ == "__main__":
    kit = Path(__file__).resolve().parents[2] / ".camarones"
    sys.path.insert(0, str(kit))
    import camarones

    print(json.dumps(shape(camarones.build_parser()), indent=1, sort_keys=True))
