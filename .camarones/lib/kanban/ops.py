"""Board operations: init, config, add, move, assign, archive, list, show. Every write holds the board lock, changes the
item file and the card in board.yaml together (item first, then the board, each through a temp file + os.replace) and
never commits to git (checkpoint/share do)."""
from __future__ import annotations

import getpass
import json
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

import yaml

from .. import docs
from ..common import IS_MAC, IS_WIN, KIT, ROOT, out, run, which
from ..harness.locks import FileLock
from . import ARCHIVE, BACKLOG, BOARD, CONFIG, DRAFTS, LOCK, PREFIX, PRIORITIES, STATUSES, TASKS, TYPES
from . import deps as graph
from .deps import norm_touch
from .items import (Item, _as_list, checklist, default_dod, description, file_name, load_dir, new_body, parse_item,
                    serialize_item, set_description)
from .items import add_criteria as append_criteria
from .merge import driver_command
from .state import dump_board, id_key, load_board, new_uid, next_id, place, stamp, stamp_time

DRIVER = "camaron-board"
ATTR_LINE = "backlog/board.yaml merge=camaron-board"
_FILE_ID = re.compile(r"^([A-Za-z]+-\d+) - ")


_log = logging.getLogger("camaron.board")

HUMAN = ("cli", "portal", "app")          # surfaces a person drives: a refused start can be forced
AGENT = ("mcp", "harness")                # surfaces an agent drives: a refused start is final


class BoardError(ValueError):
    pass


class GateError(BoardError):
    """A card cannot start: it waits on unfinished work or shares files with an item In Progress. `.blocked_by` holds
    the reasons as `deps.blocked_by` returns them."""

    def __init__(self, item_id: str, blocked_by: list[dict]):
        self.item_id, self.blocked_by = item_id, blocked_by
        super().__init__(f"{item_id} cannot start: " + "; ".join(_why(b) for b in blocked_by))


def _why(b: dict) -> str:
    if b["kind"] == "dependency":
        return f"it waits for {b['id']}, which is not done"
    if b["kind"] == "missing":
        return f"it depends on {b['id']}, which does not exist"
    return f"{b['id']} is in progress on {', '.join(b.get('files', ()))}"


def who() -> str:
    return out(["git", "config", "user.email"], cwd=ROOT) or getpass.getuser()


def launcher() -> list[str]:
    return [which("uv") or "uv", "run", "--quiet", "--script", (KIT / "camarones.py").as_posix()]


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    try:
        with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
        os.replace(tmp, path)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise


def _rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


# --- driver and config ---

def ensure_driver() -> bool:
    """Register the per-card merge driver in this clone's git config and .gitattributes. True if anything changed."""
    changed = False
    if (ROOT / ".git").exists():
        want = {f"merge.{DRIVER}.name": "Camarón board (per card)",
                f"merge.{DRIVER}.driver": driver_command(launcher())}
        for key, value in want.items():
            if out(["git", "config", "--local", "--get", key], cwd=ROOT) != value:
                run(["git", "config", "--local", key, value], cwd=ROOT, check=False, quiet=True)
                changed = True
    f = ROOT / ".gitattributes"
    text = f.read_text(encoding="utf-8") if f.exists() else ""
    if ATTR_LINE not in text.splitlines():
        sep = "" if not text or text.endswith("\n") else "\n"
        _write(f, text + sep + ATTR_LINE + "\n")
        changed = True
    return changed


def _managed_config() -> dict[str, object]:
    ws = docs.workspace()
    lang = ws["project"].get("language") or "en"
    dod = list(default_dod(lang))
    for extra in (ws.get("board") or {}).get("definition_of_done") or []:
        if extra not in dod:
            dod.append(str(extra))
    return {"project_name": ws["project"]["name"], "task_prefix": PREFIX, "statuses": list(STATUSES),
            "types": list(TYPES), "priorities": list(PRIORITIES), "definition_of_done": dod,
            "check_active_branches": False, "auto_commit": False}


def _item(v: object) -> str:
    """A list entry: plain when YAML reads it back as the same text (as Backlog.md writes it), else quoted."""
    s = str(v)
    if re.fullmatch(r"[A-Za-z][A-Za-z0-9 _.-]*", s) and yaml.safe_load(s) == s:
        return s
    return json.dumps(s, ensure_ascii=False)


