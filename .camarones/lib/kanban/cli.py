"""`camaron board`: the board from the command line. One positional `action` plus positionals (no nested subparsers, so
`catalog.args_of` and the desktop app's forms read it). Errors are one plain line on stderr and exit 2; --json output
carries no prose. `merge-driver` is what git runs: it must not need a project, so it never touches the workspace."""
from __future__ import annotations

import json
import sys
from pathlib import Path

class _Actions(tuple):
    """The actions a person picks from (help, the desktop app's form via catalog.args_of); `merge-driver`, what git
    runs, is accepted without being listed."""
    def __contains__(self, x) -> bool:
        return x == "merge-driver" or tuple.__contains__(self, x)


ACTIONS = _Actions(("init", "add", "list", "show", "move", "assign", "link", "archive", "repair"))
_NEED = {"add": 2, "show": 1, "archive": 1, "move": 2, "assign": 2, "link": 2, "merge-driver": 3}
_USAGE = {"add": "add TYPE TITLE", "show": "show ID", "archive": "archive ID", "move": "move ID STATUS",
          "assign": "assign ID WHO", "link": "link ID REF", "merge-driver": "merge-driver O A B"}
_EMPTY = "The board is empty; this shrimp is waiting for its first card: camaron board add story \"…\""


def add_parser(sp) -> None:
    b = sp.add_parser("board")
    b.add_argument("action", choices=ACTIONS)
    b.add_argument("args", nargs="*")
    b.add_argument("--epic")
    b.add_argument("--repo", action="append")
    b.add_argument("--label", action="append")
    b.add_argument("--priority")
    b.add_argument("--doc", action="append")
    b.add_argument("--status")
    b.add_argument("--docs", choices=["suspect", "unconfirmed"])
    b.add_argument("--before")
    b.add_argument("--after")
    b.add_argument("--json", action="store_true")


def line(r: dict) -> str:
    repos = f"  [{', '.join(r['repos'])}]" if r["repos"] else ""
    return f"{r['id']}  {r['status']}  {r['priority'] or '-'}  {r['title']}{repos}"


def run(a) -> int:
    from . import ops
    if a.action == "merge-driver":
        from . import merge
        if len(a.args) != 3:
            print("✖ usage: camaron board merge-driver O A B", file=sys.stderr)
            return 2
        return merge.driver(*(Path(p) for p in a.args))
    n, need = len(a.args), _NEED.get(a.action, 0)
    if n < need or (n > need and a.action != "add"):         # add: the title may be several words
        print(f"✖ usage: camaron board {_USAGE.get(a.action, a.action)}", file=sys.stderr)
        return 2
    if a.action == "list" and (len(a.repo or ()) > 1 or len(a.label or ()) > 1):
        print("✖ list takes at most one --repo and one --label", file=sys.stderr)
        return 2
    from ..harness.locks import LockBusy
    try:
        return _run(a, ops)
    except (ops.BoardError, LockBusy, OSError) as e:        # a busy lock, a file another program holds…
        print(f"✖ {e}", file=sys.stderr)
        return 2


def _show(a, data) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2, default=str) if a.json else line(data))


def _run(a, ops) -> int:
    x, args = a.action, a.args
    if x == "init":
        made = ops.init(log=(lambda _: None) if a.json else print)
        if a.json:
            print(json.dumps({"created": made}, ensure_ascii=False))
        elif not made:
            print("The board was already set up")
    elif x == "add":
        _show(a, ops.add(args[0], " ".join(args[1:]), epic=a.epic, repos=a.repo or (), labels=a.label or (),
                         priority=a.priority, docs=a.doc or ()))
    elif x == "list":
        data = ops.list_items(status=a.status, epic=a.epic, repo=(a.repo or [None])[0], label=(a.label or [None])[0],
                              docs=a.docs)
        if a.json:
            print(json.dumps(data, ensure_ascii=False, indent=2, default=str))
        else:
            for r in data["cards"]:
                print(line(r))
            for p in data["problems"]:
                print(f"! {p['path']}: {p['error']}", file=sys.stderr)
            if not data["cards"] and not (a.status or a.epic or a.repo or a.label or a.docs):
                print("🦐 " + _EMPTY)
    elif x == "show":
        d = ops.show(args[0])
        if a.json:
            print(json.dumps(d, ensure_ascii=False, indent=2, default=str))
        else:
            print(line(d))
            if d["description"]:
                print(f"\n{d['description']}")
            for c in d["criteria"]:
                print(f"  [{'x' if c.get('done') else ' '}] {c.get('text')}")
            for l in d["links"]:
                print(f"  -> {l.get('link') or l}")
    elif x == "move":
        _show(a, ops.move(args[0], args[1], before=a.before, after=a.after))
    elif x == "assign":
        _show(a, ops.assign(args[0], args[1]))
    elif x == "link":
        _show(a, ops.link(args[0], args[1]))
    elif x == "archive":
        _show(a, ops.archive(args[0]))
    elif x == "repair":
        from . import repair
        res = repair.repair(log=(lambda _: None) if a.json else print)
        if a.json:
            print(json.dumps(res, ensure_ascii=False, indent=2, default=str))
        elif not res["changed"] and not res["warnings"]:
            print("Nothing to repair")
    return 0
