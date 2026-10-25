"""The repair pass (spec §4): brings item files and board.yaml back in line after hand edits and git merges. Runs before
every checkpoint and share commit. Idempotent: a second run changes nothing. Works from uids, never from ids alone."""
from __future__ import annotations

import os
import re
from collections import defaultdict
from datetime import date, datetime, timezone

from .. import docs
from ..common import ROOT
from . import ARCHIVE, BACKLOG, BOARD, CONFIG, STATUSES, TASKS
from . import ops, xid
from .items import _as_list, file_name, load_dir
from .state import dump_board, new_uid, next_id, stamp, stamp_time

ARCHIVE_AFTER_DAYS = 14
_LINK = re.compile(r"^[A-Z]{2,5}-[0-9a-z]{4}$")
_REF_FIELDS = ("dependencies", "subtasks")


def _rel(path) -> str:
    return path.relative_to(ROOT).as_posix()


def _archive_days() -> int:
    try:
        return int((docs.workspace().get("board") or {}).get("archive_after_days", ARCHIVE_AFTER_DAYS))
    except (TypeError, ValueError):
        return ARCHIVE_AFTER_DAYS


def adopt(item, cards: dict[str, dict], *, by: str, now: datetime, warn=lambda _: None) -> tuple[str, bool]:
    """Step 1 for one item that has a uid but no card: a card in a known status (else the first), at the end of its
    column unless it has an ordinal, with the file's assignee. Returns (the card's key, whether the item changed)."""
    edited = False
    raw = str(item.fm.get("status") or "")
    status = {s.lower(): s for s in STATUSES}.get(raw.lower())
    if status is None:
        status = STATUSES[0]
        warn(f"{item.id}: unknown status {raw!r}, put in {status}")
    if item.fm.get("status") != status:
        item.fm["status"] = status
        edited = True
    ordinal = item.fm.get("ordinal")
    if not isinstance(ordinal, int) or isinstance(ordinal, bool) or ordinal <= 0:
        ordinal = max([c["ordinal"] for c in cards.values() if c["status"] == status] + [0]) + 1000
        item.fm["ordinal"] = ordinal
        edited = True
    card = {"uid": item.uid, "status": status, "ordinal": ordinal,
            "assignee": [str(a) for a in _as_list(item.fm.get("assignee"))], "t": {}}
    stamp(card, "status", by, now)
    key = item.id if item.id not in cards else f"{item.id}~{item.uid}"
    cards[key] = card
    return key, edited


