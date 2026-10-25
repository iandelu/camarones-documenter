"""Git merge driver for board.yaml: merges per card and per field so two people's moves never conflict. Pure
(`merge_boards`) plus the thin file/stderr wrapper git calls (`driver`)."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from .state import dump_board, id_key, load_board, stamp_time

FIELDS = ("status", "ordinal", "assignee")
_MIN = datetime.min.replace(tzinfo=timezone.utc)


def _parse(text: str) -> dict[str, dict]:
    if not text.strip():
        return {}
    try:
        return load_board(text)
    except ValueError:
        raise
    except Exception as e:            # e.g. a `t:` that is not a mapping
        raise ValueError(f"board.yaml is malformed ({e})") from e


def _rank(card: dict, field: str) -> tuple:
    """Who wins a field changed on both sides: latest stamp, then author, then value (same pick on every machine)."""
    raw = card.get("t", {}).get(field)
    if raw is None:
        return (_MIN, "", json.dumps(card[field]))
    return (stamp_time(raw), raw.split(" ", 1)[1] if " " in raw else "", json.dumps(card[field]))


def _birth(card: dict) -> tuple:
    """Older card first (earliest stamp it carries), uid as the last word."""
    stamps = [stamp_time(v) for v in card.get("t", {}).values()]
    return (min(stamps) if stamps else datetime.max.replace(tzinfo=timezone.utc), card["uid"])


def _merge_card(base: dict | None, ours: dict, theirs: dict) -> dict:
    out = {"uid": ours["uid"]}
    t: dict[str, str] = {}
    for f in FIELDS:
        o_ch = base is None or ours[f] != base[f]
        t_ch = base is None or theirs[f] != base[f]
        if o_ch and t_ch:
            src = ours if _rank(ours, f) >= _rank(theirs, f) else theirs
        else:
            src = theirs if t_ch else ours
        out[f] = list(src[f]) if f == "assignee" else src[f]
        if f in src.get("t", {}):
            t[f] = src["t"][f]
    for k in sorted(set(ours.get("t", {})) | set(theirs.get("t", {}))):
        if k in FIELDS:
            continue
        cands = [c["t"][k] for c in (ours, theirs) if k in c.get("t", {})]
        t[k] = max(cands, key=lambda v: (stamp_time(v), v))
    out["t"] = dict(sorted(t.items()))
    return out


def merge_boards(base: str, ours: str, theirs: str) -> tuple[str, list[str]]:
    b, o, t = _parse(base), _parse(ours), _parse(theirs)
    log: list[str] = []
    try:
        cards = _merge_all(b, o, t, log)
    except ValueError:
        raise
    except Exception as e:
        raise ValueError(f"board.yaml: cannot merge ({e})") from e
    return dump_board(cards), log


def _merge_all(b: dict, o: dict, t: dict, log: list[str]) -> dict[str, dict]:
    cards: dict[str, dict] = {}
    for key in sorted(set(b) | set(o) | set(t), key=id_key):
        base, a, c = b.get(key), o.get(key), t.get(key)
        if a is None and c is None:
            continue
        if a is None or c is None:
            side = a if a is not None else c
            if base is not None and side == base:
                continue                                  # removed on one side, untouched on the other
            if base is not None:
                log.append(f"{key}: removed on one side but changed on the other; kept")
            cards[key] = side
        elif a["uid"] != c["uid"]:
            first, second = sorted((a, c), key=_birth)
            cards[key] = first
            cards[f"{key}~{second['uid']}"] = second
            log.append(f"{key}: created on both sides; the newer one is kept as {key}~{second['uid']}")
        else:
            cards[key] = _merge_card(base, a, c)
    return cards


# --- what git runs ---

def driver(base: Path, ours: Path, theirs: Path) -> int:
    """`board merge-driver %O %A %B`: result into `ours`, log to stderr; 1 leaves `ours` untouched (git conflicts)."""
    try:
        texts = [p.read_text(encoding="utf-8") if p.exists() else "" for p in (base, ours, theirs)]
        text, log = merge_boards(*texts)
    except (ValueError, OSError) as e:
        print(f"board merge: {e}", file=sys.stderr)
        return 1
    ours.write_text(text, encoding="utf-8", newline="\n")
    for line in log:
        print(f"board merge: {line}", file=sys.stderr)
    return 0


def driver_command(launcher: list[str]) -> str:
    """The `merge.camaron-board.driver` value: git runs it through `sh` on every OS, so POSIX paths in double quotes."""
    def q(part: str) -> str:
        part = part.replace("\\", "/")
        for ch in ('"', "$", "`"):
            part = part.replace(ch, "\\" + ch)
        return f'"{part}"'
    return " ".join([*(q(p) for p in launcher), "board merge-driver %O %A %B"])