def _render(key: str, value: object) -> str:
    if isinstance(value, list):
        return f"{key}:\n" + "".join(f"  - {_item(v)}\n" for v in value)
    if isinstance(value, bool):
        return f"{key}: {'true' if value else 'false'}\n"
    return f"{key}: {json.dumps(value, ensure_ascii=False)}\n"


def write_config() -> bool:
    """config.yml with the kit's keys asserted; keys and lines people added are kept. Flat scalars and block lists only
    (Backlog.md reads scalars line by line). True if the file changed."""
    managed = _managed_config()
    old = CONFIG.read_text(encoding="utf-8").replace("\r\n", "\n") if CONFIG.exists() else ""
    blocks: list[tuple[str | None, list[str]]] = []          # (top-level key or None, its lines)
    for line in old.splitlines(keepends=True):
        m = re.match(r"^([A-Za-z_][\w-]*)\s*:", line)
        if m:
            blocks.append((m.group(1), [line]))
        elif blocks and blocks[-1][0] is not None and (line[:1] in (" ", "\t", "-") or not line.strip()):
            blocks[-1][1].append(line)
        else:
            blocks.append((None, [line]))
    seen, parts = set(), []
    for key, lines in blocks:
        if key in managed and key not in seen:
            seen.add(key)
            parts.append(_render(key, managed[key]))
        elif key in managed:
            continue                                         # a duplicated managed key
        else:
            parts.append("".join(lines))
    text = "".join(parts)
    if text and not text.endswith("\n"):
        text += "\n"
    text += "".join(_render(k, v) for k, v in managed.items() if k not in seen)
    if text == old:
        return False
    _write(CONFIG, text)
    return True


def init(log=print) -> list[str]:
    """Create the board layout in cam-docs (idempotent). Returns what it created or changed."""
    done: list[str] = []
    with FileLock(LOCK):
        for d in (TASKS, DRAFTS, ARCHIVE):
            if not d.is_dir():
                d.mkdir(parents=True, exist_ok=True)
                done.append(_rel(d) + "/")
        if not BOARD.exists():
            _write(BOARD, dump_board({}))
            done.append(_rel(BOARD))
        if write_config():
            done.append(_rel(CONFIG))
        if ensure_driver():
            done.append("board merge driver")
    for d in done:
        log(f"  + {d}")
    return done


# --- state (shared with the repair pass: always call under `locked()`) ---

def locked() -> FileLock:
    return FileLock(LOCK)


def load_state() -> tuple[dict[str, dict], dict[str, Item], list[dict]]:
    """(cards from board.yaml, items in tasks/ by id, unreadable files). BoardError if the board is not initialised."""
    if not BOARD.exists():
        raise BoardError("the board is not initialised here (run: camaron board init)")
    try:
        cards = load_board(BOARD.read_text(encoding="utf-8"))
    except ValueError as e:
        raise BoardError(str(e)) from e
    found, problems = load_dir(TASKS)
    return cards, {i.id: i for i in found}, problems


def save_item(item: Item) -> None:
    _write(item.path, serialize_item(item))


def save_board(cards: dict[str, dict]) -> None:
    _write(BOARD, dump_board(cards))


def _all_ids(cards: dict, items: dict, problems: list[dict]) -> list[str]:
    ids = list(cards) + list(items)
    archived, bad = load_dir(ARCHIVE)
    ids += [i.id for i in archived]
    for f in [p["path"] for p in problems] + [p["path"] for p in bad] + list(ARCHIVE.glob("*.md")) + list(TASKS.glob("*.md")):
        m = _FILE_ID.match(f.name)
        if m:
            ids.append(m.group(1).upper())
    return ids


def _find(items: dict[str, Item], cards: dict[str, dict], item_id: str, by: str | None = None) -> tuple[str, Item, dict]:
    """The item and its card, paired by uid (call under the lock). A file without a card (Backlog.md's, a hand-made
    one) is adopted on the spot as the repair pass would; the caller saves the board."""
    key = item_id.strip().upper()
    if key not in items:
        raise BoardError(f"unknown item {item_id}")
    item, card = items[key], cards.get(key)
    if card is None and not any(c["uid"] == item.uid for c in cards.values()):
        from .repair import adopt
        if not item.uid:
            item.fm["x-uid"] = new_uid()
        adopt(item, cards, by=by or who(), now=_now())
        card = cards[key]
    if card is None or item.uid != card["uid"]:
        raise BoardError(f"{key}: its file and its card are not the same item (run: camaron board repair)")
    return key, item, card