def repair(*, today: date | None = None, log=print) -> dict:
    """Run the six steps of spec §4 under the board lock. Returns {"changed": [...], "warnings": [...]}."""
    today = today or date.today()
    changed: list[str] = []
    warnings: list[str] = []

    def warn(msg: str) -> None:
        warnings.append(msg)
        log(f"  ! {msg}")

    with ops.locked():
        cards, _by_id, problems = ops.load_state()
        files, _ = load_dir(TASKS)
        archived, _ = load_dir(ARCHIVE)
        dirty: dict[int, object] = {}            # id(item) -> item whose file must be rewritten
        renamed: set[int] = set()                # id(item) of items whose file name follows a new id
        board_dirty = False
        fresh: set[str] = set()                  # uids adopted in this run (their mirrors are taken from the file)
        now = datetime.now(timezone.utc)

        def touch(item) -> None:
            dirty[id(item)] = item

        # 1. adopt item files without a card; give items without x-uid one
        known_uids = {c["uid"] for c in cards.values()}
        seen: set[str] = set()
        claimed = {i.uid for i in files if i.uid}      # a card's uid goes to a uid-less file only if no file owns it
        for item in files:
            if not item.uid:
                held = cards.get(item.id)
                uid = held["uid"] if held and held["uid"] not in claimed else new_uid()
                claimed.add(uid)
                item.fm["x-uid"] = uid
                touch(item)
            elif item.uid in seen:
                item.fm["x-uid"] = new_uid()
                touch(item)
                warn(f"{item.id}: two files shared one uid; {item.path.name} got a new one")
            seen.add(item.uid)
            if item.uid in known_uids:
                continue
            key, edited = adopt(item, cards, by=ops.who(), now=now, warn=warn)
            if edited:
                touch(item)
            known_uids.add(item.uid)
            fresh.add(item.uid)
            board_dirty = True
            log(f"  + adopted {key} ({item.path.name})")

        # 2. duplicate ids: the newer created_date (then higher uid) gets the next free number
        item_of = {i.uid: i for i in files}

        def born_of(card: dict) -> tuple[str, str]:
            item = item_of.get(card["uid"])
            return (str(item.fm.get("created_date") or "") if item else "", card["uid"])

        groups: dict[str, list[str]] = defaultdict(list)
        for key in cards:
            groups[key.split("~")[0]].append(key)
        refmap: dict[str, str] = {}              # "WI-5~uid" -> the id that card ends with
        moved_parent: dict[str, tuple[str, str]] = {}   # child id -> (old parent id, new parent id)
        renumbered: list[tuple[object, str]] = []
        new_ids: list[str] = []
        for base, keys in sorted(groups.items()):
            if len(keys) == 1 and "~" not in keys[0]:
                continue
            lifted = {k: cards.pop(k) for k in keys}      # lifted first: a card may take the key another one holds
            for n, key in enumerate(sorted(keys, key=lambda k: born_of(lifted[k]))):
                uid = lifted[key]["uid"]
                if n == 0:
                    final = base
                else:
                    final = next_id(ops._all_ids(cards, {i.id: i for i in files}, problems) + new_ids + list(lifted),
                                    base.rsplit("-", 1)[0])
                    new_ids.append(final)
                refmap[f"{base}~{uid}"] = final
                cards[final] = lifted[key]
                if key == final:
                    continue
                board_dirty = True
                item = item_of.get(uid)
                if item is None:
                    log(f"  ~ {base} -> {final} (card without a file)")
                    continue
                renumbered.append((item, final))
                for child in _as_list(item.fm.get("subtasks")):
                    moved_parent[str(child)] = (base, final)
                log(f"  ~ {base} -> {final} ({item.title})")

        # references follow by uid: the explicit WI-5~uid form, and the children an item lists as its own
        if refmap or moved_parent:
            for item in files + archived:
                for f in _REF_FIELDS:
                    have = _as_list(item.fm.get(f))
                    want = [refmap.get(str(v), v) for v in have]
                    if want != have:                       # a scalar stays a scalar
                        item.fm[f] = want[0] if isinstance(item.fm[f], str) else want
                        touch(item)
                parent = item.fm.get("parent_task_id")
                if parent:
                    now_parent = refmap.get(str(parent), parent)
                    old, new = moved_parent.get(item.id, (None, None))
                    now_parent = new if now_parent == old else now_parent
                    if now_parent != parent:
                        item.fm["parent_task_id"] = now_parent
                        touch(item)
        for item, final in renumbered:
            item.fm["id"] = final
            renamed.add(id(item))
            touch(item)

        # 3. mirrors that differ from board.yaml are put back
        key_of = {c["uid"]: k for k, c in cards.items()}
        for item in files:
            key = key_of.get(item.uid)
            if key is None or item.uid in fresh:
                continue
            card = cards[key]
            want = {"status": card["status"], "ordinal": card["ordinal"], "assignee": list(card["assignee"])}
            have = {"status": item.fm.get("status"), "ordinal": item.fm.get("ordinal"),
                    "assignee": [str(a) for a in (item.fm.get("assignee") or [])]}
            for f, value in want.items():
                if have[f] != value:
                    warn(f"{key}: {f} in the file was {have[f]!r}, the board says {value!r}; file rewritten")
                    item.fm[f] = value
                    touch(item)
        for key, card in cards.items():
            if card["uid"] not in item_of:
                warn(f"{key}: card without an item file")

        # 4. archive what has been Done for more than archive_after_days
        days = _archive_days()
        to_archive = []
        for key, card in sorted(cards.items()):
            stamped = (card.get("t") or {}).get("status")
            item = item_of.get(card["uid"])
            if card["status"] == "Done" and stamped and item is not None:
                try:
                    age = (today - stamp_time(stamped).date()).days
                except ValueError:
                    continue
                if age > days:
                    to_archive.append((key, item))
        for key, _ in to_archive:
            del cards[key]
            board_dirty = True

        # write: item files first, then the board
        for item in dirty.values():
            old_path = item.path
            if id(item) in renamed:
                item.path = TASKS / file_name(item.id, item.title)
            ops.save_item(item)
            if item.path != old_path:
                old_path.unlink(missing_ok=True)
            changed.append(_rel(item.path))
        for key, item in to_archive:
            ARCHIVE.mkdir(parents=True, exist_ok=True)
            os.replace(item.path, ARCHIVE / item.path.name)
            changed.append(_rel(ARCHIVE / item.path.name))
            log(f"  > archived {key} ({item.title})")
        if board_dirty or BOARD.read_text(encoding="utf-8").replace("\r\n", "\n") != dump_board(cards):
            ops.save_board(cards)
            changed.append(_rel(BOARD))

        # 5. the kit's keys in config.yml, and the merge driver
        if ops.write_config():
            changed.append(_rel(CONFIG))
        if ops.ensure_driver():
            changed.append("board merge driver")

        # 6. warnings
        for d in ("docs", "decisions", "milestones"):
            folder = BACKLOG / d
            if folder.is_dir() and any(p.is_file() for p in folder.rglob("*")):
                warn(f"backlog/{d}/ has content: the kit does not use Backlog.md's {d}")
        for key, card in cards.items():
            if card["status"] not in STATUSES:
                warn(f"{key}: unknown status {card['status']!r}")
        for p in problems:
            warn(f"{_rel(p['path'])}: unreadable item ({p['error']})")
        links = [(i, str(v)) for i in files for v in _as_list(i.fm.get("documentation"))]
        for item, v in links:
            try:
                xid.parse_link(v)
            except ops.BoardError:
                warn(f"{item.id}: unreadable doc link {v!r}")
        if any(_LINK.match(re.split(r"[#@]", v, maxsplit=1)[0]) for _, v in links):
            ids = xid.index()
            for item, v in links:
                base = re.split(r"[#@]", v, maxsplit=1)[0]
                if _LINK.match(base) and xid.link_state(v, {}, ids)["missing"]:
                    warn(f"{item.id}: links {base}, which no page has as x-id")
    return {"changed": changed, "warnings": warnings}
