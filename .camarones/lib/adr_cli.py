"""`camaron adr`: the decisions from the command line, the scripting and testing face of what the desktop app does.
One positional `action` plus positionals (no nested subparsers, so `catalog.args_of` reads it). Each action calls the
function the app's API calls: nothing here knows how an ADR is written. Errors are one plain line on stderr and exit 2,
with no joke; --json prints the function's result and no prose. A script has no stale read, so `accept` and `reject` take
the file's current sha themselves; the person who decides is the git user, as in the portal."""
from __future__ import annotations

import json
import re
import sys

ACTIONS = ("list", "new", "show", "pack", "candidates", "write", "accept", "reject")
_NEED = {"list": 0, "candidates": 0, "show": 1, "pack": 1, "write": 1, "accept": 1, "reject": 1}
_USAGE = {"list": "list", "candidates": "candidates", "new": "new TITLE --kind new|retro", "show": "show ID",
          "pack": "pack ID", "write": "write ID", "accept": "accept ID", "reject": "reject ID --why REASON"}
# flags that only mean something for some actions: anywhere else they are an error, not silently ignored
_ONLY = (("kind", "--kind", "new"), ("problem", "--problem", "new"), ("touch", "--touch", "new"),
         ("supersedes", "--supersedes", "new"), ("attendee", "--attendee", "accept"), ("why", "--why", "reject"))
_NONE = {"list": "No decisions yet: camaron adr new TITLE --kind new|retro",
         "candidates": "No candidate decisions: nothing in the code is left without an ADR"}


def add_parser(sp) -> None:
    b = sp.add_parser("adr")
    b.add_argument("action", choices=ACTIONS)
    b.add_argument("args", nargs="*")
    b.add_argument("--kind")
    b.add_argument("--problem")
    b.add_argument("--touch", action="append")
    b.add_argument("--supersedes")
    b.add_argument("--attendee", action="append")
    b.add_argument("--why")
    b.add_argument("--json", action="store_true")


def line(row: dict) -> str:
    return f"{row['id']}  {row['chip']}  {row['title']}"


def _ref(text: str) -> str:
    return f"{int(text):04d}" if re.fullmatch(r"[0-9]{1,4}", text) else text


def _misplaced(a) -> str | None:
    for dest, flag, action in _ONLY:
        if getattr(a, dest, None) not in (None, []) and a.action != action:
            return f"✖ {flag} only goes with: {action}"
    return None


def _wrong_usage(a) -> str | None:
    n = len(a.args)
    if a.action == "new":
        ok = n >= 1
    else:
        ok = n == _NEED[a.action]
    return None if ok else f"✖ usage: camaron adr {_USAGE[a.action]}"


def _who() -> str:
    from . import serve
    return serve.reviewer()


def _emit(data, a, plain) -> int:
    if a.json:
        print(json.dumps(data, ensure_ascii=False, indent=2, default=str))
    else:
        plain(data)
    return 0


def _print_row(data: dict) -> None:
    print(line(data))
    moved = ((data.get("notice") or {}).get("renumbered") or {})
    if moved:
        print(f"renumbered {moved['from']} -> {moved['to']}")


def _list(a) -> int:
    from . import adr

    def plain(rows):
        for row in rows:
            print(line(row))
        if not rows:
            print(_NONE["list"], file=sys.stderr)
    return _emit(adr.list_adrs(), a, plain)


def _candidates(a) -> int:
    from . import adr_pack

    def plain(rows):
        for row in rows:
            print(f"{row['category']}  {row['label']}  [{', '.join(row['repos'])}]")
        if not rows:
            print(_NONE["candidates"], file=sys.stderr)
    return _emit(adr_pack.candidates(), a, plain)


def _new(a) -> int:
    from . import adr
    fields = {"title": " ".join(a.args), "kind": a.kind, "problem": a.problem, "touches": a.touch or [],
              "supersedes": a.supersedes}
    return _emit(adr.new(fields), a, _print_row)


def _one(a) -> int:
    from . import adr

    def plain(data):
        print(line(data))
        text = data["raw"].rstrip("\n") or (data["state"] or {}).get("problem") or ""
        if text:
            print()
            print(text)
    return _emit(adr.get(_ref(a.args[0])), a, plain)


def _pack(a) -> int:
    from . import adr
    return _emit(adr.pack(_ref(a.args[0])), a, lambda data: print(data["markdown"].rstrip("\n")))


def _write(a) -> int:
    from . import adr
    return _emit(adr.write_without_ai(_ref(a.args[0])), a, _print_row)


def _accept(a) -> int:
    from . import adr
    id = _ref(a.args[0])
    return _emit(adr.accept(id, _who(), a.attendee, adr.get(id)["sha"]), a, _print_row)


def _reject(a) -> int:
    from . import adr
    id = _ref(a.args[0])
    return _emit(adr.reject(id, a.why, _who(), adr.get(id)["sha"]), a, _print_row)


_RUN = {"list": _list, "new": _new, "show": _one, "pack": _pack, "candidates": _candidates, "write": _write,
        "accept": _accept, "reject": _reject}


def run(a) -> int:
    wrong = _misplaced(a) or _wrong_usage(a)
    if wrong:
        print(wrong, file=sys.stderr)
        return 2
    from . import adr
    from .adr_api import BUSY
    from .harness.locks import LockBusy
    try:
        return _RUN[a.action](a)
    except KeyError as e:
        print(f"✖ no ADR {e.args[0] if e.args else ''}", file=sys.stderr)
    except LockBusy:
        print(f"✖ {BUSY}", file=sys.stderr)
    except (adr.AdrError, OSError) as e:                    # AdrConflict is one: a file changed between reading and saving
        print(f"✖ {e}", file=sys.stderr)
    return 2
