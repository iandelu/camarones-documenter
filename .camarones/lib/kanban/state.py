"""board.yaml: the kit's per-card state (one line per card so git merges per card), ids and ordinals. Pure: no I/O."""
from __future__ import annotations

import json
import re
import secrets
from datetime import datetime, timezone
from typing import Iterable

import yaml

ORDINAL_STEP = 1000
_CROCKFORD = "0123456789abcdefghjkmnpqrstvwxyz"
_ID = re.compile(r"^(.*?)-(\d+)(~.*)?$")
_FIELDS = ("uid", "status", "ordinal", "assignee", "t")
_SPECIAL = set(":,{}[]#\"'&*!|>%@`")


def id_key(item_id: str) -> tuple[str, int, str]:
    """Natural order: WI-2 < WI-10; a temporary key WI-42~uid sorts right after WI-42."""
    m = _ID.match(item_id)
    return (m.group(1), int(m.group(2)), m.group(3) or "") if m else (item_id, 0, "")


def new_uid() -> str:
    return "".join(secrets.choice(_CROCKFORD) for _ in range(8))


def next_id(existing: Iterable[str], prefix: str = "WI") -> str:
    top = 0
    for i in existing:
        m = _ID.match(i)
        if m and m.group(1) == prefix:
            top = max(top, int(m.group(2)))
    return f"{prefix}-{top + 1}"


def stamp(card: dict, field: str, who: str, now: datetime) -> None:
    card.setdefault("t", {})[field] = f"{now.astimezone(timezone.utc):%Y-%m-%dT%H:%M:%SZ} {who}"


def stamp_time(value: str) -> datetime:
    return datetime.strptime(value.split(" ", 1)[0], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


# --- reader / writer ---

def load_board(text: str) -> dict[str, dict]:
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as e:
        raise ValueError(f"board.yaml is not valid YAML: {e}") from e
    if not isinstance(data, dict) or data.get("version") != 1:
        raise ValueError("board.yaml: expected a mapping with version: 1")
    raw = data.get("cards") or {}
    if not isinstance(raw, dict):
        raise ValueError("board.yaml: cards must be a mapping")
    cards: dict[str, dict] = {}
    for key, c in raw.items():
        if not isinstance(c, dict):
            raise ValueError(f"board.yaml: card {key} is not a mapping")
        try:
            cards[str(key)] = {
                "uid": str(c["uid"]), "status": str(c["status"]), "ordinal": int(c["ordinal"]),
                "assignee": [str(a) for a in c.get("assignee") or []],
                "t": {str(k): str(v) for k, v in (c.get("t") or {}).items()},
            }
        except (KeyError, TypeError, ValueError) as e:
            raise ValueError(f"board.yaml: card {key} is malformed ({e})") from e
    return cards


def _scalar(v: object) -> str:
    s = str(v)
    plain = s == s.strip() and s != "" and not (_SPECIAL & set(s[:1])) and not any(c in s for c in ":,{}[]#\n")
    if plain:
        try:
            plain = yaml.safe_load(s) == s     # "123", "null", "true", dates... would load as another type
        except yaml.YAMLError:
            plain = False
    return s if plain else json.dumps(s, ensure_ascii=False)


def dump_board(cards: dict[str, dict]) -> str:
    lines = ["version: 1", "cards:"]
    for key in sorted(cards, key=id_key):
        c = cards[key]
        assignee = ", ".join(_scalar(a) for a in c.get("assignee", []))
        t = ", ".join(f"{_scalar(k)}: {_scalar(v)}" for k, v in c.get("t", {}).items())
        lines.append(f"  {_scalar(key)}: {{uid: {_scalar(c['uid'])}, status: {_scalar(c['status'])}, "
                     f"ordinal: {int(c['ordinal'])}, assignee: [{assignee}], t: {{{t}}}}}")
    return "\n".join(lines) + "\n"


# --- ordinals ---

def place(column: list[tuple[str, int]], *, before: str | None = None, after: str | None = None) -> dict[str, int]:
    """Ordinal for a card dropped in `column` (id, ordinal pairs): at the end, or before/after an anchor card.
    Returns {"*": new ordinal}; when there is no room between neighbours the column is rebalanced and every card
    whose ordinal changes is included too."""
    col = sorted(column, key=lambda p: p[1])
    ids = [i for i, _ in col]
    anchor = before if before is not None else after
    if anchor is None:
        pos = len(col)
    elif anchor not in ids:
        raise ValueError(f"{anchor} is not in the column")
    else:
        pos = ids.index(anchor) + (0 if before is not None else 1)
    lo = col[pos - 1][1] if pos > 0 else 0
    if pos >= len(col):
        return {"*": lo + ORDINAL_STEP}
    hi = col[pos][1]
    mid = (lo + hi) // 2
    if lo < mid < hi:
        return {"*": mid}
    out: dict[str, int] = {}
    order = ids[:pos] + ["*"] + ids[pos:]
    old = dict(col)
    for n, i in enumerate(order, 1):
        if i == "*" or old[i] != n * ORDINAL_STEP:
            out[i] = n * ORDINAL_STEP
    return out
