"""Saving a story and its approved subtasks to the board, and reading stories back (spec §4.6).

`save` checks everything before it writes anything (the clauses, the epic, the tasks' titles, footprints and
dependencies, the story's fingerprint against what is on disk), then writes under one hold of the board lock: the story
first when it is new (its subtasks need its id), the subtasks in dependency order, and the story's own changes last when
it already exists. A crash in the middle leaves a valid board: a story with fewer subtasks than approved, or subtasks
whose parent has not changed its text yet; `ops.add(parent=…)` lists each subtask on its parent as it is written and the
repair pass puts back any missing entry. `list_stories` and `item` are the left list and the opened story of the story
wizard; both are recomputed from the board on every call, nothing is stored."""
from __future__ import annotations

import re
from typing import Sequence

from . import docs as docs_mod
from .common import IS_WIN, ROOT, repo_dir
from .harness.locks import FileLock
from .kanban import LOCK, PRIORITIES, deps, index, ops
from .kanban.items import checklist, description
from .kanban.ops import BoardError
from .kanban.state import id_key
from .stories import (Proposal, Story, TASK_TITLE_MAX, _clean, _code_groups, _done, _lang, _node, _touches,
                      compose, fingerprint, invest, parse, title_for)

_WIN_BAD = re.compile(r'[<>:"|?*]')

__all__ = ["BoardError", "StoryConflict", "save", "list_stories", "item"]


class StoryConflict(BoardError):
    """The story's text on disk is not the one the person started from (409). The UI translates the message."""

    def __init__(self, story_id: str):
        self.story_id = story_id
        super().__init__(f"{story_id} changed while you were editing it: reload it")


# ── validation ───────────────────────────────────────────────────────────────────────────────────────────────────

def _check_touches(refs: Sequence[str], conn, what: str) -> list[str]:
    """Every entry must be a file of a known repo (or doc page) that exists, or one the task will create: then its folder
    exists. A folder, a path outside its repo and a code-map group label (`repo:<group>`) are refused."""
    known = set(docs_mod.repo_names()) | {index.DOCS_REPO}
    out: set[str] = set()
    for ref in refs or ():
        try:
            touch = deps.norm_touch(str(ref), fold=False)
        except ValueError as e:
            raise BoardError(f"{what}: {e}") from e
        repo, _, path = touch.partition(":")
        bad = lambda why: BoardError(f'{what}: "{ref}" is not a valid touch ({why})')        # noqa: E731
        if repo not in known:
            raise bad(f"{repo} is not a repo of this project")
        if not path.strip("/") or path.startswith("/") or ":" in path:
            raise bad("use repo:path with a path inside the repo")
        if any(ord(c) < 32 or c == "" for c in path):
            raise bad("it has control characters")
        base = ROOT if repo == index.DOCS_REPO else repo_dir(repo)
        target = base / path
        try:
            target.resolve().relative_to(base.resolve())
        except ValueError:
            raise bad("the path leaves its repo") from None
        except OSError as e:
            raise bad(f"the file system refuses it: {e.strerror or e}") from None
        try:
            if target.is_file():
                out.add(touch)
                continue
            if target.exists():
                raise bad("it is a folder, not a file")
            folder = target.parent.is_dir()
        except (OSError, ValueError) as e:
            raise bad(f"the file system refuses it: {e}") from None
        if not folder:
            raise bad("the file does not exist and neither does its folder")
        if IS_WIN and _WIN_BAD.search(path):
            raise bad('Windows does not allow < > : " | ? * in a file name')
        if repo != index.DOCS_REPO and conn.execute(
                "select 1 from files where repo = ? and grp = ? limit 1", (repo, path)).fetchone():
            raise bad("it is a group of the code map, not a file: pick its files")
        out.add(touch)
    return sorted(out)


def _check_docs(refs: Sequence[str]) -> None:
    """Every reference resolves as `xid.resolve_ref` will resolve it (the page exists and so does the `#section`), but
    nothing is written: linking stamps a page's x-id, which `ops` does when it writes."""
    if not refs:
        return
    from .kanban import xid
    ids, pages = xid.index(), xid._pages()
    for ref in refs:
        link = xid.parse_link(ref)
        logical = ids.get(link["xid"]) or (link["xid"] if link["xid"] in pages else None)
        if logical is None:
            raise BoardError(f"unknown page {link['xid']} (use an x-id or a path like flows/payments.md)")
        xid._section(xid._body(logical), link["section"])