def _mirror(item: Item, card: dict) -> None:
    item.fm["status"], item.fm["ordinal"], item.fm["assignee"] = card["status"], card["ordinal"], list(card["assignee"])
    item.fm["updated_date"] = datetime.now().strftime("%Y-%m-%d %H:%M")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _count(verb: str, surface: str) -> None:
    from .. import usage
    usage.record(f"board:{verb}:{surface}")


def _place(cards: dict, items: dict, key: str, status: str, by: str, before=None, after=None) -> None:
    """Put card `key` at the end of (or next to an anchor in) column `status`; neighbours the rebalance moves follow."""
    if before is not None and after is not None:
        raise BoardError("give either before or after, not both")
    column = [(i, c["ordinal"]) for i, c in cards.items() if c["status"] == status and i != key]
    try:
        res = place(column, before=before, after=after)
    except ValueError as e:
        raise BoardError(str(e)) from e
    now = _now()
    for i, n in res.items():
        target = key if i == "*" else i
        if cards[target]["ordinal"] != n or i == "*":
            cards[target]["ordinal"] = n
            stamp(cards[target], "ordinal", by, now)
            if target != key and target in items:
                _mirror(items[target], cards[target])
                save_item(items[target])


# --- writes ---

_PARENTS = {"epic": ("story", "bug", "spike", "task"), "story": ("task",)}     # parent type -> child types


def _parent_of(type_: str, parent: str | None, epic: str | None, items: dict[str, Item]) -> Item | None:
    """The item a new `type_` goes under (`epic` is the old name of `parent`), or None; BoardError if it cannot."""
    ref = (parent or epic or "").strip()
    if parent and epic and parent.strip().upper() != epic.strip().upper():
        raise BoardError(f"parent {parent} and epic {epic} are different items; give one of them")
    if not ref:
        return None
    found = items.get(ref.upper())
    if found is None:
        raise BoardError(f"{ref} is not an item on this board")
    if type_ not in _PARENTS.get(found.type, ()):
        raise BoardError(f"a {type_} cannot go under {found.id}, which is a {found.type}"
                         + (f" (a {found.type} takes: {', '.join(_PARENTS[found.type])})" if found.type in _PARENTS
                            else " (only an epic or a story can have children)"))
    return found


def _touches(refs: Sequence[str]) -> list[str]:
    """Footprint entries as stored: `repo:posix/path`, sorted and unique. Two spellings that differ only in case are one
    entry where the filesystem ignores case (Windows, macOS); the first in sorted order stays."""
    fold = IS_WIN or IS_MAC
    clean = set()
    for ref in refs:
        try:
            touch = norm_touch(str(ref), fold=False)
        except ValueError as e:
            raise BoardError(f'"{ref}" is not a valid touch (use repo:path, inside its repo): {e}') from e
        if not touch.partition(":")[2]:
            raise BoardError(f'"{ref}" is not a valid touch (use repo:path, inside its repo): the path is empty')
        clean.add(touch)
    seen, out_ = set(), []
    for touch in sorted(clean):
        key = norm_touch(touch, fold=fold)
        if key not in seen:
            seen.add(key)
            out_.append(touch)
    return out_


def _known_ids(items: dict[str, Item]) -> set[str]:
    archived, _ = load_dir(ARCHIVE)
    return set(items) | {i.id.upper() for i in archived}


def _existing(refs: Sequence[str], items: dict[str, Item], what: str) -> list[str]:
    """Ids of items that exist (on the board or archived), upper-cased, unique, in natural order."""
    ids = {str(r).strip().upper() for r in refs if str(r).strip()}
    known = _known_ids(items)
    missing = sorted(ids - known, key=id_key)
    if missing:
        raise BoardError(f"{what}: unknown item{'s' if len(missing) > 1 else ''} {', '.join(missing)}")
    return sorted(ids, key=id_key)


