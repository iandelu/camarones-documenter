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


ACTIONS = _Actions(("init", "add", "list", "show", "move", "assign", "link", "archive", "repair", "next", "waves", "story"))
_NEED = {"add": 2, "show": 1, "archive": 1, "move": 2, "assign": 2, "link": 2, "story": 2, "merge-driver": 3}
_USAGE = {"add": "add TYPE TITLE", "show": "show ID", "archive": "archive ID", "move": "move ID STATUS",
          "assign": "assign ID WHO", "link": "link ID REF", "story": "story lint|invest|split ID", "merge-driver": "merge-driver O A B"}
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
    b.add_argument("--story")
    b.add_argument("--n", type=int, default=3)
    b.add_argument("--touch", action="append")
    b.add_argument("--accept", action="store_true")
    b.add_argument("--force", action="store_true")
    b.add_argument("--json", action="store_true")


def line(r: dict) -> str:
    repos = f"  [{', '.join(r['repos'])}]" if r["repos"] else ""
    return f"{r['id']}  {r['status']}  {r['priority'] or '-'}  {r['title']}{repos}"


def _lang(ops) -> str:
    try:
        return "es" if ops.docs_lang() == "es" else "en"
    except Exception:                                        # noqa: BLE001 — a note must never break the command
        return "en"


def note(b: dict, lang: str) -> str:
    """Why an item cannot start, in the project's language."""
    es, i = lang == "es", b.get("id")
    if b["kind"] == "wave":
        k = int(b.get("wave") or 0) + 1                      # 0-based in --json, as `board waves` numbers them here
        return (f"choca con otra tarea lista: va en la ola {k}" if es
                else f"collides with another ready task: it goes in wave {k}")
    if b["kind"] == "dependency":
        return f"espera a {i}" if es else f"waits for {i}"
    if b["kind"] == "missing":
        return f"depende de {i}, que no existe" if es else f"depends on {i}, which does not exist"
    files = ", ".join(b.get("files", ()))
    return f"choca con {i} en {files}" if es else f"collides with {i} on {files}"


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
    except ops.GateError as e:                              # a person can force it; the line says how
        lang = _lang(ops)
        why = "; ".join(note(b, lang) for b in e.blocked_by)
        head, tail = (("no puede empezar", "--force lo mueve igual") if lang == "es"
                      else ("cannot start", "--force moves it anyway"))
        print(f"✖ {e.item_id} {head}: {why} ({tail})", file=sys.stderr)
        return 2
    except (ops.BoardError, LockBusy, OSError) as e:        # a busy lock, a file another program holds…
        print(f"✖ {e}", file=sys.stderr)
        return 2


_VERDICT = {"es": {"good": "bueno", "improve": "mejorable", "poor": "pobre"},
            "en": {"good": "good", "improve": "needs work", "poor": "poor"}}


def _story_input(story_id: str, extra) -> tuple[dict, dict]:
    """The stored story as `analyze`/`save` take it, plus `item()` itself; `--touch` entries are checked and added to its
    footprint the way `save` checks them (nothing is written)."""
    from .. import stories_save
    from . import index
    found = stories_save.item(story_id)
    touches = list(found["touches"])
    if extra:
        conn = index.connect()
        try:
            touches = sorted({*touches, *stories_save._check_touches(extra, conn, "--touch")})
        finally:
            conn.close()
    story = {k: found[k] for k in ("id", "as_", "want", "so", "criteria", "epic", "priority")}
    return {**story, "touches": touches}, found


def _wave(t: dict) -> str:
    return str(t["wave"] + 1) if t["wave"] >= 0 else "-"


