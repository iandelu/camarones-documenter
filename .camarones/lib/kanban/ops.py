"""Board operations: init, config, add, move, assign, archive, list, show. Every write holds the board lock, changes the
item file and the card in board.yaml together (item first, then the board, each through a temp file + os.replace) and
never commits to git (checkpoint/share do)."""
from __future__ import annotations

import getpass
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

import yaml

from .. import docs
from ..common import KIT, ROOT, out, run, which
from ..harness.locks import FileLock
from . import ARCHIVE, BACKLOG, BOARD, CONFIG, DRAFTS, LOCK, PREFIX, PRIORITIES, STATUSES, TASKS, TYPES
from .items import Item, checklist, default_dod, description, file_name, load_dir, new_body, parse_item, serialize_item
from .merge import driver_command
from .state import dump_board, load_board, new_uid, next_id, place, stamp, stamp_time

DRIVER = "camaron-board"
ATTR_LINE = "backlog/board.yaml merge=camaron-board"
_FILE_ID = re.compile(r"^([A-Za-z]+-\d+) - ")


class BoardError(ValueError):
    pass


def who() -> str:
    return out(["git", "config", "user.email"], cwd=ROOT) or getpass.getuser()


def launcher() -> list[str]:
    return [which("uv") or "uv", "run", "--quiet", "--script", (KIT / "camarones.py").as_posix()]


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    os.replace(tmp, path)


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


def _find(items: dict[str, Item], cards: dict[str, dict], item_id: str) -> tuple[str, Item, dict]:
    key = item_id.strip().upper()
    if key not in items or key not in cards:
        raise BoardError(f"unknown item {item_id}")
    return key, items[key], cards[key]


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

def add(type_: str, title: str, *, epic: str | None = None, repos: Sequence[str] = (), labels: Sequence[str] = (),
        priority: str | None = None, docs: Sequence[str] = (), by: str | None = None, surface: str = "cli") -> dict:
    if type_ not in TYPES:
        raise BoardError(f"unknown type {type_} (one of: {', '.join(TYPES)})")
    if priority is not None and priority not in PRIORITIES:
        raise BoardError(f"unknown priority {priority} (one of: {', '.join(PRIORITIES)})")
    if not title.strip():
        raise BoardError("a title is needed")
    by = by or who()
    with FileLock(LOCK):
        cards, items, problems = load_state()
        parent = None
        if epic:
            ekey = epic.strip().upper()
            parent = items.get(ekey)
            if parent is None or parent.type != "epic":
                raise BoardError(f"{epic} is not an epic on this board")
        from . import xid
        links = _merge_links([], [xid.resolve_ref(r) for r in docs])
        item_id = next_id(_all_ids(cards, items, problems), PREFIX)
        uid = new_uid()
        lang = docs_lang()
        dod = _managed_config()["definition_of_done"]
        fm = {"id": item_id, "title": title.strip(), "status": "Backlog", "assignee": [],
              "created_date": datetime.now().strftime("%Y-%m-%d %H:%M"),
              "labels": list(labels), "documentation": links or None,
              "parent_task_id": parent.id if parent else None, "priority": priority, "type": type_,
              "ordinal": 0, "x-uid": uid, "x-repos": list(repos) or None}
        item = Item(fm, new_body(type_, lang, dod), TASKS / file_name(item_id, title))
        card = {"uid": uid, "status": "Backlog", "ordinal": 0, "assignee": [], "t": {}}
        cards[item_id] = card
        stamp(card, "status", by, _now())
        _place(cards, items, item_id, "Backlog", by)
        item.fm["ordinal"] = card["ordinal"]
        if parent is not None:
            parent.fm["subtasks"] = [*(parent.fm.get("subtasks") or []), item_id]
            save_item(parent)
        save_item(item)
        save_board(cards)
    _count("add", surface)
    return _row(item, card)


def docs_lang() -> str:
    return str(docs.workspace()["project"].get("language") or "en")


def move(item_id: str, status: str, *, before: str | None = None, after: str | None = None, by: str | None = None,
         surface: str = "cli") -> dict:
    if status not in STATUSES:
        raise BoardError(f"unknown status {status} (one of: {', '.join(STATUSES)})")
    by = by or who()
    with FileLock(LOCK):
        cards, items, _ = load_state()
        key, item, card = _find(items, cards, item_id)
        if card["status"] != status:
            card["status"] = status
            stamp(card, "status", by, _now())
        _place(cards, items, key, status, by, before, after)
        _mirror(item, card)
        save_item(item)
        save_board(cards)
    _count("move", surface)
    return _row(item, card)