def add(type_: str, title: str, *, epic: str | None = None, parent: str | None = None, repos: Sequence[str] = (),
        labels: Sequence[str] = (), priority: str | None = None, docs: Sequence[str] = (),
        description: str | None = None, criteria: Sequence[str] = (), touches: Sequence[str] = (),
        dependencies: Sequence[str] = (), by: str | None = None, surface: str = "cli") -> dict:
    if type_ not in TYPES:
        raise BoardError(f"unknown type {type_} (one of: {', '.join(TYPES)})")
    if priority is not None and priority not in PRIORITIES:
        raise BoardError(f"unknown priority {priority} (one of: {', '.join(PRIORITIES)})")
    if not title.strip():
        raise BoardError("a title is needed")
    foot = _touches(touches)
    by = by or who()
    with FileLock(LOCK):
        cards, items, problems = load_state()
        parent_item = _parent_of(type_, parent, epic, items)
        needs = _existing(dependencies, items, "dependencies")
        from . import xid
        links = _merge_links([], [xid.resolve_ref(r) for r in docs])
        item_id = next_id(_all_ids(cards, items, problems), PREFIX)
        uid = new_uid()
        lang = docs_lang()
        dod = _managed_config()["definition_of_done"]
        in_repos = list(repos) or sorted({t.partition(":")[0] for t in foot} - {"cam-docs"})
        fm = {"id": item_id, "title": title.strip(), "status": "Backlog", "assignee": [],
              "created_date": datetime.now().strftime("%Y-%m-%d %H:%M"),
              "labels": list(labels), "dependencies": needs or None, "documentation": links or None,
              "parent_task_id": parent_item.id if parent_item else None, "priority": priority, "type": type_,
              "ordinal": 0, "x-uid": uid, "x-repos": in_repos or None, "x-touches": foot or None}
        item = Item(fm, new_body(type_, lang, dod, description=description, criteria=criteria),
                    TASKS / file_name(item_id, title))
        card = {"uid": uid, "status": "Backlog", "ordinal": 0, "assignee": [], "t": {}}
        cards[item_id] = card
        stamp(card, "status", by, _now())
        _place(cards, items, item_id, "Backlog", by)
        item.fm["ordinal"] = card["ordinal"]
        save_item(item)                         # the new item first: a failed write leaves its epic as it was
        if parent_item is not None:
            parent_item.fm["subtasks"] = [*_as_list(parent_item.fm.get("subtasks")), item_id]
            save_item(parent_item)
        save_board(cards)
    _count("add", surface)
    return _row(item, card)


def docs_lang() -> str:
    return str(docs.workspace()["project"].get("language") or "en")


def _node(row: dict, archived: bool = False) -> graph.Node:
    """An item as the pure functions of `deps` take it, from its `_row`."""
    touches = set()
    for ref in row["touches"]:
        try:
            touch = norm_touch(ref, fold=False)
        except ValueError:
            continue
        if touch.partition(":")[2]:
            touches.add(touch)
    return {"id": row["id"], "status": row["status"], "priority": row["priority"],
            "parent": str(row["parent"]).strip() if row["parent"] else None, "touches": sorted(touches),
            "repos": row["repos"], "deps": sorted({d.strip() for d in row["dependencies"] if d.strip()}, key=id_key),
            "archived": archived}


def _board_nodes(cards: dict[str, dict], items: dict[str, Item]) -> list[graph.Node]:
    """Every item of the board, open or archived, from the index; if the index cannot be opened, from the files."""
    try:
        from . import index
        conn = index.connect()
        try:
            return index.nodes(conn)
        finally:
            conn.close()
    except Exception as e:                                   # noqa: BLE001 — the gate must never be skipped
        _log.warning("board index unavailable (%s); reading the cards directly", e)
    nodes = [_node(_row(item, cards.get(i))) for i, item in items.items()]
    archived, _ = load_dir(ARCHIVE)
    nodes += [_node(_row(a, None), True) for a in archived if a.id not in items]
    return sorted(nodes, key=lambda n: id_key(n["id"]))


def _gate(key: str, item: Item, card: dict, cards: dict, items: dict, *, agent: bool) -> list[dict]:
    """Why `key` cannot go In Progress now (empty when it can). The card itself is read from its file, not the index."""
    me = _node(_row(item, card))
    board = [n for n in _board_nodes(cards, items) if n["id"] != key] + [me]
    return graph.blocked_by(me, board, agent=agent)