def _tasks_checked(tasks: Sequence[Proposal], items: dict, conn) -> list[dict]:
    """The tasks as `{key, title, touches, criteria, refs}`, in the caller's order, after the per-task checks."""
    out: list[dict] = []
    keys: set[str] = set()
    titles: set[str] = set()
    for t in tasks:
        key = str(t.get("key") or "").strip()
        title = _clean(str(t.get("title") or ""))
        if not key:
            raise BoardError("every subtask needs a key")
        if key in keys:
            raise BoardError(f"two subtasks have the same key {key}")
        if not title:
            raise BoardError(f"the subtask {key} needs a title")
        if len(title) > TASK_TITLE_MAX:
            raise BoardError(f'the title of subtask {key} is over {TASK_TITLE_MAX} characters')
        if title.casefold() in titles:
            raise BoardError(f'two subtasks are called "{title}": give each its own title')
        keys.add(key)
        titles.add(title.casefold())
        refs = [str(r).strip() for r in t.get("deps") or () if str(r).strip()]
        out.append({"key": key, "title": title, "refs": refs, "criteria": [str(c) for c in t.get("criteria") or ()],
                    "touches": _check_touches(t.get("touches") or [], conn, f"subtask {key}")})
    known = ops._known_ids(items)
    for t in out:
        mapped: list[str] = []
        for ref in t["refs"]:
            if ref in keys:
                if ref == t["key"]:
                    raise BoardError(f"the subtask {ref} depends on itself")
                mapped.append(ref)
            elif ref.upper() in known:
                mapped.append(ref.upper())
            elif ":" in ref:
                raise BoardError(f"the subtask {t['key']} depends on {ref}, which is not one of the subtasks being saved")
            else:
                raise BoardError(f"the subtask {t['key']} depends on {ref}, which is not an item on this board")
        t["deps"] = list(dict.fromkeys(mapped))
    return out


def _in_order(tasks: list[dict]) -> list[dict]:
    """The tasks in the caller's order, except that one waits for the tasks it depends on (they need their ids first)."""
    todo, done, ordered = list(tasks), set(), []
    keys = {t["key"] for t in tasks}
    while todo:
        ready = next((t for t in todo if all(d in done for d in t["deps"] if d in keys)), None)
        if ready is None:                                    # a cycle; the caller checked, but never loop for ever
            raise BoardError("the subtasks wait on each other: " + ", ".join(t["key"] for t in todo))
        todo.remove(ready)
        done.add(ready["key"])
        ordered.append(ready)
    return ordered


def _refuse_loops(tasks: list[dict]) -> None:
    """A cycle among the dependencies that will be stored is refused. Only those count: a cycle the code order proposed
    and the person broke by dropping a dependency is gone (spec §4.5). `_tasks_checked` already refused duplicate keys."""
    keys = {t["key"] for t in tasks}
    cycles = deps.sccs({t["key"]: [d for d in t["deps"] if d in keys] for t in tasks})
    if cycles:
        raise BoardError("the subtasks wait on each other: " + " -> ".join(cycles[0]))


def _norm_set(refs) -> list[str]:
    out = set()
    for ref in refs or ():
        try:
            out.add(deps.norm_touch(str(ref), fold=False))
        except ValueError:
            out.add(str(ref).strip())                     # compared as given: a bad entry is still a difference
    return sorted(out)


def _unchanged_or_mine(sid: str, existing, title: str | None, footprint: list[str], base_title: str | None,
                       base_touches: Sequence[str] | None) -> tuple[str | None, list[str] | None]:
    """(title, touches) to write on an existing story: None for a field the person did not change against its base (the
    disk value stays, whoever changed it), the person's value for one they changed. A field they changed whose disk
    value is no longer its base is a `StoryConflict`. Without a base, the field is written as given (older callers)."""
    if base_title is not None:
        mine = title is not None and _clean(title) != _clean(base_title)
        if mine and _clean(existing.title) != _clean(base_title):
            raise StoryConflict(sid)
        title = title if mine else None
    touches: list[str] | None = footprint
    if base_touches is not None:
        base = _norm_set(base_touches)
        mine = _norm_set(footprint) != base
        if mine and _norm_set(ops._as_list(existing.fm.get("x-touches"))) != base:
            raise StoryConflict(sid)
        touches = footprint if mine else None
    return title, touches


# ── save ─────────────────────────────────────────────────────────────────────────────────────────────────────────