def assign(item_id: str, who_: str, *, by: str | None = None, surface: str = "cli") -> dict:
    by = by or who()
    with FileLock(LOCK):
        cards, items, _ = load_state()
        key, item, card = _find(items, cards, item_id)
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
    from .repair import _as_list
    with FileLock(LOCK):
        cards, items, _ = load_state()
        key, item, card = _find(items, cards, item_id)
        stored = xid.resolve_ref(ref)
        item.fm["documentation"] = _merge_links(_as_list(item.fm.get("documentation")), [stored])
        _mirror(item, card)
        save_item(item)
    return _row(item, card)


def archive(item_id: str, *, by: str | None = None, surface: str = "cli") -> dict:
    with FileLock(LOCK):
        cards, items, _ = load_state()
        key, item, card = _find(items, cards, item_id)
        row = _row(item, card)
        ARCHIVE.mkdir(parents=True, exist_ok=True)
        os.replace(item.path, ARCHIVE / item.path.name)
        del cards[key]
        save_board(cards)
    return row


# --- reads ---

def _row(item: Item, card: dict | None) -> dict:
    fm = item.fm
    card = card or {"uid": item.uid, "status": fm.get("status") or STATUSES[0], "ordinal": fm.get("ordinal") or 0,
                    "assignee": fm.get("assignee") or [], "t": {}}
    return {"id": item.id, "uid": card["uid"], "title": item.title, "type": item.type, "status": card["status"],
            "ordinal": card["ordinal"], "assignee": list(card["assignee"]), "labels": list(fm.get("labels") or []),
            "priority": fm.get("priority"), "epic": fm.get("parent_task_id"), "repos": list(fm.get("x-repos") or []),
            "docs": list(fm.get("documentation") or [])}


_DOC_STATES = ("unconfirmed", "suspect", "stale", "changed", "missing")


def _in_state(st: dict, want: str) -> bool:
    if want == "unconfirmed":
        return st["trust"] is not None and st["trust"] != "confirmed"
    return bool(st["changed"] if want == "changed" else st["missing"] if want == "missing" else st["fresh"] == want)


def _linked(d: str, ids: dict) -> bool:
    from . import xid
    try:
        return xid.parse_link(d)["xid"] in ids
    except BoardError:
        return False


def list_items(*, status=None, epic=None, repo=None, label=None, docs=None) -> dict:
    cards, items, problems = load_state()
    rows = []
    state = docs in _DOC_STATES
    if state:
        from . import xid
        from .repair import _as_list
        ids = xid.index()
        want = {ids[xid.parse_link(d)["xid"]] for it in items.values()          # only the pages some item links
                for d in map(str, _as_list(it.fm.get("documentation"))) if _linked(d, ids)}
        pages = xid.page_rows(want) if want else {}
    for i, item in items.items():
        r = _row(item, cards.get(i))
        if status and r["status"] != status:
            continue
        if epic and (r["epic"] or "").upper() != epic.upper():
            continue
        if repo and repo not in r["repos"]:
            continue
        if label and label not in r["labels"]:
            continue
        if docs and state:
            if not any(_in_state(xid.link_state(d, pages, ids), docs) for d in r["docs"]):
                continue
        elif docs and not any(re.split(r"[#@]", d, maxsplit=1)[0] == docs for d in r["docs"]):
            continue
        rows.append(r)
    from .state import id_key
    order = {s: n for n, s in enumerate(STATUSES)}
    rows.sort(key=lambda r: (order.get(r["status"], len(order)), r["ordinal"], id_key(r["id"])))
    return {"cards": rows, "problems": problems}


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
    from . import xid
    row = _row(item, cards.get(key))
    ids = xid.index()
    pages = xid.page_rows({ids[xid.parse_link(d)["xid"]] for d in row["docs"] if _linked(d, ids)}) if row["docs"] else {}
    links = [xid.link_state(d, pages, ids) for d in row["docs"]]
    return {**row, "links": links, "description": description(item.body),
            "criteria": checklist(item.body, "AC"), "dod": checklist(item.body, "DOD"),
            "history": _history(cards.get(key), item.path), "file": _rel(item.path)}