def move(item_id: str, status: str, *, before: str | None = None, after: str | None = None, by: str | None = None,
         surface: str = "cli", force: bool = False) -> dict:
    """Move a card. Entering In Progress is the start gate: a card that waits on unfinished work or shares files with
    an item In Progress is refused (GateError) — a person (`HUMAN`) can `force` it, an agent (`AGENT`) never."""
    if status not in STATUSES:
        raise BoardError(f"unknown status {status} (one of: {', '.join(STATUSES)})")
    by = by or who()
    forced = False
    with FileLock(LOCK):
        cards, items, _ = load_state()
        key, item, card = _find(items, cards, item_id, by)
        if status == "In Progress" and card["status"] != status:
            agent = surface in AGENT
            blocked = _gate(key, item, card, cards, items, agent=agent)
            if blocked and (agent or not force):
                raise GateError(key, blocked)
            forced = bool(blocked)
        if card["status"] != status:
            card["status"] = status
            stamp(card, "status", by, _now())
        _place(cards, items, key, status, by, before, after)
        _mirror(item, card)
        save_item(item)
        save_board(cards)
    _count("move", surface)
    if forced:
        _count("move-forced", surface)
    return _row(item, card)


def assign(item_id: str, who_: str, *, by: str | None = None, surface: str = "cli") -> dict:
    by = by or who()
    with FileLock(LOCK):
        cards, items, _ = load_state()
        key, item, card = _find(items, cards, item_id, by)
        card["assignee"] = [] if who_ == "-" else [who_]
        stamp(card, "assignee", by, _now())
        _mirror(item, card)
        save_item(item)
        save_board(cards)
    return _row(item, card)


def _merge_links(have: list, new: list) -> list[str]:
    """Stored links with `new` added; a link to the same page and section replaces the older one (fresh hash)."""
    from . import xid

    def key(l):
        p = xid.parse_link(l)
        return p["xid"], p["section"]
    out = [str(l) for l in have]
    for link in new:
        out = [l for l in out if key(l) != key(link)] + [link]
    return out


def link(item_id: str, ref: str, *, by: str | None = None, surface: str = "cli") -> dict:
    """Link an item to a doc page or section (`FLOW-k3f9#retries` or `flows/payments.md#retries`)."""
    from . import xid
    with FileLock(LOCK):
        cards, items, _ = load_state()
        key, item, card = _find(items, cards, item_id, by)
        stored = xid.resolve_ref(ref)
        item.fm["documentation"] = _merge_links(_as_list(item.fm.get("documentation")), [stored])
        _mirror(item, card)
        save_item(item)
        save_board(cards)                       # the card _find may have just adopted
    return _row(item, card)


def update_item(item_id: str, *, title: str | None = None, description: str | None = None,
                add_criteria: Sequence[str] = (), touches: Sequence[str] | None = None, docs: Sequence[str] = (),
                subtasks: Sequence[str] | None = None, by: str | None = None, surface: str = "cli") -> dict:
    """Change what is given and nothing else. Criteria are appended after the existing ones (never renumbered); the
    description, the touches (`[]` clears them) and the subtasks are replaced; docs are linked as `link` does."""
    from . import xid
    if title is not None and not title.strip():
        raise BoardError("a title is needed")
    foot = None if touches is None else _touches(touches)
    stored = [xid.resolve_ref(r) for r in docs]
    by = by or who()
    with FileLock(LOCK):
        cards, items, _ = load_state()
        key, item, card = _find(items, cards, item_id, by)
        subs = None if subtasks is None else _existing(subtasks, items, "subtasks")
        if title is not None:
            item.fm["title"] = title.strip()
            _rename(item, TASKS / file_name(item.id, item.title))
        if description is not None:
            item.body = set_description(item.body, description)
        item.body = append_criteria(item.body, add_criteria)
        if foot is not None:
            item.fm["x-touches"] = foot or None
        if stored:
            item.fm["documentation"] = _merge_links(_as_list(item.fm.get("documentation")), stored)
        if subs is not None:
            item.fm["subtasks"] = subs or None
        _mirror(item, card)
        save_item(item)
        save_board(cards)                       # the card _find may have just adopted
    _count("update", surface)
    return _row(item, card)