def _story(a, ops) -> int:
    from .. import stories, stories_save
    verb = a.args[0]
    if verb not in ("lint", "invest", "split"):
        print(f"✖ usage: camaron board {_USAGE['story']}", file=sys.stderr)
        return 2
    lang = _lang(ops)
    es = lang == "es"
    story, found = _story_input(a.args[1], a.touch)
    if verb == "split" and a.accept and found["subtasks"]:
        print(f"✖ {found['id']} ya tiene subtareas: no se vuelve a dividir" if es
              else f"✖ {found['id']} already has subtasks: it is not split again", file=sys.stderr)
        return 2
    analysis = stories.analyze(story, lang=lang)
    if verb == "lint":
        if a.json:
            print(json.dumps(analysis["hints"], ensure_ascii=False, indent=2))
        else:
            for h in analysis["hints"]:
                print(f"{h['code']}: {h['message']}")
            if not analysis["hints"]:
                print("Sin avisos" if es else "No hints")
    elif verb == "invest":
        verdict = analysis["invest"]
        if a.json:
            print(json.dumps(verdict, ensure_ascii=False, indent=2))
        else:
            print(("Veredicto: " if es else "Verdict: ") + _VERDICT[lang][verdict["verdict"]])
            for letter, v in verdict["letters"].items():
                print(f"{'✔' if v['ok'] else '✖'} {letter}  {v['reason']}")
    elif not a.accept:
        if a.json:
            print(json.dumps(analysis["tasks"], ensure_ascii=False, indent=2))
        else:
            for t in analysis["tasks"]:
                files = f"  [{', '.join(t['touches'])}]" if t["touches"] else ""
                needs = f"  deps: {', '.join(t['deps'])}" if t["deps"] else ""
                print(f"wave {_wave(t)}  {t['title']}{files}{needs}")
    else:
        if analysis["cycle"]:
            print(("✖ las subtareas se esperan entre sí: " if es else "✖ the subtasks wait on each other: ")
                  + " -> ".join(analysis["cycle"]), file=sys.stderr)
            return 2
        if analysis["duplicates"]:
            print(("✖ dos subtareas tienen la misma clave: " if es else "✖ two subtasks have the same key: ")
                  + ", ".join(analysis["duplicates"]), file=sys.stderr)
            return 2
        saved = stories_save.save(story, title=None, tasks=analysis["tasks"], base_sha=found["sha"], lang=lang,
                                  surface="cli")
        if a.json:
            print(json.dumps(saved, ensure_ascii=False, indent=2, default=str))
        else:
            for r in saved["tasks"]:
                print(f"{r['id']}  {r['title']}")
            print(f"🦐 {len(saved['tasks'])} subtareas en {found['id']}" if es
                  else f"🦐 {len(saved['tasks'])} subtasks in {found['id']}")
    return 0


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
        _show(a, ops.move(args[0], args[1], before=a.before, after=a.after, force=a.force))
    elif x == "next":
        data = ops.next_items(a.n, story=a.story, epic=a.epic)
        if a.json:
            print(json.dumps(data, ensure_ascii=False, indent=2, default=str))
        else:
            lang = _lang(ops)
            for r in data["ready"]:
                print(line(r))
            for w in data["waiting"]:
                print(f"  · {w['id']}: " + "; ".join(note(b, lang) for b in w["blocked_by"]))
            if not data["ready"]:
                print("Nada listo para empezar" if lang == "es" else "Nothing is ready to start")
    elif x == "waves":
        data = ops.waves(story=a.story, epic=a.epic)
        if a.json:
            print(json.dumps(data, ensure_ascii=False, indent=2, default=str))
        elif "cycle" in data:
            lang = _lang(ops)
            print(("✖ ciclo de dependencias: " if lang == "es" else "✖ dependency cycle: ") + " -> ".join(data["cycle"]),
                  file=sys.stderr)
            return 2
        else:
            lang = _lang(ops)
            for n, wave in enumerate(data["waves"], 1):
                print(f"{'Ola' if lang == 'es' else 'Wave'} {n}")
                for r in wave:
                    print("  " + line(r))
    elif x == "story":
        return _story(a, ops)
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