def save(story: Story, *, title: str | None, tasks: Sequence[Proposal], base_sha: str | None, docs: Sequence[str] = (),
         lang: str, by: str | None = None, surface: str = "cli", base_title: str | None = None,
         base_touches: Sequence[str] | None = None) -> dict:
    """Write the story (new when `story["id"]` is empty) and its approved subtasks. `title` None keeps an existing
    story's title and makes a new one from the want. `base_sha` is the fingerprint `item()` gave when the person opened
    the story: if the clauses on disk have changed since and are not the ones being saved, `StoryConflict`. An existing
    story's text becomes the new clauses followed by the notes it already had; criteria it does not have yet are appended
    (existing ones keep their numbers); its footprint is replaced by `story["touches"]`; its epic is not moved here.
    `base_title` and `base_touches` are the title and footprint as the person loaded them: when given, an existing
    story's field is written only if the person changed it, so a change someone else made meanwhile is not reverted;
    a field both changed is a `StoryConflict`.
    Dependencies of a subtask are keys of the subtasks in this call or ids of items on the board. Returns
    `{"story": row, "tasks": [row…]}`, the rows in the order of `tasks`. Any problem is a `BoardError` and nothing is
    written."""
    lang = _lang(lang)
    as_, want, so = (_clean(str(story.get(k) or "")) for k in ("as_", "want", "so"))
    if not (as_ and want and so):
        raise BoardError("the story needs all three parts: who, what and why")
    sid = (story.get("id") or "").strip().upper()
    epic = (story.get("epic") or "").strip().upper()
    priority = story.get("priority") or None
    if title is not None and not title.strip():
        raise BoardError("a title is needed")
    by = by or ops.who()
    with FileLock(LOCK):
        cards, items, _ = ops.load_state()
        existing = None
        if sid:
            existing = items.get(sid)
            if existing is None:
                raise BoardError(f"unknown item {story.get('id')}")
            if existing.type != "story":
                raise BoardError(f"{sid} is a {existing.type or 'item'}, not a story")
            if epic and epic != str(existing.fm.get("parent_task_id") or "").strip().upper():
                raise BoardError(f"{sid} cannot be moved to {epic} while it is saved: change its epic on the board")
        elif epic:
            parent = items.get(epic)
            if parent is None or parent.type != "epic":
                raise BoardError(f"{epic} is not an epic on this board")
        if priority is not None and priority not in PRIORITIES:
            raise BoardError(f"unknown priority {priority} (one of: {', '.join(PRIORITIES)})")
        _check_docs(docs)
        conn = index.connect()
        try:
            footprint = _check_touches(story.get("touches") or [], conn, "the story")
            checked = _tasks_checked(tasks, items, conn)
        finally:
            conn.close()
        _refuse_loops(checked)

        notes, footprint_out = "", footprint
        if existing is not None:
            current = parse(description(existing.body), lang)
            before = fingerprint(current["as_"], current["want"], current["so"])
            if before != base_sha and before != fingerprint(as_, want, so):
                raise StoryConflict(sid)
            notes = current["rest"]
            title, footprint_out = _unchanged_or_mine(sid, existing, title, footprint, base_title, base_touches)
        text = compose(as_, want, so, lang) + ("\n\n" + notes if notes else "")
        have = {" ".join(c["text"].split()).casefold() for c in checklist(existing.body, "AC")} if existing else set()
        criteria: list[str] = []
        for c in story.get("criteria") or []:
            one = _clean(str(c))
            if one and one.casefold() not in have:
                have.add(one.casefold())
                criteria.append(one)

        # all checked: from here on, writes only
        if existing is None:
            head = ops.add("story", (title or "").strip() or title_for(want), parent=epic or None, priority=priority,
                           docs=docs, description=text, criteria=criteria, touches=footprint, by=by, surface=surface)
            sid = head["id"]
        ids: dict[str, str] = {}
        rows: dict[str, dict] = {}
        # a subtask without files counts as touching the story's repos (for agents), as the screen says
        story_repos = sorted({f.partition(":")[0] for f in footprint} - {index.DOCS_REPO}) or (
            [str(r) for r in ops._as_list(existing.fm.get("x-repos"))] if existing is not None else [])
        for t in _in_order(checked):
            rows[t["key"]] = ops.add("task", t["title"], parent=sid, description=t["title"], criteria=t["criteria"],
                                     touches=t["touches"], dependencies=[ids.get(d, d) for d in t["deps"]], by=by,
                                     repos=() if t["touches"] else story_repos, surface=surface)
            ids[t["key"]] = rows[t["key"]]["id"]
        if existing is not None:
            retitle = title.strip() if title is not None and title.strip() != existing.title else None
            head = ops.update_item(sid, title=retitle, description=text, add_criteria=criteria, touches=footprint_out,
                                   docs=docs, by=by, surface=surface)
    return {"story": head, "tasks": [rows[t["key"]] for t in checked]}


# ── reading ──────────────────────────────────────────────────────────────────────────────────────────────────────

def _story_input(item, node: deps.Node, lang: str) -> Story:
    clauses = parse(description(item.body), lang)
    return {"id": item.id, "as_": clauses["as_"], "want": clauses["want"], "so": clauses["so"],
            "criteria": [c["text"] for c in checklist(item.body, "AC")], "touches": node["touches"],
            "epic": item.fm.get("parent_task_id"), "priority": item.fm.get("priority")}