def _rename(item: Item, new_path: Path) -> None:
    """Move the item's file to `new_path` before anything is written to it, and only when the name changes. Never an
    unlink: on a filesystem that ignores case (macOS, Windows) "a.md" and "A.md" are one file, and deleting the old
    name after writing the new one would delete the only copy."""
    old_path = item.path
    if new_path.name == old_path.name:
        return
    if old_path.exists():
        os.replace(old_path, new_path)          # a case-only change renames the one file in place
    item.path = new_path


def archive(item_id: str, *, by: str | None = None, surface: str = "cli") -> dict:
    with FileLock(LOCK):
        cards, items, _ = load_state()
        key, item, card = _find(items, cards, item_id, by)
        row = _row(item, card)
        ARCHIVE.mkdir(parents=True, exist_ok=True)
        os.replace(item.path, ARCHIVE / item.path.name)
        del cards[key]
        save_board(cards)
    return row


# --- reads ---

def _row(item: Item, card: dict | None) -> dict:
    fm = item.fm
    texts = lambda v: [str(x) for x in _as_list(v)]          # noqa: E731  (a hand-written `labels: pay` is one label)
    card = card or {"uid": item.uid, "status": fm.get("status") or STATUSES[0], "ordinal": fm.get("ordinal") or 0,
                    "assignee": texts(fm.get("assignee")), "t": {}}
    return {"id": item.id, "uid": card["uid"], "title": item.title, "type": item.type, "status": card["status"],
            "ordinal": card["ordinal"], "assignee": list(card["assignee"]), "labels": texts(fm.get("labels")),
            "priority": fm.get("priority"), "epic": fm.get("parent_task_id"), "parent": fm.get("parent_task_id"),
            "repos": texts(fm.get("x-repos")), "docs": [str(d) for d in _as_list(fm.get("documentation"))],
            "touches": texts(fm.get("x-touches")), "dependencies": texts(fm.get("dependencies"))}


_DOC_STATES = ("unconfirmed", "suspect", "stale", "changed", "missing")


def _in_state(st: dict, want: str) -> bool:
    if want == "unconfirmed":
        return st["trust"] != "confirmed"           # a missing or unreadable link is not confirmed either (R15)
    if want == "suspect":
        return st["fresh"] in ("suspect", "stale")   # as the Board view's filter (kanban.js)
    return bool(st["changed"] if want == "changed" else st["missing"] if want == "missing" else st["fresh"] == want)


def _linked(d: str, ids: dict) -> bool:
    from . import xid
    try:
        return xid.parse_link(d)["xid"] in ids
    except BoardError:
        return False


def link_states(links: list[str]) -> list[list[dict]]:
    """The state of each link in each list, with the index and the linked pages read once."""
    if not any(links):
        return [[] for _ in links]
    from . import xid
    ids = xid.index()
    want = {ids[xid.parse_link(d)["xid"]] for ds in links for d in ds if _linked(d, ids)}   # only pages some item links
    pages = xid.page_rows(want) if want else {}
    return [[xid.link_state(d, pages, ids) for d in ds] for ds in links]


def list_items(*, status=None, epic=None, parent=None, repo=None, label=None, docs=None, with_links=False) -> dict:
    """Cards in board order. `with_links` adds each card's link states (the portal's Board filters on them)."""
    cards, items, problems = load_state()
    rows = []
    state = docs in _DOC_STATES or with_links
    if state:
        everything = list(items.values())
        states = dict(zip((i.id for i in everything),
                          link_states([[str(d) for d in _as_list(i.fm.get("documentation"))] for i in everything])))
    for i, item in items.items():
        r = _row(item, cards.get(i))
        if status and r["status"] != status:
            continue
        if epic and (r["epic"] or "").upper() != epic.upper():
            continue
        if parent and (r["parent"] or "").upper() != parent.upper():
            continue
        if repo and repo not in r["repos"]:
            continue
        if label and label not in r["labels"]:
            continue
        if docs in _DOC_STATES:
            if not any(_in_state(st, docs) for st in states[i]):
                continue
        elif docs and not any(re.split(r"[#@]", d, maxsplit=1)[0] == docs for d in r["docs"]):
            continue
        if with_links:
            r["links"] = states[i]
        rows.append(r)
    from .state import id_key
    order = {s: n for n, s in enumerate(STATUSES)}
    rows.sort(key=lambda r: (order.get(r["status"], len(order)), r["ordinal"], id_key(r["id"])))
    return {"cards": rows, "problems": [{**p, "path": _rel(p["path"])} for p in problems]}   # text: JSON-ready