def list_stories() -> list[dict]:
    """Every story not archived, by id: `{id, title, verdict, progress: {done, total}, conflicts: [ids]}`. The verdict
    is recomputed with `invest`; `progress` counts the story's subtasks (archived ones are done); `conflicts` are the
    other open stories that share a file with it (none for a story that is Done)."""
    lang = _lang(ops.docs_lang())
    _, items, _ = ops.load_state()
    conn = index.connect()
    try:
        board = index.nodes(conn)
        kinds = index.types(conn, [n["id"] for n in board])
        stories = [n for n in board if kinds.get(n["id"]) == "story"]
        grouped = index.groups(conn, [f for n in stories for f in n["touches"]])
    finally:
        conn.close()
    children: dict[str, list[deps.Node]] = {}
    for n in board:
        children.setdefault((n.get("parent") or "").strip().upper(), []).append(n)
    near = _code_groups(grouped)
    out = []
    for n in stories:
        item = items.get(n["id"])
        if item is None or n["archived"]:
            continue
        touches = _touches(n["touches"])
        verdict = invest(_story_input(item, n, lang), stories, groups=grouped, lang=lang)["verdict"]
        clash = [] if _done(n) else [c["id"] for c in deps.conflicts(_node(n["id"], touches), stories, groups=near)
                                     if c["kind"] == "conflict"]
        kids = children.get(n["id"], [])
        out.append({"id": n["id"], "title": item.title, "verdict": verdict,
                    "progress": {"done": sum(1 for k in kids if _done(k)), "total": len(kids)}, "conflicts": clash})
    return sorted(out, key=lambda r: id_key(r["id"]))


def _doc_sources(refs: Sequence[str]) -> list[str]:
    """The files the linked doc pages cite (`x-sources`) as `repo:path`: only files of a known repo that exist, sorted,
    once each. A link that no longer resolves, or a page that cannot be read, gives nothing (the screen only reads)."""
    from .kanban import xid
    if not refs:
        return []
    ids, pages = xid.index(), xid._pages()
    known = set(docs_mod.repo_names()) | {index.DOCS_REPO}
    out: set[str] = set()
    for ref in refs:
        try:
            link = xid.parse_link(ref)
        except BoardError:
            continue
        f = pages.get(ids.get(link["xid"]) or link["xid"])
        if f is None:
            continue
        try:
            fm = docs_mod.parse_fm(f.read_text(encoding="utf-8"))[0]
        except (OSError, UnicodeDecodeError, ValueError):
            continue
        raw = fm.get("x-sources") or []
        for src in (s for s in map(index._source, raw if isinstance(raw, list) else [raw]) if s):
            repo, path = src
            if repo not in known:
                continue
            base = ROOT if repo == index.DOCS_REPO else repo_dir(repo)
            try:
                if (base / path).is_file():
                    out.add(f"{repo}:{path}")
            except OSError:
                continue
    return sorted(out)


def item(story_id: str) -> dict:
    """A story as the wizard opens it: its clauses parsed from the description (`rest` is the text after them), its
    criteria, footprint, epic, priority and linked pages (and the files those pages cite, `doc_sources`), its subtasks
    (rows with their `wave`, 0-based among the open ones, -1 for a Done one or while they wait on each other) and
    `sha`, the fingerprint to hand back to `save`."""
    lang = _lang(ops.docs_lang())
    cards, items, _ = ops.load_state()
    key = (story_id or "").strip().upper()
    found = items.get(key)
    if found is None:
        raise BoardError(f"unknown item {story_id}")
    if found.type != "story":
        raise BoardError(f"{key} is a {found.type or 'item'}, not a story")
    clauses = parse(description(found.body), lang)
    row = ops._row(found, cards.get(key))
    placed = ops.waves(story=key)
    wave = {r["id"]: n for n, group in enumerate(placed.get("waves", [])) for r in group}
    kids = [i for i in items.values() if str(i.fm.get("parent_task_id") or "").strip().upper() == key]
    listed = [str(s).strip().upper() for s in ops._as_list(found.fm.get("subtasks"))]
    kids.sort(key=lambda i: (listed.index(i.id) if i.id in listed else len(listed), id_key(i.id)))
    return {"id": key, "title": found.title, "as_": clauses["as_"], "want": clauses["want"], "so": clauses["so"],
            "rest": clauses["rest"], "criteria": [c["text"] for c in checklist(found.body, "AC")],
            "touches": row["touches"], "epic": row["epic"], "priority": row["priority"], "docs": row["docs"],
            "subtasks": [{**ops._row(k, cards.get(k.id)), "wave": wave.get(k.id, -1)} for k in kids],
            "sha": fingerprint(clauses["as_"], clauses["want"], clauses["so"]), "doc_sources": _doc_sources(row["docs"])}