def _scope(rows: dict[str, dict], story: str | None, epic: str | None) -> set[str] | None:
    """Ids under a story (it and its children) or an epic (it, its children and theirs); None when no scope is given."""
    if story and epic:
        raise BoardError("give either a story or an epic, not both")
    root = story or epic
    if not root:
        return None
    key = root.strip().upper()
    if key not in rows:
        raise BoardError(f"unknown item {root}")
    ids = {key}
    frontier = {key}
    for _ in range(1 if story else 2):
        frontier = {i for i, r in rows.items() if (r["parent"] or "").upper() in frontier} - ids
        ids |= frontier
    return ids


def next_items(n: int = 3, *, story: str | None = None, epic: str | None = None, agent: bool = True) -> dict:
    """What can start now: `ready` (at most `n`, by wave, then priority, then id; each row has its 0-based `wave`) and
    `waiting` (every Backlog/Ready item that cannot start, with why). Limited to a story's or an epic's items if given.
    Conflicts are always judged against the whole board."""
    cards, items, _ = load_state()
    rows = {i: _row(item, cards.get(i)) for i, item in items.items()}
    scope = _scope(rows, story, epic)
    board = _board_nodes(cards, items)
    grouping = graph.containers(board)                  # stories and epics with children: their tasks are the work
    mine = [x for x in board if (scope is None or x["id"] in scope) and x["id"] in rows and x["id"] not in grouping]
    free, waiting = [], []
    for x in mine:
        if x["status"] not in ("Backlog", "Ready") or x["archived"]:
            continue
        why = graph.blocked_by(x, board, agent=agent)
        if why:
            waiting.append({"id": x["id"], "blocked_by": why})
        else:
            free.append({**x, "deps": []})              # its dependencies are Done: only file clashes separate waves
    ready = [{**rows[i], "wave": w} for w, wave in enumerate(graph.waves(free)) for i in wave]
    return {"ready": ready[:max(n, 0)], "waiting": waiting}


def waves(*, story: str | None = None, epic: str | None = None) -> dict:
    """The open work (not Done, not archived) in waves of items that can run in parallel: `{"waves": [[row…]…]}`, or
    `{"cycle": [ids]}` when items wait on each other."""
    cards, items, _ = load_state()
    rows = {i: _row(item, cards.get(i)) for i, item in items.items()}
    scope = _scope(rows, story, epic)
    board = _board_nodes(cards, items)
    grouping = graph.containers(board)                  # judged on the whole board: done children still group
    open_ = [x for x in board if x["id"] in rows and x["id"] not in grouping
             and (scope is None or x["id"] in scope) and x["status"] != "Done"]
    try:
        grouped = graph.waves(open_)
    except graph.CycleError as e:
        return {"cycle": e.cycle}
    return {"waves": [[rows[i] for i in wave] for wave in grouped]}


def _history(card: dict | None, path: Path) -> list[dict]:
    events = []
    for field, raw in ((card or {}).get("t") or {}).items():
        at, _, by = raw.partition(" ")
        events.append({"at": stamp_time(raw).isoformat(), "by": by, "what": field, "source": "board", "_k": stamp_time(raw)})
    log = out(["git", "log", "--format=%h%x00%an%x00%cI%x00%s", "--", str(path)], cwd=ROOT)
    for line in log.splitlines():
        h, an, ci, subject = (line.split("\x00") + ["", "", "", ""])[:4]
        try:
            k = datetime.fromisoformat(ci)
        except ValueError:
            continue
        events.append({"at": ci, "by": an, "what": subject, "source": "git", "hash": h, "_k": k})
    events.sort(key=lambda e: e["_k"])
    for e in events:
        del e["_k"]
    return events


def show(item_id: str) -> dict:
    cards, items, _ = load_state()
    key = item_id.strip().upper()
    if key not in items:
        raise BoardError(f"unknown item {item_id}")
    item = items[key]
    row = _row(item, cards.get(key))
    [links] = link_states([row["docs"]])
    return {**row, "links": links, "description": description(item.body),
            "criteria": checklist(item.body, "AC"), "dod": checklist(item.body, "DOD"),
            "history": _history(cards.get(key), item.path), "file": _rel(item.path)}
